"""configurable project work-item states

Adds the workspace-scoped state set used for PL-004/006/008/017. Idempotent
because local-first startup may run Base.metadata.create_all before Alembic.

Revision ID: e7a4c9d21b60
Revises: d5e9b3c2f841
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e7a4c9d21b60"
down_revision = "d5e9b3c2f841"
branch_labels = None
depends_on = None

TABLE = "project_states"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE in inspector.get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("group", sa.String(length=20), nullable=False, server_default="todo"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workspace_id", "name", name="uq_project_state"),
    )
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_table(TABLE)
