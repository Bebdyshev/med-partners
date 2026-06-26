"""Full-text + trigram search over services (and partners)."""
from __future__ import annotations

from sqlalchemy import func, or_, select, text

from app.models import Partner, Service


def search_services(db, q: str, limit: int = 20) -> list[dict]:
    """Postgres FTS with ts_rank, plus a trigram fallback for typos."""
    if not q.strip():
        return []
    # FTS
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
    rows = db.execute(sql, {"q": q, "lim": limit}).all()
    if rows:
        return [{"id": str(r.id), "canonical_name": r.canonical_name, "category": r.category,
                 "rank": float(r.rank)} for r in rows]
    # trigram fuzzy fallback
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
