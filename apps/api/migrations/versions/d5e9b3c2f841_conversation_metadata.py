"""conversation origin, type, direction and channel metadata

Adds the Customer Inbox metadata needed for CW-001/002/003/018. Idempotent for
the same reason as b4d8c2f1a730: local startup may already have created columns
through Base.metadata.create_all before Alembic is run.

Revision ID: d5e9b3c2f841
Revises: b4d8c2f1a730
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d5e9b3c2f841"
down_revision = "b4d8c2f1a730"
branch_labels = None
depends_on = None

COLUMNS = (
    ("support_tickets", "origin_channel", sa.Column("origin_channel", sa.String(length=40), nullable=False, server_default="local")),
    ("support_tickets", "conversation_type", sa.Column("conversation_type", sa.String(length=40), nullable=False, server_default="question")),
    ("ticket_messages", "direction", sa.Column("direction", sa.String(length=20), nullable=False, server_default="outbound")),
    ("ticket_messages", "channel", sa.Column("channel", sa.String(length=40), nullable=False, server_default="local")),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, name, column in COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if name not in existing:
            op.add_column(table, column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, name, _ in reversed(COLUMNS):
        existing = {c["name"] for c in inspector.get_columns(table)}
        if name in existing:
            op.drop_column(table, name)
