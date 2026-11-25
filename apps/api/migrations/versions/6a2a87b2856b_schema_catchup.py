"""schema catch-up for P1 column additions

Reconciles columns added to pre-existing tables by the P1 modules. Every
SQLite-sensitive change uses batch_alter_table (table recreate) because SQLite
has no native ALTER COLUMN SET NOT NULL / DROP CONSTRAINT support.

Revision ID: 6a2a87b2856b
Revises: c1b2a3d4e5f6
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "6a2a87b2856b"
down_revision = "c1b2a3d4e5f6"
branch_labels = None
depends_on = None

# (table, tuple of timestamp columns that are NOT NULL in the model)
TIMESTAMP_TABLES = (
    ("api_forms", ("created_at", "updated_at")),
    ("api_pages", ("created_at", "updated_at")),
    ("campaign_enrollments", ("entered_at", "created_at")),
    ("journey_steps", ("created_at",)),
    ("project_members", ("created_at", "updated_at")),
    ("project_states", ("created_at", "updated_at")),
    ("workspace_settings", ("created_at", "updated_at")),
)


def upgrade() -> None:
    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(column, existing_type=sa.DATETIME(), nullable=False)

    # New nullable columns need no batch mode.
    op.add_column("automation_runs", sa.Column("approval_status", sa.String(20), nullable=True))
    op.add_column("automations", sa.Column("schedule", sa.String(100), nullable=True))
    op.add_column("automations", sa.Column("retry_policy", sa.JSON(), nullable=True))

    # NOT NULL columns: backfill with a temporary default, then drop it in a
    # second batch so SQLite's table recreate has a value for existing rows.
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("campaign_type", sa.String(40), nullable=False,
                                   server_default="one_off"))
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("campaign_type", server_default=None)

    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("folder_id", sa.String(36), nullable=True))
        batch.create_index("ix_documents_folder_id", ["folder_id"], unique=False)
        batch.create_foreign_key("fk_documents_folder_id", "library_folders",
                                 ["folder_id"], ["id"])

    with op.batch_alter_table("experiments") as batch:
        batch.alter_column("baseline", existing_type=sa.FLOAT(), type_=sa.Double(),
                           existing_nullable=True)
        batch.alter_column("target", existing_type=sa.FLOAT(), type_=sa.Double(),
                           existing_nullable=True)

    with op.batch_alter_table("project_items") as batch:
        batch.add_column(sa.Column("parent_item_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("priority", sa.String(20), nullable=False,
                                   server_default="medium"))
        batch.add_column(sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("cycle_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
        batch.create_foreign_key("fk_project_items_parent", "project_items",
                                 ["parent_item_id"], ["id"])
        batch.create_foreign_key("fk_project_items_cycle", "project_cycles",
                                 ["cycle_id"], ["id"])
    with op.batch_alter_table("project_items") as batch:
        batch.alter_column("priority", server_default=None)
        batch.alter_column("tags", server_default=None)

    for name, col_type in (
        ("team_id", sa.String(36)),
        ("inbox_id", sa.String(36)),
        ("sla_policy_id", sa.String(36)),
        ("first_response_due_at", sa.DateTime(timezone=True)),
        ("resolution_due_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("support_tickets", sa.Column(name, col_type, nullable=True))
    with op.batch_alter_table("ticket_messages") as batch:
        batch.add_column(sa.Column("is_internal", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
    with op.batch_alter_table("ticket_messages") as batch:
        batch.alter_column("is_internal", server_default=None)

    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_index("ix_workspace_settings_workspace_id")
        batch.create_index("ix_workspace_settings_workspace_id", ["workspace_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_index("ix_workspace_settings_workspace_id")
        batch.create_index("ix_workspace_settings_workspace_id", ["workspace_id"], unique=False)

    with op.batch_alter_table("ticket_messages") as batch:
        batch.drop_column("is_internal")
    for name in ("resolution_due_at", "first_response_due_at", "sla_policy_id",
                 "inbox_id", "team_id"):
        op.drop_column("support_tickets", name)

    with op.batch_alter_table("project_items") as batch:
        batch.drop_constraint("fk_project_items_cycle", type_="foreignkey")
        batch.drop_constraint("fk_project_items_parent", type_="foreignkey")
        for name in ("tags", "cycle_id", "start_at", "priority", "description", "parent_item_id"):
            batch.drop_column(name)

    with op.batch_alter_table("experiments") as batch:
        batch.alter_column("target", existing_type=sa.Double(), type_=sa.FLOAT(),
                           existing_nullable=True)
        batch.alter_column("baseline", existing_type=sa.Double(), type_=sa.FLOAT(),
                           existing_nullable=True)

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_folder_id", type_="foreignkey")
        batch.drop_index("ix_documents_folder_id")
        batch.drop_column("folder_id")

    with op.batch_alter_table("campaigns") as batch:
        batch.drop_column("campaign_type")

    op.drop_column("automations", "retry_policy")
    op.drop_column("automations", "schedule")
    op.drop_column("automation_runs", "approval_status")

    for table, columns in TIMESTAMP_TABLES:
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(column, existing_type=sa.DATETIME(), nullable=True)
