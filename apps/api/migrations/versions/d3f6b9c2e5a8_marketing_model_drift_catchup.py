"""Catch up Alembic with the live marketing model definitions.

Revision ID: d3f6b9c2e5a8
Revises: b9d4f7a2c615
Create Date: 2026-11-23

The MT-027/MT-028 clean-room campaign extensions added ``segment_members`` and
five ``campaigns`` columns, and the journey editor added two ``journey_steps``
columns, directly to the models. Those changes were available to local
``create_all`` databases but not to fresh Alembic databases, so ``alembic check``
correctly reported drift. This additive revision closes that gap; every change
is guarded so an already-converged local database is left untouched.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "d3f6b9c2e5a8"
down_revision = "b9d4f7a2c615"
branch_labels = None
depends_on = None

COLUMNS = {
    "campaigns": {
        "cadence": sa.Column("cadence", sa.String(length=20), nullable=False,
                             server_default="once"),
        "trigger_event": sa.Column("trigger_event", sa.String(length=100), nullable=True),
        "source_type": sa.Column("source_type", sa.String(length=20), nullable=False,
                                 server_default="segment"),
        "source_segment_ids": sa.Column("source_segment_ids", sa.JSON(), nullable=False,
                                        server_default="[]"),
        "source_form_ids": sa.Column("source_form_ids", sa.JSON(), nullable=False,
                                     server_default="[]"),
    },
    "journey_steps": {
        "step_kind": sa.Column("step_kind", sa.String(length=20), nullable=False,
                               server_default="action"),
        "config": sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
    },
}


def upgrade() -> None:
    import_all()
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "segment_members" not in inspector.get_table_names():
        Base.metadata.tables["segment_members"].create(bind)

    for table, wanted in COLUMNS.items():
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, column in wanted.items():
            if name not in existing:
                op.add_column(table, column.copy())


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, wanted in reversed(list(COLUMNS.items())):
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name in reversed(list(wanted)):
            if name in existing:
                op.drop_column(table, name)

    if "segment_members" in inspector.get_table_names():
        op.drop_table("segment_members")
