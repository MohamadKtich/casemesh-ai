"""Add persisted investigation workflow state.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "investigation_runs",
        sa.Column("objective", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("current_step", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("confidence", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "abstained",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("analysis_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("assessment_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("findings_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "plan_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "evidence_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "gaps_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "citations_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_investigation_runs_state",
        "investigation_runs",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investigation_runs_state",
        table_name="investigation_runs",
    )
    op.drop_column("investigation_runs", "error_message")
    op.drop_column("investigation_runs", "metadata_json")
    op.drop_column("investigation_runs", "citations_json")
    op.drop_column("investigation_runs", "gaps_json")
    op.drop_column("investigation_runs", "evidence_json")
    op.drop_column("investigation_runs", "plan_json")
    op.drop_column("investigation_runs", "findings_text")
    op.drop_column("investigation_runs", "assessment_text")
    op.drop_column("investigation_runs", "analysis_text")
    op.drop_column("investigation_runs", "abstained")
    op.drop_column("investigation_runs", "confidence")
    op.drop_column("investigation_runs", "attempt")
    op.drop_column("investigation_runs", "current_step")
    op.drop_column("investigation_runs", "objective")
