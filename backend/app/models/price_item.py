from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import MatchStatus

if TYPE_CHECKING:
    from app.models.partner import Partner
    from app.models.price_document import PriceDocument
    from app.models.price_tier import PriceTier
    from app.models.service import Service


class PriceItem(Base, TimestampMixin):
    """One service line from one document. Prices live in related PriceTier rows."""

    __tablename__ = "price_item"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("price_document.id"), index=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("partner.id"), index=True
    )  # denormalized for query speed
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("service.id"), nullable=True, index=True
    )

    raw_name: Mapped[str] = mapped_column(Text)
    raw_code: Mapped[str | None] = mapped_column(String(128))
    raw_category: Mapped[str | None] = mapped_column(String(512))
    source_ref: Mapped[str | None] = mapped_column(String(128))  # sheet/page/row pointer
    extraction_method: Mapped[str | None] = mapped_column(String(32))  # pdf_text/pdf_ocr/xlsx/...
    extraction_confidence: Mapped[float | None] = mapped_column(Float)

    # normalization
    match_status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status"), default=MatchStatus.unmatched, index=True
    )
    match_score: Mapped[float | None] = mapped_column(Float)

    # verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_note: Mapped[str | None] = mapped_column(Text)

    # validation
    warnings: Mapped[list] = mapped_column(JSONB, default=list)

    # versioning (archive-on-change)
    effective_date: Mapped[date | None] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("price_item.id"), nullable=True
    )

    document: Mapped["PriceDocument"] = relationship(back_populates="items")
    partner: Mapped["Partner"] = relationship(back_populates="items")
    service: Mapped["Service | None"] = relationship(back_populates="items")
    tiers: Mapped[list["PriceTier"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
