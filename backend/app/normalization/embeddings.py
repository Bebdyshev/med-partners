"""Semantic embeddings for normalization.

Default model: a multilingual E5 (strong Russian retrieval). E5 expects
asymmetric prefixes — dictionary entries are "passage: ", raw queries are
"query: " — applied automatically when the model name contains "e5".

The dictionary (passage) matrix is cached to disk keyed by (model, text hash), so
the model encodes the ~1.2k services once ever, not on every server start — this
removes the cold-start stall in the live demo. Lazy + optional: if the package is
missing or USE_EMBEDDINGS is false, the engine falls back to RapidFuzz only.
"""
from __future__ import annotations

import functools
import hashlib

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


def _is_e5() -> bool:
    return "e5" in settings.embedding_model.lower()


def _encode(texts: list[str]) -> np.ndarray:
    vecs = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
    return np.asarray(vecs, dtype=np.float32)


def encode_queries(texts: list[str]) -> np.ndarray:
    if _is_e5():
        texts = [f"query: {t}" for t in texts]
    return _encode(texts)


def encode_passages(texts: list[str]) -> np.ndarray:
    """Encode dictionary entries, cached to disk (stable set, encoded once)."""
    key = hashlib.sha1(
        (settings.embedding_model + "" + "".join(texts)).encode("utf-8")
    ).hexdigest()[:16]
    settings.derived_dir.mkdir(parents=True, exist_ok=True)
    path = settings.derived_dir / f"emb_{key}.npy"
    if path.exists():
        try:
            return np.load(path)
        except Exception:  # noqa: BLE001
            pass
    prefixed = [f"passage: {t}" for t in texts] if _is_e5() else texts
    mat = _encode(prefixed)
    try:
        np.save(path, mat)
    except Exception:  # noqa: BLE001
        pass
    return mat
