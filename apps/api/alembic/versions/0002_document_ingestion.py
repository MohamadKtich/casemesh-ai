"""Add document ingestion metadata and chunks.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "case_documents",
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="upload"),
    )
    op.add_column(
        "case_documents",
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "case_documents",
        sa.Column("parser_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "case_documents",
        sa.Column("text_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "case_documents",
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "case_documents",
        sa.Column("ingestion_error", sa.Text(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_case_documents_case_sha256",
        "case_documents",
        ["case_id", "sha256"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["case_documents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
    )
    op.create_index(
        "ix_document_chunks_case_id",
        "document_chunks",
        ["case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_case_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_constraint(
        "uq_case_documents_case_sha256",
        "case_documents",
        type_="unique",
    )

    op.drop_column("case_documents", "ingestion_error")
    op.drop_column("case_documents", "ingested_at")
    op.drop_column("case_documents", "text_length")
    op.drop_column("case_documents", "parser_name")
    op.drop_column("case_documents", "size_bytes")
    op.drop_column("case_documents", "source_type")
