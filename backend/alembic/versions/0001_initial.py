"""initial schema + FTS/trigram

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op

from app.db.base import Base
import app.models  # noqa: F401  -- register all tables on Base.metadata

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Extensions: pg_trgm for fuzzy search, pgcrypto not needed (uuid4 in app).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create all ORM tables.
    Base.metadata.create_all(bind=bind)

    # --- Full-text search on services ---
    op.execute("ALTER TABLE service ADD COLUMN search_vector tsvector")
    op.execute(
        """
        UPDATE service
        SET search_vector = to_tsvector('russian', coalesce(canonical_name,'') || ' ' || coalesce(category,''))
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION service_search_vector_update() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('russian',
              coalesce(NEW.canonical_name,'') || ' ' || coalesce(NEW.category,''));
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_service_search_vector
        BEFORE INSERT OR UPDATE ON service
        FOR EACH ROW EXECUTE FUNCTION service_search_vector_update()
        """
    )
    op.execute("CREATE INDEX ix_service_search_vector ON service USING gin(search_vector)")

    # Trigram indexes for fuzzy lookups
    op.execute("CREATE INDEX ix_service_canonical_trgm ON service USING gin (canonical_name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_synonym_trgm ON service_synonym USING gin (synonym gin_trgm_ops)")
    op.execute("CREATE INDEX ix_item_raw_name_trgm ON price_item USING gin (raw_name gin_trgm_ops)")

    # Embedding column (stored as JSON array; pgvector optional upgrade later)
    op.execute("ALTER TABLE service ADD COLUMN embedding jsonb")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_service_search_vector ON service")
    op.execute("DROP FUNCTION IF EXISTS service_search_vector_update()")
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
