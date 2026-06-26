"""Validation rules. Each takes a ValItem and yields Warning records.

Kept independent of the ORM so they are pure and unit-testable. The pipeline
adapts PriceItem+tiers into a ValItem and feeds prior-version context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.config import settings
from app.models.enums import TierType

LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"


@dataclass
class TierVal:
    tier_type: TierType
    amount_kzt: Decimal


@dataclass
class ValItem:
    raw_name: str
    tiers: list[TierVal]
    effective_date: date | None = None
    confidence: float = 1.0
    is_duplicate: bool = False                 # set by pipeline (same partner+service+date)
    prev_resident_price: Decimal | None = None  # active price of previous version
    today: date | None = None


@dataclass
class Warning:
    code: str
    level: str
    message: str


@dataclass
class ValReport:
    warnings: list[Warning] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(w.level == LEVEL_ERROR for w in self.warnings)

    @property
    def needs_review(self) -> bool:
        return bool(self.warnings)


def _resident(tiers: list[TierVal]) -> Decimal | None:
    for t in tiers:
        if t.tier_type == TierType.resident_kzt:
            return t.amount_kzt
    return tiers[0].amount_kzt if tiers else None


# --- individual rules ---

def rule_price_positive(item: ValItem):
    for t in item.tiers:
        if t.amount_kzt is None or t.amount_kzt <= 0:
            yield Warning("price_not_positive", LEVEL_ERROR, f"non-positive price in tier {t.tier_type.value}")


def rule_nonresident_gte_resident(item: ValItem):
    res = _resident(item.tiers)
    if res is None:
        return
    for t in item.tiers:
        if t.tier_type in (TierType.near_abroad, TierType.far_abroad, TierType.nonresident_generic):
            if t.amount_kzt < res:
                yield Warning(
                    "nonresident_lt_resident", LEVEL_WARNING,
                    f"{t.tier_type.value} price {t.amount_kzt} < resident {res}",
                )


def rule_name_nonempty(item: ValItem):
    if not item.raw_name or not item.raw_name.strip():
        yield Warning("empty_name", LEVEL_ERROR, "service name is empty")


def rule_date_not_future(item: ValItem):
    if item.effective_date and item.today and item.effective_date > item.today:
        yield Warning("future_date", LEVEL_WARNING, f"effective_date {item.effective_date} is in the future")


def rule_duplicate(item: ValItem):
    if item.is_duplicate:
        yield Warning("duplicate", LEVEL_WARNING, "duplicate of an existing item (same partner+service+date)")


def rule_price_anomaly(item: ValItem):
    res = _resident(item.tiers)
    if res is None or item.prev_resident_price is None or item.prev_resident_price == 0:
        return
    delta_pct = abs(res - item.prev_resident_price) / item.prev_resident_price * 100
    if delta_pct > settings.price_change_anomaly_pct:
        yield Warning(
            "price_anomaly", LEVEL_WARNING,
            f"price changed {delta_pct:.0f}% vs previous ({item.prev_resident_price} -> {res})",
        )


def rule_low_confidence(item: ValItem):
    if item.confidence < 0.65:
        yield Warning("low_confidence", LEVEL_WARNING, f"low extraction confidence {item.confidence:.2f}")


ALL_RULES = [
    rule_name_nonempty,
    rule_price_positive,
    rule_nonresident_gte_resident,
    rule_date_not_future,
    rule_duplicate,
    rule_price_anomaly,
    rule_low_confidence,
]
