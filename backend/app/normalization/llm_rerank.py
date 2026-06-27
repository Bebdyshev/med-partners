"""LLM reranker — an OpenAI chat model judges the embedding shortlist.

The bi-encoder retrieves k plausible dictionary services; the LLM then reads the
raw price-list line together with those candidates and decides which one (if any)
denotes the *same* service, with a calibrated confidence. This is the precision
stage — it replaces the local cross-encoder, so the server needs no torch.

Offline/online both: gated by USE_LLM_RERANK + an OpenAI key. Absent => no-op,
the engine keeps the bi-encoder scores. Failures degrade to "no verdict" per item.
"""
from __future__ import annotations

import functools
import json
import os
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

_SYS = (
    "Ты — медицинский эксперт, который сопоставляет строку из прайс-листа клиники "
    "с эталонным справочником медицинских услуг. Учитывай сокращения, опечатки, "
    "OCR-ошибки, русский и казахский язык, синонимы. Выбери кандидата, который "
    "обозначает ТУ ЖЕ САМУЮ услугу (не просто ту же категорию). Если ни один "
    "кандидат не соответствует — верни choice = 0. "
    'Ответь строго JSON: {"choice": <номер кандидата 1..N или 0>, '
    '"confidence": <число 0..1, насколько ты уверен>}.'
)


def available() -> bool:
    if not settings.use_llm_rerank:
        return False
    try:
        import openai  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))


@functools.lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else OpenAI()


def _judge_one(raw_name: str, category: str | None, candidates: list[str]) -> tuple[int, float]:
    cand_lines = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(candidates))
    user = (
        f"Строка из прайса: «{raw_name}»\n"
        f"Категория: {category or '—'}\n\n"
        f"Кандидаты из справочника:\n{cand_lines}"
    )
    resp = _client().chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _SYS}, {"role": "user", "content": user}],
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    idx = int(data.get("choice", 0) or 0)
    conf = float(data.get("confidence", 0) or 0.0)
    return idx, max(0.0, min(1.0, conf))


def judge_batch(items: list[tuple[str, str | None, list[str]]]) -> list[tuple[int, float]]:
    """items: (raw_name, category, candidate_names). Returns (chosen_idx_1based|0, confidence)."""
    if not items:
        return []

    def work(it):
        try:
            return _judge_one(it[0], it[1], it[2])
        except Exception:  # noqa: BLE001 — never let one bad call sink the batch
            return (0, 0.0)

    workers = max(1, min(settings.llm_max_workers, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(work, items))
