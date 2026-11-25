"""contact external identity provenance and global do-not-contact

Adds optional external identity fields (MT-113) and the global do-not-contact
flag (MT-019) to contacts. NOVARA's own id stays authoritative; external ids
only preserve what a named system called the same person. Idempotent because
local-first startup may run Base.metadata.create_all before Alembic.

Revision ID: a9c4e2f6b815
Revises: f2b7c1a9d403
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a9c4e2f6b815"
down_revision = "f2b7c1a9d403"
branch_labels = None
depends_on = None

TABLE = "contacts"
COLUMNS = {
    "external_id": sa.String(length=200),
    "external_source": sa.String(length=100),
    "do_not_contact": sa.Boolean(),
}
INDEX = "ix_contacts_external_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(TABLE)}
    for name, column_type in COLUMNS.items():
        if name not in existing:
            kwargs = {"nullable": False, "server_default": sa.false()} if name == "do_not_contact" else {"nullable": True}
            op.add_column(TABLE, sa.Column(name, column_type, **kwargs))
    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, ["external_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name=TABLE)
    existing = {column["name"] for column in inspector.get_columns(TABLE)}
    for name in reversed(list(COLUMNS)):
        if name in existing:
            op.drop_column(TABLE, name)
