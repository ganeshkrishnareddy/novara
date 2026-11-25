"""Clean-room project extension tables (PL-019/028/116/117).

Revision ID: e7d2c4b8a1f6
Revises: d3f6b9c2e5a8
Create Date: 2026-11-23

Four new, additive workspace-scoped tables modelled from the acceptance criteria
alone. No upstream source is copied and no existing table is altered.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "e7d2c4b8a1f6"
down_revision = "d3f6b9c2e5a8"
branch_labels = None
depends_on = None

TABLES = (
    "milestone_work_links",
    "custom_property_definitions",
    "custom_property_values",
    "resource_grants",
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
