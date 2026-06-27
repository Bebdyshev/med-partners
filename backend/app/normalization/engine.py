"""Normalization engine: match a raw service line to a dictionary Service.

Order of signals (high precision first):
  1. CODE — raw_code vs the dictionary tariff code (exact, name-independent).
  2. NAME — RapidFuzz candidate gen, or (when embeddings are on) full semantic
     retrieval over the whole dictionary, blended max(fuzzy, cosine), with a
     same-specialty boost so the right category wins ties.

Decision is threshold-driven (config): >= auto -> auto, >= floor -> review with
ranked suggestions, else unmatched.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from app.config import settings
from app.models.enums import MatchMethod, MatchStatus
from app.normalization import embeddings, llm_rerank, rerank
from app.normalization.code_match import CodeIndex, find_code_in_text
from app.normalization.fuzzy import Entry, build_entries, fuzzy_candidates
from app.normalization.text_norm import normalize

CATEGORY_BOOST = 0.08  # added to score when raw category fuzzily matches the service specialty


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
    def __init__(self, services: list[tuple]):
        # services: list of (id, name, [synonyms], category?, icd_code?)
        self.entries: list[Entry] = build_entries(services)
        self.code_index = CodeIndex(
            (rec[4], rec[0], rec[1]) for rec in services if len(rec) > 4 and rec[4]
        )
        self._use_embeddings = embeddings.available()
        self._emb = None
        if self._use_embeddings and self.entries:
            try:
                self._emb = embeddings.encode_passages([e.norm or e.text for e in self.entries])
            except Exception:  # noqa: BLE001
                self._use_embeddings = False
                self._emb = None
        # LLM reranker takes precedence (no local ML); else fall back to the local
        # cross-encoder. Bind at build time so decision thresholds match the scale used.
        self._llm = llm_rerank.available()
        self._reranker = False
        if not self._llm and rerank.available():
            try:
                rerank._model()  # warm/verify load
                self._reranker = True
            except Exception:  # noqa: BLE001
                self._reranker = False

    # ---- code (tried first) ----
    def code_lookup(self, raw_code: str | None) -> Suggestion | None:
        hit = self.code_index.lookup(raw_code)
        if hit is None:
            return None
        sid, name = hit
        return Suggestion(sid, name, 1.0, MatchMethod.exact)

    # ---- single ----
    def suggest(self, raw_name: str, k: int = 5, category: str | None = None) -> list[Suggestion]:
        return self.suggest_many([raw_name], k=k, categories=[category])[0]

    def match(self, raw_name: str, raw_code: str | None = None, category: str | None = None) -> MatchResult:
        code = self.code_lookup(raw_code)
        if code is None:
            # Lab scans bury the tariff code (often Cyrillic homoglyphs) in the name.
            alt = find_code_in_text(raw_name)
            if alt:
                code = self.code_lookup(alt)
        if code is not None:
            return MatchResult(MatchStatus.auto, 1.0, MatchMethod.exact, code.service_id, [code])
        return self._decide(self.suggest(raw_name, category=category))

    # ---- batch ----
    def suggest_many(self, raw_names: list[str], k: int = 5, categories: list | None = None) -> list[list[Suggestion]]:
        if not self.entries:
            return [[] for _ in raw_names]
        cats = categories or [None] * len(raw_names)
        if self._use_embeddings and self._emb is not None:
            return self._suggest_semantic(raw_names, cats, k)
        return [self._suggest_fuzzy(rn, c, k) for rn, c in zip(raw_names, cats)]

    def match_many(self, raw_names: list[str], categories: list | None = None) -> list[MatchResult]:
        return [self._decide(s) for s in self.suggest_many(raw_names, categories=categories)]

    # ---- impl ----
    def _boost(self, score: float, raw_cat: str | None, entry_cat: str | None) -> float:
        if raw_cat and entry_cat:
            if fuzz.token_set_ratio(normalize(raw_cat), normalize(entry_cat)) >= 80:
                return min(1.0, score + CATEGORY_BOOST)
        return score

    def _suggest_fuzzy(self, raw_name: str, category: str | None, k: int) -> list[Suggestion]:
        cands = fuzzy_candidates(raw_name, self.entries, k=k)
        out = [
            Suggestion(e.service_id, e.canonical_name, self._boost(s, category, e.category), MatchMethod.fuzzy)
            for e, s in cands
        ]
        out.sort(key=lambda s: s.score, reverse=True)
        return out

    def _suggest_semantic(self, raw_names: list[str], categories: list, k: int) -> list[list[Suggestion]]:
        import numpy as np

        queries = [normalize(r) for r in raw_names]
        qmat = embeddings.encode_queries(queries)        # (n, d) L2-normalized
        sims = qmat @ self._emb.T                          # (n, n_entries) cosine
        out: list[list[Suggestion]] = []
        for qi in range(len(raw_names)):
            row = sims[qi]
            top_idx = np.argsort(-row)[: k * 4]
            best: dict[str, Suggestion] = {}
            for idx in top_idx:
                e = self.entries[idx]
                cos = max(0.0, float(row[idx]))
                fz = fuzz.token_set_ratio(queries[qi], e.norm) / 100.0
                score = self._boost(max(cos, fz), categories[qi], e.category)
                method = MatchMethod.embedding if cos >= fz else MatchMethod.fuzzy
                if e.service_id not in best or score > best[e.service_id].score:
                    best[e.service_id] = Suggestion(e.service_id, e.canonical_name, score, method)
            out.append(sorted(best.values(), key=lambda s: s.score, reverse=True)[:k])

        # LLM reranker (precision stage): judge the shortlist for items the bi-encoder
        # found at least plausible. The LLM's confidence becomes the new top score.
        if self._llm:
            band, locs = [], []
            for qi, lst in enumerate(out):
                if lst and lst[0].score >= settings.llm_rerank_band_lo:
                    band.append((raw_names[qi], categories[qi], [s.canonical_name for s in lst]))
                    locs.append(qi)
            if band:
                verdicts = llm_rerank.judge_batch(band)
                for qi, (idx, conf) in zip(locs, verdicts):
                    lst = out[qi]
                    if idx and 1 <= idx <= len(lst):
                        chosen = lst[idx - 1]
                        chosen.score = conf
                        chosen.method = MatchMethod.embedding  # LLM verdict over the embedding shortlist
                        for j, s in enumerate(lst):
                            if j != idx - 1:
                                s.score = min(s.score, conf * 0.5)
                        out[qi] = sorted(lst, key=lambda s: s.score, reverse=True)
                    else:
                        # LLM found no exact match: cap below auto so it can't auto-match,
                        # but keep the embedding ranking — a still-plausible top candidate
                        # (>= review floor) lands in the review queue with suggestions; the
                        # rest fall below the floor and become unmatched.
                        cap = settings.llm_auto_threshold - 0.01
                        for s in lst:
                            s.score = min(s.score, cap)
                        out[qi] = sorted(lst, key=lambda s: s.score, reverse=True)
            return out

        # optional cross-encoder rerank of the shortlist (offline; high precision)
        if self._reranker:
            pairs, idx = [], []
            for qi, lst in enumerate(out):
                for j, s in enumerate(lst):
                    pairs.append((raw_names[qi], s.canonical_name))
                    idx.append((qi, j))
            try:
                scores = rerank.score_pairs(pairs)
                for (qi, j), sc in zip(idx, scores):
                    out[qi][j].score = self._boost(sc, categories[qi], None)
                    out[qi][j].method = MatchMethod.embedding
                out = [sorted(lst, key=lambda s: s.score, reverse=True) for lst in out]
            except Exception:  # noqa: BLE001
                pass
        return out

    def _decide(self, sugg: list[Suggestion]) -> MatchResult:
        if not sugg:
            return MatchResult(MatchStatus.unmatched, None, MatchMethod.fuzzy, None, [])
        # thresholds depend on the scoring scale actually used
        if self._llm:
            auto_t, floor_t = settings.llm_auto_threshold, settings.llm_review_floor
        elif self._reranker:
            auto_t, floor_t = settings.rerank_auto_threshold, settings.rerank_review_floor
        else:
            auto_t, floor_t = settings.match_auto_threshold, settings.match_review_floor
        best = sugg[0]
        if best.score >= auto_t:
            return MatchResult(MatchStatus.auto, best.score, best.method, best.service_id, sugg)
        if best.score >= floor_t:
            return MatchResult(MatchStatus.review, best.score, best.method, None, sugg)
        return MatchResult(MatchStatus.unmatched, best.score, best.method, None, sugg)
