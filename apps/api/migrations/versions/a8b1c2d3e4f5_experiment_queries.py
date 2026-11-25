"""Local experiment data exploration and reporting tables (GrowthBook cluster).

Revision ID: a8b1c2d3e4f5
Revises: f7a8b1c2d3e4
Create Date: 2026-11-23

Eight additive, workspace-scoped tables owned by the clean-room
``experiment_queries`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a8b1c2d3e4f5"
down_revision = "f7a8b1c2d3e4"
branch_labels = None
depends_on = None

TABLES = (
    "experiment_query_fact_tables",
    "experiment_discovery_queries",
    "experiment_assignment_queries",
    "experiment_identifier_types",
    "experiment_identifier_joins",
    "experiment_funnels",
    "experiment_custom_reports",
    "experiment_carryover_assessments",
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
