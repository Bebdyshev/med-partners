"""Re-run normalization over stored items against the current dictionary.

Two passes: (1) code-first — exact tariff-code matches (near-100% precision);
(2) name matching for the rest, batched over distinct (name, category) so the
embedding model encodes each unique name once. Operator-confirmed matches
(match_status=manual) are never overwritten.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import session_scope
from app.models import MatchDecision, PriceItem
from app.models.enums import MatchAction, MatchMethod, MatchStatus
from app.normalization.dictionary import load_matcher


def _uuid(v):
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


def renormalize_all() -> dict:
    counts = {"code": 0, "auto": 0, "review": 0, "unmatched": 0, "kept_manual": 0}
    with session_scope() as db:
        matcher = load_matcher(db)
        items = db.execute(select(PriceItem)).scalars().all()

        # --- pass 1: code-first ---
        pending = []
        for item in items:
            if item.match_status == MatchStatus.manual:
                counts["kept_manual"] += 1
                continue
            code = matcher.code_lookup(item.raw_code)
            if code is not None:
                sid = _uuid(code.service_id)
                item.service_id = sid
                item.match_status = MatchStatus.auto
                item.match_score = 1.0
                db.add(MatchDecision(
                    price_item_id=item.id, candidate_service_id=sid, score=1.0,
                    method=MatchMethod.exact, action=MatchAction.accepted, decided_by=None,
                ))
                counts["code"] += 1
                counts["auto"] += 1
            else:
                pending.append(item)

        # --- pass 2: name matching, batched by distinct (name, category) ---
        keys = sorted({(it.raw_name, it.raw_category or "") for it in pending})
        names = [k[0] for k in keys]
        cats = [k[1] or None for k in keys]
        results = dict(zip(keys, matcher.match_many(names, categories=cats)))

        for item in pending:
            res = results.get((item.raw_name, item.raw_category or ""))
            if res is None:
                continue
            item.match_status = res.status
            item.match_score = res.score
            if res.status == MatchStatus.auto and res.service_id:
                sid = _uuid(res.service_id)
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
