from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Partner, PriceItem
from app.models.enums import TierType
from app.schemas.dto import PartnerOut, ServicePriceOut, TierOut

router = APIRouter()
_TIER_ORDER = {t: i for i, t in enumerate(TierType)}


@router.get("/partners", response_model=list[PartnerOut])
def list_partners(
    city: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Partner)
    if city:
        stmt = stmt.where(Partner.city == city)
    if is_active is not None:
        stmt = stmt.where(Partner.is_active.is_(is_active))
    stmt = stmt.order_by(Partner.code).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


@router.get("/partners/{partner_id}/services", response_model=list[ServicePriceOut])
def partner_services(
    partner_id: uuid.UUID,
    active_only: bool = Query(True),
    limit: int = Query(500, le=5000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if db.get(Partner, partner_id) is None:
        raise HTTPException(404, "partner not found")
    stmt = select(PriceItem).where(PriceItem.partner_id == partner_id)
    if active_only:
        stmt = stmt.where(PriceItem.is_active.is_(True))
    stmt = stmt.order_by(PriceItem.raw_category, PriceItem.raw_name).limit(limit).offset(offset)
    items = db.execute(stmt).scalars().all()
    out = []
    for item in items:
        tiers = sorted(item.tiers, key=lambda t: _TIER_ORDER.get(t.tier_type, 99))
        out.append(ServicePriceOut(
            service_id=item.service_id,
            raw_name=item.raw_name,
            category=item.raw_category,
            match_status=item.match_status.value,
            effective_date=item.effective_date,
            tiers=[TierOut.model_validate(t) for t in tiers],
        ))
    return out
