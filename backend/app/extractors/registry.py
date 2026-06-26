"""Extractor registry: route a file to the right plugin by extension + magic bytes.

Add a new format = import its extractor and append to _EXTRACTORS. Nothing else
in the pipeline changes (pluggable-formats requirement).
"""
from __future__ import annotations

from pathlib import Path

from app.extractors.base import BaseExtractor
from app.extractors.docx_extractor import DocxExtractor
from app.extractors.pdf_extractor import PdfExtractor
from app.extractors.xls_extractor import XlsExtractor
from app.extractors.xlsx_extractor import XlsxExtractor
from app.models.enums import FileFormat

_EXTRACTORS: list[BaseExtractor] = [
    XlsxExtractor(),
    XlsExtractor(),
    DocxExtractor(),
    PdfExtractor(),
]

# magic-byte signatures to confirm the true type (mislabeled extensions happen)
_SIGNATURES = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "zip",   # xlsx/docx are zip containers
    b"\xd0\xcf\x11\xe0": "ole",  # legacy xls/doc (OLE2)
}


def sniff(path: Path) -> str | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
    except OSError:
        return None
    for sig, kind in _SIGNATURES.items():
        if head.startswith(sig):
            return kind
    return None


def detect_format(path: Path) -> FileFormat:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"xlsx", "xlsm"}:
        return FileFormat.xlsx
    if ext == "xls":
        return FileFormat.xls
    if ext == "docx":
        return FileFormat.docx
    if ext == "pdf":
        return FileFormat.pdf  # text vs scan is decided during extraction
    # fall back to magic bytes
    kind = sniff(path)
    if kind == "pdf":
        return FileFormat.pdf
    if kind == "ole":
        return FileFormat.xls
    return FileFormat.unknown


def get_extractor(path: Path) -> BaseExtractor | None:
    for ex in _EXTRACTORS:
        if ex.can_handle(path):
            return ex
    # extension unknown/mislabeled -> use magic bytes
    kind = sniff(path)
    mapping = {"pdf": PdfExtractor, "zip": XlsxExtractor, "ole": XlsExtractor}
    cls = mapping.get(kind or "")
    return cls() if cls else None
