"""Papermark data-room governance P2/P3 (PM-050/057/058/059/060/061/062/064/065/066)

Revision ID: a7b8c9d0e1f2
Revises: e6f7a8b9c1d2
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "e6f7a8b9c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drg_room_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "room_id", name="uq_drg_room_setting"),
    )
    op.create_table(
        "drg_room_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "drg_room_folders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("drg_room_folders.id"), index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "room_id", "path", name="uq_drg_room_folder_path"),
    )
    op.create_table(
        "drg_room_item_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False, index=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "room_id", "item_type", "item_id", name="uq_drg_item_order"),
    )
    op.create_table(
        "drg_viewer_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "room_id", "name", name="uq_drg_viewer_group"),
    )
    op.create_table(
        "drg_group_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("drg_viewer_groups.id"), nullable=False, index=True),
        sa.Column("effect", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("include_subdomains", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "group_id", "effect", "kind", "value", name="uq_drg_group_rule"),
    )
    op.create_table(
        "drg_group_item_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("drg_viewer_groups.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("can_view", sa.Boolean(), nullable=False),
        sa.Column("can_download", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "group_id", "document_id", name="uq_drg_group_item"),
    )
    op.create_table(
        "drg_link_item_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("can_view", sa.Boolean(), nullable=False),
        sa.Column("can_download", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "link_id", "document_id", name="uq_drg_link_item"),
    )
    op.create_table(
        "drg_link_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("drg_viewer_groups.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "link_id", name="uq_drg_link_group"),
    )
    op.create_table(
        "drg_room_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, index=True, unique=True),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "room_id", "email", name="uq_drg_room_invite"),
    )
    op.create_table(
        "drg_access_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("data_rooms.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("drg_access_decisions")
    op.drop_table("drg_room_invitations")
    op.drop_table("drg_link_groups")
    op.drop_table("drg_link_item_permissions")
    op.drop_table("drg_group_item_permissions")
    op.drop_table("drg_group_rules")
    op.drop_table("drg_viewer_groups")
    op.drop_table("drg_room_item_orders")
    op.drop_table("drg_room_folders")
    op.drop_table("drg_room_events")
    op.drop_table("drg_room_settings")

