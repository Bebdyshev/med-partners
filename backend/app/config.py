"""Central configuration via pydantic-settings (env / .env driven)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database / queue
    database_url: str = "postgresql+psycopg2://medarchive:medarchive@localhost:5432/medarchive"
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_dir: Path = Path("./storage")

    # Normalization
    match_auto_threshold: float = 0.85
    match_review_floor: float = 0.60
    use_embeddings: bool = True
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Validation
    price_change_anomaly_pct: float = 50.0

    # OCR / PDF
    ocr_lang: str = "rus+kaz+eng"
    ocr_dpi: int = 300
    pdf_text_min_chars_per_page: int = 200

    @property
    def raw_files_dir(self) -> Path:
        return self.storage_dir / "raw_files"

    @property
    def derived_dir(self) -> Path:
        return self.storage_dir / "derived"

    def ensure_dirs(self) -> None:
        self.raw_files_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
