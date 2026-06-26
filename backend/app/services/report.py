"""Quality report: documents processed, normalization rate, queue sizes."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import session_scope
from app.models import PriceDocument, PriceItem, Service
from app.models.enums import MatchStatus, ParseStatus


def compute_report() -> dict:
    with session_scope() as db:
        docs = dict(
            db.execute(select(PriceDocument.status, func.count()).group_by(PriceDocument.status)).all()
        )
        total_items = db.execute(select(func.count(PriceItem.id))).scalar() or 0
        by_match = dict(
            db.execute(select(PriceItem.match_status, func.count()).group_by(PriceItem.match_status)).all()
        )
        active_items = db.execute(
            select(func.count(PriceItem.id)).where(PriceItem.is_active.is_(True))
        ).scalar() or 0
        flagged = db.execute(
            select(func.count(PriceItem.id)).where(PriceItem.warnings != "[]")
        ).scalar() or 0
        n_services = db.execute(select(func.count(Service.id))).scalar() or 0

        auto = by_match.get(MatchStatus.auto, 0)
        auto_pct = (auto / total_items * 100) if total_items else 0.0
        return {
            "documents": {(k.value if hasattr(k, "value") else str(k)): v for k, v in docs.items()},
            "documents_total": sum(docs.values()),
            "items_total": total_items,
            "items_active": active_items,
            "services_in_dictionary": n_services,
            "normalization": {
                "auto": by_match.get(MatchStatus.auto, 0),
                "review": by_match.get(MatchStatus.review, 0),
                "unmatched": by_match.get(MatchStatus.unmatched, 0),
                "manual": by_match.get(MatchStatus.manual, 0),
                "auto_match_pct": round(auto_pct, 1),
            },
            "flagged_for_validation": flagged,
        }


def print_report() -> None:
    import json

    print(json.dumps(compute_report(), ensure_ascii=False, indent=2))
