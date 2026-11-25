"""In-app targeting, triggers and survey controls (FB-055..FB-084).

Revision ID: a2b3c4d5e6f8
Revises: f1a2b3c4d5e6
Create Date: 2026-11-23

Five additive, workspace-scoped tables owned by the clean-room
``feedback_targeting`` module. No upstream source is copied and no existing
table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "a2b3c4d5e6f8"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

TABLES = (
    "survey_user_profiles",
    "survey_action_classes",
    "survey_triggers",
    "targeting_decisions",
    "survey_controls",
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
