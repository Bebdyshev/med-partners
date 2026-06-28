"""Vision-LLM structured extraction for scanned price-list pages.

Scanned/lab PDFs are legible to the eye but their TABLE STRUCTURE is lost by the
text-layer parser: service name + tariff code + biomaterial get merged into one
field and codes never reach ``raw_code``. Here an OpenAI vision model reads a
rasterized page image and returns clean STRUCTURED rows (name / code /
biomaterial / resident & non-resident prices), which we map to ``RawRow``.

Gated by ``use_vision_ocr`` + an OpenAI key (mirrors ``llm_rerank.available()``).
A bad page never raises — issues are swallowed and whatever parsed is returned.
"""
from __future__ import annotations

import base64
import functools
import json
import os
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.config import settings
from app.extractors.base import RawPrice, RawRow

_SYS = (
    "Ты извлекаешь строки из отсканированного медицинского прайс-листа клиники "
    "или лаборатории. На изображении одна страница таблицы. Верни КАЖДУЮ строку "
    "услуги отдельным объектом. РАЗДЕЛЯЙ поля: название услуги (name) НЕ должно "
    "содержать код тарифа или биоматериал; код тарифа (code, например B06.457.006 "
    "или внутренний код клиники) — отдельно; биоматериал (biomaterial, например "
    "'сыворотка крови', 'моча') — отдельно; цены — числами без пробелов и валюты. "
    "Если в таблице две цены — для резидентов/граждан РК и для нерезидентов — "
    "верни price_resident и price_nonresident; если цена одна, заполни "
    "price_resident, а price_nonresident оставь null. Любое отсутствующее поле = "
    "null. Не выдумывай данные. "
    'Ответь строго JSON-объектом вида {"rows": [{"name": str, "code": str|null, '
    '"biomaterial": str|null, "price_resident": number|null, '
    '"price_nonresident": number|null}, ...]}.'
)

_MAX_RETRIES = 4
_BASE_DELAY = 1.0


def available() -> bool:
    if not settings.use_vision_ocr:
        return False
    try:
        import openai  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    if settings.llm_provider == "ollama":
        return True  # Ollama needs no API key (Qwen2.5-VL or InternVL2)
    return bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))


@functools.lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    if settings.llm_provider == "ollama":
        return OpenAI(base_url=settings.ollama_base_url, api_key="ollama")
    return OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else OpenAI()


def _render_png(pdf_path: Path, page_index: int, dpi: int = 200) -> bytes:
    """Rasterize a single page to PNG bytes with PyMuPDF (~200 DPI)."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_index)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()


def _call_vision(png_b64: str) -> dict:
    """Call the vision model with retry/backoff; returns the parsed JSON object."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = _client().chat.completions.create(
                model=settings.active_vision_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYS},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Извлеки все строки услуг с этой страницы.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{png_b64}"
                                },
                            },
                        ],
                    },
                ],
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_DELAY * (2**attempt))
    raise last_exc if last_exc else RuntimeError("vision call failed")


def _clean(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _to_decimal(val) -> Decimal | None:
    """Parse a price into Decimal; tolerate strings with spaces/commas. None if unusable."""
    if val is None:
        return None
    if isinstance(val, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(val, (int, float)):
        try:
            d = Decimal(str(val))
        except InvalidOperation:
            return None
        return d if d > 0 else None
    s = str(val).strip()
    if not s:
        return None
    # keep digits, separators; drop currency text / spaces
    s = s.replace(" ", "").replace(" ", "")
    s = s.replace(",", ".")
    cleaned = "".join(ch for ch in s if ch.isdigit() or ch == ".")
    if not cleaned or not any(ch.isdigit() for ch in cleaned):
        return None
    # Disambiguate '.' by the trailing group: a final group of 1-2 digits is a
    # decimal fraction ("1234.56"); a longer trailing group means the dot is a
    # thousands separator ("12.500" -> 12500, "1.234.567" -> 1234567).
    last_dot = cleaned.rfind(".")
    if last_dot != -1:
        tail = cleaned[last_dot + 1 :]
        if tail.isdigit() and 1 <= len(tail) <= 2:
            int_part = cleaned[:last_dot].replace(".", "") or "0"
            cleaned = f"{int_part}.{tail}"
        else:
            cleaned = cleaned.replace(".", "")
    try:
        d = Decimal(cleaned)
    except InvalidOperation:
        return None
    return d if d > 0 else None


def _row_to_rawrow(row: dict, page_index: int) -> RawRow | None:
    """Map one JSON row -> RawRow. Returns None for rows that fail validation."""
    name = _clean(row.get("name"))
    if not name:
        return None

    prices: list[RawPrice] = []
    res = _to_decimal(row.get("price_resident"))
    if res is not None:
        prices.append(RawPrice("резидент", res))
    nonres = _to_decimal(row.get("price_nonresident"))
    if nonres is not None:
        prices.append(RawPrice("нерезидент", nonres))
    if not prices:
        return None

    return RawRow(
        raw_name=name,
        prices=prices,
        code=_clean(row.get("code")),
        category=_clean(row.get("biomaterial")),
        source_ref=f"page={page_index + 1};vision",
        extraction_method="pdf_ocr",
        confidence=0.85,
    )


def extract_page_rows(pdf_path: Path, page_index: int) -> list[RawRow]:
    """Extract structured rows from ONE scanned PDF page via the vision model.

    Never raises: a failed call or unparseable page yields an empty list so a bad
    page cannot crash the document.
    """
    try:
        png = _render_png(pdf_path, page_index)
        b64 = base64.b64encode(png).decode("ascii")
        data = _call_vision(b64)
    except Exception:  # noqa: BLE001 — bad page must not sink the document
        return []

    raw_rows = data.get("rows")
    if not isinstance(raw_rows, list):
        return []

    out: list[RawRow] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        rr = _row_to_rawrow(item, page_index)
        if rr is not None:
            out.append(rr)
    return out
