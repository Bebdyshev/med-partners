"""Semantic embeddings for normalization.

Two providers, selected by `settings.embedding_provider`:
  - "openai": the OpenAI Embeddings API (default model text-embedding-3-large).
    Vectors are L2-normalized so the engine's dot product == cosine, keeping the
    same score scale the thresholds expect.
  - "sentence_transformers": a local multilingual E5. E5 expects asymmetric
    prefixes — dictionary entries are "passage: ", raw queries are "query: ".

The dictionary (passage) matrix is cached to disk keyed by (model, text hash), so
the ~1.2k services are encoded once ever (no cold-start stall, no repeat API cost).
Lazy + optional: if the provider is unavailable or USE_EMBEDDINGS is false, the
engine falls back to RapidFuzz only.
"""
from __future__ import annotations

import functools
import hashlib

import numpy as np

from app.config import settings

_OPENAI_BATCH = 256  # inputs per API request


def _provider() -> str:
    return "openai" if settings.embedding_provider == "openai" else "sentence_transformers"


# ---------- OpenAI provider ----------
@functools.lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    # short timeout so a slow/credit-less API can't hang the pipeline
    key = settings.openai_api_key
    return OpenAI(api_key=key, timeout=8.0, max_retries=0) if key else OpenAI(timeout=8.0, max_retries=0)


def _embed_batch_with_retry(client, model: str, chunk: list[str], attempts: int = 2):
    import time

    from app.normalization import _breaker

    delay = 1.0
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return client.embeddings.create(model=model, input=chunk).data
        except Exception as exc:  # noqa: BLE001 — rate limits / transient API errors
            last = exc
            time.sleep(delay)
            delay = min(delay * 2, 4.0)
    _breaker.trip()  # API failing (no credits / down) → skip OpenAI for a while
    raise last  # type: ignore[misc]


def _encode_openai(texts: list[str]) -> np.ndarray:
    from concurrent.futures import ThreadPoolExecutor

    from app.normalization import _breaker
    if _breaker.is_open():
        raise RuntimeError("openai breaker open")  # skip fast → caller falls back to fuzzy
    client = _openai_client()
    model = settings.openai_embedding_model
    batches = [
        [t if t.strip() else " " for t in texts[i : i + _OPENAI_BATCH]]
        for i in range(0, len(texts), _OPENAI_BATCH)
    ]
    results: list = [None] * len(batches)

    def work(bi: int):
        return bi, _embed_batch_with_retry(client, model, batches[bi])

    workers = max(1, min(settings.llm_max_workers, len(batches)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for bi, data in ex.map(work, range(len(batches))):
            results[bi] = data

    out: list[list[float]] = []
    for data in results:
        out.extend(d.embedding for d in data)
    mat = np.asarray(out, dtype=np.float32)
    # L2-normalize so dot product is cosine (matches the engine + thresholds)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


# ---------- sentence-transformers provider ----------
@functools.lru_cache(maxsize=1)
def _st_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def _encode_st(texts: list[str]) -> np.ndarray:
    vecs = _st_model().encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
    return np.asarray(vecs, dtype=np.float32)


# ---------- public API ----------
def available() -> bool:
    if not settings.use_embeddings:
        return False
    if _provider() == "openai":
        from app.normalization import _breaker
        if _breaker.is_open():
            return False
        try:
            import openai  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return bool(settings.openai_api_key)
    try:
        import sentence_transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _is_e5() -> bool:
    return _provider() == "sentence_transformers" and "e5" in settings.embedding_model.lower()


def _encode(texts: list[str]) -> np.ndarray:
    return _encode_openai(texts) if _provider() == "openai" else _encode_st(texts)


def encode_queries(texts: list[str]) -> np.ndarray:
    if _is_e5():
        texts = [f"query: {t}" for t in texts]
    return _encode(texts)


def encode_passages(texts: list[str]) -> np.ndarray:
    """Encode dictionary entries, cached to disk (stable set, encoded once)."""
    key = hashlib.sha1(
        (settings.active_embedding_model + "" + "".join(texts)).encode("utf-8")
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
