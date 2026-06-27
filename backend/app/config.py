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
    match_auto_threshold: float = 0.85       # bi-encoder (e5) score scale
    match_review_floor: float = 0.60
    rerank_auto_threshold: float = 0.65      # cross-encoder score scale (lower band)
    rerank_review_floor: float = 0.45
    use_embeddings: bool = True
    # provider: "openai" (API, text-embedding-3-*) or "sentence_transformers" (local e5)
    embedding_provider: str = "openai"
    embedding_model: str = "intfloat/multilingual-e5-base"   # used when provider = sentence_transformers
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-large"
    use_reranker: bool = False  # local cross-encoder (heavy); superseded by the LLM reranker below
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # LLM reranker — an OpenAI chat model judges the embedding shortlist (no local ML).
    use_llm_rerank: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_auto_threshold: float = 0.70   # LLM-confirmed match -> auto
    llm_review_floor: float = 0.65     # LLM rejected but candidate still plausible (cosine) -> review; else unmatched
    llm_rerank_band_lo: float = 0.40   # only judge items whose top embedding score >= this
    llm_max_workers: int = 12          # concurrency for batch judging

    # Vision OCR — an OpenAI vision model returns STRUCTURED rows for scanned pages,
    # preserving table structure (name / code / biomaterial / prices) that the text
    # layer loses. Gated by an OpenAI key (like the LLM reranker). No local ML.
    use_vision_ocr: bool = True
    vision_model: str = "gpt-4o"

    # LLM name normalization: clean each raw name to a canonical phrase before embedding
    # (lifts retrieval recall on messy/abbreviated names). Disk-cached. No local ML.
    use_llm_normalize: bool = True
    match_top_k: int = 20              # shortlist size handed to the LLM judge (recall vs cost)

    @property
    def active_embedding_model(self) -> str:
        """Name of the embedding model for the selected provider (also the cache key)."""
        if self.embedding_provider == "openai":
            return self.openai_embedding_model
        return self.embedding_model

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
