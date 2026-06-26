"""Detect inline section/category rows.

Price tables interleave section headers ("1. СТАЦИОНАР", "ПРИЕМ ВРАЧА",
"Раздел 2.1.Выездные услуги") that have a name but no price. These must become
the running category context for following rows, not be stored as services.
"""
from __future__ import annotations

import re

from app.extractors.common.price_parse import looks_like_price

_SECTION_RE = re.compile(
    r"^\s*(раздел|глава|часть|приложение)\b|^\s*\d+(\.\d+)*\.?\s*[А-ЯЁA-Z]",
    re.IGNORECASE,
)


def is_category_row(name: str | None, price_cells: list) -> bool:
    """True when the row names a section but carries no price."""
    if not name or not str(name).strip():
        return False
    has_price = any(looks_like_price(c) for c in price_cells)
    if has_price:
        return False
    text = str(name).strip()
    # All-caps heading, or matches a "Раздел N"/numbered-section pattern.
    if _SECTION_RE.search(text):
        return True
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7 and len(text) < 80:
        return True
    return False


def clean_category(name: str) -> str:
    """Strip leading numbering/"Раздел" prefix for a tidy category label."""
    text = str(name).strip()
    text = re.sub(r"^\s*(раздел|глава|часть)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\d+(\.\d+)*\.?\s*", "", text)
    return text.strip(" .:-") or text
