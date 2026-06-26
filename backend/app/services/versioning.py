"""Versioning: archive-on-change.

When a newer document brings a price for the same (partner, service) — or the
same (partner, raw_name) when still unmatched — the older active item is marked
inactive and linked via superseded_by_id. Nothing is ever deleted, so the full
price history is queryable indefinitely.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import PriceItem
from app.normalization.text_norm import normalize


def supersede_previous(db, new_item: PriceItem) -> int:
    """Archive prior active items that the new_item replaces. Returns count archived."""
    q = select(PriceItem).where(
        PriceItem.partner_id == new_item.partner_id,
        PriceItem.is_active.is_(True),
        PriceItem.id != new_item.id,
    )
    if new_item.service_id is not None:
        q = q.where(PriceItem.service_id == new_item.service_id)
        candidates = db.execute(q).scalars().all()
    else:
        target = normalize(new_item.raw_name)
        candidates = [
            it for it in db.execute(q).scalars().all() if normalize(it.raw_name) == target
        ]

    archived = 0
    for old in candidates:
        # only supersede strictly older (or undated) versions
        if (
            new_item.effective_date is None
            or old.effective_date is None
            or old.effective_date <= new_item.effective_date
        ):
            old.is_active = False
            old.superseded_by_id = new_item.id
            archived += 1
    return archived
