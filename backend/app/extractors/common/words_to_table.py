"""Reconstruct an aligned table from positioned words.

Both PDF paths produce the same word structure, so one reconstructor serves both:
  - text layer:   pdfplumber page.extract_words()
  - OCR fallback: pytesseract image_to_data (TSV)

A "word" is a dict: {text, x0, x1, top}. Algorithm:
  1. cluster words into lines by vertical proximity;
  2. find column boundaries from vertical whitespace gaps in the x-projection of
     all words (robust to multi-word cells and wrapped headers);
  3. assign every word to a column band -> aligned list-of-lists table.
"""
from __future__ import annotations

import re

from app.extractors.base import RawPrice, RawRow
from app.extractors.common.column_map import _NAME_KW, _PRICE_KW, _CODE_KW, _UNIT_KW, _matches, _norm
from app.extractors.common.price_parse import parse_price

_LEADING_NUM = re.compile(r"^\s*\d{1,4}[.)]?\s+")

_HEADER_GROUPS = [_NAME_KW, _PRICE_KW, _CODE_KW, _UNIT_KW]


def _group_lines(words: list[dict], y_tol: float = 6.0) -> list[list[dict]]:
    if not words:
        return []
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    current: list[dict] = [words[0]]
    cur_top = words[0]["top"]
    for w in words[1:]:
        if abs(w["top"] - cur_top) <= y_tol:
            current.append(w)
        else:
            lines.append(sorted(current, key=lambda x: x["x0"]))
            current = [w]
            cur_top = w["top"]
    lines.append(sorted(current, key=lambda x: x["x0"]))
    return lines


def _score_header(line: list[dict]) -> int:
    cells = [w["text"] for w in line]
    return sum(1 for g in _HEADER_GROUPS if any(_matches(_norm(c), g) for c in cells))


def _column_bounds(words: list[dict], min_gap: float = 12.0) -> list[float]:
    """Find column separator x-positions from gaps in horizontal coverage."""
    if not words:
        return []
    intervals = sorted((w["x0"], w["x1"]) for w in words)
    merged: list[list[float]] = [list(intervals[0])]
    for x0, x1 in intervals[1:]:
        if x0 <= merged[-1][1] + min_gap:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    # separators are midpoints of the gaps between merged bands
    seps = []
    for a, b in zip(merged, merged[1:]):
        seps.append((a[1] + b[0]) / 2)
    return seps


def _col_of(x_center: float, seps: list[float]) -> int:
    idx = 0
    for s in seps:
        if x_center > s:
            idx += 1
        else:
            break
    return idx


def words_to_table(words: list[dict], max_scan: int = 40) -> list[list]:
    lines = _group_lines(words)
    if not lines:
        return []

    header_i, best = -1, 0
    for i, line in enumerate(lines[:max_scan]):
        s = _score_header(line)
        if s > best and s >= 2:
            best, header_i = s, i
    if header_i < 0:
        return []

    body = lines[header_i:]
    flat = [w for line in body for w in line]
    seps = _column_bounds(flat)
    n_cols = len(seps) + 1

    table: list[list] = []
    for line in body:
        cells = [""] * n_cols
        for w in line:
            c = _col_of((w["x0"] + w["x1"]) / 2, seps)
            cells[c] = (cells[c] + " " + w["text"]).strip()
        table.append([c or None for c in cells])
    return table


def words_to_rows_headerless(
    words: list[dict], *, method: str, source_prefix: str = "", confidence: float = 0.55
) -> list[RawRow]:
    """Position-based parser for scans/text-layers with NO usable header row.

    Detects columns from x-gaps, then classifies each column by content:
    numeric columns become price tiers; the widest text column becomes the name.
    Resolves the space-grouped-thousands ambiguity that flat text cannot
    (e.g. "148 500 166 400 186 400" splits correctly via x-positions).
    """
    lines = _group_lines(words)
    if len(lines) < 3:
        return []
    flat = [w for line in lines for w in line]
    seps = _column_bounds(flat)
    n_cols = len(seps) + 1
    if n_cols < 2:
        return []

    grid: list[list[str]] = []
    for line in lines:
        cells = [""] * n_cols
        for w in line:
            c = _col_of((w["x0"] + w["x1"]) / 2, seps)
            cells[c] = (cells[c] + " " + w["text"]).strip()
        grid.append(cells)

    # classify columns by how often their cells parse as a price >= 100
    price_score = [0] * n_cols
    text_len = [0] * n_cols
    filled = [0] * n_cols
    for row in grid:
        for c, val in enumerate(row):
            if not val:
                continue
            filled[c] += 1
            p = parse_price(val)
            if p is not None and 100 <= p[0] <= 100_000_000:
                price_score[c] += 1
            else:
                text_len[c] += len(val)
    price_cols = [
        c for c in range(n_cols) if filled[c] >= 3 and price_score[c] / filled[c] >= 0.6
    ]
    text_cols = [c for c in range(n_cols) if c not in price_cols and filled[c] >= 3]
    if not price_cols or not text_cols:
        return []
    # name column = the text column with the largest average text length
    name_col = max(text_cols, key=lambda c: text_len[c] / max(filled[c], 1))

    rows: list[RawRow] = []
    for ri, row in enumerate(grid):
        name = _LEADING_NUM.sub("", (row[name_col] or "")).strip(" .:|-")
        if not name or not any(ch.isalpha() for ch in name):
            continue
        prices: list[RawPrice] = []
        for c in price_cols:
            p = parse_price(row[c])
            if p is not None and 0 < p[0] <= 100_000_000:
                prices.append(RawPrice(label=None, amount=p[0], currency=p[1]))
        if not prices:
            continue
        rows.append(RawRow(
            raw_name=name, prices=prices, source_ref=f"{source_prefix}row={ri}",
            extraction_method=method, confidence=confidence,
        ))
    return rows
