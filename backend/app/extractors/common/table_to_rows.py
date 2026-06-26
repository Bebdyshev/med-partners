"""Turn a raw table (list of row value-lists) into RawRow objects.

Shared by every tabular extractor (xlsx, xls, docx, pdf-text). Encapsulates:
header detection -> column mapping -> category tracking -> price parsing.
"""
from __future__ import annotations

import re

from app.extractors.base import RawPrice, RawRow
from app.extractors.common.category_detect import clean_category, is_category_row
from app.extractors.common.header_detect import detect_header
from app.extractors.common.column_map import infer_price_columns, map_columns
from app.extractors.common.price_parse import parse_price

# a name that is just a number / punctuation (e.g. the "1 2 3 4" column-numbering row)
_NON_NAME_RE = re.compile(r"^[\d\W_]+$")
# generic header words that are not real service names (column-reconstruction noise)
_GENERIC_NAMES = {"услуга", "наименование", "наименование услуги", "название", "service"}
# prices above this are almost certainly column-merge artifacts, not real KZT amounts
_MAX_SANE_PRICE = 100_000_000


def _cell(row: list, idx: int | None):
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def table_to_rows(
    table: list[list],
    *,
    method: str,
    source_prefix: str = "",
    confidence: float = 1.0,
) -> tuple[list[RawRow], list[str]]:
    """Return (rows, warnings). Empty list if no usable header found."""
    warnings: list[str] = []
    if not table:
        return [], warnings

    det = detect_header(table)
    if det is None:
        warnings.append(f"{source_prefix}: no header row detected")
        return [], warnings
    header_idx, header = det
    cm = map_columns(header)
    # data-driven pass: promote unlabeled numeric columns (tariff-tier price cols)
    infer_price_columns(cm, table[header_idx + 1 :], header)
    if not cm.is_usable:
        warnings.append(f"{source_prefix}: header at row {header_idx} has no name+price columns")
        return [], warnings

    single_price = len(cm.price_cols) == 1
    rows: list[RawRow] = []
    current_category: str | None = None

    for r in range(header_idx + 1, len(table)):
        row = table[r]
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        name = _cell(row, cm.name)
        price_cells = [_cell(row, c) for c in cm.price_cols]

        if is_category_row(name, price_cells):
            current_category = clean_category(str(name))
            continue
        if name is None or not str(name).strip():
            continue
        name_s = str(name).strip()
        # skip column-numbering rows like "1 | 2 | 3 | 4"
        if _NON_NAME_RE.match(name_s):
            continue
        # skip generic header-fragment names produced by failed column reconstruction
        if name_s.lower() in _GENERIC_NAMES:
            continue

        prices: list[RawPrice] = []
        for c in cm.price_cols:
            parsed = parse_price(_cell(row, c))
            if parsed is None:
                continue
            amount, currency = parsed
            if not (0 < amount <= _MAX_SANE_PRICE):
                continue  # non-positive or column-merge artifact (numbers stuck together)
            prices.append(RawPrice(label=cm.price_labels.get(c), amount=amount, currency=currency))

        if not prices:
            # a named row with no parseable price — skip but keep a light warning budget
            continue

        rows.append(
            RawRow(
                raw_name=str(name).strip(),
                prices=prices,
                code=(str(_cell(row, cm.code)).strip() if _cell(row, cm.code) else None),
                category=current_category,
                source_ref=f"{source_prefix}row={r + 1}",
                extraction_method=method,
                confidence=confidence,
            )
        )
    return rows, warnings
