"""Ingestion: take a ZIP / directory / single file into the system.

Saves each raw file immutably, parses partner code + year from the filename,
upserts the Partner, creates a PriceDocument (skipping exact-hash duplicates),
and either processes synchronously or enqueues a Celery task.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db.session import session_scope
from app.models import Partner, PriceDocument
from app.models.enums import ParseStatus
from app.extractors.registry import detect_format

_CODE_RE = re.compile(r"(клиника\s*\d+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"((?:19|20)\d{2})")


def parse_filename(name: str) -> tuple[str, int | None]:
    stem = Path(name).stem
    m = _CODE_RE.search(stem)
    code = re.sub(r"\s+", " ", m.group(1)).strip().title() if m else stem.strip()
    y = _YEAR_RE.search(stem)
    year = int(y.group(1)) if y else None
    return code, year


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(path: Path):
    if path.is_dir():
        for f in sorted(path.iterdir()):
            if f.is_file() and not f.name.startswith("~$"):
                yield f
    elif path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="medzip_"))
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        for f in sorted(tmp.rglob("*")):
            if f.is_file() and not f.name.startswith("~$"):
                yield f
    else:
        yield path


def register_file(db, src: Path, allow_duplicate: bool = False) -> PriceDocument | None:
    """Save raw file + create PriceDocument. Returns None if duplicate hash
    (unless `allow_duplicate`, used by the demo so it can always re-run a fresh doc)."""
    settings.ensure_dirs()
    file_hash = _sha256(src)
    if not allow_duplicate and db.execute(
        select(PriceDocument).where(PriceDocument.file_hash == file_hash)
    ).first():
        return None

    code, year = parse_filename(src.name)
    partner = db.execute(select(Partner).where(Partner.code == code)).scalar_one_or_none()
    if partner is None:
        partner = Partner(code=code, display_name=code)
        db.add(partner)
        db.flush()

    dest_dir = settings.raw_files_dir / str(uuid.uuid4())
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)

    doc = PriceDocument(
        partner_id=partner.id,
        source_filename=src.name,
        stored_path=str(dest),
        file_format=detect_format(src),
        file_hash=file_hash,
        year=year,
        effective_date=datetime(year, 1, 1) if year else None,
        status=ParseStatus.queued,
    )
    db.add(doc)
    db.flush()
    return doc


def ingest_path(path: Path, *, asynchronous: bool = False) -> list[str]:
    """Register every file under path. Returns the list of created document ids.
    If asynchronous, enqueue Celery tasks; else process synchronously now."""
    from app.services.processing import process_document

    doc_ids: list[str] = []
    with session_scope() as db:
        for f in _iter_files(path):
            doc = register_file(db, f)
            if doc is None:
                print(f"  skip duplicate: {f.name}")
                continue
            doc_ids.append(str(doc.id))
            print(f"  registered: {f.name} -> {doc.id}")

    if asynchronous:
        from app.tasks.process_document import process_document_task

        for did in doc_ids:
            process_document_task.delay(did)
    else:
        for did in doc_ids:
            try:
                with session_scope() as db:
                    doc = db.get(PriceDocument, uuid.UUID(did))
                    summary = process_document(db, doc)
                    print(f"  processed {doc.source_filename}: {summary}")
            except Exception as exc:  # noqa: BLE001 -- one bad doc must not abort the batch
                print(f"  ERROR processing {did}: {type(exc).__name__}: {exc}")
                with session_scope() as db:
                    doc = db.get(PriceDocument, uuid.UUID(did))
                    if doc is not None:
                        doc.status = ParseStatus.error
                        doc.parse_log = f"{type(exc).__name__}: {exc}"
    return doc_ids
