"""Support reporting and CSAT governance tables (Chatwoot P2 cluster).

Revision ID: b2c3d4e5f6a7
Revises: f2b3c4d5e6f7
Create Date: 2026-11-23

Four additive, workspace-scoped tables owned by the clean-room
``support_reporting`` module. They reference existing support rows by foreign
key only; no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "b2c3d4e5f6a7"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None

TABLES = (
    "support_report_runs",
    "support_csat_survey_rules",
    "support_csat_response_tokens",
    "support_csat_responses",
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
