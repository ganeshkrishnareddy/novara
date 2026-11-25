"""Visual automation builder: stored definitions plus real execution logs.

A definition is an ordered list of steps. The dry_run endpoint interprets those
steps against stored workspace records and appends an AutomationRun row; it
never sends a message, creates a CRM record, or performs any external action.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import NOTIFICATION_CREATED, publish_event, register_event_types
from ..models import (
    Company,
    Contact,
    Lead,
    Note,
    Notification,
    OutreachDraft,
    Task,
    WorkspaceMember,
    new_id,
    now,
)
from ..permissions import EVENT_READ, TASK_READ, TASK_WRITE, WORKSPACE_MANAGE

AUTOMATION_CREATED = "automation.created"
AUTOMATION_UPDATED = "automation.updated"
AUTOMATION_DELETED = "automation.deleted"
AUTOMATION_STATUS_CHANGED = "automation.status_changed"
AUTOMATION_RUN_RECORDED = "automation.run_recorded"
# Novu P1 local workflow events. Every name is registered here so the shared
# append-only event spine accepts it without a change to events.py.
WORKFLOW_TRIGGER_RECEIVED = "workflow.trigger_received"
WORKFLOW_STEP_RECORDED = "workflow.step_recorded"
WORKFLOW_DELAY_SCHEDULED = "workflow.delay_scheduled"
WORKFLOW_DELAY_RESUMED = "workflow.delay_resumed"
WORKFLOW_PAYLOAD_SCHEMA_UPDATED = "workflow.payload_schema_updated"
TOPIC_CREATED = "topic.created"
TOPIC_UPDATED = "topic.updated"
TOPIC_DELETED = "topic.deleted"
TOPIC_SUBSCRIPTION_CHANGED = "topic.subscription_changed"
DIGEST_EVENT_RECORDED = "digest.event_recorded"
DIGEST_FLUSHED = "digest.flushed"
THROTTLE_SKIPPED = "throttle.skipped"
SCHEDULED_RUN_CREATED = "workflow.scheduled"
SCHEDULED_RUN_FIRED = "workflow.scheduled_fired"
register_event_types(
    AUTOMATION_CREATED,
    AUTOMATION_UPDATED,
    AUTOMATION_DELETED,
    AUTOMATION_STATUS_CHANGED,
    AUTOMATION_RUN_RECORDED,
    WORKFLOW_TRIGGER_RECEIVED,
    WORKFLOW_STEP_RECORDED,
    WORKFLOW_DELAY_SCHEDULED,
    WORKFLOW_DELAY_RESUMED,
    WORKFLOW_PAYLOAD_SCHEMA_UPDATED,
    TOPIC_CREATED,
    TOPIC_UPDATED,
    TOPIC_DELETED,
    TOPIC_SUBSCRIPTION_CHANGED,
    DIGEST_EVENT_RECORDED,
    DIGEST_FLUSHED,
    THROTTLE_SKIPPED,
    SCHEDULED_RUN_CREATED,
    SCHEDULED_RUN_FIRED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/automations",
    tags=["automation"],
)

TRIGGER_TYPES = ("form_submission", "lead_qualified", "deal_won", "manual")
STEP_CHECKS = (
    "contact",
    "lead",
    "qualified_lead",
    "converted_lead",
    "company",
    "task",
    "note",
    "outreach_draft",
)
RUN_STATUSES = ("success", "failed", "skipped")
# NV-003 workspace limits. These are real, enforced request caps.
MAX_BULK_RECIPIENTS = 50
MAX_DIGEST_EVENTS_PER_WINDOW = 1000
MAX_THROTTLE_WINDOW_SECONDS = 86400
MAX_SCHEDULE_LEAD_SECONDS = 366 * 24 * 3600
PAYLOAD_TYPES = ("str", "int", "float", "bool", "list", "dict")
# Windows builds without the optional ``tzdata`` package cannot load the IANA
# database. These zones have a fixed UTC offset for future scheduling, so they
# can be honoured truthfully without pretending to model DST. Zones with DST
# still require a real tz database and are rejected when it is unavailable.
FIXED_OFFSET_ZONES = {
    "UTC": timedelta(0),
    "Etc/UTC": timedelta(0),
    "Asia/Kolkata": timedelta(hours=5, minutes=30),
    "Asia/Calcutta": timedelta(hours=5, minutes=30),
    "Asia/Shanghai": timedelta(hours=8),
    "Asia/Singapore": timedelta(hours=8),
    "Asia/Tokyo": timedelta(hours=9),
    "Australia/Perth": timedelta(hours=8),
    "America/Phoenix": timedelta(hours=-7),
}

CHECK_MODELS = {
    "contact": (Contact, "contact_id"),
    "lead": (Lead, "lead_id"),
    "qualified_lead": (Lead, "lead_id"),
    "converted_lead": (Lead, "lead_id"),
    "company": (Company, "company_id"),
    "task": (Task, "task_id"),
    "note": (Note, "note_id"),
    "outreach_draft": (OutreachDraft, "draft_id"),
}


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Automation(Base):
    __tablename__ = "automations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_automation_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    schedule: Mapped[str | None] = mapped_column(String(100))
    retry_policy: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    definition: Mapped[list] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    approval_status: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Novu P1 workflow tables. Each is owned by this module; the coordinator adds
# one consolidated migration for the new names reported in the hand-off.
# --------------------------------------------------------------------------


class TriggerReceipt(Base):
    """Idempotency ledger for bulk/topic triggers (NV-003, NV-004)."""

    __tablename__ = "workflow_trigger_receipts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_workflow_trigger_idem"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowRunStep(Base):
    """One real per-step outcome for a run (NV-008, NV-048, NV-106)."""

    __tablename__ = "workflow_run_steps"
    __table_args__ = (
        Index("ix_workflow_run_steps_run", "workspace_id", "run_id"),
        UniqueConstraint("run_id", "step_id", name="uq_workflow_run_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("automation_runs.id"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowDelayState(Base):
    """A paused run waiting for its configured resume time (NV-010)."""

    __tablename__ = "workflow_delay_states"
    __table_args__ = (UniqueConstraint("run_id", name="uq_workflow_delay_run"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("automation_runs.id"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remaining_steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationPayloadSchema(Base):
    """Per-workflow typed payload contract (NV-018)."""

    __tablename__ = "automation_payload_schemas"
    __table_args__ = (UniqueConstraint("automation_id", name="uq_automation_payload_schema"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False)
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Topic(Base):
    """Workspace-unique named subscriber group (NV-045)."""

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_topic_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TopicSubscription(Base):
    """Subscriber opt-in with payload/context conditions (NV-046)."""

    __tablename__ = "topic_subscriptions"
    __table_args__ = (UniqueConstraint("topic_id", "user_id", name="uq_topic_subscription_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    conditions: Mapped[dict | None] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DigestBucket(Base):
    """Collected events for one subscriber/group/window (NV-012)."""

    __tablename__ = "digest_buckets"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "automation_id", "subscriber_key", "group_key", "window_start",
            name="uq_digest_bucket",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False)
    subscriber_key: Mapped[str] = mapped_column(String(100), nullable=False)
    group_key: Mapped[str] = mapped_column(String(200), nullable=False, default="*")
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count: Mapped[int] = mapped_column(default=0, nullable=False)
    events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    flushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ThrottleCounter(Base):
    """Per-subscriber/group execution counter in a fixed window (NV-014)."""

    __tablename__ = "throttle_counters"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "automation_id", "subscriber_key", "group_key", "window_start",
            name="uq_throttle_counter",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False)
    subscriber_key: Mapped[str] = mapped_column(String(100), nullable=False)
    group_key: Mapped[str] = mapped_column(String(200), nullable=False, default="*")
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScheduledRun(Base):
    """Wall-clock scheduled workflow run with resolved time zone (NV-011)."""

    __tablename__ = "scheduled_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowMessageLink(Base):
    """Links a local in-app message to the workflow run that produced it."""

    __tablename__ = "workflow_message_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("automation_runs.id"), nullable=False, index=True)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="in_app")
    transaction_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


def _validate_definition(value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValueError("definition must be a non-empty list of steps")
    for index, step in enumerate(value):
        if not isinstance(step, dict):
            raise ValueError(f"step {index} must be an object")
        if not isinstance(step.get("id"), str) or not step["id"].strip():
            raise ValueError(f"step {index} requires a non-empty id")
        if not isinstance(step.get("type"), str) or not step["type"].strip():
            raise ValueError(f"step {index} requires a non-empty type")
        check = step.get("check")
        if check is not None and check not in STEP_CHECKS:
            raise ValueError(f"step {index} has an unsupported check: {check}")
    return value


class AutomationCreate(BaseModel):
    name: str
    trigger_type: Literal["form_submission", "lead_qualified", "deal_won", "manual", "scheduled", "event"]
    definition: list[dict[str, Any]]
    description: str | None = None
    schedule: str | None = None
    retry_policy: dict[str, Any] | None = None
    status: Literal["active", "paused"] = "active"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("definition")
    @classmethod
    def valid_definition(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _validate_definition(value)  # type: ignore[return-value]


class AutomationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: Literal["form_submission", "lead_qualified", "deal_won", "manual", "scheduled", "event"] | None = None
    schedule: str | None = None
    retry_policy: dict[str, Any] | None = None
    status: Literal["active", "paused"] | None = None
    definition: list[dict[str, Any]] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value.strip() if value is not None else None

    @field_validator("definition")
    @classmethod
    def valid_definition(cls, value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        return _validate_definition(value)


class StatusUpdate(BaseModel):
    status: Literal["active", "paused"]

    model_config = ConfigDict(extra="forbid")


class DryRunRequest(BaseModel):
    trigger_event: str = "manual"
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("trigger_event")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("trigger_event must not be blank")
        return value.strip()


class AutomationOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    trigger_type: str
    schedule: str | None
    retry_policy: dict[str, Any] | None
    status: str
    definition: list[dict[str, Any]]
    created_by: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class RunOut(BaseModel):
    id: str
    automation_id: str
    trigger_event: str
    status: str
    steps: list[dict[str, Any]]
    error: str | None
    started_at: object
    finished_at: object

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _automation_or_404(db: Session, workspace_id: str, automation_id: str) -> Automation:
    automation = db.execute(
        select(Automation).where(Automation.id == automation_id, Automation.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if automation is None:
        raise HTTPException(status_code=404, detail="automation not found")
    return automation


def _walk_steps(
    db: Session,
    workspace_id: str,
    definition: list[dict[str, Any]],
    context: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Evaluate each step against stored records. Read-only; returns a trace.

    Every step is evaluated with a fresh facts snapshot that includes the
    recorded outcomes of earlier steps under ``steps.<step_id>`` and, in order,
    under ``step_order``. A declarative condition can therefore gate a step on
    prior-step data without any expression parser or code execution (NV-008).
    """
    trace: list[dict[str, Any]] = []
    reasons: list[str] = []
    prior_steps: dict[str, dict[str, Any]] = {}
    step_order: list[dict[str, Any]] = []

    def record(item: dict[str, Any]) -> None:
        trace.append(item)
        summary: dict[str, Any] = {
            "id": item.get("id"),
            "result": item.get("result"),
            "matched": item.get("matched", 0),
            "reason": item.get("reason"),
        }
        prior_steps[str(item.get("id", ""))] = summary
        step_order.append(summary)

    for step in definition:
        facts: dict[str, Any] = dict(context or {})
        facts["steps"] = dict(prior_steps)
        facts["step_order"] = list(step_order)
        item: dict[str, Any] = {
            "id": step["id"],
            "type": step["type"],
            "result": "ok",
            "matched": 0,
            "reason": "step executed",
        }
        gate_reason: str | None = None
        # A step-level condition gates this step in a real run. Failed gates
        # produce an explicit skip trace with the evaluator's reason (NV-008).
        if "conditions" in step:
            passed, reason = evaluate_conditions(step.get("conditions"), facts)
            if not passed:
                item["result"] = "skipped"
                item["reason"] = reason
                record(item)
                reasons.append(f"step {step['id']}: {reason}")
                continue
            item["reason"] = reason
            gate_reason = reason
        step_type = step.get("type", "")
        # Conditional branch
        if step_type == "condition":
            # A declarative ``conditions`` tree already evaluated above is the
            # real reason this step ran; keep it in the stored trace instead of
            # replacing it with a generic legacy-condition message.
            if gate_reason is not None:
                item["matched"] = 1
                item["result"] = "ok"
                record(item)
                continue
            field = step.get("field")
            op = step.get("operator", "eq")
            expected = step.get("value")
            actual = facts.get(field)
            passed = False
            if op == "eq":
                passed = actual == expected
            elif op == "ne":
                passed = actual != expected
            elif op == "gt":
                passed = actual is not None and actual > expected
            elif op == "lt":
                passed = actual is not None and actual < expected
            elif op == "contains":
                passed = isinstance(actual, (list, str)) and expected in actual
            item["matched"] = 1 if passed else 0
            item["result"] = "ok" if passed else "skipped"
            item["reason"] = (
                f"condition {field} {op} {expected!r} passed"
                if passed else f"condition {field} {op} {expected!r} not met"
            )
            if not passed:
                reasons.append(f"step {step['id']}: {item['reason']}")
            record(item)
            continue
        # Delay
        if step_type == "delay":
            seconds = int(step.get("seconds", 0) or 0)
            item["delay_seconds"] = seconds
            item["result"] = "ok"
            record(item)
            continue
        # Human approval gate
        if step_type == "approval":
            item["approval_required"] = True
            item["result"] = "pending_approval"
            reasons.append(f"step {step['id']}: awaiting human approval")
            record(item)
            continue
        # Notification intent (no external send)
        if step_type == "notify":
            channel = step.get("channel", "in_app")
            item["channel"] = channel
            item["result"] = "queued"
            record(item)
            continue
        check = step.get("check")
        if check is None:
            item["result"] = "noop"
            record(item)
            continue
        model, id_key = CHECK_MODELS[check]
        query = select(func.count()).select_from(model).where(model.workspace_id == workspace_id)
        target_id = step.get("target_id") or step.get(id_key) or context.get(id_key)
        if target_id:
            if not isinstance(target_id, str):
                target_id = str(target_id)
            query = query.where(model.id == target_id)
            item["target_id"] = target_id
        if check == "qualified_lead":
            query = query.where(Lead.status == "qualified")
        elif check == "converted_lead":
            query = query.where(Lead.status == "converted")
        filters = step.get("filters")
        if filters is not None and not isinstance(filters, dict):
            reasons.append(f"step {step['id']}: filters must be an object")
            item["result"] = "skipped"
            record(item)
            continue
        for field, value in (filters or {}).items():
            if isinstance(field, str) and hasattr(model, field):
                query = query.where(getattr(model, field) == value)
        count = int(db.execute(query).scalar() or 0)
        item["matched"] = count
        if count == 0:
            item["result"] = "skipped"
            reasons.append(f"step {step['id']}: no matching {check}")
        record(item)
    return trace, reasons


# --------------------------------------------------------------------------
# Declarative workflow helpers (pure, no I/O unless a db is passed).
# --------------------------------------------------------------------------


def _field_value(facts: dict, field: str) -> tuple[Any, bool]:
    """Resolve a dotted field path against nested facts without eval."""
    current: Any = facts
    for part in str(field).split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True


def evaluate_conditions(condition: dict | None, facts: dict) -> tuple[bool, str]:
    """Evaluate a nested AND/OR/NOT rule tree over subscriber/payload/step facts.

    There is no expression parser and no ``eval``: only the declared operators
    are honoured, so a stored rule cannot execute code or read secrets.
    """
    if not condition:
        return True, "no conditions"
    if not isinstance(condition, dict):
        return False, "condition must be an object"
    if "all" in condition:
        children = condition["all"]
        if not isinstance(children, list) or not children:
            return True, "empty all group"
        reasons = []
        for child in children:
            passed, reason = evaluate_conditions(child, facts)
            reasons.append(reason)
            if not passed:
                return False, "all group failed: " + reason
        return True, "all group matched (" + "; ".join(reasons) + ")"
    if "any" in condition:
        children = condition["any"]
        if not isinstance(children, list) or not children:
            return False, "empty any group"
        reasons = []
        for child in children:
            passed, reason = evaluate_conditions(child, facts)
            reasons.append(reason)
            if passed:
                return True, "any group matched: " + reason
        return False, "any group failed (" + "; ".join(reasons) + ")"
    if "not" in condition:
        passed, reason = evaluate_conditions(condition["not"], facts)
        return (not passed), f"negation {'failed' if passed else 'matched'}: {reason}"

    field = condition.get("field")
    if not isinstance(field, str) or not field:
        return False, "condition requires a field"
    actual, found = _field_value(facts, field)
    op = str(condition.get("op", condition.get("operator", "eq"))).lower()
    expected = condition.get("value")
    passed = False
    if op == "exists":
        passed = found
    elif op == "eq":
        passed = found and actual == expected
    elif op == "ne":
        passed = (not found) or actual != expected
    elif op in {"gt", "gte", "lt", "lte"}:
        if found and isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            passed = {
                "gt": actual > expected,
                "gte": actual >= expected,
                "lt": actual < expected,
                "lte": actual <= expected,
            }[op]
    elif op == "in":
        passed = found and isinstance(expected, (list, tuple, set)) and actual in expected
    elif op == "contains":
        passed = found and isinstance(actual, (list, tuple, str, dict)) and expected in actual
    else:
        return False, f"unsupported operator: {op}"
    verb = "matched" if passed else "not met"
    return passed, f"{field} {op} {expected!r} {verb}"


def validate_payload(fields: dict, payload: dict) -> list[str]:
    """Validate a trigger payload against a stored per-workflow contract."""
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    if not isinstance(fields, dict):
        return ["schema fields must be an object"]
    for name, spec in fields.items():
        if not isinstance(spec, dict):
            errors.append(f"{name}: invalid field specification")
            continue
        if name not in payload:
            if spec.get("required", False):
                errors.append(f"{name}: required")
            continue
        value = payload[name]
        expected = spec.get("type")
        type_ok = {
            "str": lambda v: isinstance(v, str),
            "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "bool": lambda v: isinstance(v, bool),
            "list": lambda v: isinstance(v, list),
            "dict": lambda v: isinstance(v, dict),
        }.get(expected)
        if expected is not None and type_ok is None:
            errors.append(f"{name}: unsupported type {expected!r}")
        elif expected is not None and not type_ok(value):  # type: ignore[operator]
            errors.append(f"{name}: expected {expected}")
        allowed = spec.get("allowed")
        if allowed is not None and value not in allowed:
            errors.append(f"{name}: value is not allowed")
    unknown = sorted(set(payload) - set(fields))
    if unknown:
        errors.append("unexpected fields: " + ", ".join(unknown))
    return errors


def _as_utc(moment: datetime) -> datetime:
    """Normalize SQLite-naive and provider-aware timestamps to aware UTC."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _resolve_zone(tz_name: str):
    """Load a real IANA zone, or a documented fixed-offset fallback."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        offset = FIXED_OFFSET_ZONES.get(tz_name)
        if offset is None:
            raise ValueError(f"unknown timezone: {tz_name}") from None
        return timezone(offset)


def resolve_schedule(schedule: dict, base: datetime, tz_name: str = "UTC") -> datetime:
    """Resolve a wall-clock schedule in a subscriber time zone to an aware UTC time."""
    if not isinstance(schedule, dict) or not schedule:
        raise ValueError("schedule must be a non-empty object")
    zone = _resolve_zone(tz_name)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    local = base.astimezone(zone)

    cadence = str(schedule.get("cadence", "minute")).lower()
    every = schedule.get("every_minutes")
    if every is not None:
        if not isinstance(every, int) or isinstance(every, bool) or every < 1 or every > 1440:
            raise ValueError("every_minutes must be between 1 and 1440")
        candidate = local.replace(second=0, microsecond=0) + timedelta(minutes=every)
        return candidate.astimezone(timezone.utc)

    hour = int(schedule.get("hour", local.hour))
    minute = int(schedule.get("minute", local.minute))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("hour and minute are outside their valid range")

    candidate: datetime | None = None
    if cadence == "minute":
        candidate = local.replace(second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(minutes=1)
    elif cadence == "hour":
        candidate = local.replace(minute=minute, second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(hours=1)
    elif cadence == "day":
        for offset in range(0, 3):
            probe = (local + timedelta(days=offset)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if probe > local:
                candidate = probe
                break
    elif cadence == "week":
        weekday = int(schedule.get("weekday", local.weekday()))
        if not 0 <= weekday <= 6:
            raise ValueError("weekday must be between 0 and 6")
        for offset in range(0, 14):
            probe_day = local + timedelta(days=offset)
            if probe_day.weekday() != weekday:
                continue
            probe = probe_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if probe > local:
                candidate = probe
                break
    elif cadence == "month":
        day = int(schedule.get("day", local.day))
        if not 1 <= day <= 31:
            raise ValueError("day must be between 1 and 31")
        year, month = local.year, local.month
        for _ in range(0, 14):
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            probe = local.replace(year=year, month=month, day=min(day, last_day),
                                  hour=hour, minute=minute, second=0, microsecond=0)
            if probe > local:
                candidate = probe
                break
            month += 1
            if month > 12:
                month, year = 1, year + 1
    else:
        raise ValueError(f"unsupported cadence: {cadence}")
    if candidate is None:
        raise ValueError("no future slot could be resolved for this schedule")
    return candidate.astimezone(timezone.utc)


def _window_bounds(moment: datetime, window_seconds: int) -> tuple[datetime, datetime]:
    """Fixed, deterministic epoch-aligned window used by digest and throttle."""
    if not isinstance(window_seconds, int) or window_seconds < 1:
        raise ValueError("window_seconds must be a positive integer")
    epoch = moment.timestamp()
    start_epoch = (int(epoch) // window_seconds) * window_seconds
    return (
        datetime.fromtimestamp(start_epoch, tz=timezone.utc),
        datetime.fromtimestamp(start_epoch + window_seconds, tz=timezone.utc),
    )


def _facts_for(user_id: str, payload: dict | None, context: dict | None) -> dict:
    facts: dict[str, Any] = {"subscriber": {"id": user_id}}
    facts.update(context or {})
    facts["payload"] = payload or {}
    for key, value in (payload or {}).items():
        facts.setdefault(key, value)
    return facts


def _run_or_404(db: Session, workspace_id: str, automation_id: str, run_id: str) -> AutomationRun:
    run = db.execute(
        select(AutomationRun).where(
            AutomationRun.id == run_id,
            AutomationRun.workspace_id == workspace_id,
            AutomationRun.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _record_step(
    db: Session, workspace_id: str, run: AutomationRun, item: dict, correlation_id: str
) -> WorkflowRunStep:
    # Guarantee a strictly increasing trace order even when several steps are
    # recorded inside the same clock tick; UUID ordering is not definition order.
    latest = db.execute(
        select(func.max(WorkflowRunStep.occurred_at)).where(
            WorkflowRunStep.workspace_id == workspace_id,
            WorkflowRunStep.run_id == run.id,
        )
    ).scalar()
    stamp = now()
    if latest is not None:
        latest_utc = _as_utc(latest)
        if stamp <= latest_utc:
            stamp = latest_utc + timedelta(microseconds=1)
    row = WorkflowRunStep(
        id=new_id(),
        workspace_id=workspace_id,
        run_id=run.id,
        correlation_id=correlation_id,
        step_id=str(item.get("id", "")),
        step_type=str(item.get("type", "")),
        outcome=str(item.get("result", "ok")),
        reason=str(item.get("reason") or ""),
        detail=item,
        occurred_at=stamp,
    )
    db.add(row)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=WORKFLOW_STEP_RECORDED,
        entity_id=run.id,
        payload={"step_id": row.step_id, "outcome": row.outcome, "reason": row.reason},
        correlation_id=correlation_id,
    )
    return row


def _create_message(
    db: Session,
    *,
    workspace_id: str,
    user_id: str,
    run: AutomationRun,
    message: str,
    transaction_id: str,
    correlation_id: str,
) -> Notification:
    """Create a real local in-app message and link it to its workflow run."""
    notification = Notification(
        id=new_id(),
        workspace_id=workspace_id,
        user_id=user_id,
        title="Workflow notification",
        message=message[:500],
        category="workflow",
        read=False,
        seen=False,
        created_at=now(),
    )
    db.add(notification)
    db.flush()
    db.add(
        WorkflowMessageLink(
            id=new_id(),
            workspace_id=workspace_id,
            run_id=run.id,
            notification_id=notification.id,
            channel="in_app",
            transaction_id=transaction_id,
            correlation_id=correlation_id,
            created_at=now(),
        )
    )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=NOTIFICATION_CREATED,
        entity_id=notification.id,
        payload={"category": "workflow", "transaction_id": transaction_id},
        correlation_id=correlation_id,
    )
    return notification


def _active_member(db: Session, workspace_id: str, user_id: str) -> bool:
    return db.execute(
        select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none() is not None


def _schema_errors(db: Session, workspace_id: str, automation_id: str, payload: dict) -> list[str]:
    schema = db.execute(
        select(AutomationPayloadSchema).where(
            AutomationPayloadSchema.workspace_id == workspace_id,
            AutomationPayloadSchema.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if schema is None:
        return []
    return validate_payload(schema.fields, payload)


def _new_run(
    db: Session,
    *,
    workspace_id: str,
    automation: Automation,
    user_id: str,
    trigger_event: str,
    correlation_id: str | None = None,
) -> AutomationRun:
    run = AutomationRun(
        id=new_id(),
        workspace_id=workspace_id,
        automation_id=automation.id,
        trigger_event=trigger_event,
        status="success",
        steps=[],
        error=None,
        started_at=now(),
        finished_at=now(),
    )
    db.add(run)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=WORKFLOW_TRIGGER_RECEIVED,
        entity_id=run.id,
        payload={
            "automation_id": automation.id,
            "user_id": user_id,
            "trigger_event": trigger_event,
        },
        correlation_id=correlation_id or run.id,
    )
    return run


def _walk_and_record(
    db: Session,
    *,
    workspace_id: str,
    automation: Automation,
    run: AutomationRun,
    definition: list[dict[str, Any]],
    facts: dict,
    correlation_id: str,
) -> tuple[list[dict], list[str]]:
    trace, reasons = _walk_steps(db, workspace_id, definition, facts)
    for item in trace:
        _record_step(db, workspace_id, run, item, correlation_id)
    return trace, reasons


# --------------------------------------------------------------------------
# Automation endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[AutomationOut])
def list_automations(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[Automation]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Automation).where(Automation.workspace_id == workspace_id).order_by(Automation.created_at.desc())
    ).scalars().all()


@router.post("", response_model=AutomationOut, status_code=status.HTTP_201_CREATED)
def create_automation(
    workspace_id: str,
    body: AutomationCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Automation:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Automation).where(Automation.workspace_id == workspace_id, Automation.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="an automation with this name already exists")
    automation = Automation(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        schedule=body.schedule,
        retry_policy=body.retry_policy,
        status=body.status,
        definition=body.definition,
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(automation)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AUTOMATION_CREATED,
        entity_id=automation.id,
        payload={"name": automation.name, "trigger_type": automation.trigger_type},
        actor_id=principal.user.id,
    )
    db.commit()
    return automation


@router.get("/{automation_id}", response_model=AutomationOut)
def get_automation(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> Automation:
    verify_workspace(principal, workspace_id)
    return _automation_or_404(db, workspace_id, automation_id)


@router.patch("/{automation_id}", response_model=AutomationOut)
def update_automation(
    workspace_id: str,
    automation_id: str,
    body: AutomationUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Automation:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != automation.name:
        duplicate = db.execute(
            select(Automation).where(
                Automation.workspace_id == workspace_id,
                Automation.name == updates["name"],
                Automation.id != automation.id,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="an automation with this name already exists")
    previous_status = automation.status
    for key, value in updates.items():
        setattr(automation, key, value)
    automation.updated_at = now()
    db.flush()
    if updates.get("status") is not None and updates["status"] != previous_status:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=AUTOMATION_STATUS_CHANGED,
            entity_id=automation.id,
            payload={"from": previous_status, "to": automation.status},
            actor_id=principal.user.id,
        )
    else:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=AUTOMATION_UPDATED,
            entity_id=automation.id,
            payload={"fields": sorted(updates.keys())},
            actor_id=principal.user.id,
        )
    db.commit()
    return automation


@router.delete("/{automation_id}")
def delete_automation(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AUTOMATION_DELETED,
        entity_id=automation.id,
        payload={"name": automation.name},
        actor_id=principal.user.id,
    )
    db.delete(automation)
    db.commit()
    return {"deleted": True, "automation_id": automation.id}


@router.post("/{automation_id}/status", response_model=AutomationOut)
def change_status(
    workspace_id: str,
    automation_id: str,
    body: StatusUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Automation:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    previous_status = automation.status
    automation.status = body.status
    automation.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AUTOMATION_STATUS_CHANGED,
        entity_id=automation.id,
        payload={"from": previous_status, "to": automation.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return automation


@router.post("/{automation_id}/dry_run", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def dry_run(
    workspace_id: str,
    automation_id: str,
    body: DryRunRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> AutomationRun:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    started_at = now()
    trace, reasons = _walk_steps(db, workspace_id, automation.definition, body.context)
    if automation.status == "paused":
        reasons.append("automation is paused")
    run_status = "skipped" if reasons else "success"
    run = AutomationRun(
        id=new_id(),
        workspace_id=workspace_id,
        automation_id=automation.id,
        trigger_event=body.trigger_event,
        status=run_status,
        steps=trace,
        error="; ".join(reasons) if reasons else None,
        started_at=started_at,
        finished_at=now(),
    )
    db.add(run)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AUTOMATION_RUN_RECORDED,
        entity_id=run.id,
        payload={"automation_id": automation.id, "status": run.status, "steps": len(trace)},
        actor_id=principal.user.id,
    )
    db.commit()
    return run


# --------------------------------------------------------------------------
# Novu P1 request/response schemas
# --------------------------------------------------------------------------


def _nonblank(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be blank")
    return value.strip()


class PayloadSchemaRequest(BaseModel):
    fields: dict[str, dict]

    model_config = ConfigDict(extra="forbid")

    @field_validator("fields")
    @classmethod
    def fields_valid(cls, value: dict[str, dict]) -> dict[str, dict]:
        if not value:
            raise ValueError("fields must not be empty")
        for name, spec in value.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("field names must not be blank")
            if spec.get("type") not in PAYLOAD_TYPES:
                raise ValueError(f"field {name} has an unsupported type")
            if not isinstance(spec.get("required", False), bool):
                raise ValueError(f"field {name} required must be a boolean")
        return value


class PayloadSchemaOut(BaseModel):
    automation_id: str
    fields: dict[str, dict]
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class TriggerBase(BaseModel):
    payload: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    idempotency_key: str
    message: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("idempotency_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "idempotency_key")


class BulkTriggerRequest(TriggerBase):
    recipients: list[str]

    @field_validator("idempotency_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "idempotency_key")

    @field_validator("recipients")
    @classmethod
    def recipients_valid(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("recipients must not be empty")
        if len(value) > MAX_BULK_RECIPIENTS:
            raise ValueError(f"at most {MAX_BULK_RECIPIENTS} recipients are allowed per request")
        cleaned = [_nonblank(item, "recipient") for item in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("recipients must be unique")
        return cleaned


class TriggerOut(BaseModel):
    idempotency_key: str
    kind: str
    count: int
    runs: list[dict]
    replayed: bool = False

    model_config = ConfigDict(extra="forbid")


class TopicTriggerRequest(TriggerBase):
    topic_key: str
    exclude_actor: bool = True

    @field_validator("topic_key")
    @classmethod
    def topic_valid(cls, value: str) -> str:
        return _nonblank(value, "topic_key")


class TopicCreate(BaseModel):
    key: str
    name: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "key")

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str) -> str:
        return _nonblank(value, "name")


class TopicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class TopicOut(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    created_by: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class SubscriptionCreate(BaseModel):
    user_id: str
    conditions: dict | None = None
    context: dict = Field(default_factory=dict)
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("user_id")
    @classmethod
    def user_valid(cls, value: str) -> str:
        return _nonblank(value, "user_id")


class SubscriptionUpdate(BaseModel):
    conditions: dict | None = None
    context: dict | None = None
    enabled: bool | None = None

    model_config = ConfigDict(extra="forbid")


class SubscriptionOut(BaseModel):
    id: str
    topic_id: str
    user_id: str
    conditions: dict | None
    context: dict
    enabled: bool
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class DigestRequest(BaseModel):
    user_id: str
    payload: dict = Field(default_factory=dict)
    group_key: str = "*"
    window_seconds: int = Field(default=3600, ge=1, le=86400)
    idempotency_key: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("idempotency_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "idempotency_key")

    @field_validator("user_id")
    @classmethod
    def user_valid(cls, value: str) -> str:
        return _nonblank(value, "user_id")


class DigestBucketOut(BaseModel):
    id: str
    automation_id: str
    subscriber_key: str
    group_key: str
    window_start: object
    window_end: object
    event_count: int
    status: str
    correlation_id: str

    model_config = ConfigDict(from_attributes=True)


class ThrottleRequest(BaseModel):
    user_id: str
    payload: dict = Field(default_factory=dict)
    group_key: str = "*"
    max_events: int = Field(default=1, ge=1, le=1000)
    window_seconds: int = Field(default=3600, ge=1, le=MAX_THROTTLE_WINDOW_SECONDS)
    message: str = "Throttled workflow message"
    idempotency_key: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("idempotency_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "idempotency_key")

    @field_validator("user_id")
    @classmethod
    def user_valid(cls, value: str) -> str:
        return _nonblank(value, "user_id")


class ThrottleOut(BaseModel):
    run_id: str
    outcome: str
    count: int
    max_events: int
    window_start: object
    window_end: object
    reason: str
    message_created: bool

    model_config = ConfigDict(extra="forbid")


class ScheduleRequest(BaseModel):
    user_id: str
    schedule: dict
    timezone: str = "UTC"
    payload: dict = Field(default_factory=dict)
    message: str = "Scheduled workflow notification"
    idempotency_key: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("idempotency_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return _nonblank(value, "idempotency_key")

    @field_validator("user_id")
    @classmethod
    def user_valid(cls, value: str) -> str:
        return _nonblank(value, "user_id")


class ScheduledRunOut(BaseModel):
    id: str
    automation_id: str
    user_id: str
    schedule: dict
    timezone: str
    fire_at: object
    payload: dict
    status: str
    correlation_id: str

    model_config = ConfigDict(from_attributes=True)


class RunTimelineEntry(BaseModel):
    step_id: str
    step_type: str
    outcome: str
    reason: str
    occurred_at: object


class RunTimelineOut(BaseModel):
    run_id: str
    automation_id: str
    status: str
    trigger_event: str
    correlation_id: str
    steps: list[RunTimelineEntry]
    messages: list[dict]


# --------------------------------------------------------------------------
# Workflow helpers for real runs
# --------------------------------------------------------------------------


def _finish_run(run: AutomationRun, trace: list[dict], reasons: list[str]) -> None:
    run.steps = trace
    run.status = "skipped" if reasons else "success"
    run.error = "; ".join(reasons) if reasons else None
    run.finished_at = now()


def _delay_fire_at(step: dict, facts: dict) -> datetime:
    """Resolve a delay step to a concrete future instant.

    Supported forms are a fixed ``seconds`` interval, a payload-derived
    ``seconds_field``, a wall-clock ``fire_at`` timestamp (optionally from
    ``fire_at_field``) and a calendar ``schedule`` with a ``timezone``. Every
    form is validated; no timer is started until the run is actually paused.
    """
    start = now()
    target: datetime | None = None
    raw_timestamp = step.get("fire_at")
    timestamp_field = step.get("fire_at_field") or step.get("timestamp_field")
    if timestamp_field:
        value, found = _field_value(facts, timestamp_field)
        if not found:
            raise HTTPException(status_code=422, detail=f"delay field not found: {timestamp_field}")
        raw_timestamp = value
    if raw_timestamp is not None:
        if not isinstance(raw_timestamp, str):
            raise HTTPException(status_code=422, detail="delay timestamp must be an ISO string")
        try:
            target = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="delay timestamp is not valid ISO 8601") from exc
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        seconds = (_as_utc(target) - _as_utc(start)).total_seconds()
    elif step.get("schedule"):
        try:
            target = resolve_schedule(step["schedule"], start, step.get("timezone", "UTC"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        seconds = (_as_utc(target) - _as_utc(start)).total_seconds()
    else:
        seconds_field = step.get("seconds_field") or step.get("seconds_path")
        if seconds_field:
            value, found = _field_value(facts, seconds_field)
            if not found:
                raise HTTPException(status_code=422, detail=f"delay field not found: {seconds_field}")
        else:
            value = step.get("seconds", 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail="delay seconds must be a number")
        seconds = float(value)
    if seconds < 1:
        raise HTTPException(status_code=422, detail="delay must resolve to a future instant")
    # Preserve the exact configured instant; truncating to whole seconds could
    # resume an explicit timestamp or wall-clock slot just before it arrived.
    if target is not None:
        return _as_utc(target)
    return _as_utc(start) + timedelta(seconds=seconds)


def _apply_definition(
    db: Session,
    *,
    workspace_id: str,
    automation: Automation,
    run: AutomationRun,
    facts: dict,
    correlation_id: str,
) -> str:
    """Execute a definition, pausing at the first delay step if present."""
    definition = automation.definition
    delay_index = next(
        (index for index, step in enumerate(definition) if step.get("type") == "delay"), None
    )
    if delay_index is None:
        trace, reasons = _walk_and_record(
            db, workspace_id=workspace_id, automation=automation, run=run,
            definition=definition, facts=facts, correlation_id=correlation_id,
        )
        _finish_run(run, trace, reasons)
        return "completed"
    before = definition[:delay_index]
    delay_step = definition[delay_index]
    after = definition[delay_index + 1 :]
    fire_at = _delay_fire_at(delay_step, facts)
    seconds = int((fire_at - now()).total_seconds())
    trace, reasons = _walk_and_record(
        db, workspace_id=workspace_id, automation=automation, run=run,
        definition=before, facts=facts, correlation_id=correlation_id,
    )
    db.add(
        WorkflowDelayState(
            id=new_id(), workspace_id=workspace_id, run_id=run.id,
            correlation_id=correlation_id, fire_at=fire_at, remaining_steps=after,
            context=facts, status="waiting", created_at=now(),
        )
    )
    run.steps = trace
    run.status = "delayed"
    run.error = "; ".join(reasons) if reasons else None
    publish_event(
        db, workspace_id=workspace_id, event_type=WORKFLOW_DELAY_SCHEDULED,
        entity_id=run.id, payload={"fire_at": fire_at.isoformat(), "seconds": seconds},
        correlation_id=correlation_id,
    )
    return "delayed"


def _receipt_or_create(
    db: Session,
    *,
    workspace_id: str,
    automation: Automation,
    kind: str,
    idempotency_key: str,
    actor_id: str,
) -> tuple[TriggerReceipt | None, dict | None]:
    existing = db.execute(
        select(TriggerReceipt).where(
            TriggerReceipt.workspace_id == workspace_id,
            TriggerReceipt.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, existing.result
    receipt = TriggerReceipt(
        id=new_id(), workspace_id=workspace_id, idempotency_key=idempotency_key,
        kind=kind, automation_id=automation.id, actor_id=actor_id, result={}, created_at=now(),
    )
    db.add(receipt)
    db.flush()
    return receipt, None


# --------------------------------------------------------------------------
# Per-workflow payload schema (NV-018)
# --------------------------------------------------------------------------


@router.put("/{automation_id}/payload_schema", response_model=PayloadSchemaOut)
def put_payload_schema(
    workspace_id: str,
    automation_id: str,
    body: PayloadSchemaRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> AutomationPayloadSchema:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    schema = db.execute(
        select(AutomationPayloadSchema).where(
            AutomationPayloadSchema.workspace_id == workspace_id,
            AutomationPayloadSchema.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if schema is None:
        schema = AutomationPayloadSchema(
            id=new_id(), workspace_id=workspace_id, automation_id=automation_id,
            fields=body.fields, created_at=now(), updated_at=now(),
        )
        db.add(schema)
    else:
        schema.fields = body.fields
        schema.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=WORKFLOW_PAYLOAD_SCHEMA_UPDATED,
        entity_id=automation_id, payload={"fields": sorted(body.fields)},
        actor_id=principal.user.id,
    )
    db.commit()
    return schema


@router.get("/{automation_id}/payload_schema", response_model=PayloadSchemaOut)
def get_payload_schema(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> AutomationPayloadSchema:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    schema = db.execute(
        select(AutomationPayloadSchema).where(
            AutomationPayloadSchema.workspace_id == workspace_id,
            AutomationPayloadSchema.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if schema is None:
        raise HTTPException(status_code=404, detail="payload schema not found")
    return schema


# --------------------------------------------------------------------------
# Bulk trigger (NV-003) and topic fan-out (NV-004)
# --------------------------------------------------------------------------


@router.post("/{automation_id}/bulk_trigger", response_model=TriggerOut)
def bulk_trigger(
    workspace_id: str,
    automation_id: str,
    body: BulkTriggerRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> TriggerOut:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    errors = _schema_errors(db, workspace_id, automation_id, body.payload)
    if errors:
        raise HTTPException(status_code=422, detail={"payload_errors": errors})
    for user_id in body.recipients:
        if not _active_member(db, workspace_id, user_id):
            raise HTTPException(status_code=422, detail=f"recipient is not an active member: {user_id}")
    receipt, replay = _receipt_or_create(
        db, workspace_id=workspace_id, automation=automation, kind="bulk",
        idempotency_key=body.idempotency_key, actor_id=principal.user.id,
    )
    if replay is not None:
        return TriggerOut(**replay, replayed=True)
    correlation_id = new_id()
    runs = []
    for index, user_id in enumerate(body.recipients):
        run = _new_run(
            db, workspace_id=workspace_id, automation=automation, user_id=user_id,
            trigger_event="bulk", correlation_id=correlation_id,
        )
        facts = _facts_for(user_id, body.payload, body.context)
        outcome = _apply_definition(
            db, workspace_id=workspace_id, automation=automation, run=run,
            facts=facts, correlation_id=correlation_id,
        )
        if body.message:
            _create_message(
                db, workspace_id=workspace_id, user_id=user_id, run=run,
                message=body.message, transaction_id=f"bulk:{body.idempotency_key}:{index}",
                correlation_id=correlation_id,
            )
        runs.append({"run_id": run.id, "user_id": user_id, "status": run.status, "outcome": outcome})
    result = {
        "idempotency_key": body.idempotency_key, "kind": "bulk",
        "count": len(runs), "runs": runs,
    }
    receipt.result = result
    db.flush()
    db.commit()
    return TriggerOut(**result)


@router.post("/{automation_id}/topic_trigger", response_model=TriggerOut)
def topic_trigger(
    workspace_id: str,
    automation_id: str,
    body: TopicTriggerRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> TriggerOut:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    topic = db.execute(
        select(Topic).where(Topic.workspace_id == workspace_id, Topic.key == body.topic_key)
    ).scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")
    errors = _schema_errors(db, workspace_id, automation_id, body.payload)
    if errors:
        raise HTTPException(status_code=422, detail={"payload_errors": errors})
    receipt, replay = _receipt_or_create(
        db, workspace_id=workspace_id, automation=automation, kind="topic",
        idempotency_key=body.idempotency_key, actor_id=principal.user.id,
    )
    if replay is not None:
        return TriggerOut(**replay, replayed=True)
    subscriptions = db.execute(
        select(TopicSubscription).where(
            TopicSubscription.workspace_id == workspace_id,
            TopicSubscription.topic_id == topic.id,
            TopicSubscription.enabled.is_(True),
        )
    ).scalars().all()
    correlation_id = new_id()
    runs = []
    for subscription in subscriptions:
        if body.exclude_actor and subscription.user_id == principal.user.id:
            continue
        if not _active_member(db, workspace_id, subscription.user_id):
            continue
        facts = _facts_for(subscription.user_id, body.payload, body.context)
        # Exact-match per-tenant scope: a subscription context key must equal
        # the same key in the trigger context or payload.
        scope_ok = all(
            facts.get(key) == value or (body.context or {}).get(key) == value
            for key, value in (subscription.context or {}).items()
        )
        matched, _ = evaluate_conditions(subscription.conditions, facts)
        if not (scope_ok and matched):
            continue
        run = _new_run(
            db, workspace_id=workspace_id, automation=automation,
            user_id=subscription.user_id, trigger_event="topic", correlation_id=correlation_id,
        )
        _apply_definition(
            db, workspace_id=workspace_id, automation=automation, run=run,
            facts=facts, correlation_id=correlation_id,
        )
        if body.message:
            _create_message(
                db, workspace_id=workspace_id, user_id=subscription.user_id, run=run,
                message=body.message,
                transaction_id=f"topic:{body.idempotency_key}:{subscription.user_id}",
                correlation_id=correlation_id,
            )
        runs.append({"run_id": run.id, "user_id": subscription.user_id, "status": run.status})
    result = {
        "idempotency_key": body.idempotency_key, "kind": "topic",
        "count": len(runs), "runs": runs,
    }
    receipt.result = result
    db.flush()
    db.commit()
    return TriggerOut(**result)


# --------------------------------------------------------------------------
# Delay resume and run timeline (NV-010, NV-048, NV-106)
# --------------------------------------------------------------------------


@router.post("/{automation_id}/runs/{run_id}/resume", response_model=RunOut)
def resume_delayed_run(
    workspace_id: str,
    automation_id: str,
    run_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> AutomationRun:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    run = _run_or_404(db, workspace_id, automation_id, run_id)
    delay = db.execute(
        select(WorkflowDelayState).where(
            WorkflowDelayState.workspace_id == workspace_id,
            WorkflowDelayState.run_id == run.id,
        )
    ).scalar_one_or_none()
    if delay is None:
        raise HTTPException(status_code=404, detail="delayed run state not found")
    if delay.status != "waiting":
        raise HTTPException(status_code=409, detail="delayed run has already resumed")
    current = now()
    if _as_utc(current) < _as_utc(delay.fire_at):
        raise HTTPException(status_code=409, detail="delay has not elapsed")
    trace, reasons = _walk_and_record(
        db, workspace_id=workspace_id, automation=automation, run=run,
        definition=delay.remaining_steps, facts=delay.context,
        correlation_id=delay.correlation_id,
    )
    combined = list(run.steps or []) + trace
    _finish_run(run, combined, reasons)
    delay.status = "resumed"
    delay.resumed_at = current
    publish_event(
        db, workspace_id=workspace_id, event_type=WORKFLOW_DELAY_RESUMED,
        entity_id=run.id,
        payload={"run_id": run.id, "steps_resumed": len(trace)},
        correlation_id=delay.correlation_id, actor_id=principal.user.id,
    )
    db.commit()
    return run


@router.get("/{automation_id}/runs/{run_id}/timeline", response_model=RunTimelineOut)
def run_timeline(
    workspace_id: str,
    automation_id: str,
    run_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> RunTimelineOut:
    verify_workspace(principal, workspace_id)
    run = _run_or_404(db, workspace_id, automation_id, run_id)
    steps = db.execute(
        select(WorkflowRunStep).where(
            WorkflowRunStep.workspace_id == workspace_id,
            WorkflowRunStep.run_id == run.id,
        ).order_by(WorkflowRunStep.occurred_at, WorkflowRunStep.id)
    ).scalars().all()
    links = db.execute(
        select(WorkflowMessageLink, Notification).join(
            Notification, Notification.id == WorkflowMessageLink.notification_id
        ).where(
            WorkflowMessageLink.workspace_id == workspace_id,
            WorkflowMessageLink.run_id == run.id,
        )
    ).all()
    messages = [
        {
            "notification_id": notification.id,
            "channel": link.channel,
            "transaction_id": link.transaction_id,
            "message": notification.message,
            "created_at": notification.created_at,
        }
        for link, notification in links
    ]
    correlation_id = (
        steps[0].correlation_id if steps
        else links[0][0].correlation_id if links
        else run.id
    )
    return RunTimelineOut(
        run_id=run.id, automation_id=run.automation_id, status=run.status,
        trigger_event=run.trigger_event, correlation_id=correlation_id,
        steps=[
            RunTimelineEntry(
                step_id=row.step_id, step_type=row.step_type, outcome=row.outcome,
                reason=row.reason, occurred_at=row.occurred_at,
            )
            for row in steps
        ],
        messages=messages,
    )


# --------------------------------------------------------------------------
# Digest and throttle steps (NV-012, NV-014)
# --------------------------------------------------------------------------


@router.post("/{automation_id}/digest/events", response_model=DigestBucketOut)
def digest_event(
    workspace_id: str,
    automation_id: str,
    body: DigestRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> DigestBucket:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    errors = _schema_errors(db, workspace_id, automation_id, body.payload)
    if errors:
        raise HTTPException(status_code=422, detail={"payload_errors": errors})
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="user is not an active member")
    receipt, replay = _receipt_or_create(
        db, workspace_id=workspace_id, automation=automation, kind="digest",
        idempotency_key=body.idempotency_key, actor_id=principal.user.id,
    )
    if replay is not None:
        bucket = db.execute(
            select(DigestBucket).where(DigestBucket.id == replay["bucket_id"])
        ).scalar_one_or_none()
        if bucket is not None:
            return bucket
    start, end = _window_bounds(now(), body.window_seconds)
    bucket = db.execute(
        select(DigestBucket).where(
            DigestBucket.workspace_id == workspace_id,
            DigestBucket.automation_id == automation_id,
            DigestBucket.subscriber_key == body.user_id,
            DigestBucket.group_key == body.group_key,
            DigestBucket.window_start == start,
        )
    ).scalar_one_or_none()
    if bucket is None:
        bucket = DigestBucket(
            id=new_id(), workspace_id=workspace_id, automation_id=automation_id,
            subscriber_key=body.user_id, group_key=body.group_key,
            window_start=start, window_end=end, event_count=0, events=[],
            status="open", correlation_id=new_id(), created_at=now(),
        )
        db.add(bucket)
        db.flush()
    if bucket.status != "open":
        raise HTTPException(status_code=409, detail="digest window is already flushed")
    if bucket.event_count >= MAX_DIGEST_EVENTS_PER_WINDOW:
        raise HTTPException(status_code=422, detail="digest window event limit reached")
    bucket.event_count += 1
    bucket.events = list(bucket.events or []) + [body.payload]
    publish_event(
        db, workspace_id=workspace_id, event_type=DIGEST_EVENT_RECORDED,
        entity_id=bucket.id,
        payload={"event_count": bucket.event_count, "group_key": body.group_key},
        correlation_id=bucket.correlation_id, actor_id=principal.user.id,
    )
    receipt.result = {
        "bucket_id": bucket.id, "event_count": bucket.event_count,
        "kind": "digest", "idempotency_key": body.idempotency_key,
        "count": 1, "runs": [],
    }
    db.flush()
    db.commit()
    return bucket


@router.post("/{automation_id}/digest/buckets/{bucket_id}/flush", response_model=RunOut)
def flush_digest(
    workspace_id: str,
    automation_id: str,
    bucket_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> AutomationRun:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    bucket = db.execute(
        select(DigestBucket).where(
            DigestBucket.id == bucket_id,
            DigestBucket.workspace_id == workspace_id,
            DigestBucket.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if bucket is None:
        raise HTTPException(status_code=404, detail="digest bucket not found")
    if bucket.status != "open":
        raise HTTPException(status_code=409, detail="digest window is already flushed")
    run = _new_run(
        db, workspace_id=workspace_id, automation=automation,
        user_id=bucket.subscriber_key, trigger_event="digest",
        correlation_id=bucket.correlation_id,
    )
    facts = _facts_for(
        bucket.subscriber_key,
        {"event_count": bucket.event_count, "events": bucket.events, "group_key": bucket.group_key},
        {"digest": {"event_count": bucket.event_count}},
    )
    trace, reasons = _walk_and_record(
        db, workspace_id=workspace_id, automation=automation, run=run,
        definition=automation.definition, facts=facts, correlation_id=bucket.correlation_id,
    )
    _finish_run(run, trace, reasons)
    bucket.status = "flushed"
    bucket.flushed_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=DIGEST_FLUSHED,
        entity_id=bucket.id,
        payload={"event_count": bucket.event_count, "run_id": run.id, "group_key": bucket.group_key},
        correlation_id=bucket.correlation_id, actor_id=principal.user.id,
    )
    db.commit()
    return run


@router.get("/{automation_id}/digest/buckets", response_model=list[DigestBucketOut])
def list_digest_buckets(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[DigestBucket]:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    return db.execute(
        select(DigestBucket).where(
            DigestBucket.workspace_id == workspace_id,
            DigestBucket.automation_id == automation_id,
        ).order_by(DigestBucket.created_at.desc())
    ).scalars().all()


@router.post("/{automation_id}/throttle", response_model=ThrottleOut)
def throttle_trigger(
    workspace_id: str,
    automation_id: str,
    body: ThrottleRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ThrottleOut:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    errors = _schema_errors(db, workspace_id, automation_id, body.payload)
    if errors:
        raise HTTPException(status_code=422, detail={"payload_errors": errors})
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="user is not an active member")
    receipt, replay = _receipt_or_create(
        db, workspace_id=workspace_id, automation=automation, kind="throttle",
        idempotency_key=body.idempotency_key, actor_id=principal.user.id,
    )
    if replay is not None:
        return ThrottleOut(**replay["result"])
    start, end = _window_bounds(now(), body.window_seconds)
    counter = db.execute(
        select(ThrottleCounter).where(
            ThrottleCounter.workspace_id == workspace_id,
            ThrottleCounter.automation_id == automation_id,
            ThrottleCounter.subscriber_key == body.user_id,
            ThrottleCounter.group_key == body.group_key,
            ThrottleCounter.window_start == start,
        )
    ).scalar_one_or_none()
    if counter is None:
        counter = ThrottleCounter(
            id=new_id(), workspace_id=workspace_id, automation_id=automation_id,
            subscriber_key=body.user_id, group_key=body.group_key,
            window_start=start, window_end=end, count=0, created_at=now(),
        )
        db.add(counter)
        db.flush()
    skipped = counter.count >= body.max_events
    if skipped:
        counter.count += 1
        reason = f"throttle limit {body.max_events} reached for this window"
        publish_event(
            db, workspace_id=workspace_id, event_type=THROTTLE_SKIPPED,
            entity_id=counter.id, payload={"reason": reason, "count": counter.count},
            actor_id=principal.user.id,
        )
        result = ThrottleOut(
            run_id="", outcome="skipped", count=counter.count, max_events=body.max_events,
            window_start=start, window_end=end, reason=reason, message_created=False,
        )
        receipt.result = {"result": jsonable_encoder(result)}
        db.flush()
        db.commit()
        return result
    counter.count += 1
    facts = _facts_for(body.user_id, body.payload, {"throttle": {"count": counter.count}})
    run = _new_run(
        db, workspace_id=workspace_id, automation=automation,
        user_id=body.user_id, trigger_event="throttle",
    )
    _apply_definition(
        db, workspace_id=workspace_id, automation=automation, run=run,
        facts=facts, correlation_id=run.id,
    )
    _create_message(
        db, workspace_id=workspace_id, user_id=body.user_id, run=run,
        message=body.message,
        transaction_id=f"throttle:{body.idempotency_key}:{counter.count}",
        correlation_id=run.id,
    )
    outcome = ThrottleOut(
        run_id=run.id, outcome=run.status, count=counter.count, max_events=body.max_events,
        window_start=start, window_end=end, reason="within throttle window", message_created=True,
    )
    receipt.result = {"result": jsonable_encoder(outcome)}
    db.flush()
    db.commit()
    return outcome


# --------------------------------------------------------------------------
# Scheduled notification in the recipient time zone (NV-011)
# --------------------------------------------------------------------------


@router.post("/{automation_id}/schedule", response_model=ScheduledRunOut, status_code=status.HTTP_201_CREATED)
def schedule_run(
    workspace_id: str,
    automation_id: str,
    body: ScheduleRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ScheduledRun:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    errors = _schema_errors(db, workspace_id, automation_id, body.payload)
    if errors:
        raise HTTPException(status_code=422, detail={"payload_errors": errors})
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="user is not an active member")
    receipt, replay = _receipt_or_create(
        db, workspace_id=workspace_id, automation=automation, kind="schedule",
        idempotency_key=body.idempotency_key, actor_id=principal.user.id,
    )
    if replay is not None:
        scheduled = db.execute(
            select(ScheduledRun).where(ScheduledRun.id == replay["scheduled_id"])
        ).scalar_one_or_none()
        if scheduled is not None:
            return scheduled
    try:
        fire_at = resolve_schedule(body.schedule, now(), body.timezone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scheduled = ScheduledRun(
        id=new_id(), workspace_id=workspace_id, automation_id=automation_id,
        user_id=body.user_id, schedule=body.schedule, timezone=body.timezone,
        fire_at=fire_at, payload={**body.payload, "message": body.message},
        status="scheduled", correlation_id=new_id(), created_at=now(),
    )
    db.add(scheduled)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=SCHEDULED_RUN_CREATED,
        entity_id=scheduled.id,
        payload={"fire_at": fire_at.isoformat(), "timezone": body.timezone},
        correlation_id=scheduled.correlation_id, actor_id=principal.user.id,
    )
    receipt.result = {
        "scheduled_id": scheduled.id, "kind": "schedule", "idempotency_key": body.idempotency_key,
        "count": 1, "runs": [],
    }
    db.flush()
    db.commit()
    return scheduled


@router.get("/{automation_id}/schedule", response_model=list[ScheduledRunOut])
def list_scheduled_runs(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[ScheduledRun]:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    return db.execute(
        select(ScheduledRun).where(
            ScheduledRun.workspace_id == workspace_id,
            ScheduledRun.automation_id == automation_id,
        ).order_by(ScheduledRun.fire_at)
    ).scalars().all()


@router.post("/{automation_id}/schedule/{scheduled_id}/fire", response_model=RunOut)
def fire_scheduled_run(
    workspace_id: str,
    automation_id: str,
    scheduled_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> AutomationRun:
    verify_workspace(principal, workspace_id)
    automation = _automation_or_404(db, workspace_id, automation_id)
    scheduled = db.execute(
        select(ScheduledRun).where(
            ScheduledRun.id == scheduled_id,
            ScheduledRun.workspace_id == workspace_id,
            ScheduledRun.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if scheduled is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    if scheduled.status != "scheduled":
        raise HTTPException(status_code=409, detail="scheduled run has already fired")
    current = now()
    if _as_utc(current) < _as_utc(scheduled.fire_at):
        raise HTTPException(status_code=409, detail="scheduled slot has not arrived")
    run = _new_run(
        db, workspace_id=workspace_id, automation=automation,
        user_id=scheduled.user_id, trigger_event="scheduled",
        correlation_id=scheduled.correlation_id,
    )
    _apply_definition(
        db, workspace_id=workspace_id, automation=automation, run=run,
        facts=_facts_for(scheduled.user_id, scheduled.payload, {"scheduled": True}),
        correlation_id=scheduled.correlation_id,
    )
    scheduled.status = "fired"
    scheduled.fired_at = current
    publish_event(
        db, workspace_id=workspace_id, event_type=SCHEDULED_RUN_FIRED,
        entity_id=scheduled.id, payload={"run_id": run.id},
        correlation_id=scheduled.correlation_id, actor_id=principal.user.id,
    )
    db.commit()
    return run


# --------------------------------------------------------------------------
# Topics and subscriptions on a dedicated router (NV-045, NV-046)
# --------------------------------------------------------------------------

def _topic_or_404(db: Session, workspace_id: str, topic_id: str) -> Topic:
    topic = db.execute(
        select(Topic).where(Topic.id == topic_id, Topic.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")
    return topic


@router.post("/topics/create", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def create_topic(
    workspace_id: str,
    body: TopicCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Topic:
    verify_workspace(principal, workspace_id)
    duplicate = db.execute(
        select(Topic.id).where(Topic.workspace_id == workspace_id, Topic.key == body.key)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="topic key already exists in this workspace")
    topic = Topic(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        description=body.description, created_by=principal.user.id,
        created_at=now(), updated_at=now(),
    )
    db.add(topic)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_CREATED, entity_id=topic.id,
        payload={"key": topic.key}, actor_id=principal.user.id,
    )
    db.commit()
    return topic


@router.get("/topics/list", response_model=list[TopicOut])
def list_topics(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[Topic]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Topic).where(Topic.workspace_id == workspace_id).order_by(Topic.key)
    ).scalars().all()


@router.get("/topics/get/{topic_id}", response_model=TopicOut)
def get_topic(
    workspace_id: str,
    topic_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> Topic:
    verify_workspace(principal, workspace_id)
    return _topic_or_404(db, workspace_id, topic_id)


@router.patch("/topics/update/{topic_id}", response_model=TopicOut)
def update_topic(
    workspace_id: str,
    topic_id: str,
    body: TopicUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Topic:
    verify_workspace(principal, workspace_id)
    topic = _topic_or_404(db, workspace_id, topic_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = _nonblank(updates["name"], "name")
    for key, value in updates.items():
        setattr(topic, key, value)
    topic.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_UPDATED, entity_id=topic.id,
        payload={"fields": sorted(updates)}, actor_id=principal.user.id,
    )
    db.commit()
    return topic


@router.delete("/topics/delete/{topic_id}")
def delete_topic(
    workspace_id: str,
    topic_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    topic = _topic_or_404(db, workspace_id, topic_id)
    subscriptions = db.execute(
        select(TopicSubscription).where(
            TopicSubscription.workspace_id == workspace_id,
            TopicSubscription.topic_id == topic.id,
        )
    ).scalars().all()
    for subscription in subscriptions:
        db.delete(subscription)
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_DELETED, entity_id=topic.id,
        payload={"key": topic.key}, actor_id=principal.user.id,
    )
    db.delete(topic)
    db.commit()
    return {"deleted": True, "topic_id": topic.id}


def _subscription_or_404(
    db: Session, workspace_id: str, topic_id: str, subscription_id: str
) -> TopicSubscription:
    row = db.execute(
        select(TopicSubscription).where(
            TopicSubscription.id == subscription_id,
            TopicSubscription.workspace_id == workspace_id,
            TopicSubscription.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    return row


@router.post("/topics/{topic_id}/subscriptions/create", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(
    workspace_id: str,
    topic_id: str,
    body: SubscriptionCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> TopicSubscription:
    verify_workspace(principal, workspace_id)
    _topic_or_404(db, workspace_id, topic_id)
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="user is not an active member")
    duplicate = db.execute(
        select(TopicSubscription.id).where(
            TopicSubscription.workspace_id == workspace_id,
            TopicSubscription.topic_id == topic_id,
            TopicSubscription.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="subscription already exists")
    row = TopicSubscription(
        id=new_id(), workspace_id=workspace_id, topic_id=topic_id, user_id=body.user_id,
        conditions=body.conditions, context=body.context, enabled=body.enabled,
        created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_SUBSCRIPTION_CHANGED,
        entity_id=row.id, payload={"action": "created", "user_id": row.user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return row


@router.get("/topics/{topic_id}/subscriptions/list", response_model=list[SubscriptionOut])
def list_subscriptions(
    workspace_id: str,
    topic_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[TopicSubscription]:
    verify_workspace(principal, workspace_id)
    _topic_or_404(db, workspace_id, topic_id)
    return db.execute(
        select(TopicSubscription).where(
            TopicSubscription.workspace_id == workspace_id,
            TopicSubscription.topic_id == topic_id,
        ).order_by(TopicSubscription.created_at)
    ).scalars().all()


@router.patch("/topics/{topic_id}/subscriptions/update/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(
    workspace_id: str,
    topic_id: str,
    subscription_id: str,
    body: SubscriptionUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> TopicSubscription:
    verify_workspace(principal, workspace_id)
    row = _subscription_or_404(db, workspace_id, topic_id, subscription_id)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_SUBSCRIPTION_CHANGED,
        entity_id=row.id, payload={"action": "updated", "fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return row


@router.delete("/topics/{topic_id}/subscriptions/delete/{subscription_id}")
def delete_subscription(
    workspace_id: str,
    topic_id: str,
    subscription_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _subscription_or_404(db, workspace_id, topic_id, subscription_id)
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=TOPIC_SUBSCRIPTION_CHANGED,
        entity_id=row.id, payload={"action": "deleted"}, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "subscription_id": row.id}


# Topic routes use /topics/<action> paths instead of /topics so they are never
# captured by the earlier /{automation_id} route on this router.


@router.get("/{automation_id}/runs", response_model=list[RunOut])
def list_runs(
    workspace_id: str,
    automation_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[AutomationRun]:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    return db.execute(
        select(AutomationRun)
        .where(AutomationRun.workspace_id == workspace_id, AutomationRun.automation_id == automation_id)
        .order_by(AutomationRun.started_at.desc())
    ).scalars().all()


@router.post("/{automation_id}/runs/{run_id}/approve", response_model=RunOut)
def approve_run(
    workspace_id: str,
    automation_id: str,
    run_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> AutomationRun:
    verify_workspace(principal, workspace_id)
    _automation_or_404(db, workspace_id, automation_id)
    run = db.execute(
        select(AutomationRun).where(
            AutomationRun.id == run_id,
            AutomationRun.workspace_id == workspace_id,
            AutomationRun.automation_id == automation_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    run.approval_status = "approved"
    publish_event(
        db, workspace_id=workspace_id, event_type=AUTOMATION_RUN_RECORDED,
        entity_id=run.id, payload={"approval": "approved"}, actor_id=principal.user.id,
    )
    db.commit()
    return run
