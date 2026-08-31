"""Add durable approval, policy, and audit fields.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("reviewer_ref", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.add_column(
        "action_requests",
        sa.Column("investigation_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "action_requests",
        sa.Column("resolution_draft_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "action_requests",
        sa.Column("thread_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "action_requests",
        sa.Column(
            "policy_decision",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "action_requests",
        sa.Column("policy_rationale", sa.Text(), nullable=True),
    )
    op.add_column(
        "action_requests",
        sa.Column("risk_level", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "action_requests",
        sa.Column(
            "requires_human_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "action_requests",
        sa.Column(
            "reviewed_payload_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "action_requests",
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_action_requests_investigation_run_id",
        "action_requests",
        "investigation_runs",
        ["investigation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_action_requests_resolution_draft_id",
        "action_requests",
        "resolution_drafts",
        ["resolution_draft_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_action_requests_investigation_run_id",
        "action_requests",
        ["investigation_run_id"],
    )
    op.create_index(
        "ix_action_requests_status",
        "action_requests",
        ["status"],
    )
    op.create_index(
        "ux_action_requests_thread_id",
        "action_requests",
        ["thread_id"],
        unique=True,
    )

    op.add_column(
        "audit_events",
        sa.Column("investigation_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("action_request_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_audit_events_investigation_run_id",
        "audit_events",
        "investigation_runs",
        ["investigation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_audit_events_action_request_id",
        "audit_events",
        "action_requests",
        ["action_request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_audit_events_investigation_run_id",
        "audit_events",
        ["investigation_run_id"],
    )
    op.create_index(
        "ix_audit_events_action_request_id",
        "audit_events",
        ["action_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_events_action_request_id",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_events_investigation_run_id",
        table_name="audit_events",
    )
    op.drop_constraint(
        "fk_audit_events_action_request_id",
        "audit_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_audit_events_investigation_run_id",
        "audit_events",
        type_="foreignkey",
    )
    op.drop_column("audit_events", "action_request_id")
    op.drop_column("audit_events", "investigation_run_id")

    op.drop_index(
        "ux_action_requests_thread_id",
        table_name="action_requests",
    )
    op.drop_index(
        "ix_action_requests_status",
        table_name="action_requests",
    )
    op.drop_index(
        "ix_action_requests_investigation_run_id",
        table_name="action_requests",
    )
    op.drop_constraint(
        "fk_action_requests_resolution_draft_id",
        "action_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_action_requests_investigation_run_id",
        "action_requests",
        type_="foreignkey",
    )
    op.drop_column("action_requests", "error_message")
    op.drop_column("action_requests", "reviewed_payload_json")
    op.drop_column("action_requests", "requires_human_approval")
    op.drop_column("action_requests", "risk_level")
    op.drop_column("action_requests", "policy_rationale")
    op.drop_column("action_requests", "policy_decision")
    op.drop_column("action_requests", "thread_id")
    op.drop_column("action_requests", "resolution_draft_id")
    op.drop_column("action_requests", "investigation_run_id")

    op.drop_column("approvals", "metadata_json")
    op.drop_column("approvals", "decided_at")
    op.drop_column("approvals", "reviewer_ref")
