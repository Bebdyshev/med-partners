from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Partner, PriceDocument
from app.services.ingestion import _sha256, parse_filename, register_file

router = APIRouter()


def _pdf_page_count(p: Path) -> int:
    """Page count of an uploaded PDF (0 if not a PDF / unreadable) — used to cap a
    trimmed file's replay to the pages the user actually uploaded."""
    if p.suffix.lower() != ".pdf":
        return 0
    try:
        import fitz

        d = fitz.open(str(p))
        try:
            return d.page_count
        finally:
            d.close()
    except Exception:  # noqa: BLE001
        return 0


def _find_existing(db: Session, f: Path) -> str | None:
    """Find an already-processed document to replay for this upload — by exact hash,
    then (demo fallback, e.g. out of API credits or a trimmed file) by the same clinic
    parsed from the filename. Returns the doc id or None."""
    dupes = db.execute(
        select(PriceDocument)
        .where(PriceDocument.file_hash == _sha256(f))
        .order_by(PriceDocument.created_at.desc())
    ).scalars().all()
    if dupes:
        return str(next((d for d in dupes if d.parsed_at is not None), dupes[0]).id)
    code, _ = parse_filename(f.name)
    partner = db.execute(select(Partner).where(Partner.code == code)).scalar_one_or_none()
    if partner is not None:
        procs = db.execute(
            select(PriceDocument)
            .where(PriceDocument.partner_id == partner.id, PriceDocument.parsed_at.isnot(None))
            .order_by(PriceDocument.created_at.desc())
        ).scalars().all()
        if procs:
            want = f.suffix.lower().lstrip(".")
            # prefer a processed doc of the same format (so a PDF upload replays a PDF,
            # keeping the page scanner), else the most recent processed doc
            same = next((d for d in procs if (d.file_format.value if hasattr(d.file_format, "value")
                                              else str(d.file_format)).lower() == want), None)
            return str((same or procs[0]).id)
    return None


@router.post("/upload", summary="Загрузка прайс-листа (ZIP/файл)",
             description="Принимает ZIP-архив или одиночный файл (PDF/скан/DOCX/XLSX/XLS); "
                         "дедуп по хэшу, постановка в обработку. Возвращает created/existing/replay_pages.")
async def upload(
    file: UploadFile = File(..., description="A ZIP archive or a single price-list file"),
    process: bool = Query(True, description="enqueue processing immediately"),
    asynchronous: bool = Query(True, description="use Celery (true) or process inline (false)"),
    dedupe: bool = Query(True, description="skip files whose hash is already in the DB"),
    db: Session = Depends(get_db),
):
    # save the uploaded payload to a temp file
    suffix = Path(file.filename).suffix
    tmp = Path(tempfile.mkdtemp(prefix="upload_")) / (file.filename or f"upload{suffix}")
    with open(tmp, "wb") as fh:
        fh.write(await file.read())

    # ZIP -> expand; else single file
    from app.services.ingestion import _iter_files

    created: list[str] = []
    existing: list[str] = []
    replay_pages: dict[str, int] = {}  # doc_id -> uploaded page count (cap for trimmed files)
    skipped = 0
    for f in _iter_files(tmp):
        # Prefer replaying an already-processed document (by hash, else same clinic) —
        # the demo reuses stored data and never needs OpenAI credits.
        ex = _find_existing(db, f) if dedupe else None
        if ex is not None:
            existing.append(ex)
            n = _pdf_page_count(f)
            if n:
                replay_pages[ex] = n
            skipped += 1
            continue
        doc = register_file(db, f, allow_duplicate=not dedupe)
        if doc is None:
            skipped += 1
            continue
        created.append(str(doc.id))
    db.commit()

    if process and created:
        if asynchronous:
            from app.tasks.process_document import process_document_task

            for did in created:
                process_document_task.delay(did)
        else:
            from app.services.processing import process_document

            for did in created:
                doc = db.get(PriceDocument, uuid.UUID(did))
                process_document(db, doc)
            db.commit()

    return {"created": created, "existing": existing, "replay_pages": replay_pages,
            "skipped_duplicates": skipped, "queued": process}
