"""Add vector embeddings and hybrid retrieval indexes.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "document_chunks",
        sa.Column("embedding", Vector(768), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )

    op.execute(
        """
        CREATE INDEX ix_document_chunks_content_fts
        ON document_chunks
        USING gin (to_tsvector('english', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts")
    op.drop_index(
        "ix_document_chunks_embedding_hnsw",
        table_name="document_chunks",
    )
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
