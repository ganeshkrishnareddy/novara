"""notification rich state, seen/read, workspace settings

Adds the P0 in-app notification fields (NV-023/035), the workspace notification
settings table (NV-068), and the indexes that back the scoped feed queries.

This revision is deliberately idempotent: local-first installations call
``init_db()`` at startup, so a developer may already have the new table created
by ``Base.metadata.create_all`` before Alembic is run. Each object is created
only when it is actually missing.

Revision ID: b4d8c2f1a730
Revises: 9951aadc14c8
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b4d8c2f1a730"
down_revision = "9951aadc14c8"
branch_labels = None
depends_on = None

NOTIFICATION_COLUMNS = (
    ("title", lambda: sa.Column("title", sa.String(length=200), nullable=True)),
    ("category", lambda: sa.Column("category", sa.String(length=50), nullable=False, server_default="general")),
    ("link", lambda: sa.Column("link", sa.String(length=500), nullable=True)),
    ("read_at", lambda: sa.Column("read_at", sa.DateTime(timezone=True), nullable=True)),
    ("seen", lambda: sa.Column("seen", sa.Boolean(), nullable=False, server_default=sa.false())),
    ("seen_at", lambda: sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True)),
)
SETTINGS_INDEX = "ix_workspace_notification_settings_workspace_id"


def _existing(bind) -> tuple[set[str], set[str], set[str]]:
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    columns = (
        {column["name"] for column in inspector.get_columns("notifications")}
        if "notifications" in tables else set()
    )
    indexes = (
        {index["name"] for index in inspector.get_indexes("notifications")}
        if "notifications" in tables else set()
    )
    return tables, columns, indexes


def upgrade() -> None:
    bind = op.get_bind()
    tables, columns, indexes = _existing(bind)

    for name, factory in NOTIFICATION_COLUMNS:
        if name not in columns:
            op.add_column("notifications", factory())
    for name in ("ix_notif_workspace_user", "ix_notif_workspace_category"):
        if name not in indexes:
            fields = ["workspace_id", "user_id"] if name.endswith("user") else ["workspace_id", "category"]
            op.create_index(name, "notifications", fields)

    # Existing delivered messages have been displayed if they were read.
    op.execute(
        "UPDATE notifications SET seen = 1, "
        "seen_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE read = 1"
    )

    if "workspace_notification_settings" not in tables:
        op.create_table(
            "workspace_notification_settings",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=False),
            sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("delivery_window_start", sa.String(length=5), nullable=True),
            sa.Column("delivery_window_end", sa.String(length=5), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workspace_id"),
        )
    settings_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("workspace_notification_settings")
    }
    if SETTINGS_INDEX not in settings_indexes:
        op.create_index(
            SETTINGS_INDEX, "workspace_notification_settings", ["workspace_id"], unique=True
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables, columns, indexes = _existing(bind)

    if "workspace_notification_settings" in tables:
        settings_indexes = {
            index["name"] for index in sa.inspect(bind).get_indexes("workspace_notification_settings")
        }
        if SETTINGS_INDEX in settings_indexes:
            op.drop_index(SETTINGS_INDEX, table_name="workspace_notification_settings")
        op.drop_table("workspace_notification_settings")
    for name in ("ix_notif_workspace_category", "ix_notif_workspace_user"):
        if name in indexes:
            op.drop_index(name, table_name="notifications")
    for name, _ in reversed(NOTIFICATION_COLUMNS):
        if name in columns:
            op.drop_column("notifications", name)
