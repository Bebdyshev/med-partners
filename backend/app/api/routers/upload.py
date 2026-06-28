from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PriceDocument
from app.services.ingestion import _sha256, register_file

router = APIRouter()


@router.post("/upload")
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
    skipped = 0
    for f in _iter_files(tmp):
        doc = register_file(db, f, allow_duplicate=not dedupe)
        if doc is None:
            skipped += 1
            # surface the already-stored document so the client can show its data —
            # prefer a fully-processed copy (parsed_at set) over an interrupted/queued one
            dupes = db.execute(
                select(PriceDocument)
                .where(PriceDocument.file_hash == _sha256(f))
                .order_by(PriceDocument.created_at.desc())
            ).scalars().all()
            if dupes:
                best = next((d for d in dupes if d.parsed_at is not None), dupes[0])
                existing.append(str(best.id))
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

    return {"created": created, "existing": existing, "skipped_duplicates": skipped, "queued": process}
