"""Visitor conversation site tokens (CW-035).

Revision ID: f5a7b9c1d2e4
Revises: e2f4a6b8c0d3
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f5a7b9c1d2e4"
down_revision = "e2f4a6b8c0d3"
branch_labels = None
depends_on = None

TABLES = ("support_visitor_sites", "support_visitor_conversations")


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
