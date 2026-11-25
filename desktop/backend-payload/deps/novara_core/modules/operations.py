"""Operational summary and audit access.

Read-only views over real workspace data. Every value is computed from stored
rows at request time; nothing is cached or estimated. The component view states
explicitly which capabilities are local-only and which are blocked by missing
external infrastructure.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..models import Contact, Event, Lead, Notification, OutreachDraft, Task, now
from ..permissions import EVENT_READ
from .adapters import AdapterCall, ADAPTER_NOTES
from .agents import AgentConfig, AgentRun
from .integrations import Integration
from .jobs import JOB_NOTES, Job

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/operations",
    tags=["operations"],
)

SUMMARY_NOTES = (
    "All counts are computed from stored workspace rows. No external system is "
    "queried and no delivery status is inferred."
)


class OperationsSummary(BaseModel):
    workspace_id: str
    contacts: int
    leads: int
    open_tasks: int
    pending_drafts: int
    unread_notifications: int
    agents_active: int
    agent_runs: int
    integrations_configured: int
    integrations_disabled: int
    jobs_queued: int
    jobs_running: int
    jobs_dead_letter: int
    adapter_calls_recorded: int
    adapter_calls_rejected: int
    events_total: int
    generated_at: datetime
    notes: str = SUMMARY_NOTES

    model_config = ConfigDict(from_attributes=True)


class ComponentStatus(BaseModel):
    name: str
    state: str
    detail: str


class ComponentList(BaseModel):
    workspace_id: str
    components: list[ComponentStatus]
    notes: str = (
        "States describe this installation only. 'local' means implemented and "
        "running locally; 'blocked' means external verification is unavailable."
    )


class AuditEntry(BaseModel):
    id: str
    event_type: str
    entity_id: str | None
    correlation_id: str
    occurred_at: datetime
    payload: dict


def _count(db: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model).where(*conditions)
    return int(db.execute(query).scalar() or 0)


@router.get("/summary", response_model=OperationsSummary)
def summary(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> OperationsSummary:
    verify_workspace(principal, workspace_id)
    from ..models import now

    return OperationsSummary(
        workspace_id=workspace_id,
        contacts=_count(db, Contact, Contact.workspace_id == workspace_id),
        leads=_count(db, Lead, Lead.workspace_id == workspace_id),
        open_tasks=_count(
            db, Task, Task.workspace_id == workspace_id, Task.status == "open"
        ),
        pending_drafts=_count(
            db,
            OutreachDraft,
            OutreachDraft.workspace_id == workspace_id,
            OutreachDraft.status == "draft",
        ),
        unread_notifications=_count(
            db,
            Notification,
            Notification.workspace_id == workspace_id,
            Notification.read.is_(False),
        ),
        agents_active=_count(
            db,
            AgentConfig,
            AgentConfig.workspace_id == workspace_id,
            AgentConfig.status == "active",
        ),
        agent_runs=_count(db, AgentRun, AgentRun.workspace_id == workspace_id),
        integrations_configured=_count(
            db,
            Integration,
            Integration.workspace_id == workspace_id,
            Integration.status == "configured",
        ),
        integrations_disabled=_count(
            db,
            Integration,
            Integration.workspace_id == workspace_id,
            Integration.status == "disabled",
        ),
        jobs_queued=_count(
            db, Job, Job.workspace_id == workspace_id, Job.status == "queued"
        ),
        jobs_running=_count(
            db, Job, Job.workspace_id == workspace_id, Job.status == "running"
        ),
        jobs_dead_letter=_count(
            db, Job, Job.workspace_id == workspace_id, Job.status == "dead_letter"
        ),
        adapter_calls_recorded=_count(
            db,
            AdapterCall,
            AdapterCall.workspace_id == workspace_id,
            AdapterCall.status == "recorded",
        ),
        adapter_calls_rejected=_count(
            db,
            AdapterCall,
            AdapterCall.workspace_id == workspace_id,
            AdapterCall.status == "rejected",
        ),
        events_total=_count(db, Event, Event.workspace_id == workspace_id),
        generated_at=now(),
    )


@router.get("/components", response_model=ComponentList)
def components(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> ComponentList:
    verify_workspace(principal, workspace_id)
    items = [
        ComponentStatus(
            name="database",
            state="local",
            detail="SQLite verified locally; PostgreSQL compilation verified, no live server",
        ),
        ComponentStatus(name="job_queue", state="local", detail=JOB_NOTES),
        ComponentStatus(name="adapters", state="local_mock", detail=ADAPTER_NOTES),
        ComponentStatus(
            name="integrations",
            state="configured_only",
            detail="non-sensitive settings recorded; no outbound adapter is active",
        ),
        ComponentStatus(
            name="ai_providers",
            state="blocked",
            detail="no external AI provider called; no credentials present",
        ),
        ComponentStatus(
            name="containers",
            state="blocked",
            detail="Docker is unavailable in this workspace",
        ),
    ]
    return ComponentList(workspace_id=workspace_id, components=items)


@router.get("/audit", response_model=list[AuditEntry])
def audit(
    workspace_id: str,
    event_type: str | None = None,
    correlation_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[Event]:
    verify_workspace(principal, workspace_id)
    query = select(Event).where(Event.workspace_id == workspace_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if correlation_id:
        query = query.where(Event.correlation_id == correlation_id)
    return db.execute(
        query.order_by(Event.seq.desc()).limit(limit)
    ).scalars().all()


# --------------------------------------------------------------------------
# NV-081: honest local queue health
# --------------------------------------------------------------------------


class QueueHealthOut(BaseModel):
    workspace_id: str
    queued: int
    running: int
    succeeded: int
    dead_letter: int
    cancelled: int
    total: int
    stale_running: int
    handlers: list[str]
    notes: str = (
        "In-process local queue only; no external broker or BullMQ worker is "
        "running. Counts are computed from stored Job rows at request time."
    )


@router.get("/queue-health", response_model=QueueHealthOut)
def queue_health(
    workspace_id: str,
    stale_after_seconds: int = Query(default=300, ge=1, le=86400),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> QueueHealthOut:
    verify_workspace(principal, workspace_id)
    from .jobs import handler_names

    counts = dict(
        db.execute(
            select(Job.status, func.count())
            .where(Job.workspace_id == workspace_id)
            .group_by(Job.status)
        ).all()
    )
    cutoff = now() - timedelta(seconds=stale_after_seconds)
    stale = _count(
        db,
        Job,
        Job.workspace_id == workspace_id,
        Job.status == "running",
        Job.locked_at.is_not(None),
        Job.locked_at <= cutoff,
    )
    return QueueHealthOut(
        workspace_id=workspace_id,
        queued=counts.get("queued", 0),
        running=counts.get("running", 0),
        succeeded=counts.get("succeeded", 0),
        dead_letter=counts.get("dead_letter", 0),
        cancelled=counts.get("cancelled", 0),
        total=sum(counts.values()),
        stale_running=stale,
        handlers=handler_names(),
    )


# --------------------------------------------------------------------------
# NV-106: retrieve one event with real step outcomes and linked messages
# --------------------------------------------------------------------------


class EventStepOut(BaseModel):
    step_id: str
    step_type: str
    outcome: str
    reason: str
    occurred_at: object


class EventMessageOut(BaseModel):
    notification_id: str | None
    channel: str
    transaction_id: str
    message: str | None


class EventDetailOut(BaseModel):
    id: str
    event_id: str
    event_type: str
    entity_id: str | None
    correlation_id: str
    occurred_at: object
    payload: dict
    steps: list[EventStepOut]
    messages: list[EventMessageOut]


@router.get("/events/{event_id}", response_model=EventDetailOut)
def event_detail(
    workspace_id: str,
    event_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> EventDetailOut:
    verify_workspace(principal, workspace_id)
    from .automation import WorkflowMessageLink, WorkflowRunStep

    event = db.execute(
        select(Event).where(
            Event.id == event_id,
            Event.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    steps = db.execute(
        select(WorkflowRunStep).where(
            WorkflowRunStep.workspace_id == workspace_id,
            WorkflowRunStep.correlation_id == event.correlation_id,
        ).order_by(WorkflowRunStep.occurred_at, WorkflowRunStep.id)
    ).scalars().all()
    links = db.execute(
        select(WorkflowMessageLink, Notification).join(
            Notification, Notification.id == WorkflowMessageLink.notification_id
        ).where(
            WorkflowMessageLink.workspace_id == workspace_id,
            WorkflowMessageLink.correlation_id == event.correlation_id,
        )
    ).all()
    return EventDetailOut(
        id=event.id,
        event_id=event.id,
        event_type=event.event_type,
        entity_id=event.entity_id,
        correlation_id=event.correlation_id,
        occurred_at=event.occurred_at,
        payload=event.payload,
        steps=[
            EventStepOut(
                step_id=row.step_id, step_type=row.step_type,
                outcome=row.outcome, reason=row.reason, occurred_at=row.occurred_at,
            )
            for row in steps
        ],
        messages=[
            EventMessageOut(
                notification_id=notification.id, channel=link.channel,
                transaction_id=link.transaction_id, message=notification.message,
            )
            for link, notification in links
        ],
    )
