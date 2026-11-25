"""AI agent control center.

This build is deliberately governor-only: it records agent configuration and
run/approval activity in the workspace database and publishes audit events. It
does not call any external AI provider and does not fabricate AI output.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import EVENT_READ, OUTREACH_APPROVE

AGENT_CREATED = "agent.created"
AGENT_STATUS_CHANGED = "agent.status_changed"
AGENT_RUN_REQUESTED = "agent.run_requested"
AGENT_RUN_APPROVED = "agent.run_approved"
register_event_types(AGENT_CREATED, AGENT_STATUS_CHANGED, AGENT_RUN_REQUESTED, AGENT_RUN_APPROVED)

AGENT_NOTES = (
    "No external AI provider is called in this build. The agent center records "
    "and governs agent activity; it does not fabricate AI output."
)

# NOVARA-owned descriptors. These are governance labels only: a run records
# local steps and audit events; it never produces external output. There is no
# sender role — autonomous delivery is deliberately absent from this build.
AGENT_ROLE_DESCRIPTORS = {
    "scout": {
        "workspace_read": True,
        "workspace_write": False,
        "create_drafts": False,
        "approve": False,
        "send": False,
        "delegation_limit": 1,
    },
    "writer": {
        "workspace_read": True,
        "workspace_write": False,
        "create_drafts": True,
        "approve": False,
        "send": False,
        "delegation_limit": 2,
    },
    "handler": {
        "workspace_read": True,
        "workspace_write": False,
        "create_drafts": False,
        "approve": False,
        "send": False,
        "delegation_limit": 1,
    },
}
NO_SENDER_ROLE_NOTE = (
    "There is no sender role in this build: no agent, role or route can send an "
    "external message."
)

MODEL_PROVIDERS = frozenset({"local", "openai", "anthropic"})
AGENT_STATUSES = frozenset({"active", "paused"})
RUN_STATUSES = frozenset({"queued", "running", "completed", "failed", "awaiting_approval"})

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/agents",
    tags=["agents"],
)


def _validated_role(value: str | None) -> str | None:
    if value is None:
        return None
    role = value.strip().lower()
    if role not in AGENT_ROLE_DESCRIPTORS:
        raise ValueError("role must be one of " + ", ".join(sorted(AGENT_ROLE_DESCRIPTORS)))
    return role


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class AgentConfig(Base):
    __tablename__ = "agent_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_agent_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    boundary: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agent_configs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    task: Mapped[str] = mapped_column(Text, nullable=False)
    steps_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class AgentConfigCreate(BaseModel):
    name: str
    purpose: str
    model_provider: str
    model_name: str
    boundary: str
    role: str | None = None
    max_steps: int = Field(default=10, ge=1, le=1000)
    status: Literal["active", "paused"] = "active"
    requires_approval: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str | None) -> str | None:
        return _validated_role(value)

    @field_validator("name", "purpose", "model_name", "boundary")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("this field must not be empty")
        return value

    @field_validator("model_provider")
    @classmethod
    def provider_allowed(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in MODEL_PROVIDERS:
            raise ValueError("model_provider must be local, openai or anthropic")
        return value


class AgentConfigUpdate(BaseModel):
    name: str | None = None
    purpose: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    boundary: str | None = None
    role: str | None = None
    max_steps: int | None = Field(default=None, ge=1, le=1000)
    status: Literal["active", "paused"] | None = None
    requires_approval: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str | None) -> str | None:
        return _validated_role(value)

    @field_validator("name", "purpose", "model_name", "boundary")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("this field must not be empty")
        return value

    @field_validator("model_provider")
    @classmethod
    def provider_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in MODEL_PROVIDERS:
            raise ValueError("model_provider must be local, openai or anthropic")
        return value


class AgentStatusUpdate(BaseModel):
    status: Literal["active", "paused"]

    model_config = ConfigDict(extra="forbid")


class AgentConfigOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    purpose: str
    model_provider: str
    model_name: str
    boundary: str
    role: str | None = None
    max_steps: int
    status: str
    requires_approval: bool
    created_by: str
    created_at: object
    updated_at: object
    notes: str = AGENT_NOTES
    role_notes: str = NO_SENDER_ROLE_NOTE

    model_config = ConfigDict(from_attributes=True)


class AgentRunCreate(BaseModel):
    task: str
    steps_taken: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("task")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task is required")
        return value


class RunProgress(BaseModel):
    steps_taken: int | None = Field(default=None, ge=0)
    status: Literal["running", "completed", "failed", "awaiting_approval"] | None = None
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


class AgentRunOut(BaseModel):
    id: str
    workspace_id: str
    agent_id: str
    status: str
    task: str
    steps_taken: int
    error: str | None
    requested_at: object
    finished_at: object | None
    actor_id: str
    notes: str = AGENT_NOTES

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _agent_or_404(db: Session, workspace_id: str, agent_id: str) -> AgentConfig:
    agent = db.execute(
        select(AgentConfig).where(
            AgentConfig.id == agent_id,
            AgentConfig.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


def _run_or_404(db: Session, workspace_id: str, agent_id: str, run_id: str) -> AgentRun:
    run = db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.agent_id == agent_id,
            AgentRun.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return run


# --------------------------------------------------------------------------
# Endpoints — agent configs
# --------------------------------------------------------------------------


@router.get("", response_model=list[AgentConfigOut])
def list_agents(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[AgentConfig]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(AgentConfig)
        .where(AgentConfig.workspace_id == workspace_id)
        .order_by(AgentConfig.created_at.desc())
    ).scalars().all()


@router.post("", response_model=AgentConfigOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    workspace_id: str,
    body: AgentConfigCreate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentConfig:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(AgentConfig).where(
            AgentConfig.workspace_id == workspace_id,
            AgentConfig.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="an agent with this name already exists")
    agent = AgentConfig(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        purpose=body.purpose,
        model_provider=body.model_provider,
        model_name=body.model_name,
        boundary=body.boundary,
        role=_validated_role(body.role),
        max_steps=body.max_steps,
        status=body.status,
        requires_approval=body.requires_approval,
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(agent)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_CREATED,
        entity_id=agent.id,
        payload={
            "name": agent.name,
            "model_provider": agent.model_provider,
            "role": agent.role,
            "max_steps": agent.max_steps,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return agent


@router.get("/runs", response_model=list[AgentRunOut])
def list_runs(
    workspace_id: str,
    agent_id: str | None = None,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[AgentRun]:
    verify_workspace(principal, workspace_id)
    query = select(AgentRun).where(AgentRun.workspace_id == workspace_id)
    if agent_id:
        _agent_or_404(db, workspace_id, agent_id)
        query = query.where(AgentRun.agent_id == agent_id)
    return db.execute(query.order_by(AgentRun.requested_at.desc())).scalars().all()


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(
    workspace_id: str,
    run_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> AgentRun:
    verify_workspace(principal, workspace_id)
    run = db.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return run


@router.get("/{agent_id}", response_model=AgentConfigOut)
def get_agent(
    workspace_id: str,
    agent_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> AgentConfig:
    verify_workspace(principal, workspace_id)
    return _agent_or_404(db, workspace_id, agent_id)


@router.patch("/{agent_id}", response_model=AgentConfigOut)
def update_agent(
    workspace_id: str,
    agent_id: str,
    body: AgentConfigUpdate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentConfig:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != agent.name:
        conflict = db.execute(
            select(AgentConfig).where(
                AgentConfig.workspace_id == workspace_id,
                AgentConfig.name == updates["name"],
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="an agent with this name already exists")
    previous_status = agent.status
    for key, value in updates.items():
        setattr(agent, key, value)
    agent.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_STATUS_CHANGED,
        entity_id=agent.id,
        payload={
            "action": "updated",
            "fields": sorted(updates),
            "status_from": previous_status,
            "status_to": agent.status,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return agent


@router.post("/{agent_id}/status", response_model=AgentConfigOut)
def set_agent_status(
    workspace_id: str,
    agent_id: str,
    body: AgentStatusUpdate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentConfig:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    previous_status = agent.status
    agent.status = body.status
    agent.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_STATUS_CHANGED,
        entity_id=agent.id,
        payload={"action": "status_changed", "from": previous_status, "to": agent.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return agent


@router.delete("/{agent_id}")
def delete_agent(
    workspace_id: str,
    agent_id: str,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    run_count = db.execute(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.workspace_id == workspace_id,
            AgentRun.agent_id == agent.id,
        )
    ).scalar()
    if run_count:
        raise HTTPException(status_code=409, detail="agent has runs; runs are retained for audit")
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_STATUS_CHANGED,
        entity_id=agent.id,
        payload={"action": "deleted", "name": agent.name},
        actor_id=principal.user.id,
    )
    db.delete(agent)
    db.commit()
    return {"deleted": True, "agent_id": agent_id, "notes": AGENT_NOTES}


# --------------------------------------------------------------------------
# Endpoints — agent runs
# --------------------------------------------------------------------------


@router.post("/{agent_id}/runs", response_model=AgentRunOut, status_code=status.HTTP_201_CREATED)
def request_agent_run(
    workspace_id: str,
    agent_id: str,
    body: AgentRunCreate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentRun:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    if agent.status != "active":
        raise HTTPException(status_code=409, detail="paused agents cannot accept runs")
    if body.steps_taken > agent.max_steps:
        raise HTTPException(status_code=422, detail="run steps exceed the agent max_steps limit")
    run = AgentRun(
        id=new_id(),
        workspace_id=workspace_id,
        agent_id=agent.id,
        status="queued",
        task=body.task,
        steps_taken=body.steps_taken,
        error=None,
        requested_at=now(),
        finished_at=None,
        actor_id=principal.user.id,
    )
    db.add(run)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_RUN_REQUESTED,
        entity_id=run.id,
        payload={"agent_id": agent.id, "status": run.status, "steps_taken": run.steps_taken},
        actor_id=principal.user.id,
    )
    db.commit()
    return run


@router.post("/{agent_id}/runs/{run_id}/progress", response_model=AgentRunOut)
def record_run_progress(
    workspace_id: str,
    agent_id: str,
    run_id: str,
    body: RunProgress,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentRun:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    run = _run_or_404(db, workspace_id, agent.id, run_id)
    if run.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="this run is already finished")
    if run.status == "awaiting_approval":
        raise HTTPException(status_code=409, detail="this run is awaiting approval")
    steps = run.steps_taken if body.steps_taken is None else body.steps_taken
    if steps > agent.max_steps:
        raise HTTPException(status_code=422, detail="run steps exceed the agent max_steps limit")
    if steps < run.steps_taken:
        raise HTTPException(status_code=422, detail="steps_taken cannot decrease")
    target = body.status or run.status
    if target == "completed" and agent.requires_approval:
        target = "awaiting_approval"
    previous_status = run.status
    run.steps_taken = steps
    run.status = target
    if body.error is not None:
        run.error = body.error
    if target in {"completed", "failed"}:
        run.finished_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_STATUS_CHANGED,
        entity_id=run.id,
        payload={
            "action": "run_status_changed",
            "agent_id": agent.id,
            "from": previous_status,
            "to": target,
            "steps_taken": steps,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return run


@router.post("/{agent_id}/runs/{run_id}/approve", response_model=AgentRunOut)
def approve_agent_run(
    workspace_id: str,
    agent_id: str,
    run_id: str,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AgentRun:
    verify_workspace(principal, workspace_id)
    agent = _agent_or_404(db, workspace_id, agent_id)
    run = _run_or_404(db, workspace_id, agent.id, run_id)
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="only awaiting_approval runs can be approved")
    previous_status = run.status
    run.status = "completed"
    run.finished_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=AGENT_RUN_APPROVED,
        entity_id=run.id,
        payload={
            "agent_id": agent.id,
            "from": previous_status,
            "to": run.status,
            "steps_taken": run.steps_taken,
            "approved_by": principal.user.id,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return run
