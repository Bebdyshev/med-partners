from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PriceDocument
from app.services.ingestion import register_file

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
    skipped = 0
    for f in _iter_files(tmp):
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

    return {"created": created, "skipped_duplicates": skipped, "queued": process}
