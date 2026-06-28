"""DOCX extractor.

Reads tables directly from the document XML so tracked changes are handled:
text inside <w:ins> is accepted, text inside <w:del> is dropped (work with the
final/accepted version). python-docx ignores revisions, so we parse XML.
Also harvests the org name from the first paragraphs for partner enrichment.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from app.extractors.base import BaseExtractor, ExtractResult
from app.extractors.common.table_to_rows import table_to_rows

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _cell_text(tc: ET.Element) -> str:
    """Concatenate text of a table cell, accepting insertions and dropping deletions."""
    parts: list[str] = []
    for node in tc.iter():
        tag = node.tag
        if tag == W + "t":
            # skip if inside a <w:del> (deleted text uses <w:delText>, but guard anyway)
            parts.append(node.text or "")
        elif tag == W + "delText":
            continue  # dropped tracked deletion
    return "".join(parts).strip()


def _iter_tables(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    body = root.find(W + "body")
    if body is None:
        return
    for tbl in body.iter(W + "tbl"):
        table: list[list] = []
        for tr in tbl.findall(W + "tr"):
            row = [_cell_text(tc) or None for tc in tr.findall(W + "tc")]
            table.append(row)
        yield table


def _harvest_org_name(xml_bytes: bytes) -> str | None:
    root = ET.fromstring(xml_bytes)
    for p in root.iter(W + "p"):
        text = "".join(t.text or "" for t in p.iter(W + "t")).strip()
        if len(text) > 8 and any(k in text for k in ("ТОО", "АО", "Фонд", "клиник", "Клиник", "центр")):
            return text[:512]
    return None


class DocxExtractor(BaseExtractor):
    supported_extensions = {"docx"}

    def extract(self, path: Path, progress=None, should_cancel=None) -> ExtractResult:
        result = ExtractResult()
        with zipfile.ZipFile(path) as z:
            xml_bytes = z.read("word/document.xml")
        org = _harvest_org_name(xml_bytes)
        if org:
            result.meta["org_name"] = org
        n_tables = 0
        for ti, table in enumerate(_iter_tables(xml_bytes)):
            n_tables += 1
            rows, warns = table_to_rows(table, method="docx", source_prefix=f"table={ti};")
            for row in rows:
                result.add_row(row)
            result.warnings.extend(warns)
        result.meta["tables"] = n_tables
        if not result.rows:
            result.warnings.append("docx: no rows extracted from tables")
        return result
