"""Advanced feature-flag governance tables (GrowthBook P2 cluster).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-23

Twelve additive, workspace-scoped tables owned by the clean-room
``feature_flag_governance`` module. They reference existing NOVARA rows only by
workspace id; no existing table is altered and no upstream source is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

TABLES = (
    "fg_schedules",
    "fg_secure_attributes",
    "fg_sticky_assignments",
    "fg_prerequisites",
    "fg_redirects",
    "fg_environments",
    "fg_templates",
    "fg_safe_rollouts",
    "fg_settings",
    "fg_ramps",
    "fg_revisions",
    "fg_configs",
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
