from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_db
from app.models import MatchDecision, PriceItem, Service, ServiceSynonym
from app.models.enums import MatchAction, MatchMethod, MatchStatus
from app.normalization import llm_rerank
from app.normalization.dictionary import load_matcher_cached
from app.schemas.dto import MatchRequest, TierOut, UnmatchedOut

router = APIRouter()


@router.get("/unmatched", response_model=list[UnmatchedOut], summary="Очередь верификации",
            description="Несопоставленные и спорные позиции с ранжированными кандидатами справочника.")
def unmatched(
    include_review: bool = Query(True),
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Items that need an operator: unmatched (and, by default, low-confidence review).
    Each comes with ranked dictionary suggestions."""
    statuses = [MatchStatus.unmatched]
    if include_review:
        statuses.append(MatchStatus.review)
    stmt = (
        select(PriceItem)
        .where(PriceItem.match_status.in_(statuses), PriceItem.is_active.is_(True))
        .options(selectinload(PriceItem.tiers), joinedload(PriceItem.partner), joinedload(PriceItem.document))
        .order_by(PriceItem.match_score.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    items = db.execute(stmt).scalars().all()
    matcher = load_matcher_cached(db)
    # One batched, judge-free pass: ranked embedding hints for display (fast). The LLM
    # judge is for the auto-decision, not for showing candidates — running it per item
    # here would make every page load do dozens of LLM calls (gateway timeout).
    sugg_lists = matcher.suggest_many(
        [it.raw_name for it in items], k=5,
        categories=[it.raw_category for it in items], judge=False,
    )
    out = []
    for it, sugg in zip(items, sugg_lists):
        doc = it.document
        fmt = (doc.file_format.value if doc and hasattr(doc.file_format, "value")
               else (str(doc.file_format) if doc else None))
        year = it.effective_date.year if it.effective_date else (doc.year if doc else None)
        out.append(UnmatchedOut(
            item_id=it.id,
            raw_name=it.raw_name,
            raw_code=it.raw_code,
            raw_category=it.raw_category,
            partner_id=it.partner_id,
            partner_name=it.partner.display_name if it.partner else None,
            document_id=it.document_id,
            source_filename=doc.source_filename if doc else None,
            file_format=fmt,
            year=year,
            source_ref=it.source_ref,
            match_status=it.match_status.value,
            match_score=it.match_score,
            extraction_method=it.extraction_method,
            tiers=[TierOut.model_validate(t) for t in it.tiers],
            suggestions=[{"service_id": s.service_id, "canonical_name": s.canonical_name,
                          "score": round(s.score, 3)} for s in sugg],
        ))
    return out


@router.post("/review/ai-compare", summary="ИИ-сравнение позиции со справочником")
def ai_compare(item_id: uuid.UUID = Body(..., embed=True), db: Session = Depends(get_db)):
    """Run the LLM judge on one item's dictionary candidates and explain the best fit."""
    if not llm_rerank.available():
        raise HTTPException(400, "LLM сравнение недоступно (нет ключа OpenAI / выключено)")
    it = db.get(PriceItem, item_id)
    if it is None:
        raise HTTPException(404, "item not found")
    matcher = load_matcher_cached(db)
    sugg = matcher.suggest_many([it.raw_name], k=5, categories=[it.raw_category], judge=False)[0]
    if not sugg:
        return {"choice": 0, "confidence": 0.0, "reason": "Кандидатов из справочника нет.", "best": None, "candidates": []}
    res = llm_rerank.compare_one(it.raw_name, it.raw_category, [s.canonical_name for s in sugg])
    choice = res["choice"]
    best = sugg[choice - 1] if 1 <= choice <= len(sugg) else None
    return {
        "choice": choice,
        "confidence": res["confidence"],
        "reason": res["reason"],
        "best": ({"service_id": best.service_id, "canonical_name": best.canonical_name,
                  "score": round(best.score, 3)} if best else None),
        "candidates": [{"service_id": s.service_id, "canonical_name": s.canonical_name,
                        "score": round(s.score, 3)} for s in sugg],
    }


@router.post("/review/bulk-accept", summary="Массовое принятие по порогу")
def bulk_accept(min_score: float = Query(0.80, ge=0, le=1), dry_run: bool = Query(False)):
    """Accept the top suggestion for every active review item with score >= min_score.
    Use dry_run=true first to see how many are eligible."""
    from app.services.review_ops import bulk_accept_review

    return bulk_accept_review(min_score, dry_run=dry_run, decided_by="operator/bulk")


@router.post("/match", summary="Ручное сопоставление / создание услуги")
def manual_match(req: MatchRequest, db: Session = Depends(get_db)):
    """Operator confirms/changes a match, or creates a new dictionary service.
    Learns a synonym so future documents auto-match."""
    item = db.get(PriceItem, req.item_id)
    if item is None:
        raise HTTPException(404, "price item not found")

    if req.service_id is None and req.create_name:
        svc = Service(canonical_name=req.create_name, category=req.category or item.raw_category)
        db.add(svc)
        db.flush()
        action = MatchAction.created_service
    elif req.service_id is not None:
        svc = db.get(Service, req.service_id)
        if svc is None:
            raise HTTPException(404, "service not found")
        action = MatchAction.accepted
    else:
        raise HTTPException(400, "provide either service_id or create_name")

    item.service_id = svc.id
    item.match_status = MatchStatus.manual
    item.match_score = 1.0
    item.is_verified = True
    if req.note:
        item.verification_note = req.note

    # learn the raw spelling as a synonym (idempotent-ish)
    exists = db.execute(
        select(ServiceSynonym).where(
            ServiceSynonym.service_id == svc.id, ServiceSynonym.synonym == item.raw_name
        )
    ).first()
    if not exists:
        db.add(ServiceSynonym(service_id=svc.id, synonym=item.raw_name, source="learned"))

    db.add(MatchDecision(
        price_item_id=item.id,
        candidate_service_id=svc.id,
        score=1.0,
        method=MatchMethod.manual,
        action=action,
        decided_by=req.decided_by,
    ))
    db.commit()
    return {"item_id": str(item.id), "service_id": str(svc.id), "action": action.value}
