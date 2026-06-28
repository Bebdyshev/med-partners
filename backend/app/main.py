"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    settings.ensure_dirs()
    app = FastAPI(
        title="MedArchive API",
        version="0.1.0",
        description=(
            "Автоматическая обработка прайс-листов клиник: загрузка и извлечение "
            "(PDF/скан/DOCX/XLSX), нормализация к справочнику услуг (code-first → "
            "эмбеддинг → LLM-судья → fuzzy), валидация качества, версионирование "
            "цен (archive-on-change) и гибридный поиск.\n\n"
            "**Группы:** ingestion — загрузка и обработка документов; services — справочник "
            "услуг; partners — клиники; search — поиск; review — очередь верификации; "
            "dashboard — аналитика."
        ),
        openapi_tags=[
            {"name": "ingestion", "description": "Загрузка, обработка, статус и стрим документов."},
            {"name": "services", "description": "Справочник услуг, описания, кто оказывает услугу."},
            {"name": "partners", "description": "Партнёры-клиники и их прайсы."},
            {"name": "search", "description": "Гибридный поиск по услугам и партнёрам."},
            {"name": "review", "description": "Очередь верификации и ручное сопоставление."},
            {"name": "dashboard", "description": "Сводные метрики и аналитика."},
            {"name": "meta", "description": "Служебные эндпоинты."},
        ],
    )

    # Routers are imported lazily to keep optional/heavy deps out of import path
    from app.api.routers import (
        documents,
        partners,
        review,
        search,
        services,
        upload,
    )

    app.include_router(upload.router, tags=["ingestion"])
    app.include_router(documents.router, tags=["ingestion"])
    app.include_router(services.router, tags=["services"])
    app.include_router(partners.router, tags=["partners"])
    app.include_router(search.router, tags=["search"])
    app.include_router(review.router, tags=["review"])

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
