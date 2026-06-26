"""Re-run normalization over stored items against the current dictionary.

Used after the dictionary is (re)loaded. Operator-confirmed matches
(match_status=manual) are never overwritten. Matching is batched over distinct
raw names so the embedding model encodes each unique name only once.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import session_scope
from app.models import MatchDecision, PriceItem
from app.models.enums import MatchAction, MatchStatus
from app.normalization.dictionary import load_matcher


def renormalize_all() -> dict:
    counts = {"auto": 0, "review": 0, "unmatched": 0, "kept_manual": 0}
    with session_scope() as db:
        matcher = load_matcher(db)
        items = db.execute(select(PriceItem)).scalars().all()

        distinct = sorted({it.raw_name for it in items if it.match_status != MatchStatus.manual})
        results = dict(zip(distinct, matcher.match_many(distinct)))

        for item in items:
            if item.match_status == MatchStatus.manual:
                counts["kept_manual"] += 1
                continue
            res = results.get(item.raw_name)
            if res is None:
                continue
            item.match_status = res.status
            item.match_score = res.score
            if res.status == MatchStatus.auto and res.service_id:
                sid = res.service_id if isinstance(res.service_id, uuid.UUID) else uuid.UUID(str(res.service_id))
                item.service_id = sid
                counts["auto"] += 1
                db.add(MatchDecision(
                    price_item_id=item.id, candidate_service_id=sid, score=res.score,
                    method=res.method, action=MatchAction.accepted, decided_by=None,
                ))
            elif res.status == MatchStatus.review:
                item.service_id = None
                counts["review"] += 1
            else:
                item.service_id = None
                counts["unmatched"] += 1
    return counts
