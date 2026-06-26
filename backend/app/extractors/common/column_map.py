"""Map a detected header row's cells onto canonical fields.

Canonical fields: "name", "code", "unit", "price" (one or many price columns).
Detection is two-pronged:
  1. keyword scoring on the header cells (token-aware to avoid false hits like
     "тариф" matching "тарификатору");
  2. a data-driven numeric scan that promotes unlabeled numeric columns to price
     columns — needed because some real price headers are pure tariff-tier
     descriptions ("для граждан Республики Казахстан") with no "цена" keyword.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.extractors.common.price_parse import looks_like_price

_NAME_KW = ["наименование услуг", "наименование", "услуга", "название", "service"]
_CODE_KW = ["код услуги", "код по тарификатору", "код", "шифр", "code", "мкб"]
_UNIT_KW = ["ед.изм", "ед. изм", "единица", "ед.  изм", "unit", "кол-во", "количество"]
_PRICE_KW = ["цена", "стоимость", "тариф", "прайс", "price", "сумма", "для граждан", "руб", "тенге"]
# columns that are never a service price (index / row numbers)
_IGNORE_KW = ["№", "п/п", "n п/п", "no", "№ п/п"]

_WORD_RE = re.compile(r"[а-яёa-zіөүұқғңһәi0-9][а-яёa-zіөүұқғңһәi0-9.\-]*", re.IGNORECASE)


@dataclass
class ColumnMap:
    name: int | None = None
    code: int | None = None
    unit: int | None = None
    price_cols: list[int] = field(default_factory=list)
    price_labels: dict[int, str] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.name is not None and bool(self.price_cols)


def _norm(s) -> str:
    return str(s).strip().lower().replace("\n", " ") if s is not None else ""


def _matches(cell: str, keywords: list[str]) -> bool:
    """Token-aware keyword match. Phrases (with spaces) use substring/fuzz;
    single-word keywords must match a whole token (with a small startswith slack)
    so 'тариф' does not match 'тарификатору'."""
    if not cell:
        return False
    words = _WORD_RE.findall(cell)
    for kw in keywords:
        if " " in kw:
            if kw in cell or fuzz.partial_ratio(kw, cell) >= 92:
                return True
            continue
        for w in words:
            if w == kw:
                return True
            if len(kw) >= 5 and w.startswith(kw) and (len(w) - len(kw)) <= 2:
                return True
    return False


def map_columns(header_cells: list) -> ColumnMap:
    cm = ColumnMap()
    for idx, raw in enumerate(header_cells):
        cell = _norm(raw)
        if not cell:
            continue
        if _matches(cell, _IGNORE_KW) and not _matches(cell, _PRICE_KW):
            continue
        if _matches(cell, _PRICE_KW):
            cm.price_cols.append(idx)
            cm.price_labels[idx] = str(raw).strip()
            continue
        if cm.name is None and _matches(cell, _NAME_KW):
            cm.name = idx
            continue
        if cm.code is None and _matches(cell, _CODE_KW):
            cm.code = idx
            continue
        if cm.unit is None and _matches(cell, _UNIT_KW):
            cm.unit = idx
    return cm


def infer_price_columns(cm: ColumnMap, data_rows: list[list], header: list) -> None:
    """Promote unclassified, predominantly-numeric columns to price columns.

    Mutates `cm` in place. Skips columns already classified as name/code/unit/price
    and columns whose header is an index marker (№ п/п)."""
    claimed = {cm.name, cm.code, cm.unit, *cm.price_cols}
    n_cols = max((len(r) for r in data_rows), default=0)
    n_cols = max(n_cols, len(header))
    sample = data_rows[:40]
    for c in range(n_cols):
        if c in claimed:
            continue
        head_text = _norm(header[c]) if c < len(header) else ""
        if head_text and (_matches(head_text, _IGNORE_KW) or _matches(head_text, _UNIT_KW)):
            continue
        numeric = total = 0
        ints_seq = []
        for row in sample:
            if c >= len(row):
                continue
            val = row[c]
            if val is None or str(val).strip() == "":
                continue
            total += 1
            if looks_like_price(val):
                numeric += 1
                try:
                    ints_seq.append(float(str(val).replace(" ", "").replace(",", ".")))
                except ValueError:
                    pass
        if total >= 3 and numeric / total >= 0.7:
            # guard: skip a 1,2,3,... index column that slipped through
            if len(ints_seq) >= 5 and ints_seq == sorted(ints_seq) and all(
                abs(b - a - 1) < 0.001 for a, b in zip(ints_seq, ints_seq[1:])
            ):
                continue
            # guard: a constant-valued column (e.g. Кол-во always 1) is not a price
            if len(ints_seq) >= 3 and len(set(ints_seq)) == 1:
                continue
            cm.price_cols.append(c)
            if c < len(header) and header[c]:
                cm.price_labels[c] = str(header[c]).strip()
    cm.price_cols.sort()
