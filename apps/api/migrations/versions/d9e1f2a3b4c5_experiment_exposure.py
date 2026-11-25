"""Experiment exposure tracker adapter tables.

Revision ID: d9e1f2a3b4c5
Revises: c8d0e1f2a3b4
Create Date: 2026-11-23

Five additive, workspace-scoped tables owned by the clean-room
``experiment_exposure`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d9e1f2a3b4c5"
down_revision = "c8d0e1f2a3b4"
branch_labels = None
depends_on = None

TABLES = (
    "exposure_trackers",
    "exposure_field_mappings",
    "normalized_exposures",
    "exposure_rejections",
    "exposure_batches",
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
