"""Clean-room GrowthBook SDK compatibility boundary (GB-148..GB-157)

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-11-24

One additive, workspace-scoped table owned by the clean-room
``growthbook_sdk_boundary`` module. No SDK package, provider endpoint, upstream
source or existing experiment/flag row is introduced or altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gbsdk_boundaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("sdk_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("ecosystem", sa.String(40), nullable=False),
        sa.Column("boundary", sa.String(80), nullable=False),
        sa.Column("adapter", sa.String(120), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("docs_reference", sa.Text(), nullable=False),
        sa.Column("notice_file", sa.String(120), nullable=False),
        sa.Column("default_dependency", sa.Boolean(), nullable=False),
        sa.Column("external_endpoint", sa.String(200)),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "sdk_id", name="uq_gbsdk_workspace_sdk"),
    )


def downgrade() -> None:
    op.drop_table("gbsdk_boundaries")
