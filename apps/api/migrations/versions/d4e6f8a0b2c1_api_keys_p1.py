"""API keys / personal access tokens (PL-045, PL-070).

Local-first startup creates module tables with Base.metadata.create_all before
Alembic runs, so the table is guarded by a has_table check. Fresh Alembic
databases receive the real model definition including indexes and constraints.

Revision ID: d4e6f8a0b2c1
Revises: c9f7e1b3a5d2
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d4e6f8a0b2c1"
down_revision = "c9f7e1b3a5d2"
branch_labels = None
depends_on = None

TABLES = ("api_keys",)


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
