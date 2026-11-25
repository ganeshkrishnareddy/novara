"""Local experimentation delivery and refresh tables (GrowthBook cluster).

Revision ID: c2d3e4f5a7b8
Revises: b1c2d3e4f5a7
Create Date: 2026-11-23

Seven additive, workspace-scoped tables owned by the clean-room
``experiment_delivery`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "c2d3e4f5a7b8"
down_revision = "b1c2d3e4f5a7"
branch_labels = None
depends_on = None

TABLES = (
    "experiment_webhooks",
    "experiment_webhook_deliveries",
    "experiment_notifier_messages",
    "experiment_cache_entries",
    "experiment_cache_purges",
    "experiment_proxy_snapshots",
    "experiment_refresh_jobs",
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
