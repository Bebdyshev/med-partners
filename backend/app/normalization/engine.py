"""Normalization engine: match a raw service name to a dictionary Service.

Strategy:
  * Without embeddings: RapidFuzz candidate generation only.
  * With embeddings: full semantic retrieval — all dictionary entries are encoded
    once; each query is matched by cosine against the whole dictionary (cheap at
    ~1.2k services), so purely-semantic matches (different words, same meaning)
    are found even when fuzzy overlap is low. The final score blends fuzzy and
    cosine (max), so either signal can confirm a match.

Decision is threshold-driven (config): >= auto -> auto-match, >= floor -> review
queue with ranked suggestions, else unmatched.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from app.config import settings
from app.models.enums import MatchMethod, MatchStatus
from app.normalization import embeddings
from app.normalization.fuzzy import Entry, build_entries, fuzzy_candidates
from app.normalization.text_norm import normalize


@dataclass
class Suggestion:
    service_id: str
    canonical_name: str
    score: float
    method: MatchMethod


@dataclass
class MatchResult:
    status: MatchStatus
    score: float | None
    method: MatchMethod
    service_id: str | None
    suggestions: list[Suggestion]


class Matcher:
    """In-memory matcher built from the current dictionary snapshot."""

    def __init__(self, services: list[tuple]):
        # services: list of (service_id, canonical_name, [synonyms])
        self.entries: list[Entry] = build_entries(services)
        self._use_embeddings = embeddings.available()
        self._emb = None
        if self._use_embeddings and self.entries:
            try:
                self._emb = embeddings.encode([e.norm or e.text for e in self.entries])
            except Exception:  # noqa: BLE001
                self._use_embeddings = False
                self._emb = None

    # ---- single ----
    def suggest(self, raw_name: str, k: int = 5) -> list[Suggestion]:
        return self.suggest_many([raw_name], k=k)[0]

    def match(self, raw_name: str) -> MatchResult:
        return self._decide(self.suggest(raw_name))

    # ---- batch (used by renormalize over many items) ----
    def suggest_many(self, raw_names: list[str], k: int = 5) -> list[list[Suggestion]]:
        if not self.entries:
            return [[] for _ in raw_names]
        if self._use_embeddings and self._emb is not None:
            return self._suggest_semantic(raw_names, k)
        return [self._suggest_fuzzy(rn, k) for rn in raw_names]

    def match_many(self, raw_names: list[str]) -> list[MatchResult]:
        return [self._decide(s) for s in self.suggest_many(raw_names)]

    # ---- implementations ----
    def _suggest_fuzzy(self, raw_name: str, k: int) -> list[Suggestion]:
        cands = fuzzy_candidates(raw_name, self.entries, k=k)
        return [Suggestion(e.service_id, e.canonical_name, s, MatchMethod.fuzzy) for e, s in cands]

    def _suggest_semantic(self, raw_names: list[str], k: int) -> list[list[Suggestion]]:
        import numpy as np

        queries = [normalize(r) for r in raw_names]
        qmat = embeddings.encode(queries)  # (n, d), L2-normalized
        sims = qmat @ self._emb.T          # (n, n_entries) cosine
        out: list[list[Suggestion]] = []
        for qi, raw_name in enumerate(raw_names):
            row = sims[qi]
            top_idx = np.argsort(-row)[: k * 4]
            best: dict[str, Suggestion] = {}
            for idx in top_idx:
                e = self.entries[idx]
                cos = max(0.0, float(row[idx]))
                fz = fuzz.token_set_ratio(queries[qi], e.norm) / 100.0
                score = max(cos, fz)
                method = MatchMethod.embedding if cos >= fz else MatchMethod.fuzzy
                if e.service_id not in best or score > best[e.service_id].score:
                    best[e.service_id] = Suggestion(e.service_id, e.canonical_name, score, method)
            out.append(sorted(best.values(), key=lambda s: s.score, reverse=True)[:k])
        return out

    def _decide(self, sugg: list[Suggestion]) -> MatchResult:
        if not sugg:
            return MatchResult(MatchStatus.unmatched, None, MatchMethod.fuzzy, None, [])
        best = sugg[0]
        if best.score >= settings.match_auto_threshold:
            return MatchResult(MatchStatus.auto, best.score, best.method, best.service_id, sugg)
        if best.score >= settings.match_review_floor:
            return MatchResult(MatchStatus.review, best.score, best.method, None, sugg)
        return MatchResult(MatchStatus.unmatched, best.score, best.method, None, sugg)
