"""Signal-driven sales engagement governance tables (Sellbird cluster).

Revision ID: b7c9d0e1f2a3
Revises: a6b8c9d0e1f2
Create Date: 2026-11-23

Eight additive, workspace-scoped tables owned by the clean-room
``sales_engagement`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "b7c9d0e1f2a3"
down_revision = "a6b8c9d0e1f2"
branch_labels = None
depends_on = None

TABLES = (
    "signal_codes",
    "sales_cohorts",
    "sales_outreach_drafts",
    "offer_suggestions",
    "outbox_messages",
    "sending_configs",
    "inbox_pauses",
    "send_rules",
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