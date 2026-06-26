"""Celery task wrapping the document processing pipeline."""
from __future__ import annotations

import uuid

from app.db.session import session_scope
from app.models import PriceDocument
from app.models.enums import ParseStatus
from app.services.processing import process_document
from app.tasks.celery_app import celery


@celery.task(name="process_document", bind=True)
def process_document_task(self, doc_id: str) -> dict:
    with session_scope() as db:
        doc = db.get(PriceDocument, uuid.UUID(doc_id))
        if doc is None:
            return {"status": "missing", "doc_id": doc_id}
        try:
            return process_document(db, doc)
        except Exception as exc:  # noqa: BLE001
            doc.status = ParseStatus.error
            doc.parse_log = f"task error: {type(exc).__name__}: {exc}"
            raise
