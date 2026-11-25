"""Work-item planning tables (Plane P2 cluster).

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-11-23

Nine additive, workspace-scoped tables owned by the clean-room
``work_item_planning`` module. They extend existing project rows by foreign key
only; no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

TABLES = (
    "planning_relations",
    "planning_dependencies",
    "planning_estimate_schemes",
    "planning_estimates",
    "planning_item_updates",
    "planning_templates",
    "planning_recurrences",
    "planning_time_logs",
    "planning_subscribers",
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
