"""document view contact linkage and engagement events

Adds the optional CRM contact reference on a document visit so a shared view
event can appear on the customer timeline and notify the sharing salesperson.
Idempotent because local-first startup may run Base.metadata.create_all before
Alembic.

Revision ID: f2b7c1a9d403
Revises: e7a4c9d21b60
Create Date: 2026-11-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f2b7c1a9d403"
down_revision = "e7a4c9d21b60"
branch_labels = None
depends_on = None

TABLE = "document_link_visits"
COLUMN = "contact_id"
INDEX = "ix_document_link_visits_contact_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if COLUMN not in columns:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=36), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, [COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name=TABLE)
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if COLUMN in columns:
        op.drop_column(TABLE, COLUMN)
