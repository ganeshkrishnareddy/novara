"""Notification automation and delivery governance tables (Novu cluster).

Revision ID: a6b8c9d0e1f2
Revises: f5a7b8c9d0e1
Create Date: 2026-11-23

Ten additive, workspace-scoped tables owned by the clean-room
``notification_automation`` module. No existing table is altered and no
upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a6b8c9d0e1f2"
down_revision = "f5a7b8c9d0e1"
branch_labels = None
depends_on = None

TABLES = (
    "automation_subscribers",
    "subscriber_channel_endpoints",
    "workflow_code_steps",
    "local_http_stubs",
    "workflow_http_steps",
    "provider_routing_rules",
    "demo_provider_quotas",
    "demo_deliveries",
    "automation_quotas",
    "automation_feature_flags",
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