"""Pydantic response/request DTOs."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tier_type: str
    label_raw: str | None
    amount_kzt: Decimal
    currency_original: str


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    canonical_name: str
    category: str | None
    icd_code: str | None = None


class ServiceUpdate(BaseModel):
    """Partial edit of a dictionary service (only sent fields are changed)."""
    canonical_name: str | None = None
    category: str | None = None
    icd_code: str | None = None
    is_active: bool | None = None


class PartnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    display_name: str
    legal_name: str | None = None
    city: str | None = None
    is_active: bool


class PartnerPriceOut(BaseModel):
    """A partner offering a service, with prices."""
    partner_id: uuid.UUID
    partner_name: str
    city: str | None
    raw_name: str
    effective_date: date | None
    tiers: list[TierOut]
    is_verified: bool


class ServicePriceOut(BaseModel):
    """A service offered by a partner (partner's full price list view)."""
    service_id: uuid.UUID | None
    raw_name: str
    category: str | None
    match_status: str
    effective_date: date | None
    tiers: list[TierOut]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    partner_id: uuid.UUID
    source_filename: str
    file_format: str
    status: str
    year: int | None
    parsed_at: datetime | None
    method_summary: dict
    warnings: list


class UnmatchedOut(BaseModel):
    item_id: uuid.UUID
    raw_name: str
    raw_code: str | None = None
    raw_category: str | None
    partner_id: uuid.UUID
    partner_name: str | None = None
    # provenance — so the operator can open the source and cross-check (ТЗ 4.4)
    document_id: uuid.UUID | None = None
    source_filename: str | None = None
    file_format: str | None = None
    year: int | None = None
    source_ref: str | None = None  # sheet=..;row=.. | page=N;vision | table=0;row=..
    match_status: str
    match_score: float | None
    extraction_method: str | None
    tiers: list[TierOut] = []
    suggestions: list[dict]


class MatchRequest(BaseModel):
    item_id: uuid.UUID
    service_id: uuid.UUID | None = None   # None + create_name => create new service
    create_name: str | None = None
    category: str | None = None
    decided_by: str | None = None
    note: str | None = None


class SearchOut(BaseModel):
    services: list[dict]
    partners: list[dict]
