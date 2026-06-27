"""Adaptive PDF extractor: text-first, OCR fallback — decided PER PAGE.

1. Open with pdfplumber; per page try ruled-table extraction, then word-position
   reconstruction from the embedded text layer.
2. Quality gate: if a page's text layer is too sparse/garbled, rasterize it with
   PyMuPDF and OCR with Tesseract (rus+kaz+eng), reusing the same word->table
   reconstructor on the Tesseract TSV output.
3. Each row records whether it came from "pdf_text" or "pdf_ocr"; OCR rows get a
   lower confidence so they are biased toward the verification queue.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.config import settings
from app.extractors import vision_extract
from app.extractors.base import BaseExtractor, ExtractResult
from app.extractors.common.line_items import parse_line_items, parse_trailing_prices
from app.extractors.common.table_to_rows import table_to_rows
from app.extractors.common.words_to_table import words_to_rows_headerless, words_to_table

_CYRILLIC = re.compile(r"[А-Яа-яЁёІіҚқҢңҒғҮүҰұӘәӨөҺһ]")


def _page_is_scan(page, cover_threshold: float = 0.8) -> bool:
    """A page is a scan when a single image covers most of it (full-page raster)."""
    imgs = getattr(page, "images", None) or []
    if not imgs:
        return False
    page_area = float(page.width * page.height) or 1.0
    cover = max((float(i["width"] * i["height"]) for i in imgs), default=0.0) / page_area
    return cover >= cover_threshold


def _text_quality(text: str) -> tuple[int, float]:
    """Return (char_count, cyrillic_ratio). Low values => treat page as scan."""
    if not text:
        return 0, 0.0
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return len(text.strip()), 0.0
    cyr = sum(1 for c in letters if _CYRILLIC.match(c))
    return len(text.strip()), cyr / len(letters)


class PdfExtractor(BaseExtractor):
    supported_extensions = {"pdf"}

    #: cap OCR pages per document so a huge scan cannot blow the time budget
    ocr_page_budget = 60

    def extract(self, path: Path) -> ExtractResult:
        result = ExtractResult()
        self._ocr_used = 0
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            result.meta["page_count"] = len(pdf.pages)
            for pageno, page in enumerate(pdf.pages, start=1):
                self._extract_page(page, pageno, result, path)
        if not result.rows:
            result.warnings.append("pdf: no rows extracted (text + OCR both empty)")
        return result

    def _extract_page(self, page, pageno: int, result: ExtractResult, pdf_path: Path) -> None:
        text = page.extract_text() or ""
        chars, cyr_ratio = _text_quality(text)
        good_text = chars >= settings.pdf_text_min_chars_per_page and cyr_ratio >= 0.3

        # A scanned page carries a full-page image; its embedded OCR text layer is
        # unreliable (columns merge, codes land in the name). Prefer the vision model,
        # which returns STRUCTURED rows. Falls through to text/Tesseract if vision is off.
        if _page_is_scan(page) and vision_extract.available() and self._ocr_used < self.ocr_page_budget:
            self._ocr_used += 1
            n_before = len(result.rows)
            self._from_vision(pageno, result, pdf_path)
            if len(result.rows) > n_before:
                return

        if good_text:
            # the page has a usable text layer: parse it via the fast path first
            n_before = len(result.rows)
            self._from_text_layer(page, pageno, result)
            if len(result.rows) > n_before:
                return
            for r in parse_line_items(
                text, method="pdf_text", source_prefix=f"page={pageno};li;", confidence=0.7
            ):
                result.add_row(r)
            for r in parse_trailing_prices(
                text, method="pdf_text", source_prefix=f"page={pageno};tp;", confidence=0.55
            ):
                result.add_row(r)
            if len(result.rows) > n_before:
                return
            # text layer present but unparseable -> fall through to OCR (bounded)

        # OCR a scanned page (has an image) within the per-document OCR budget.
        has_image = bool(getattr(page, "images", None))
        if has_image and self._ocr_used < self.ocr_page_budget:
            self._ocr_used += 1
            # Prefer the vision model: it returns STRUCTURED rows (name / code /
            # biomaterial / prices kept apart) instead of merged Tesseract text.
            if vision_extract.available():
                n_before = len(result.rows)
                self._from_vision(pageno, result, pdf_path)
                if len(result.rows) > n_before:
                    return
                # vision yielded nothing (call failed / empty) -> Tesseract fallback
            self._from_ocr(pageno, result, pdf_path)

    # --- vision-LLM path (structured OCR) ---
    def _from_vision(self, pageno: int, result: ExtractResult, pdf_path: Path) -> None:
        try:
            rows = vision_extract.extract_page_rows(pdf_path, pageno - 1)
        except Exception as exc:  # noqa: BLE001 — never let vision crash the doc
            result.warnings.append(f"pdf page {pageno}: vision extraction failed ({exc})")
            return
        for r in rows:
            result.add_row(r)

    # --- text layer path ---
    def _from_text_layer(self, page, pageno: int, result: ExtractResult) -> None:
        # 1) try ruled tables
        try:
            for ti, tbl in enumerate(page.extract_tables() or []):
                rows, warns = table_to_rows(
                    tbl, method="pdf_text", source_prefix=f"page={pageno};tbl={ti};"
                )
                for r in rows:
                    result.add_row(r)
                result.warnings.extend(warns)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"pdf page {pageno}: extract_tables failed ({exc})")
        if any(r.source_ref and f"page={pageno};" in r.source_ref for r in result.rows):
            return
        # 2) reconstruct from positioned words (header case)
        try:
            words = [
                {"text": w["text"], "x0": w["x0"], "x1": w["x1"], "top": w["top"]}
                for w in page.extract_words()
            ]
            table = words_to_table(words)
            rows, warns = table_to_rows(
                table, method="pdf_text", source_prefix=f"page={pageno};words;"
            )
            for r in rows:
                result.add_row(r)
            if rows:
                return
            # 3) headerless position-based parser (numbered lists w/ trailing prices)
            for r in words_to_rows_headerless(
                words, method="pdf_text", source_prefix=f"page={pageno};hl;", confidence=0.6
            ):
                result.add_row(r)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"pdf page {pageno}: word reconstruction failed ({exc})")

    # --- OCR path ---
    def _from_ocr(self, pageno: int, result: ExtractResult, pdf_path: Path) -> None:
        try:
            import io

            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"pdf page {pageno}: OCR deps unavailable ({exc})")
            return
        try:
            # Rasterize this single page with PyMuPDF.
            mdoc = fitz.open(str(pdf_path))
            mpage = mdoc.load_page(pageno - 1)
            zoom = settings.ocr_dpi / 72.0
            pix = mpage.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            data = pytesseract.image_to_data(
                img, lang=settings.ocr_lang, output_type=pytesseract.Output.DICT
            )
            words = []
            for i in range(len(data["text"])):
                txt = (data["text"][i] or "").strip()
                if not txt:
                    continue
                words.append(
                    {
                        "text": txt,
                        "x0": float(data["left"][i]),
                        "x1": float(data["left"][i] + data["width"][i]),
                        "top": float(data["top"][i]),
                    }
                )
            table = words_to_table(words)
            rows, warns = table_to_rows(
                table, method="pdf_ocr", source_prefix=f"page={pageno};ocr;", confidence=0.6
            )
            if rows:
                for r in rows:
                    result.add_row(r)
            else:
                # headerless position-based parser first (resolves column splits via x)
                hl = words_to_rows_headerless(
                    words, method="pdf_ocr", source_prefix=f"page={pageno};ocr-hl;", confidence=0.5
                )
                if hl:
                    for r in hl:
                        result.add_row(r)
                else:
                    # last resort: free-form line-item parse on plain OCR text
                    plain = pytesseract.image_to_string(img, lang=settings.ocr_lang)
                    for r in parse_line_items(
                        plain, method="pdf_ocr", source_prefix=f"page={pageno};ocr-li;", confidence=0.5
                    ):
                        result.add_row(r)
                    for r in parse_trailing_prices(
                        plain, method="pdf_ocr", source_prefix=f"page={pageno};ocr-tp;", confidence=0.45
                    ):
                        result.add_row(r)
            mdoc.close()
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"pdf page {pageno}: OCR failed ({exc})")
