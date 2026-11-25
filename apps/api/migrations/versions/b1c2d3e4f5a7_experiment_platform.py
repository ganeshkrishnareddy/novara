"""Experimentation role bindings table (GrowthBook platform governance).

Revision ID: b1c2d3e4f5a7
Revises: a8b1c2d3e4f5
Create Date: 2026-11-23

One additive, workspace-scoped table owned by the clean-room
``experiment_platform`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "b1c2d3e4f5a7"
down_revision = "a8b1c2d3e4f5"
branch_labels = None
depends_on = None

TABLES = ("experiment_role_bindings",)


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
