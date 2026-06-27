"""Quality report: documents processed, normalization rate, queue sizes."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import session_scope
from app.models import Partner, PriceDocument, PriceItem, Service
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


def compute_document_breakdown() -> dict:
    """Per-document composition (positions split by match-status + extraction method) plus
    global provenance and category mix — powers the dashboard 'intake ledger'."""
    with session_scope() as db:
        docs = db.execute(
            select(PriceDocument, Partner.display_name)
            .join(Partner, Partner.id == PriceDocument.partner_id, isouter=True)
        ).all()

        ms: dict = {}
        for did, st, c in db.execute(
            select(PriceItem.document_id, PriceItem.match_status, func.count())
            .group_by(PriceItem.document_id, PriceItem.match_status)
        ).all():
            ms.setdefault(did, {})[st] = c

        meth: dict = {}
        for did, m, c in db.execute(
            select(PriceItem.document_id, PriceItem.extraction_method, func.count())
            .group_by(PriceItem.document_id, PriceItem.extraction_method)
        ).all():
            meth.setdefault(did, {})[m or "—"] = c

        flagged = dict(db.execute(
            select(PriceItem.document_id, func.count())
            .where(PriceItem.warnings != "[]")
            .group_by(PriceItem.document_id)
        ).all())

        out_docs = []
        for d, pname in docs:
            mm = ms.get(d.id, {})
            items = sum(mm.values())
            out_docs.append({
                "id": str(d.id),
                "source_filename": d.source_filename,
                "partner_name": pname,
                "file_format": d.file_format.value if hasattr(d.file_format, "value") else str(d.file_format),
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "year": d.year,
                "parsed_at": d.parsed_at.isoformat() if d.parsed_at else None,
                "items": items,
                "auto": mm.get(MatchStatus.auto, 0),
                "review": mm.get(MatchStatus.review, 0),
                "unmatched": mm.get(MatchStatus.unmatched, 0),
                "manual": mm.get(MatchStatus.manual, 0),
                "flagged": flagged.get(d.id, 0),
                "methods": meth.get(d.id, {}),
            })
        out_docs.sort(key=lambda x: x["items"], reverse=True)

        by_method: dict = {}
        for mdict in meth.values():
            for m, c in mdict.items():
                by_method[m] = by_method.get(m, 0) + c

        # clean dictionary categories (Service.category) over matched items — raw_category
        # is noisy (section headers, biomaterials like "сыв.", spacing dupes).
        cats = db.execute(
            select(Service.category, func.count())
            .join(PriceItem, PriceItem.service_id == Service.id)
            .group_by(Service.category)
            .order_by(func.count().desc())
        ).all()
        by_category = [{"category": c, "items": n} for c, n in cats if c and c.strip()][:10]

        return {"documents": out_docs, "by_method": by_method, "by_category": by_category}


def print_report() -> None:
    import json

    print(json.dumps(compute_report(), ensure_ascii=False, indent=2))
