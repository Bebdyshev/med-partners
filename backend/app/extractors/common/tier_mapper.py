"""Classify a raw price-column label into a TierType.

Centralized so extractors stay dumb. The raw label is always preserved on the
PriceTier; unknown labels fall back to nonresident_generic/unknown rather than
being dropped. Examples from the samples:
  "Цена с учетом НДС для граждан Республики Казахстан, оралманов..." -> resident_kzt
  "...для граждан стран СНГ/ ближнего зарубежья..."                  -> near_abroad
  "...для граждан стран дальнего зарубежья..."                       -> far_abroad
  "Цена без учета НДС"                                               -> base_no_vat
  "Стоимость, тенге" / single price column                          -> resident_kzt
"""
from __future__ import annotations

from app.models.enums import TierType


def map_tier(label: str | None, *, single_column: bool = False) -> TierType:
    if not label:
        return TierType.resident_kzt if single_column else TierType.unknown
    low = label.lower()

    if "без учета ндс" in low or "без ндс" in low:
        return TierType.base_no_vat
    if "дальнего зарубежья" in low or "дальнее зарубежье" in low:
        return TierType.far_abroad
    if "снг" in low or "ближнего зарубежья" in low or "ближнее зарубежье" in low:
        return TierType.near_abroad
    if (
        "республики казахстан" in low
        or "рк" in low.split()
        or "оралман" in low
        or "резидент" in low
    ):
        return TierType.resident_kzt
    if "нерезидент" in low or "иностран" in low:
        return TierType.nonresident_generic

    # A generic single "Цена"/"Стоимость" column is the resident price.
    if single_column:
        return TierType.resident_kzt
    return TierType.resident_kzt
