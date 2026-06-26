from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.price_document import PriceDocument
    from app.models.price_item import PriceItem


class Partner(Base, TimestampMixin):
    __tablename__ = "partner"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Stable code parsed from the filename, e.g. "Клиника 2". Used for dedup/identity.
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    legal_name: Mapped[str | None] = mapped_column(String(512))  # harvested from letterhead
    bin_iin: Mapped[str | None] = mapped_column(String(12), index=True)
    city: Mapped[str | None] = mapped_column(String(128), index=True)
    address: Mapped[str | None] = mapped_column(String(512))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    documents: Mapped[list["PriceDocument"]] = relationship(back_populates="partner")
    items: Mapped[list["PriceItem"]] = relationship(back_populates="partner")
