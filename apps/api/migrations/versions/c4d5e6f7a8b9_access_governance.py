"""Access governance tables (CW-130/CW-139/PL-124/PL-125/NV-070).

Revision ID: c4d5e6f7a8b9
Revises: f6a7b8c9d0e1
Create Date: 2026-11-24

Three additive, workspace-scoped tables owned by the clean-room
``access_governance`` module. No existing table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "c4d5e6f7a8b9"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

TABLES = (
    "custom_roles",
    "permission_schemes",
    "permission_scheme_assignments",
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
