from __future__ import annotations

import functools
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Partner, PriceItem, Service
from app.models.enums import TierType
from app.schemas.dto import PartnerPriceOut, ServiceOut, ServiceUpdate, TierOut

router = APIRouter()

_TIER_ORDER = {t: i for i, t in enumerate(TierType)}

_DESC_FILE = Path(__file__).parent.parent.parent / "data" / "service_descriptions.json"


@functools.lru_cache(maxsize=1)
def _load_descriptions() -> list[dict]:
    try:
        return json.loads(_DESC_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _find_description(canonical_name: str) -> dict | None:
    name_lower = canonical_name.lower()
    for d in _load_descriptions():
        pattern = (d.get("canonical_name_pattern") or "").lower()
        if pattern and pattern in name_lower:
            return d
        slug_check = (d.get("slug") or "").replace("-", " ")
        if slug_check and slug_check in name_lower:
            return d
    return None


@router.get("/service-descriptions")
def list_descriptions():
    """All curated service descriptions (for search/enrichment)."""
    return _load_descriptions()


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


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: uuid.UUID, body: ServiceUpdate, db: Session = Depends(get_db)):
    """Operator edits a dictionary service (name / category / code / active flag)."""
    svc = db.get(Service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    data = body.model_dump(exclude_unset=True)
    if "canonical_name" in data:
        name = (data["canonical_name"] or "").strip()
        if not name:
            raise HTTPException(400, "canonical_name cannot be empty")
        svc.canonical_name = name
    if "category" in data:
        svc.category = (data["category"] or "").strip() or None
    if "icd_code" in data:
        svc.icd_code = (data["icd_code"] or "").strip() or None
    if data.get("is_active") is not None:
        svc.is_active = data["is_active"]
    db.commit()
    db.refresh(svc)
    return svc


@router.get("/services/{service_id}/description")
def service_description(service_id: uuid.UUID, db: Session = Depends(get_db)):
    """Curated educational description for a service (what it is, why useful, how to prepare)."""
    svc = db.get(Service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    desc = _find_description(svc.canonical_name)
    if desc is None:
        return {"canonical_name": svc.canonical_name, "found": False}
    return {**desc, "canonical_name": svc.canonical_name, "found": True}


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
