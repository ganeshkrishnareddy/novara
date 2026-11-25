"""Chatwoot help-centre governance P2/P3 (CW-066/067/087/088/089/090/091/092)

Revision ID: b7c8d9e0f1a2
Revises: a7b8c9d0e1f2
Create Date: 2026-11-24

Ten additive, workspace-scoped tables owned by the clean-room
``help_centre_governance`` module. Existing portal, article and document rows
are referenced only by id; no existing table is altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hcg_portal_branding",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("brand_name", sa.String(200), nullable=False),
        sa.Column("accent", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "portal_id", name="uq_hcg_portal_brand"),
    )
    op.create_table(
        "hcg_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portal_id", "slug", name="uq_hcg_category_slug"),
    )
    op.create_table(
        "hcg_article_meta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("support_help_articles.id"), nullable=False, index=True),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("embeds", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("article_id", name="uq_hcg_article_meta"),
    )
    op.create_table(
        "hcg_article_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("support_help_articles.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(300), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("article_id", "version", name="uq_hcg_revision"),
    )
    op.create_table(
        "hcg_article_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("support_help_articles.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("visitor_key", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "hcg_search_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("query", sa.String(300), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("visitor_key", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "hcg_page_visibility",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("support_help_articles.id"), nullable=False, index=True),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("allowed_group", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("article_id", name="uq_hcg_page_visibility"),
    )
    op.create_table(
        "hcg_widget_surfaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portal_id", name="uq_hcg_widget"),
    )
    op.create_table(
        "hcg_content_gaps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("portal_id", sa.String(36), sa.ForeignKey("support_help_portals.id"), nullable=False, index=True),
        sa.Column("query", sa.String(300), nullable=False),
        sa.Column("searches", sa.Integer(), nullable=False),
        sa.Column("zero_result_searches", sa.Integer(), nullable=False),
        sa.Column("advisory", sa.String(500), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portal_id", "query", name="uq_hcg_gap"),
    )
    op.create_table(
        "hcg_faq_index",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("support_help_articles.id"), index=True),
        sa.Column("citation", sa.JSON(), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "document_id", name="uq_hcg_faq_doc"),
    )


def downgrade() -> None:
    op.drop_table("hcg_faq_index")
    op.drop_table("hcg_content_gaps")
    op.drop_table("hcg_widget_surfaces")
    op.drop_table("hcg_page_visibility")
    op.drop_table("hcg_search_events")
    op.drop_table("hcg_article_views")
    op.drop_table("hcg_article_revisions")
    op.drop_table("hcg_article_meta")
    op.drop_table("hcg_categories")
    op.drop_table("hcg_portal_branding")
