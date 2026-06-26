"""Fallback parser for header-less, free-form price lists.

Many small-clinic price lists (and noisy OCR output) are just lines of
"<service name> <price> тг [| <price> тг]" with no table header at all. When the
table reconstructor finds no header, we parse each line: the name is the text
before the first price token; prices are the тг-suffixed numbers on the line.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.extractors.base import RawPrice, RawRow

# a price = a number (optionally space-grouped) immediately followed by a KZT marker
_PRICE_RE = re.compile(r"(\d[\d\s ]{0,9}\d|\d)\s*(?:тг|тенге|тнг|tr|₸|тт)\b", re.IGNORECASE)
# minimal plausible service name: has at least 3 cyrillic/latin letters
_HAS_NAME = re.compile(r"[А-Яа-яЁёA-Za-z].*[А-Яа-яЁёA-Za-z].*[А-Яа-яЁёA-Za-z]")
# prices above this are column-merge artifacts, not real KZT amounts
_MAX_SANE_PRICE = 100_000_000

# a "price group": space-grouped thousands ("148 500") or a plain >=3-digit number.
# >=3 digits avoids catching row numbers / quantities like "1" or "29".
_PG = r"\d{1,3}(?:[  ]\d{3})+|\d{3,}"
# a trailing run of 1-4 price groups anchored at end of line
_TRAILING_RE = re.compile(rf"((?:{_PG})(?:[  ]+(?:{_PG})){{0,3}})\s*$")
_LEADING_NUM_RE = re.compile(r"^\s*\d{1,4}[.)]?\s+")  # leading row number to strip from name


def _to_decimal(num: str) -> Decimal | None:
    cleaned = num.replace(" ", "").replace(" ", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_line_items(
    text: str, *, method: str, source_prefix: str = "", confidence: float = 0.5
) -> list[RawRow]:
    rows: list[RawRow] = []
    for li, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        matches = list(_PRICE_RE.finditer(line))
        if not matches:
            continue
        name = line[: matches[0].start()].strip(" .:|-\t")
        if not name or not _HAS_NAME.search(name):
            continue
        prices: list[RawPrice] = []
        for m in matches:
            d = _to_decimal(m.group(1))
            if d is not None and 0 < d <= _MAX_SANE_PRICE:
                prices.append(RawPrice(label=None, amount=d, currency="KZT"))
        if not prices:
            continue
        rows.append(
            RawRow(
                raw_name=name,
                prices=prices,
                source_ref=f"{source_prefix}line={li + 1}",
                extraction_method=method,
                confidence=confidence,
            )
        )
    return rows


def parse_trailing_prices(
    text: str, *, method: str, source_prefix: str = "", confidence: float = 0.5
) -> list[RawRow]:
    """Parse numbered lists whose lines end with bare price numbers (no тг marker),
    e.g. "9 Выездная консультация ... пакет 148 500 166 400 186 400". The trailing
    run of price groups becomes the tiers; the rest (minus the row number) is the name."""
    rows: list[RawRow] = []
    for li, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        m = _TRAILING_RE.search(line)
        if not m:
            continue
        name = _LEADING_NUM_RE.sub("", line[: m.start()]).strip(" .:|-\t")
        if not name or not _HAS_NAME.search(name):
            continue
        prices: list[RawPrice] = []
        # iterate price-groups (handles "19 800" as one number, not "19" + "800")
        for gm in re.finditer(_PG, m.group(1)):
            d = _to_decimal(gm.group(0))
            if d is not None and 0 < d <= _MAX_SANE_PRICE:
                prices.append(RawPrice(label=None, amount=d, currency="KZT"))
        if not prices:
            continue
        rows.append(RawRow(
            raw_name=name, prices=prices, source_ref=f"{source_prefix}line={li + 1}",
            extraction_method=method, confidence=confidence,
        ))
    return rows
