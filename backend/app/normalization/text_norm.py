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


# Search-only abbreviation lexicon. Extends _ABBREV with high-value lab/imaging
# pairs the registry uses as *canonical* names (so the full form finds the
# abbreviated canonical and vice-versa). Kept separate from _ABBREV so the tuned
# normalization pipeline is untouched.
SEARCH_ABBREV = {
    **_ABBREV,
    "оак": "общий анализ крови",
    "оам": "общий анализ мочи",
    "соэ": "скорость оседания эритроцитов",
    "пцр": "полимеразная цепная реакция",
    "ифа": "иммуноферментный анализ",
    "ихл": "иммунохемилюминесцентный анализ",
    "ттг": "тиреотропный гормон",
    "пса": "простатический специфический антиген",
    "рг": "рентгенография",
    "флг": "флюорография",
    "эгдс": "эзофагогастродуоденоскопия",
    "огк": "органов грудной клетки",
    "алт": "аланинаминотрансфераза",
    "аст": "аспартатаминотрансфераза",
    "хгч": "хорионический гонадотропин",
}


def expand_search_terms(q: str, limit: int = 6) -> list[str]:
    """Equivalent query forms via the abbreviation lexicon, in BOTH directions.

    Forward: "оак" -> "общий анализ крови". Reverse: "общий анализ крови" -> "оак"
    (the key direction — many canonicals are stored as abbreviations). The original
    query is always first. Used only by full-text search, NOT by normalize()."""
    q = (q or "").strip()
    if not q:
        return []
    ql = q.lower()
    forms = [q]
    seen = {ql}

    def _add(form: str) -> None:
        if form and form not in seen:
            seen.add(form)
            forms.append(form)

    for abbr, full in SEARCH_ABBREV.items():
        if len(forms) >= limit:
            break
        # forward: whole-token abbreviation -> full phrase
        if re.search(rf"(?<!\w){re.escape(abbr)}(?!\w)", ql):
            _add(re.sub(rf"(?<!\w){re.escape(abbr)}(?!\w)", full, ql))
        # reverse: full phrase present -> abbreviation
        if full in ql:
            _add(ql.replace(full, abbr))
    return forms
