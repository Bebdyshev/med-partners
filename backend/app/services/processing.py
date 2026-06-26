"""The per-document processing pipeline.

extract -> build PriceItems + PriceTiers -> normalize -> validate -> version ->
set document status. Used both synchronously (CLI) and by the Celery task.
"""
from __future__ import annotations

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


def process_document(db, doc: PriceDocument) -> dict:
    """Process one document in-place within the given session. Returns a summary."""
    doc.status = ParseStatus.processing
    db.flush()

    extractor = get_extractor(Path(doc.stored_path))
    if extractor is None:
        doc.status = ParseStatus.error
        doc.parse_log = "no extractor for file format"
        return {"status": "error", "items": 0}

    try:
        result = extractor.extract(Path(doc.stored_path))
    except Exception as exc:  # noqa: BLE001
        doc.status = ParseStatus.error
        doc.parse_log = f"extraction crashed: {type(exc).__name__}: {exc}"
        return {"status": "error", "items": 0}

    doc.method_summary = dict(result.method_stats)
    doc.warnings = result.warnings[:200]
    doc.raw_content = "\n".join(r.raw_name for r in result.rows)[:_RAW_CONTENT_LIMIT]

    matcher = load_matcher(db)
    eff_date: date | None = doc.effective_date.date() if doc.effective_date else None
    today = datetime.utcnow().date()

    n_items = n_auto = n_review = n_unmatched = n_flagged = 0

    for raw in result.rows:
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
        # --- tiers ---
        single = len(raw.prices) == 1
        tier_vals: list[TierVal] = []
        for p in raw.prices:
            tier_type = _map_tier(p.label, single)
            amount_kzt = to_kzt(p.amount, p.currency)
            item.tiers.append(
                PriceTier(
                    tier_type=tier_type,
                    label_raw=p.label,
                    amount_kzt=amount_kzt,
                    amount_original=p.amount,
                    currency_original=p.currency,
                )
            )
            tier_vals.append(TierVal(tier_type=tier_type, amount_kzt=amount_kzt))

        # --- normalization ---
        match = matcher.match(raw.raw_name)
        item.match_status = match.status
        item.match_score = match.score
        if match.status == MatchStatus.auto and match.service_id:
            item.service_id = _to_uuid(match.service_id)
            n_auto += 1
        elif match.status == MatchStatus.review:
            n_review += 1
        else:
            n_unmatched += 1

        db.add(item)
        db.flush()  # assign item.id

        if match.status == MatchStatus.auto and match.service_id:
            db.add(MatchDecision(
                price_item_id=item.id,
                candidate_service_id=_to_uuid(match.service_id),
                score=match.score,
                method=match.method,
                action=MatchAction.accepted,
                decided_by=None,  # automatic
            ))

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

        # --- versioning ---
        supersede_previous(db, item)
        n_items += 1

    # document status
    needs_review = (n_review + n_unmatched + n_flagged) > 0
    doc.status = ParseStatus.needs_review if needs_review else ParseStatus.done
    doc.parsed_at = datetime.utcnow()
    db.flush()

    return {
        "status": doc.status.value,
        "items": n_items,
        "auto": n_auto,
        "review": n_review,
        "unmatched": n_unmatched,
        "flagged": n_flagged,
    }


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
