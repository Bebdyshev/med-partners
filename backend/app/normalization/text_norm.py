"""Normalize service-name text before matching.

Lowercase, strip punctuation/extra whitespace, expand a few common medical
abbreviations so "консультация врача кмн" and "консультация к.м.н." converge.
"""
from __future__ import annotations

import re

_ABBREV = {
    "к.м.н": "кандидат медицинских наук",
    "д.м.н": "доктор медицинских наук",
    "кмн": "кандидат медицинских наук",
    "дмн": "доктор медицинских наук",
    "узи": "ультразвуковое исследование",
    "уздг": "ультразвуковая допплерография",
    "узди": "ультразвуковое дуплексное исследование",
    "экг": "электрокардиография",
    "ээг": "электроэнцефалография",
    "эхокг": "эхокардиография",
    "эхо-кг": "эхокардиография",
    "фгдс": "фиброгастродуоденоскопия",
    "ктг": "кардиотокография",
    "кт": "компьютерная томография",
    "мрт": "магнитно-резонансная томография",
    "оак": "общий анализ крови",
    "оам": "общий анализ мочи",
    "бх": "биохимический",
    "рв": "реакция вассермана",
    "спб": "специфические",
}

# clinical synonyms: dictionary uses "приём", clinics write "консультация/осмотр".
# Collapsing these is precision-safe and lifts true matches for the commonest case.
_SYNONYMS = {
    "консультация": "прием",
    "консультативный": "прием",
    "консультирование": "прием",
    "осмотр": "прием",
    "консультация-осмотр": "прием",
    "взятие": "забор",
    "анализ": "исследование",
    "определение": "исследование",
}
# noise tokens that don't change the service identity
_STOPWORDS = {
    "врача", "врач", "первичный", "первичная", "повторный", "повторная", "услуга",
    "1", "шт", "ед", "сеанс", "посещение",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    # expand abbreviations (whole-token, before punctuation removal of dots)
    for abbr, full in _ABBREV.items():
        t = re.sub(rf"(?<!\w){re.escape(abbr)}(?!\w)", full, t)
    t = _PUNCT_RE.sub(" ", t)
    tokens = [_SYNONYMS.get(w, w) for w in t.split()]
    tokens = [w for w in tokens if w not in _STOPWORDS]
    return " ".join(tokens).strip()
