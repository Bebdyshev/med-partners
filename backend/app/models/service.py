from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import MatchMethod

if TYPE_CHECKING:
    from app.models.price_item import PriceItem


class Service(Base, TimestampMixin):
    """Target dictionary entry. service_name_raw values are normalized onto this."""

    __tablename__ = "service"

    id: Mapped[uuid.UUID] = uuid_pk()
    canonical_name: Mapped[str] = mapped_column(Text, index=True)
    category: Mapped[str | None] = mapped_column(String(255), index=True)
    icd_code: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # search_vector (tsvector) + embedding columns are added via migration (raw DDL)

    synonyms: Mapped[list["ServiceSynonym"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    items: Mapped[list["PriceItem"]] = relationship(back_populates="service")


class ServiceSynonym(Base):
    __tablename__ = "service_synonym"

    id: Mapped[uuid.UUID] = uuid_pk()
    service_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("service.id"), index=True
    )
    synonym: Mapped[str] = mapped_column(Text, index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | learned | seed

    service: Mapped["Service"] = relationship(back_populates="synonyms")
