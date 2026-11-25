"""Advanced local search tables (Meilisearch MIT-core clean-room cluster).

Revision ID: e4f5a7b8c9d0
Revises: d3e4f5a7b8c9
Create Date: 2026-11-23

Nine additive, workspace-scoped tables owned by the clean-room
``search_advanced`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e4f5a7b8c9d0"
down_revision = "d3e4f5a7b8c9"
branch_labels = None
depends_on = None

TABLES = (
    "search_embedders",
    "search_vectors",
    "search_locales",
    "search_suggestions",
    "search_federations",
    "search_index_swaps",
    "search_compactions",
    "search_templates",
    "search_previews",
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
