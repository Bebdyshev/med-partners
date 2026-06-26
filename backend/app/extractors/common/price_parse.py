"""Parse messy price strings into (Decimal, currency).

Handles real-world artifacts seen in the samples: NBSP/space thousands
separators ("14 400"), trailing currency words ("12 840 тг"), comma decimals
("2099,5"), and stray symbols. Returns None when the cell is not a price.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# currency hints -> ISO-ish code
_CURRENCY_HINTS = {
    "kzt": "KZT", "тг": "KZT", "тенге": "KZT", "₸": "KZT",
    "usd": "USD", "$": "USD", "доллар": "USD",
    "rub": "RUB", "руб": "RUB", "₽": "RUB",
    "eur": "EUR", "€": "EUR",
}

_NUM_RE = re.compile(r"[-+]?\d[\d\s .,]*\d|\d")


def detect_currency(text: str) -> str:
    low = text.lower()
    for hint, code in _CURRENCY_HINTS.items():
        if hint in low:
            return code
    return "KZT"


def parse_price(value) -> tuple[Decimal, str] | None:
    """Return (amount, currency) or None if the value is not a usable price."""
    if value is None:
        return None
    # Numeric cells (from openpyxl/pandas) come pre-typed.
    if isinstance(value, (int, float)):
        try:
            return (Decimal(str(value)), "KZT")
        except InvalidOperation:
            return None
    if isinstance(value, Decimal):
        return (value, "KZT")

    text = str(value).strip()
    if not text:
        return None

    currency = detect_currency(text)
    m = _NUM_RE.search(text)
    if not m:
        return None
    num = m.group(0)
    # Normalize separators: drop spaces/NBSP, decide decimal sep.
    num = num.replace(" ", "").replace(" ", "")
    if "," in num and "." in num:
        # assume "." thousands, "," decimal (ru) -> e.g. 1.234,56
        num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        # single comma -> decimal sep
        num = num.replace(",", ".")
    try:
        amount = Decimal(num)
    except InvalidOperation:
        return None
    return (amount, currency)


def looks_like_price(value) -> bool:
    return parse_price(value) is not None
