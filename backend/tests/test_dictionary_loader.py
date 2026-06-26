"""Unit test for the organizer-dictionary XLSX reader (no DB needed)."""
from __future__ import annotations

from pathlib import Path

import openpyxl

from app.normalization.dictionary import _read_xlsx


def test_read_xlsx_dictionary(tmp_path: Path):
    p = tmp_path / "dict.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Специальность", "Code", "Name_ru", "TarificatrCode"])
    ws.append([1, "Аллерголог", 9, "Прием аллерголога", "A02.120.000"])
    ws.append([1, "Аллерголог", 10, "Аллергопробы", "D99.121.801"])
    wb.save(p)

    rows = _read_xlsx(p)
    assert len(rows) == 2
    first = rows[0]
    assert first["name"] == "Прием аллерголога"
    assert first["category"] == "Аллерголог"
    assert first["icd"] == "A02.120.000"
