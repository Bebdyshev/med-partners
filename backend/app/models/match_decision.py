from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.models.enums import MatchAction, MatchMethod


class MatchDecision(Base):
    """Audit trail + review-queue resolution history for normalization."""

    __tablename__ = "match_decision"

    id: Mapped[uuid.UUID] = uuid_pk()
    price_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("price_item.id"), index=True
    )
    candidate_service_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("service.id"), nullable=True
    )
    score: Mapped[float | None] = mapped_column(Float)
    method: Mapped[MatchMethod] = mapped_column(Enum(MatchMethod, name="match_method"))
    action: Mapped[MatchAction | None] = mapped_column(Enum(MatchAction, name="match_action"))
    decided_by: Mapped[str | None] = mapped_column(String(128))  # operator id/email, null = auto
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
