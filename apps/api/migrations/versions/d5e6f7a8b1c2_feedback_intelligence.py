"""Feedback Intelligence / Unify Feedback tables (Formbricks P2 cluster).

Revision ID: d5e6f7a8b1c2
Revises: c4d5e6f7a8b1
Create Date: 2026-11-23

Seven additive, workspace-scoped tables owned by the clean-room
``feedback_intelligence`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d5e6f7a8b1c2"
down_revision = "c4d5e6f7a8b1"
branch_labels = None
depends_on = None

TABLES = (
    "feedback_library_fields",
    "feedback_survey_fields",
    "feedback_datasets",
    "feedback_sources",
    "feedback_records",
    "feedback_segments",
    "feedback_dashboards",
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
