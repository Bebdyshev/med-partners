from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk
from app.models.enums import TierType

if TYPE_CHECKING:
    from app.models.price_item import PriceItem


class PriceTier(Base):
    """A single price column for a PriceItem. One item may have several tiers
    (resident / near-abroad / far-abroad / base-no-VAT), handling both the
    2-column spec and richer real-world price tables uniformly."""

    __tablename__ = "price_tier"

    id: Mapped[uuid.UUID] = uuid_pk()
    price_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("price_item.id"), index=True
    )
    tier_type: Mapped[TierType] = mapped_column(Enum(TierType, name="tier_type"))
    label_raw: Mapped[str | None] = mapped_column(String(512))  # original column header text
    amount_kzt: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # normalized to KZT
    amount_original: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency_original: Mapped[str] = mapped_column(String(8), default="KZT")

    item: Mapped["PriceItem"] = relationship(back_populates="tiers")
