"""Papermark share-link presentation and hardening P2 (PM-023/035/036/037/043/044/046/071)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-11-24

Ten additive, workspace-scoped tables owned by the clean-room
``share_link_presentation`` module. Existing document, link and data-room rows
are referenced only by id; no existing table is altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slp_share_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_slp_set_slug"),
    )
    op.create_table(
        "slp_share_set_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("share_set_id", sa.String(36), sa.ForeignKey("slp_share_sets.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("share_set_id", "document_id", name="uq_slp_set_item"),
    )
    op.create_table(
        "slp_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "domain", name="uq_slp_domain"),
    )
    op.create_table(
        "slp_link_slugs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("domain_id", sa.String(36), sa.ForeignKey("slp_domains.id"), nullable=False, index=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", name="uq_slp_slug_link"),
        sa.UniqueConstraint("domain_id", "slug", name="uq_slp_domain_slug"),
    )
    op.create_table(
        "slp_og_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", name="uq_slp_og_link"),
    )
    op.create_table(
        "slp_password_screens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", name="uq_slp_password_screen"),
    )
    op.create_table(
        "slp_screenshot_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("limitation", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", name="uq_slp_screenshot_config"),
    )
    op.create_table(
        "slp_screenshot_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("detected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "slp_watermark_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("document_links.id"), nullable=False, index=True),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("style", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", name="uq_slp_watermark_profile"),
    )
    op.create_table(
        "slp_branding_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "scope", "entity_type", "entity_id", name="uq_slp_branding_config"),
    )


def downgrade() -> None:
    op.drop_table("slp_branding_configs")
    op.drop_table("slp_watermark_profiles")
    op.drop_table("slp_screenshot_attempts")
    op.drop_table("slp_screenshot_configs")
    op.drop_table("slp_password_screens")
    op.drop_table("slp_og_metadata")
    op.drop_table("slp_link_slugs")
    op.drop_table("slp_domains")
    op.drop_table("slp_share_set_items")
    op.drop_table("slp_share_sets")
