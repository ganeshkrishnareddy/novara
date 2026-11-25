"""Wiki page collaboration tables (Plane P2 cluster).

Revision ID: e0f2a3b4c5d6
Revises: d9e1f2a3b4c5
Create Date: 2026-11-23

Additive, workspace-scoped tables owned by the clean-room ``wiki_pages``
module. They extend the existing ``project_pages`` table by foreign key only;
no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e0f2a3b4c5d6"
down_revision = "d9e1f2a3b4c5"
branch_labels = None
depends_on = None

TABLES = (
    "wiki_page_revisions",
    "wiki_page_views",
    "wiki_page_publications",
    "wiki_page_exports",
    "wiki_page_labels",
    "wiki_page_label_links",
    "wiki_page_nodes",
    "wiki_page_collections",
    "wiki_page_collection_items",
    "wiki_page_blocks",
    "wiki_page_comments",
    "wiki_edit_sessions",
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
