"""Celery application."""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery = Celery(
    "medarchive",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.process_document"],
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # time budgets per spec: 60s text / 180s OCR; give OCR docs the larger limit
    task_soft_time_limit=180,
    task_time_limit=240,
    worker_max_tasks_per_child=20,
)
