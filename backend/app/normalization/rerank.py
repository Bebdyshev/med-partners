"""Cross-encoder reranking (precision booster).

Bi-encoder cosine (e5) ranks candidates well but its *absolute* scores compress
into a narrow high band for medical text, so a score threshold separates correct
from wrong poorly. A cross-encoder reads (query, candidate) together and gives a
far more discriminative relevance score — used to re-score the bi-encoder
shortlist so the auto/review threshold becomes meaningful.

Offline only (heavy on CPU); the live API reads stored matches. Gated by
USE_RERANKER; absent package/flag => no-op (engine keeps bi-encoder scores).
"""
from __future__ import annotations

import functools
import math

from app.config import settings


def available() -> bool:
    if not settings.use_reranker:
        return False
    try:
        import sentence_transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@functools.lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.reranker_model, max_length=256)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Relevance in 0..1 for each (query, candidate) pair."""
    if not pairs:
        return []
    raw = _model().predict(pairs, batch_size=64, show_progress_bar=False)
    return [_sigmoid(float(s)) for s in raw]
