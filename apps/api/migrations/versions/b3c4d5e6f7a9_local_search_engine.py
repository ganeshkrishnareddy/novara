"""Local search engine indexes and documents (Meilisearch P2 cluster).

Revision ID: b3c4d5e6f7a9
Revises: a2b3c4d5e6f8
Create Date: 2026-11-23

Two additive, workspace-scoped tables owned by the clean-room
``search_engine`` module. No upstream source is copied and no existing table
is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "b3c4d5e6f7a9"
down_revision = "a2b3c4d5e6f8"
branch_labels = None
depends_on = None

TABLES = ("search_indexes", "search_documents")


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
