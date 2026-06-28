"""In-process registry of background processing jobs.

Decouples document processing from the HTTP stream: `start_processing()` runs the
pipeline in a daemon thread that keeps going even if the browser disconnects, so a
page reload does not lose progress. The stream endpoint just *tails* a job (replay
past events, then live) and reconnecting re-attaches to the same job. Jobs are kept
after finishing so a late reconnect can still replay the final state.

Cancellation: each job carries a threading.Event; the pipeline checks it between
pages/items and raises CancelledError, which rolls back the worker's session.
"""
from __future__ import annotations

import threading
import uuid


class CancelledError(Exception):
    """Raised inside the pipeline when a job's cancel flag is set."""


class Job:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.events: list[dict] = []
        self.done = False
        self.cancel = threading.Event()
        self.cond = threading.Condition()

    def emit(self, ev: dict) -> None:
        with self.cond:
            self.events.append(ev)
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.done = True
            self.cond.notify_all()


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def get_job(doc_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(doc_id)


def start_processing(doc_id: str) -> Job:
    """Idempotently start (or re-attach to) processing for a document.

    If a job already exists (running or finished) it is returned as-is — never
    re-processed. Otherwise a fresh job + daemon worker is launched."""
    with _LOCK:
        existing = _JOBS.get(doc_id)
        if existing is not None:
            return existing
        job = Job(doc_id)
        _JOBS[doc_id] = job
    threading.Thread(target=_run, args=(doc_id, job), daemon=True).start()
    return job


def _run(doc_id: str, job: Job) -> None:
    from app.db.session import session_scope
    from app.models import PriceDocument
    from app.services.processing import process_document

    try:
        with session_scope() as db:
            doc = db.get(PriceDocument, uuid.UUID(doc_id))
            if doc is None:
                job.emit({"stage": "error", "message": "document not found"})
                return
            process_document(db, doc, progress=job.emit, should_cancel=job.cancel.is_set)
    except CancelledError:
        job.emit({"stage": "canceled"})
    except Exception as exc:  # noqa: BLE001 — surface to the client
        job.emit({"stage": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        job.finish()
