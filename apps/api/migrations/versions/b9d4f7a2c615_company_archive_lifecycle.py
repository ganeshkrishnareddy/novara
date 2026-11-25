"""SB-013 company update/archive lifecycle.

Revision ID: b9d4f7a2c615
Revises: a7c3e9f1b5d8
Create Date: 2026-11-23

Additive only: one nullable-backed boolean column with a server-side default on
``companies``. No existing row or column is altered, so upgrade/downgrade is
data-preserving.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b9d4f7a2c615"
down_revision = "a7c3e9f1b5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("companies"):
        columns = {col["name"] for col in inspector.get_columns("companies")}
        if "archived" not in columns:
            op.add_column(
                "companies",
                sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("companies"):
        columns = {col["name"] for col in inspector.get_columns("companies")}
        if "archived" in columns:
            op.drop_column("companies", "archived")
