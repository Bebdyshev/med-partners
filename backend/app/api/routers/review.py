from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import MatchDecision, PriceItem, Service, ServiceSynonym
from app.models.enums import MatchAction, MatchMethod, MatchStatus
from app.normalization.dictionary import load_matcher
from app.schemas.dto import MatchRequest, UnmatchedOut

router = APIRouter()


@router.get("/unmatched", response_model=list[UnmatchedOut])
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
        .order_by(PriceItem.match_score.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    items = db.execute(stmt).scalars().all()
    matcher = load_matcher(db)
    out = []
    for it in items:
        sugg = matcher.suggest(it.raw_name, k=5)
        out.append(UnmatchedOut(
            item_id=it.id,
            raw_name=it.raw_name,
            raw_category=it.raw_category,
            partner_id=it.partner_id,
            match_status=it.match_status.value,
            match_score=it.match_score,
            extraction_method=it.extraction_method,
            suggestions=[{"service_id": s.service_id, "canonical_name": s.canonical_name,
                          "score": round(s.score, 3)} for s in sugg],
        ))
    return out


@router.post("/match")
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
