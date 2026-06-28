"""Extractor plugin contract.

Every format extractor returns the SAME structures so the downstream pipeline
(tier-mapping, normalization, validation) is format-agnostic. Extractors stay
"dumb": they keep the original price-column label and let the tier_mapper decide
resident/non-resident classification. New format = new BaseExtractor subclass +
one line in registry.py — the core never changes (pluggable-formats requirement).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass
class RawPrice:
    """One price cell as found in the source, label preserved verbatim."""

    label: str | None          # original column header, e.g. "Цена для граждан РК"
    amount: Decimal
    currency: str = "KZT"


@dataclass
class RawRow:
    """One extracted service line."""

    raw_name: str
    prices: list[RawPrice] = field(default_factory=list)
    code: str | None = None
    category: str | None = None
    source_ref: str | None = None          # e.g. "sheet=Страховой;row=21" or "page=3"
    extraction_method: str = "unknown"     # xlsx | xls | docx | pdf_text | pdf_ocr
    confidence: float = 1.0                # 0..1; OCR rows get lower confidence


@dataclass
class ExtractResult:
    rows: list[RawRow] = field(default_factory=list)
    meta: dict = field(default_factory=dict)       # {org_name, year, sheets, page_count}
    warnings: list[str] = field(default_factory=list)
    method_stats: dict[str, int] = field(default_factory=dict)  # {"pdf_text": 40, "pdf_ocr": 5}

    def add_row(self, row: RawRow) -> None:
        self.rows.append(row)
        self.method_stats[row.extraction_method] = self.method_stats.get(row.extraction_method, 0) + 1


class BaseExtractor(abc.ABC):
    """Interface implemented by every format plugin."""

    #: lower-case extensions (without dot) this extractor handles
    supported_extensions: set[str] = set()

    def can_handle(self, path: Path, mime: str | None = None) -> bool:
        return path.suffix.lower().lstrip(".") in self.supported_extensions

    @abc.abstractmethod
    def extract(self, path: Path, progress=None) -> ExtractResult:
        """Parse the file into structured rows. Must not raise on partial data —
        collect problems into ExtractResult.warnings instead.

        `progress` is an optional callable(dict) for live status (used by the
        streaming demo endpoint). Most extractors ignore it; only PdfExtractor
        emits per-page OCR events through it."""
        raise NotImplementedError
