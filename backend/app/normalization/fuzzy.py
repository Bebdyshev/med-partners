"""RapidFuzz candidate generation against canonical names + synonyms."""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from app.normalization.text_norm import normalize


@dataclass
class Entry:
    service_id: str
    canonical_name: str
    text: str          # the canonical or synonym text this entry indexes
    norm: str          # normalized form for matching
    category: str | None = None


def build_entries(services: list[tuple]) -> list[Entry]:
    """services: list of (service_id, canonical_name, [synonyms], category?, icd?)."""
    entries: list[Entry] = []
    for rec in services:
        sid, canonical, synonyms = rec[0], rec[1], rec[2]
        category = rec[3] if len(rec) > 3 else None
        entries.append(Entry(str(sid), canonical, canonical, normalize(canonical), category))
        for syn in synonyms or []:
            entries.append(Entry(str(sid), canonical, syn, normalize(syn), category))
    return entries


def fuzzy_candidates(raw_name: str, entries: list[Entry], k: int = 5) -> list[tuple[Entry, float]]:
    """Return up to k (entry, score 0..1) ranked by token-set similarity."""
    q = normalize(raw_name)
    if not q or not entries:
        return []
    choices = [e.norm for e in entries]
    results = process.extract(q, choices, scorer=fuzz.token_set_ratio, limit=k * 3)
    # dedup by service_id keeping best
    best: dict[str, tuple[Entry, float]] = {}
    for _text, score, idx in results:
        e = entries[idx]
        s = score / 100.0
        if e.service_id not in best or s > best[e.service_id][1]:
            best[e.service_id] = (e, s)
    ranked = sorted(best.values(), key=lambda t: t[1], reverse=True)
    return ranked[:k]
