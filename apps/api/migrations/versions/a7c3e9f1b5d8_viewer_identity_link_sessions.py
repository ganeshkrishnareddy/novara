"""PM-080 viewer identities and PM-039/042 restricted link sessions.

Revision ID: a7c3e9f1b5d8
Revises: a7c3e9d14b62
Create Date: 2026-11-23

Both tables are new and additive: no existing table or column is altered, so a
downgrade/upgrade round trip preserves all pre-existing workspace data.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a7c3e9f1b5d8"
down_revision = "a7c3e9d14b62"
branch_labels = None
depends_on = None

TABLES = ("viewer_identities", "document_link_sessions")


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
