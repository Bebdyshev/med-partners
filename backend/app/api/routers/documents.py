from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PriceDocument
from app.schemas.dto import DocumentOut
from app.services.report import compute_document_breakdown, compute_report

router = APIRouter()


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
