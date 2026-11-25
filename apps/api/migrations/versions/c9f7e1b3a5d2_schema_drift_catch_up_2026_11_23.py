"""Schema drift catch-up (2026-11-23).

The earlier P1 revisions created the tables that existed when they were
generated. Later clean-room modules added the tables below before a matching
revision was generated, so a fresh Alembic database diverged from
``Base.metadata`` even though a local ``create_all`` database worked.

Each table is guarded with ``has_table``: local development databases that
already contain it converge without a destructive drop, and fresh databases
receive the real model definition including indexes and constraints.

Revision ID: c9f7e1b3a5d2
Revises: b8f4c2d6e0a3
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from novara_core.database import Base
from novara_core.modules import import_all

revision = "c9f7e1b3a5d2"
down_revision = "b8f4c2d6e0a3"
branch_labels = None
depends_on = None

TABLES = (
    "contact_field_definitions",
    "marketing_forms",
    "marketing_jobs",
    "marketing_report_definitions",
    "message_records",
    "scoring_rules",
    "stage_definitions",
    "topics",
    "webhook_subscriptions",
    "automation_payload_schemas",
    "digest_buckets",
    "marketing_job_runs",
    "message_failures",
    "scheduled_runs",
    "throttle_counters",
    "topic_subscriptions",
    "webhook_deliveries",
    "workflow_trigger_receipts",
    "channel_preferences",
    "channel_rules",
    "contact_anonymizations",
    "local_deliveries",
    "marketing_form_submissions",
    "sms_dnc_entries",
    "sms_replies",
    "stage_history",
    "workflow_delay_states",
    "workflow_run_steps",
    "score_changes",
    "workflow_message_links",
)


def _tables() -> dict:
    import_all()
    missing = [name for name in TABLES if name not in Base.metadata.tables]
    if missing:
        raise RuntimeError(f"Tables missing from Base.metadata: {missing}")
    return {name: Base.metadata.tables[name] for name in TABLES}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name, table in _tables().items():
        if not inspector.has_table(name):
            table.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name in reversed(TABLES):
        if inspector.has_table(name):
            op.drop_table(name)
