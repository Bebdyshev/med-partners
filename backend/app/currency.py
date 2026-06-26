"""Currency normalization to KZT.

Spec requires non-KZT prices be converted at the rate on the price date while
keeping the original. For the MVP we use a small static rate table (KZT per unit);
a real deployment would look rates up by date from the National Bank.
"""
from __future__ import annotations

from decimal import Decimal

# KZT per 1 unit of the currency (approximate; override per-date in production)
_RATES: dict[str, Decimal] = {
    "KZT": Decimal(1),
    "USD": Decimal("480"),
    "RUB": Decimal("5.3"),
    "EUR": Decimal("520"),
}


def to_kzt(amount: Decimal, currency: str) -> Decimal:
    rate = _RATES.get((currency or "KZT").upper(), Decimal(1))
    return (amount * rate).quantize(Decimal("0.01"))
