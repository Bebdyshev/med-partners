from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PriceDocument
from app.schemas.dto import DocumentOut
from app.services.report import compute_document_breakdown, compute_report

router = APIRouter()

_MEDIA = {
    "pdf": "application/pdf",
    "scan_pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    status: str | None = Query(None),
    limit: int = Query(200, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(PriceDocument)
    if status:
        stmt = stmt.where(PriceDocument.status == status)
    stmt = stmt.order_by(PriceDocument.created_at.desc()).limit(limit).offset(offset)
    docs = db.execute(stmt).scalars().all()
    return [_to_out(d) for d in docs]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(PriceDocument, doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return _to_out(doc)


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Serve the immutable original upload — opens inline (PDF) or downloads (Excel/Word)."""
    doc = db.get(PriceDocument, doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    path = Path(doc.stored_path)
    if not path.is_file():
        raise HTTPException(404, "stored file missing")
    fmt = doc.file_format.value if hasattr(doc.file_format, "value") else str(doc.file_format)
    media = _MEDIA.get(fmt) or mimetypes.guess_type(doc.source_filename)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media,
        filename=doc.source_filename,
        content_disposition_type="inline",
    )


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    return compute_report()


@router.get("/dashboard/documents")
def dashboard_documents():
    """Per-document composition + provenance + category mix for the dashboard ledger."""
    return compute_document_breakdown()


def _to_out(d: PriceDocument) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        partner_id=d.partner_id,
        source_filename=d.source_filename,
        file_format=d.file_format.value,
        status=d.status.value,
        year=d.year,
        parsed_at=d.parsed_at,
        method_summary=d.method_summary or {},
        warnings=d.warnings or [],
    )
