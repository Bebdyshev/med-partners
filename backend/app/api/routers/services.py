from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Partner, PriceItem, Service
from app.models.enums import TierType
from app.schemas.dto import PartnerPriceOut, ServiceOut, TierOut

router = APIRouter()

_TIER_ORDER = {t: i for i, t in enumerate(TierType)}


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    category: str | None = Query(None),
    q: str | None = Query(None, description="substring filter on name"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Service).where(Service.is_active.is_(True))
    if category:
        stmt = stmt.where(Service.category == category)
    if q:
        stmt = stmt.where(Service.canonical_name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Service.canonical_name).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


@router.get("/services/{service_id}/partners", response_model=list[PartnerPriceOut])
def service_partners(service_id: uuid.UUID, db: Session = Depends(get_db)):
    svc = db.get(Service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    items = db.execute(
        select(PriceItem, Partner)
        .join(Partner, Partner.id == PriceItem.partner_id)
        .where(PriceItem.service_id == service_id, PriceItem.is_active.is_(True))
    ).all()
    out = []
    for item, partner in items:
        tiers = sorted(item.tiers, key=lambda t: _TIER_ORDER.get(t.tier_type, 99))
        out.append(PartnerPriceOut(
            partner_id=partner.id,
            partner_name=partner.display_name,
            city=partner.city,
            raw_name=item.raw_name,
            effective_date=item.effective_date,
            tiers=[TierOut.model_validate(t) for t in tiers],
            is_verified=item.is_verified,
        ))
    # cheapest resident price first
    out.sort(key=lambda p: (p.tiers[0].amount_kzt if p.tiers else 0))
    return out
