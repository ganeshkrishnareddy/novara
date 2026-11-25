"""workspace admin settings and native API resource contexts

Idempotent migration for PL-001 (workspace_settings) and MT-072 (api_forms,
api_pages). Local-first startup creates module tables with
Base.metadata.create_all before Alembic runs, so each table is guarded.

Revision ID: 9b7c4e2a1d63
Revises: e4b1c7a9d052
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9b7c4e2a1d63"
down_revision = "e4b1c7a9d052"
branch_labels = None
depends_on = None

TABLES = ("workspace_settings", "api_forms", "api_pages")


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "workspace_settings" not in existing:
        op.create_table(
            "workspace_settings",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False, unique=True),
            sa.Column("settings", sa.JSON(), nullable=False),
            sa.Column("updated_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_workspace_settings_workspace_id", "workspace_settings", ["workspace_id"])

    if "api_forms" not in existing:
        op.create_table(
            "api_forms",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("fields", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False,
                      server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("workspace_id", "name", name="uq_api_form_workspace_name"),
        )
        op.create_index("ix_api_forms_workspace_id", "api_forms", ["workspace_id"])

    if "api_pages" not in existing:
        op.create_table(
            "api_pages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workspace_id", sa.String(length=36),
                      sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("slug", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text()),
            sa.Column("status", sa.String(length=20), nullable=False,
                      server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("workspace_id", "slug", name="uq_api_page_workspace_slug"),
        )
        op.create_index("ix_api_pages_workspace_id", "api_pages", ["workspace_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(TABLES):
        if table in existing:
            op.drop_table(table)
