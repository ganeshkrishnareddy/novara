"""marketing journey steps and campaign enrollments

Adds the local-only journey tables used by MT-025/MT-115. Idempotent because
local-first startup creates module tables with Base.metadata.create_all before
Alembic runs.

Revision ID: e4b1c7a9d052
Revises: c7d3e8a4f926
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e4b1c7a9d052"
down_revision = "c7d3e8a4f926"
branch_labels = None
depends_on = None

TABLES = ("journey_steps", "campaign_enrollments")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "journey_steps" not in existing:
        op.create_table(
            "journey_steps",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("campaign_id", sa.String(length=36),
                      sa.ForeignKey("campaigns.id"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=20), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("campaign_id", "position", name="uq_journey_step_position"),
        )
        op.create_index("ix_journey_steps_workspace_id", "journey_steps", ["workspace_id"])
        op.create_index("ix_journey_steps_campaign_id", "journey_steps", ["campaign_id"])
    if "campaign_enrollments" not in existing:
        op.create_table(
            "campaign_enrollments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("campaign_id", sa.String(length=36),
                      sa.ForeignKey("campaigns.id"), nullable=False),
            sa.Column("contact_id", sa.String(length=36),
                      sa.ForeignKey("contacts.id"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_at", sa.DateTime(timezone=True)),
            sa.Column("exited_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_enrollment"),
        )
        op.create_index("ix_campaign_enrollments_workspace_id", "campaign_enrollments", ["workspace_id"])
        op.create_index("ix_campaign_enrollments_campaign_id", "campaign_enrollments", ["campaign_id"])
        op.create_index("ix_campaign_enrollments_contact_id", "campaign_enrollments", ["contact_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(TABLES):
        if table in existing:
            op.drop_table(table)
