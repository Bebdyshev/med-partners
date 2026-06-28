"""LLM name normalization — clean a raw price-list name to a canonical service phrase
BEFORE embedding, to lift retrieval recall on messy/abbreviated names.

The bi-encoder only surfaces the true dictionary service in its top-k ~65% of the time
for messy names; a cleaned query ("Узи орг.бр.пол+почки" -> "УЗИ органов брюшной
полости и почек") embeds much closer to the dictionary phrasing. Clinically important
modifiers are preserved (первичный/повторный, IgG/IgM, с контрастом, сторона, орган).

Batched + threaded + disk-cached (storage/derived/llm_norm_cache.json) so each distinct
name is cleaned once ever. Gated by an OpenAI key; failures fall back to the raw name.
"""
from __future__ import annotations

import functools
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

_BATCH = 20

_SYS = (
    "Ты приводишь строки из медицинского прайс-листа к чистому каноничному названию услуги. "
    "Для каждой строки: убери коды, биоматериал, единицы, артефакты OCR; расшифруй сокращения "
    "(ОАК→общий анализ крови, ОАМ→общий анализ мочи, УЗИ, КТ, МРТ, ЭКГ и т.п.). "
    "СОХРАНИ клинически важные различия: первичный/повторный, IgG/IgM, с контрастом/без контраста, "
    "левый/правый, конкретный орган/сустав. Не выдумывай услуги, которых нет в строке. "
    'Верни строго JSON: {"items":[{"i":<номер строки>,"name":"<чистое название>"}, ...]} для ВСЕХ строк.'
)


def available() -> bool:
    if not settings.use_llm_normalize:
        return False
    try:
        import openai  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    if settings.llm_provider == "ollama":
        return True  # Ollama needs no API key
    return bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))


@functools.lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    if settings.llm_provider == "ollama":
        return OpenAI(base_url=settings.ollama_base_url, api_key="ollama", timeout=30.0, max_retries=1)
    key = settings.openai_api_key
    return OpenAI(api_key=key, timeout=30.0, max_retries=1) if key else OpenAI(timeout=30.0, max_retries=1)


def _clean_batch(batch: list[str]) -> dict[str, str]:
    """Map each raw name in the batch to its cleaned form; fall back to raw on failure."""
    user = "Строки:\n" + "\n".join(f"{i}. {raw}" for i, raw in enumerate(batch))
    delay = 1.0
    for _ in range(5):
        try:
            resp = _client().chat.completions.create(
                model=settings.active_llm_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": _SYS}, {"role": "user", "content": user}],
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            out: dict[str, str] = {}
            for it in data.get("items", []):
                try:
                    idx = int(it["i"])
                except (KeyError, ValueError, TypeError):
                    continue
                if 0 <= idx < len(batch):
                    name = str(it.get("name") or "").strip()
                    out[batch[idx]] = name or batch[idx]
            return {n: out.get(n, n) for n in batch}  # ensure every name has a value
        except Exception:  # noqa: BLE001 — rate limits / transient
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
    return {n: n for n in batch}  # give up -> raw names


def clean_names(names: list[str]) -> list[str]:
    """Return an LLM-cleaned canonical name per input name (order preserved). Disk-cached."""
    settings.derived_dir.mkdir(parents=True, exist_ok=True)
    cache_path = settings.derived_dir / "llm_norm_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cache = {}

    missing = [n for n in dict.fromkeys(names) if n and n not in cache]
    if missing:
        batches = [missing[i : i + _BATCH] for i in range(0, len(missing), _BATCH)]
        workers = max(1, min(settings.llm_max_workers, len(batches)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for part in ex.map(_clean_batch, batches):
                cache.update(part)
        try:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    return [cache.get(n, n) for n in names]
