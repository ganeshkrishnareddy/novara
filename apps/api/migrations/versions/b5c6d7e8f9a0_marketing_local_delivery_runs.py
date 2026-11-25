"""Workable local marketing delivery runs (approval-gated).

Revision ID: b5c6d7e8f9a0
Revises: e0f1a2b3c4d5
Create Date: 2026-11-25

One additive, workspace-scoped table owned by the ``marketing_delivery`` module.
No existing table is altered and no external provider is introduced. The run
record carries the approval decision and correlation id that ties the audience,
campaign, local delivery adapter and analytics trail together.
"""

from alembic import op
import sqlalchemy as sa

revision = "b5c6d7e8f9a0"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_local_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("broadcast_campaigns.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("audience_count", sa.Integer, nullable=False),
        sa.Column("blocked_count", sa.Integer, nullable=False),
        sa.Column("delivered_count", sa.Integer, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(36)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_id", "correlation_id", name="uq_marketing_run_correlation"),
    )


def downgrade() -> None:
    op.drop_table("marketing_local_runs")
