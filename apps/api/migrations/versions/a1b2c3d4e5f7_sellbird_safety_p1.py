"""Sellbird P1 local safety tables: policy footer and suppression list.

Local-first startup creates tables with Base.metadata.create_all before Alembic
runs, so table and column creation is guarded for an already-current database.

Revision ID: a1b2c3d4e5f7
Revises: 6a2a87b2856b
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "6a2a87b2856b"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return any(
        item["name"] == column
        for item in sa.inspect(op.get_bind()).get_columns(table)
    )


def upgrade() -> None:
    if not _has_table("workspace_outreach_policies"):
        op.create_table(
            "workspace_outreach_policies",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "workspace_id", sa.String(36),
                sa.ForeignKey("workspaces.id"), nullable=False, index=True, unique=True,
            ),
            sa.Column("compliance_footer", sa.Text(), nullable=False),
            sa.Column("updated_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not _has_table("outreach_suppressions"):
        op.create_table(
            "outreach_suppressions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "workspace_id", sa.String(36),
                sa.ForeignKey("workspaces.id"), nullable=False, index=True,
            ),
            sa.Column("recipient", sa.String(320), nullable=False),
            sa.Column("scope", sa.String(20), nullable=False),
            sa.Column("reason", sa.String(200), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "workspace_id", "recipient", "scope", "reason",
                name="uq_suppression_workspace_recipient_scope_reason",
            ),
        )
        op.create_index(
            "ix_suppression_workspace_recipient", "outreach_suppressions",
            ["workspace_id", "recipient"],
        )
    if _has_table("agent_configs") and not _has_column("agent_configs", "role"):
        op.add_column("agent_configs", sa.Column("role", sa.String(30), nullable=True))


def downgrade() -> None:
    if _has_table("agent_configs") and _has_column("agent_configs", "role"):
        op.drop_column("agent_configs", "role")
    if _has_table("outreach_suppressions"):
        op.drop_table("outreach_suppressions")
    if _has_table("workspace_outreach_policies"):
        op.drop_table("workspace_outreach_policies")
