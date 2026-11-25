"""Document collaboration and engagement analytics tables (Papermark cluster).

Revision ID: f5a7b8c9d0e1
Revises: e4f5a7b8c9d0
Create Date: 2026-11-23

Six additive, workspace-scoped tables owned by the clean-room
``document_engagement`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f5a7b8c9d0e1"
down_revision = "e4f5a7b8c9d0"
branch_labels = None
depends_on = None

TABLES = (
    "document_reactions",
    "document_feedbacks",
    "document_annotations",
    "document_version_targets",
    "document_engagement_events",
    "document_internal_visitors",
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