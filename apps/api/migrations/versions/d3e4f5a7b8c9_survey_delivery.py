"""Survey delivery, flow, branding and creative tables (Formbricks cluster).

Revision ID: d3e4f5a7b8c9
Revises: c2d3e4f5a7b8
Create Date: 2026-11-23

Seven additive, workspace-scoped tables owned by the clean-room
``survey_delivery`` module. No existing table is altered and no upstream
source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d3e4f5a7b8c9"
down_revision = "c2d3e4f5a7b8"
branch_labels = None
depends_on = None

TABLES = (
    "survey_delivery_configs",
    "survey_flow_pages",
    "survey_flow_rules",
    "survey_email_brandings",
    "survey_email_followups",
    "survey_head_scripts",
    "survey_creatives",
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
