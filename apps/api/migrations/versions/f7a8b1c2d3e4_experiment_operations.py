"""Experimentation operations and flag lifecycle tables (GrowthBook P2 cluster).

Revision ID: f7a8b1c2d3e4
Revises: e6f7a8b1c2d3
Create Date: 2026-11-23

Nine additive, workspace-scoped tables owned by the clean-room
``experiment_operations`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f7a8b1c2d3e4"
down_revision = "e6f7a8b1c2d3"
branch_labels = None
depends_on = None

TABLES = (
    "experiment_projects",
    "experiment_saved_groups",
    "experiment_flag_revisions",
    "experiment_flag_archives",
    "experiment_dimensions",
    "experiment_segments",
    "experiment_aa_tests",
    "experiment_aa_observations",
    "experiment_timeseries",
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
