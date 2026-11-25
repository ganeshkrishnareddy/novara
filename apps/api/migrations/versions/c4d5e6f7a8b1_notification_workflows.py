"""Notification workflow engine tables (Novu P2 cluster).

Revision ID: c4d5e6f7a8b1
Revises: b3c4d5e6f7a9
Create Date: 2026-11-23

Seven additive, workspace-scoped tables owned by the clean-room
``notification_workflows`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "c4d5e6f7a8b1"
down_revision = "b3c4d5e6f7a9"
branch_labels = None
depends_on = None

TABLES = (
    "notification_workflows",
    "notification_feeds",
    "notification_layouts",
    "notification_contexts",
    "notification_workflow_messages",
    "notification_webhook_endpoints",
    "notification_webhook_deliveries",
)


def upgrade() -> None:
    import_all()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name in TABLES:
        if not inspector.has_table(name):
            Base.metadata.tables[name].create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name in reversed(TABLES):
        if inspector.has_table(name):
            op.drop_table(name)
