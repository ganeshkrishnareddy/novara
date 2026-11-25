"""Project intake tables (PL-088).

Revision ID: e2f4a6b8c0d3
Revises: d4e6f8a0b2c1
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e2f4a6b8c0d3"
down_revision = "d4e6f8a0b2c1"
branch_labels = None
depends_on = None

TABLES = ("project_intake_links", "project_intake_requests")


def _tables() -> dict:
    import_all()
    missing = [name for name in TABLES if name not in Base.metadata.tables]
    if missing:
        raise RuntimeError(f"Tables missing from Base.metadata: {missing}")
    return {name: Base.metadata.tables[name] for name in TABLES}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name, table in _tables().items():
        if not inspector.has_table(name):
            table.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name in reversed(TABLES):
        if inspector.has_table(name):
            op.drop_table(name)
