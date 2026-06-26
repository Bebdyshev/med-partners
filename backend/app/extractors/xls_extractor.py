"""Legacy .xls extractor via xlrd, with a libreoffice->xlsx conversion fallback."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.extractors.base import BaseExtractor, ExtractResult
from app.extractors.common.table_to_rows import table_to_rows


class XlsExtractor(BaseExtractor):
    supported_extensions = {"xls"}

    def extract(self, path: Path) -> ExtractResult:
        result = ExtractResult()
        try:
            import xlrd

            book = xlrd.open_workbook(str(path))
            result.meta["sheets"] = book.sheet_names()
            for sheet in book.sheets():
                table = [
                    [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                    for r in range(sheet.nrows)
                ]
                # xlrd yields empty strings for blanks; normalize to None
                table = [[(v if v != "" else None) for v in row] for row in table]
                rows, warns = table_to_rows(
                    table, method="xls", source_prefix=f"sheet={sheet.name};"
                )
                for row in rows:
                    result.add_row(row)
                result.warnings.extend(warns)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"xls: xlrd failed ({exc}); trying libreoffice conversion")
            converted = self._convert_with_libreoffice(path)
            if converted is not None:
                from app.extractors.xlsx_extractor import XlsxExtractor

                sub = XlsxExtractor().extract(converted)
                result.rows.extend(sub.rows)
                result.method_stats = sub.method_stats
                result.warnings.extend(sub.warnings)
            else:
                result.warnings.append("xls: libreoffice conversion unavailable")
        if not result.rows:
            result.warnings.append("xls: no rows extracted")
        return result

    @staticmethod
    def _convert_with_libreoffice(path: Path) -> Path | None:
        soffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not soffice:
            return None
        outdir = Path(tempfile.mkdtemp(prefix="xls2xlsx_"))
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "xlsx", "--outdir", str(outdir), str(path)],
                check=True,
                capture_output=True,
                timeout=120,
            )
            out = outdir / (path.stem + ".xlsx")
            return out if out.exists() else None
        except Exception:  # noqa: BLE001
            return None
