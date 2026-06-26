"""Bulk operations on the review queue.

Hand-verifying thousands of review items is impractical. bulk_accept_review
accepts the top dictionary suggestion for every active `review` item whose score
is >= a chosen threshold — turning the high-confidence tail of the queue into
matches in one pass, while low-confidence items stay for manual handling.

Accepted items get match_status=auto (machine-accepted) and an audit MatchDecision
tagged with the threshold; is_verified stays false (not human-verified), and no
synonym is learned (bulk accept shouldn't pollute the synonym set).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import session_scope
from app.models import MatchDecision, PriceItem
from app.models.enums import MatchAction, MatchStatus
from app.normalization.dictionary import load_matcher_cached


def bulk_accept_review(min_score: float, dry_run: bool = False, decided_by: str | None = None) -> dict:
    with session_scope() as db:
        items = db.execute(
            select(PriceItem).where(
                PriceItem.is_active.is_(True),
                PriceItem.match_status == MatchStatus.review,
                PriceItem.match_score >= min_score,
            )
        ).scalars().all()
        if dry_run:
            return {"eligible": len(items), "accepted": 0, "min_score": min_score, "dry_run": True}

        matcher = load_matcher_cached(db)
        distinct = sorted({it.raw_name for it in items})
        sugg = dict(zip(distinct, matcher.suggest_many(distinct)))

        accepted = 0
        for it in items:
            top = (sugg.get(it.raw_name) or [None])[0]
            if top is None:
                continue
            sid = top.service_id if isinstance(top.service_id, uuid.UUID) else uuid.UUID(str(top.service_id))
            it.service_id = sid
            it.match_status = MatchStatus.auto
            it.match_score = top.score
            db.add(MatchDecision(
                price_item_id=it.id, candidate_service_id=sid, score=top.score,
                method=top.method, action=MatchAction.accepted,
                decided_by=decided_by or f"bulk>={min_score}",
            ))
            accepted += 1
        return {"eligible": len(items), "accepted": accepted, "min_score": min_score, "dry_run": False}
