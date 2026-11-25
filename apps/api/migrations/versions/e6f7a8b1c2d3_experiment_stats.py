"""Experimentation statistics tables (GrowthBook P2 clean-room cluster).

Revision ID: e6f7a8b1c2d3
Revises: d5e6f7a8b1c2
Create Date: 2026-11-23

Three additive, workspace-scoped tables owned by the clean-room
``experiment_stats`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e6f7a8b1c2d3"
down_revision = "d5e6f7a8b1c2"
branch_labels = None
depends_on = None

TABLES = (
    "experiment_metrics",
    "experiment_definitions",
    "experiment_observations",
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
