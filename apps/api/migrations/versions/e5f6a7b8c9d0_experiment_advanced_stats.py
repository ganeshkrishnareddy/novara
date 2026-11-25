"""Advanced experimentation statistics tables (GrowthBook P2 cluster).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-23

Three additive, workspace-scoped tables owned by the clean-room
``experiment_advanced_stats`` module. They reference existing NOVARA rows only
by workspace id; no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

TABLES = (
    "adv_analyses",
    "adv_bandit_arms",
    "adv_holdouts",
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
