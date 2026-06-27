"""Hybrid search over services (and partners).

Layers, cheapest-first:
  1. Lexical — Postgres FTS over abbreviation-expanded query forms (ОАК ↔ «общий
     анализ крови»). Precise, instant, free; covers exact + abbreviation queries.
  2. Semantic — when FTS is sparse, embed the query and cosine-rank against the
     service embeddings (reuses the normalization Matcher). Catches paraphrases the
     lexicon can't ("сахар крови" → глюкоза). One OpenAI call, only on weak queries.
  3. Trigram — typo fallback when both yield nothing.
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select, text

from app.models import Partner, Service
from app.normalization import embeddings
from app.normalization.text_norm import expand_search_terms

# Below this many lexical hits we reach for the semantic layer to lift recall.
_SEMANTIC_FLOOR = 5


def _semantic_services(db, q: str, limit: int) -> list[dict]:
    """Cosine top-k of the query against service embeddings via the cached Matcher."""
    if not embeddings.available():
        return []
    try:
        from app.normalization.dictionary import load_matcher_cached

        matcher = load_matcher_cached(db)
        lists = matcher.suggest_many([q], k=limit, query_texts=[q], judge=False)
    except Exception:
        return []
    sugg = lists[0] if lists else []
    if not sugg:
        return []
    ids = [uuid.UUID(s.service_id) for s in sugg]
    cats = {str(i): c for i, c in db.execute(
        select(Service.id, Service.category).where(Service.id.in_(ids))
    ).all()}
    return [{"id": s.service_id, "canonical_name": s.canonical_name,
             "category": cats.get(s.service_id), "rank": float(s.score)} for s in sugg]


def search_services(db, q: str, limit: int = 20) -> list[dict]:
    """Hybrid lexical + semantic search (see module docstring)."""
    if not q.strip():
        return []
    # 1) lexical: FTS over each abbreviation-expanded query form, unioned by id (max rank)
    sql = text(
        """
        SELECT id, canonical_name, category,
               ts_rank(search_vector, plainto_tsquery('russian', :q)) AS rank
        FROM service
        WHERE search_vector @@ plainto_tsquery('russian', :q)
        ORDER BY rank DESC
        LIMIT :lim
        """
    )
    merged: dict[str, dict] = {}
    for form in expand_search_terms(q):
        for r in db.execute(sql, {"q": form, "lim": limit}).all():
            key = str(r.id)
            rank = float(r.rank)
            if key not in merged or rank > merged[key]["rank"]:
                merged[key] = {"id": key, "canonical_name": r.canonical_name,
                               "category": r.category, "rank": rank}
    fts = sorted(merged.values(), key=lambda x: x["rank"], reverse=True)
    if len(fts) >= _SEMANTIC_FLOOR:
        return fts[:limit]

    # 2) semantic: sparse lexical results — append cosine matches (deduped, after FTS)
    seen = {r["id"] for r in fts}
    combined = fts + [r for r in _semantic_services(db, q, limit) if r["id"] not in seen]
    if combined:
        return combined[:limit]

    # 3) trigram fuzzy fallback (typos)
    sql2 = text(
        """
        SELECT id, canonical_name, category, similarity(canonical_name, :q) AS sim
        FROM service
        WHERE canonical_name % :q
        ORDER BY sim DESC
        LIMIT :lim
        """
    )
    rows = db.execute(sql2, {"q": q, "lim": limit}).all()
    return [{"id": str(r.id), "canonical_name": r.canonical_name, "category": r.category,
             "rank": float(r.sim)} for r in rows]


def search_partners(db, q: str, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(Partner.id, Partner.display_name, Partner.city)
        .where(or_(Partner.display_name.ilike(f"%{q}%"), Partner.legal_name.ilike(f"%{q}%")))
        .limit(limit)
    ).all()
    return [{"id": str(r.id), "display_name": r.display_name, "city": r.city} for r in rows]
