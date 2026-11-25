"""Conversation operations tables (Chatwoot cluster).

Revision ID: c8d0e1f2a3b4
Revises: b7c9d0e1f2a3
Create Date: 2026-11-23

Twelve additive, workspace-scoped tables owned by the clean-room
``conversation_ops`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "c8d0e1f2a3b4"
down_revision = "b7c9d0e1f2a3"
branch_labels = None
depends_on = None

TABLES = (
    "agent_presence",
    "conversation_snoozes",
    "note_mentions",
    "typing_indicators",
    "message_receipts",
    "conversation_mutes",
    "conversation_folders",
    "inbox_hours",
    "hours_slots",
    "hours_overrides",
    "inbox_holidays",
    "reply_dedup",
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