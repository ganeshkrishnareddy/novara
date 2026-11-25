"""REST v2 and document-store tables (GB-060, GB-087).

Revision ID: a7c3e9d14b62
Revises: f5a7b9c1d2e4
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a7c3e9d14b62"
down_revision = "f5a7b9c1d2e4"
branch_labels = None
depends_on = None

TABLES = (
    "api_v2_records",
    "docstore_collections",
    "docstore_indexes",
    "docstore_documents",
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
