"""Email content and engagement tracking tables (Mautic clean-room cluster).

Revision ID: f2b3c4d5e6f7
Revises: a1b2c3d4e5f6, e0f2a3b4c5d6
Create Date: 2026-11-23

Merges the two existing Alembic heads so the repository has one linear head
again; the merge point also adds the seven email engagement tables.

Seven additive, workspace-scoped tables owned by the clean-room
``email_engagement`` module. No existing table is altered and no upstream source
is copied.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "f2b3c4d5e6f7"
down_revision = ("a1b2c3d4e5f6", "e0f2a3b4c5d6")
branch_labels = None
depends_on = None

TABLES = (
    "email_engagement_templates",
    "email_engagement_translations",
    "email_engagement_variants",
    "email_engagement_tokens",
    "email_engagement_events",
    "email_engagement_signatures",
    "email_engagement_images",
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
