"""Plane local background-task ledger P2/P3 (PL-073/076/078/081/082/083/084/086)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-11-24

Nine additive, workspace-scoped tables owned by the clean-room
``plane_task_ledger`` module. Existing job, project, page, storage and event
rows are referenced only by id; no existing table is altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plt_task_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "request_key", name="uq_plt_result_request"),
    )
    op.create_table(
        "plt_email_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("authorized_by", sa.String(36)),
        sa.Column("authorized_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", name="uq_plt_email_policy"),
    )
    op.create_table(
        "plt_email_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("dispatch_mode", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plt_webhook_endpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target_hint", sa.String(300), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("failures_before_success", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plt_webhook_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("endpoint_id", sa.String(36), sa.ForeignKey("plt_webhook_endpoints.id"), nullable=False, index=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("canonical_payload", sa.Text(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("algorithm", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("endpoint_id", "attempt", name="uq_plt_webhook_attempt"),
    )
    op.create_table(
        "plt_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("export_type", sa.String(30), nullable=False),
        sa.Column("export_format", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plt_page_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("project_pages.id"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("editor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("page_id", "version", name="uq_plt_page_version"),
    )
    op.create_table(
        "plt_asset_processings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("stored_files.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("file_id", name="uq_plt_asset_file"),
    )
    op.create_table(
        "plt_seed_defaults",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("seed_key", sa.String(80), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "seed_key", name="uq_plt_seed_key"),
    )


def downgrade() -> None:
    op.drop_table("plt_seed_defaults")
    op.drop_table("plt_asset_processings")
    op.drop_table("plt_page_versions")
    op.drop_table("plt_exports")
    op.drop_table("plt_webhook_deliveries")
    op.drop_table("plt_webhook_endpoints")
    op.drop_table("plt_email_drafts")
    op.drop_table("plt_email_policies")
    op.drop_table("plt_task_results")
