"""Find the header row inside a tabular sheet.

Sample files bury the header under 8-17 rows of letterhead/signatures
("Утверждаю", org names, approval lines). We slide down the first N rows,
score each by how many column-keyword groups it contains, and pick the best.
Supports a 2-row merged header by merging the winner with the next row when
that row adds price/unit keywords (the Клиника 8 case).
"""
from __future__ import annotations

from app.extractors.common.column_map import (
    _CODE_KW,
    _NAME_KW,
    _PRICE_KW,
    _UNIT_KW,
    _matches,
    _norm,
    map_columns,
)

_GROUPS = [_NAME_KW, _PRICE_KW, _CODE_KW, _UNIT_KW]


def _row_score(cells: list) -> int:
    score = 0
    for group in _GROUPS:
        if any(_matches(_norm(c), group) for c in cells if c is not None):
            score += 1
    return score


def detect_header(rows: list[list], max_scan: int = 30) -> tuple[int, list] | None:
    """Return (header_row_index, merged_header_cells) or None.

    `rows` is a list of row value-lists (already read from the sheet/table).
    """
    best_idx, best_score = -1, 0
    limit = min(len(rows), max_scan)
    for i in range(limit):
        score = _row_score(rows[i])
        # must contain at least a name-ish and a price-ish keyword to qualify
        if score > best_score and score >= 2:
            best_score, best_idx = score, i
    if best_idx < 0:
        return None

    header = list(rows[best_idx])
    header_end = best_idx
    # merge a sparse continuation row (multi-row merged header). A sparse row right
    # after the header is almost always a continuation carrying extra tier labels,
    # e.g. Клиника 8 puts "для граждан РК" on the row below the main header.
    nxt = best_idx + 1
    if nxt < len(rows):
        next_cells = rows[nxt]
        non_empty = sum(1 for c in next_cells if c is not None and str(c).strip())
        header_non_empty = sum(1 for c in header if c is not None and str(c).strip())
        # Merge only a GENUINELY sparse continuation row (a wrapped/merged header
        # cell), i.e. far fewer filled cells than the header. A row as full as the
        # header is the first data row, not a header continuation.
        if 1 <= non_empty <= max(1, len(header) // 3) and non_empty < header_non_empty:
            width = max(len(header), len(next_cells))
            a_row = list(header) + [None] * (width - len(header))
            b_row = list(next_cells) + [None] * (width - len(next_cells))
            merged = []
            for a, b in zip(a_row, b_row):
                a_s = "" if a is None else str(a).strip()
                b_s = "" if b is None else str(b).strip()
                merged.append((a_s + " " + b_s).strip() or None)
            header = merged
            header_end = nxt
    return header_end, header


def find_columns(rows: list[list], max_scan: int = 30):
    """Convenience: detect header and return (header_idx, ColumnMap)."""
    res = detect_header(rows, max_scan=max_scan)
    if res is None:
        return None
    idx, header = res
    return idx, map_columns(header)
