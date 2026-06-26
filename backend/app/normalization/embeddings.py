"""Optional semantic reranking via sentence-transformers.

Heavy (pulls in torch). Loaded lazily and only if settings.use_embeddings is
true AND the package is importable; otherwise the engine silently falls back to
RapidFuzz-only so normalization never hard-fails.
"""
from __future__ import annotations

import functools

import numpy as np

from app.config import settings


@functools.lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def available() -> bool:
    if not settings.use_embeddings:
        return False
    try:
        import sentence_transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def encode(texts: list[str]) -> np.ndarray:
    vecs = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def cosine_rerank(raw_name: str, candidate_texts: list[str]) -> list[float]:
    """Cosine similarity (clamped 0..1) of raw_name vs each candidate text."""
    if not candidate_texts:
        return []
    mat = encode([raw_name] + candidate_texts)
    q = mat[0]
    sims = mat[1:] @ q  # already L2-normalized -> cosine in [-1, 1]
    return [max(0.0, float(s)) for s in sims]
