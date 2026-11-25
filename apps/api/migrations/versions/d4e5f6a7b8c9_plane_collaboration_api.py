"""Work-item collaboration and API governance tables (Plane P2 cluster).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-23

Five additive, workspace-scoped tables owned by the clean-room
``plane_collaboration_api`` module. They reference existing NOVARA rows only by
id; no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

TABLES = (
    "collab_attachments",
    "collab_mentions",
    "collab_activities",
    "collab_cursor_pages",
    "collab_item_restrictions",
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
