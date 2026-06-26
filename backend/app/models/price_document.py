from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import FileFormat, ParseStatus

if TYPE_CHECKING:
    from app.models.partner import Partner
    from app.models.price_item import PriceItem


class PriceDocument(Base, TimestampMixin):
    __tablename__ = "price_document"

    id: Mapped[uuid.UUID] = uuid_pk()
    partner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("partner.id"), index=True
    )
    source_filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))  # immutable original
    file_format: Mapped[FileFormat] = mapped_column(Enum(FileFormat, name="file_format"))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256, dedup re-uploads
    year: Mapped[int | None] = mapped_column(Integer)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), default=ParseStatus.queued, index=True
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_log: Mapped[str | None] = mapped_column(Text)
    method_summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # {pdf_text: n, pdf_ocr: m}
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    raw_content: Mapped[str | None] = mapped_column(Text)  # extracted raw text, for audit

    partner: Mapped["Partner"] = relationship(back_populates="documents")
    items: Mapped[list["PriceItem"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
