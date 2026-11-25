"""Formbricks P2 survey-extension tables (FB-008..FB-044 cluster).

Revision ID: f1a2b3c4d5e6
Revises: e7d2c4b8a1f6
Create Date: 2026-11-23

Four additive, workspace-scoped tables owned by the clean-room
``feedback_extensions`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f1a2b3c4d5e6"
down_revision = "e7d2c4b8a1f6"
branch_labels = None
depends_on = None

TABLES = (
    "survey_configs",
    "survey_questions",
    "survey_answers",
    "survey_embedded_data",
    "survey_links",
    "survey_displays",
    "survey_tags",
    "survey_answer_tags",
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
