"""project membership and restricted flag

Adds the project-level membership registry and the opt-in restricted flag used
by PL-003/PL-040. Idempotent because local-first startup creates module tables
with Base.metadata.create_all before Alembic runs.

Revision ID: c7d3e8a4f926
Revises: a9c4e2f6b815
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c7d3e8a4f926"
down_revision = "a9c4e2f6b815"
branch_labels = None
depends_on = None

TABLE = "project_members"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    projects = set(inspector.get_table_names())
    if "projects" in projects:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "restricted" not in columns:
            op.add_column(
                "projects",
                sa.Column("restricted", sa.Boolean(), nullable=False,
                          server_default=sa.false()),
            )
    if TABLE not in projects:
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("project_id", sa.String(length=36),
                      sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False,
                      server_default="member"),
            sa.Column("is_default_assignee", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("subscribed", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("workspace_id", "project_id", "user_id",
                                name="uq_project_member"),
        )
        op.create_index("ix_project_members_workspace_id", TABLE, ["workspace_id"])
        op.create_index("ix_project_members_project_id", TABLE, ["project_id"])
        op.create_index("ix_project_members_user_id", TABLE, ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE in tables:
        op.drop_table(TABLE)
    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "restricted" in columns:
            op.drop_column("projects", "restricted")
