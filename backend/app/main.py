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
            "Automatic processing of clinic price lists: ingestion, extraction, "
            "normalization to a service dictionary, versioned storage and search."
        ),
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
