"""The per-document processing pipeline.

extract -> build PriceItems + PriceTiers -> normalize -> validate -> version ->
set document status. Used both synchronously (CLI) and by the Celery task.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from app.currency import to_kzt
from app.extractors.registry import get_extractor
from app.models import MatchDecision, PriceDocument, PriceItem, PriceTier, Service
from app.models.enums import MatchAction, MatchStatus, ParseStatus, TierType
from app.normalization.dictionary import load_matcher
from app.services.versioning import supersede_previous
from app.validation.engine import validate
from app.validation.rules import TierVal, ValItem

_RAW_CONTENT_LIMIT = 200_000

# Emit live progress every N items so the counters stream smoothly without flooding.
_PARSE_EVERY = 8   # разбор позиций — fast, coarse updates are fine
_ITEMS_EVERY = 2   # нормализация — finer updates so the tally visibly climbs


def process_document(
    db, doc: PriceDocument,
    progress: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    """Process one document in-place within the given session. Returns a summary.

    When `progress` is given it is called with small dict events at each stage
    (read/extract/ocr/parse/normalize/validate/done) — used by the streaming
    endpoint to drive a live UI. It is a no-op everywhere else (CLI, Celery).
    When `should_cancel` is given it is polled between pages/items; if it returns
    True the pipeline raises CancelledError so the worker's session rolls back."""

    def emit(ev: dict) -> None:
        if progress is not None:
            try:
                progress(ev)
            except Exception:  # noqa: BLE001 — progress must never break processing
                pass

    def ck() -> None:
        if should_cancel is not None and should_cancel():
            from app.services.jobs import CancelledError
            raise CancelledError()

    doc.status = ParseStatus.processing
    db.flush()

    emit({"stage": "read", "filename": doc.source_filename, "format": doc.file_format.value
          if hasattr(doc.file_format, "value") else str(doc.file_format)})

    extractor = get_extractor(Path(doc.stored_path))
    if extractor is None:
        doc.status = ParseStatus.error
        doc.parse_log = "no extractor for file format"
        emit({"stage": "error", "message": "no extractor for file format"})
        return {"status": "error", "items": 0}

    emit({"stage": "extract"})
    from app.services.jobs import CancelledError
    try:
        result = extractor.extract(Path(doc.stored_path), progress=progress, should_cancel=should_cancel)
    except CancelledError:
        raise  # let the worker handle cancellation (rolls back the session)
    except Exception as exc:  # noqa: BLE001
        doc.status = ParseStatus.error
        doc.parse_log = f"extraction crashed: {type(exc).__name__}: {exc}"
        emit({"stage": "error", "message": f"{type(exc).__name__}: {exc}"})
        return {"status": "error", "items": 0}

    doc.method_summary = dict(result.method_stats)
    doc.warnings = result.warnings[:200]
    doc.raw_content = "\n".join(r.raw_name for r in result.rows)[:_RAW_CONTENT_LIMIT]

    total_rows = len(result.rows)
    emit({"stage": "extract_done", "methods": dict(result.method_stats), "rows": total_rows})

    matcher = load_matcher(db)
    eff_date: date | None = doc.effective_date.date() if doc.effective_date else None
    today = datetime.utcnow().date()

    n_items = n_auto = n_review = n_unmatched = n_flagged = 0

    # ── Pass 1 · разбор позиций и цен — build items + tiers (fast, no API) ──
    built: list[tuple] = []  # (item, raw, tier_vals)
    for i, raw in enumerate(result.rows, start=1):
        ck()
        item = PriceItem(
            document_id=doc.id,
            partner_id=doc.partner_id,
            raw_name=raw.raw_name,
            raw_code=raw.code,
            raw_category=raw.category,
            source_ref=raw.source_ref,
            extraction_method=raw.extraction_method,
            extraction_confidence=raw.confidence,
            effective_date=eff_date,
            is_active=True,
        )
        single = len(raw.prices) == 1
        tier_vals: list[TierVal] = []
        for p in raw.prices:
            tier_type = _map_tier(p.label, single)
            amount_kzt = to_kzt(p.amount, p.currency)
            item.tiers.append(PriceTier(
                tier_type=tier_type, label_raw=p.label, amount_kzt=amount_kzt,
                amount_original=p.amount, currency_original=p.currency,
            ))
            tier_vals.append(TierVal(tier_type=tier_type, amount_kzt=amount_kzt))
        db.add(item)
        built.append((item, raw, tier_vals))
        if progress is not None and (i % _PARSE_EVERY == 0 or i == total_rows):
            emit({"stage": "parse", "done": i, "total": total_rows})
    db.flush()  # assign item.ids

    # ── Pass 2 · нормализация к справочнику — match + validate + version (streams) ──
    for (item, raw, tier_vals) in built:
        ck()
        match = matcher.match(raw.raw_name, raw.code, raw.category)
        item.match_status = match.status
        item.match_score = match.score
        if match.status == MatchStatus.auto and match.service_id:
            item.service_id = _to_uuid(match.service_id)
            n_auto += 1
            db.add(MatchDecision(
                price_item_id=item.id,
                candidate_service_id=_to_uuid(match.service_id),
                score=match.score,
                method=match.method,
                action=MatchAction.accepted,
                decided_by=None,  # automatic
            ))
        elif match.status == MatchStatus.review:
            n_review += 1
        else:
            n_unmatched += 1

        # --- validation ---
        prev_price = _prev_resident_price(db, item)
        report = validate(ValItem(
            raw_name=item.raw_name,
            tiers=tier_vals,
            effective_date=eff_date,
            confidence=raw.confidence,
            prev_resident_price=prev_price,
            today=today,
        ))
        if report.warnings:
            item.warnings = [{"code": w.code, "level": w.level, "message": w.message} for w in report.warnings]
            n_flagged += 1

        supersede_previous(db, item)
        n_items += 1

        if progress is not None and (n_items % _ITEMS_EVERY == 0 or n_items == total_rows):
            emit({"stage": "normalize", "done": n_items, "total": total_rows,
                  "auto": n_auto, "review": n_review, "unmatched": n_unmatched})

    # document status
    emit({"stage": "validate"})
    needs_review = (n_review + n_unmatched + n_flagged) > 0
    doc.status = ParseStatus.needs_review if needs_review else ParseStatus.done
    doc.parsed_at = datetime.utcnow()
    db.flush()

    summary = {
        "status": doc.status.value,
        "items": n_items,
        "auto": n_auto,
        "review": n_review,
        "unmatched": n_unmatched,
        "flagged": n_flagged,
    }
    emit({"stage": "done", "doc_id": str(doc.id), "summary": summary,
          "methods": dict(result.method_stats), "preview": _preview_items(db, doc.id, 8)})
    return summary


def replay_existing(
    db, doc: PriceDocument,
    progress: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    """Replay the full live animation from a document's ALREADY-STORED results.

    No OpenAI calls, no DB writes — used when the file is already in the base (e.g.
    out of API credits): we re-emit the read/extract/ocr/parse/normalize/done events
    paced over a few seconds, derived from the saved items. Page images for the
    scanner still render locally (PyMuPDF), so the demo looks identical."""
    import re
    import time
    from sqlalchemy import select

    def emit(ev: dict) -> None:
        if progress is not None:
            try:
                progress(ev)
            except Exception:  # noqa: BLE001
                pass

    def ck() -> None:
        if should_cancel is not None and should_cancel():
            from app.services.jobs import CancelledError
            raise CancelledError()

    fmt = doc.file_format.value if hasattr(doc.file_format, "value") else str(doc.file_format)
    emit({"stage": "read", "filename": doc.source_filename, "format": fmt})
    time.sleep(0.35)

    rows = db.execute(
        select(PriceItem, Service)
        .outerjoin(Service, Service.id == PriceItem.service_id)
        .where(PriceItem.document_id == doc.id)
        .order_by(PriceItem.id)
    ).all()
    total = len(rows)
    methods = doc.method_summary or {}

    # OCR replay — per-page, counts derived from each item's source_ref (page=N)
    per_page: dict[int, int] = {}
    for item, _ in rows:
        m = re.search(r"page=(\d+)", item.source_ref or "")
        if m:
            per_page[int(m.group(1))] = per_page.get(int(m.group(1)), 0) + 1
    page_total = max(per_page) if per_page else 0
    emit({"stage": "extract", "page_total": page_total})
    time.sleep(0.2)
    for p in sorted(per_page):
        ck()
        emit({"stage": "ocr", "page": p, "page_total": page_total})
        time.sleep(0.45)
        emit({"stage": "ocr_done", "page": p, "rows": per_page[p]})

    emit({"stage": "extract_done", "methods": methods, "rows": total})
    time.sleep(0.15)

    # parse counter
    for i in range(_PARSE_EVERY, total + 1, _PARSE_EVERY):
        ck()
        emit({"stage": "parse", "done": i, "total": total})
        time.sleep(0.03)
    emit({"stage": "parse", "done": total, "total": total})

    # normalize counter — running tallies from the stored match_status
    auto = review = unmatched = 0
    for i, (item, _svc) in enumerate(rows, start=1):
        st = item.match_status.value if hasattr(item.match_status, "value") else str(item.match_status)
        if st == MatchStatus.auto.value:
            auto += 1
        elif st == MatchStatus.review.value:
            review += 1
        else:
            unmatched += 1
        if i % _ITEMS_EVERY == 0 or i == total:
            ck()
            emit({"stage": "normalize", "done": i, "total": total,
                  "auto": auto, "review": review, "unmatched": unmatched})
            time.sleep(0.02)

    emit({"stage": "validate"})
    time.sleep(0.15)
    status = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
    summary = {"status": status, "items": total, "auto": auto, "review": review, "unmatched": unmatched}
    emit({"stage": "done", "doc_id": str(doc.id), "summary": summary,
          "methods": methods, "preview": _preview_items(db, doc.id, 8)})
    return summary


def _preview_items(db, doc_id, limit: int = 8) -> list[dict]:
    """First N items of a document with their match status + canonical + price,
    for the demo result card."""
    from sqlalchemy import select

    rows = db.execute(
        select(PriceItem, Service)
        .outerjoin(Service, Service.id == PriceItem.service_id)
        .where(PriceItem.document_id == doc_id)
        .order_by(PriceItem.id)
        .limit(limit)
    ).all()
    out: list[dict] = []
    for item, svc in rows:
        amount = None
        for t in item.tiers:
            if t.tier_type == TierType.resident_kzt:
                amount = str(t.amount_kzt)
                break
        if amount is None and item.tiers:
            amount = str(item.tiers[0].amount_kzt)
        status = item.match_status.value if hasattr(item.match_status, "value") else str(item.match_status)
        out.append({
            "raw_name": item.raw_name,
            "match_status": status,
            "match_score": float(item.match_score) if item.match_score is not None else None,
            "canonical_name": svc.canonical_name if svc else None,
            "amount_kzt": amount,
        })
    return out


def _map_tier(label, single: bool) -> TierType:
    from app.extractors.common.tier_mapper import map_tier

    return map_tier(label, single_column=single)


def _prev_resident_price(db, item: PriceItem):
    """Resident price of the most recent active prior version, for anomaly check."""
    from sqlalchemy import select

    from app.normalization.text_norm import normalize

    q = select(PriceItem).where(
        PriceItem.partner_id == item.partner_id,
        PriceItem.is_active.is_(True),
        PriceItem.id != item.id,
    )
    if item.service_id is not None:
        q = q.where(PriceItem.service_id == item.service_id)
        prev = db.execute(q).scalars().first()
    else:
        target = normalize(item.raw_name)
        prev = next(
            (it for it in db.execute(q).scalars().all() if normalize(it.raw_name) == target), None
        )
    if prev is None:
        return None
    for t in prev.tiers:
        if t.tier_type == TierType.resident_kzt:
            return t.amount_kzt
    return prev.tiers[0].amount_kzt if prev.tiers else None


def _to_uuid(val):
    import uuid

    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))
