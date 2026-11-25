"""Guest work-request intake for projects (PL-088).

A workspace administrator creates a revocable intake link. The link token is
shown once and stored only as a hash. A guest who holds the token can submit a
request without an account; the request stays in a local queue until an
administrator accepts, declines or snoozes it. Acceptance creates a genuine
project work item through the project module's own creation path, so the item
carries the normal state mapping, activity entry and audit event.

No email, external message or public hosting is involved.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import TASK_READ, TASK_WRITE, WORKSPACE_MANAGE
from ..security import hash_token
from .projects import ItemCreate, Project, create_item

INTAKE_LINK_CREATED = "project.intake_link_created"
INTAKE_LINK_REVOKED = "project.intake_link_revoked"
INTAKE_SUBMITTED = "project.intake_submitted"
INTAKE_ACCEPTED = "project.intake_accepted"
INTAKE_DECLINED = "project.intake_declined"
INTAKE_SNOOZED = "project.intake_snoozed"
register_event_types(
    INTAKE_LINK_CREATED, INTAKE_LINK_REVOKED, INTAKE_SUBMITTED,
    INTAKE_ACCEPTED, INTAKE_DECLINED, INTAKE_SNOOZED,
)

STATES = ("submitted", "accepted", "declined", "snoozed")
DECISIONS = ("accept", "decline", "snooze")

router = APIRouter(tags=["project-intake"])

ADMIN_ROUTER = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}/intake",
    tags=["project-intake"],
)
PUBLIC_ROUTER = APIRouter(prefix="/api/v1/public/project-intake", tags=["project-intake"])


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class ProjectIntakeLink(Base):
    __tablename__ = "project_intake_links"
    __table_args__ = (UniqueConstraint("workspace_id", "token_hash", name="uq_intake_token"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectIntakeRequest(Base):
    __tablename__ = "project_intake_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("project_intake_links.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    requester_name: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("project_items.id"), nullable=True)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IntakeLinkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("intake link name is required")
        return value


class IntakeLinkOut(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    name: str
    active: bool
    created_by: str
    created_at: object
    expires_at: object | None
    revoked_at: object | None

    model_config = ConfigDict(from_attributes=True)


class IntakeLinkIssuedOut(IntakeLinkOut):
    token: str


class IntakeSubmit(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    requester_name: str = Field(min_length=1, max_length=120)
    requester_email: str = Field(min_length=3, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "requester_name")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("this field is required")
        return value

    @field_validator("requester_email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("a valid requester email is required")
        return value


class IntakeRequestOut(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    link_id: str
    state: str
    title: str
    description: str | None
    requester_name: str
    requester_email: str
    created_at: object
    decided_by: str | None
    decided_at: object | None
    snooze_until: object | None
    item_id: str | None

    model_config = ConfigDict(from_attributes=True)


class IntakeDecision(BaseModel):
    decision: str
    snooze_until: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value: str) -> str:
        if value not in DECISIONS:
            raise ValueError("decision must be accept, decline or snooze")
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _expired(value: datetime | None) -> bool:
    current = _utc(now())
    expiry = _utc(value)
    if expiry is None or current is None:
        return False
    return expiry <= current


def _project(db: Session, workspace_id: str, project_id: str) -> Project:
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _link(db: Session, workspace_id: str, project_id: str, link_id: str) -> ProjectIntakeLink:
    row = db.execute(
        select(ProjectIntakeLink).where(
            ProjectIntakeLink.id == link_id,
            ProjectIntakeLink.workspace_id == workspace_id,
            ProjectIntakeLink.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="intake link not found")
    return row


def _request(db: Session, workspace_id: str, project_id: str, request_id: str) -> ProjectIntakeRequest:
    row = db.execute(
        select(ProjectIntakeRequest).where(
            ProjectIntakeRequest.id == request_id,
            ProjectIntakeRequest.workspace_id == workspace_id,
            ProjectIntakeRequest.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="intake request not found")
    return row


def _publish(db, workspace_id, event_type, entity_id, payload, actor_id):
    publish_event(
        db, workspace_id=workspace_id, event_type=event_type, entity_id=entity_id,
        payload=payload, actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Administrator endpoints
# ---------------------------------------------------------------------------


@ADMIN_ROUTER.post("/links", response_model=IntakeLinkIssuedOut, status_code=status.HTTP_201_CREATED)
def create_intake_link(
    workspace_id: str,
    project_id: str,
    body: IntakeLinkCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project(db, workspace_id, project_id)
    token = "pil_" + secrets.token_urlsafe(24)
    row = ProjectIntakeLink(
        id=new_id(), workspace_id=workspace_id, project_id=project_id, name=body.name,
        token_hash=hash_token(token), active=True, created_by=principal.user.id,
        created_at=now(), expires_at=_utc(body.expires_at), revoked_at=None,
    )
    db.add(row)
    db.flush()
    _publish(db, workspace_id, INTAKE_LINK_CREATED, row.id,
             {"project_id": project_id, "name": row.name}, principal.user.id)
    db.commit()
    return {**IntakeLinkOut.model_validate(row).model_dump(), "token": token}


@ADMIN_ROUTER.get("/links", response_model=list[IntakeLinkOut])
def list_intake_links(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectIntakeLink]:
    verify_workspace(principal, workspace_id)
    _project(db, workspace_id, project_id)
    return db.execute(
        select(ProjectIntakeLink).where(
            ProjectIntakeLink.workspace_id == workspace_id,
            ProjectIntakeLink.project_id == project_id,
        ).order_by(ProjectIntakeLink.created_at.desc())
    ).scalars().all()


@ADMIN_ROUTER.delete("/links/{link_id}")
def revoke_intake_link(
    workspace_id: str,
    project_id: str,
    link_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _link(db, workspace_id, project_id, link_id)
    if not row.active:
        return {"revoked": True, "id": row.id}
    row.active = False
    row.revoked_at = now()
    _publish(db, workspace_id, INTAKE_LINK_REVOKED, row.id,
             {"project_id": project_id}, principal.user.id)
    db.commit()
    return {"revoked": True, "id": row.id}


@ADMIN_ROUTER.get("/requests", response_model=list[IntakeRequestOut])
def list_intake_requests(
    workspace_id: str,
    project_id: str,
    state: str | None = Query(None),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectIntakeRequest]:
    verify_workspace(principal, workspace_id)
    _project(db, workspace_id, project_id)
    if state is not None and state not in STATES:
        raise HTTPException(status_code=422, detail="invalid intake state")
    query = select(ProjectIntakeRequest).where(
        ProjectIntakeRequest.workspace_id == workspace_id,
        ProjectIntakeRequest.project_id == project_id,
    )
    if state is not None:
        query = query.where(ProjectIntakeRequest.state == state)
    return db.execute(query.order_by(ProjectIntakeRequest.created_at.desc())).scalars().all()


@ADMIN_ROUTER.post("/requests/{request_id}/decision", response_model=IntakeRequestOut)
def decide_intake_request(
    workspace_id: str,
    project_id: str,
    request_id: str,
    body: IntakeDecision,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectIntakeRequest:
    verify_workspace(principal, workspace_id)
    row = _request(db, workspace_id, project_id, request_id)
    if row.state not in ("submitted", "snoozed"):
        raise HTTPException(status_code=409, detail="intake request already decided")
    if body.decision == "snooze":
        until = _utc(body.snooze_until)
        if until is None or _expired(until):
            raise HTTPException(status_code=422, detail="snooze_until must be in the future")
        row.state = "snoozed"
        row.snooze_until = until
        event_type = INTAKE_SNOOZED
    elif body.decision == "decline":
        row.state = "declined"
        row.snooze_until = None
        event_type = INTAKE_DECLINED
    else:
        description = (
            f"Guest intake from {row.requester_name} <{row.requester_email}>."
            + (f"\n\n{row.description}" if row.description else "")
        )
        item = create_item(
            workspace_id,
            project_id,
            ItemCreate(title=row.title, description=description, priority="medium"),
            principal,
            db,
        )
        row.state = "accepted"
        row.item_id = item.id
        row.snooze_until = None
        event_type = INTAKE_ACCEPTED
    row.decided_by = principal.user.id
    row.decided_at = now()
    db.flush()
    _publish(db, workspace_id, event_type, row.id,
             {"project_id": project_id, "item_id": row.item_id,
              "decision": body.decision},
             principal.user.id)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# Public guest endpoint
# ---------------------------------------------------------------------------


@PUBLIC_ROUTER.post("/{token}/requests", response_model=IntakeRequestOut, status_code=status.HTTP_201_CREATED)
def submit_intake_request(
    token: str,
    body: IntakeSubmit,
    db: Session = Depends(get_db),
) -> ProjectIntakeRequest:
    row = db.execute(
        select(ProjectIntakeLink).where(ProjectIntakeLink.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if row is None or not row.active or _expired(row.expires_at):
        raise HTTPException(status_code=401, detail="invalid or expired intake link")
    request = ProjectIntakeRequest(
        id=new_id(), workspace_id=row.workspace_id, project_id=row.project_id,
        link_id=row.id, state="submitted", title=body.title,
        description=body.description, requester_name=body.requester_name,
        requester_email=body.requester_email, created_at=now(),
    )
    db.add(request)
    db.flush()
    _publish(db, row.workspace_id, INTAKE_SUBMITTED, request.id,
             {"project_id": row.project_id, "title": request.title}, None)
    db.commit()
    return request


router.include_router(ADMIN_ROUTER)
router.include_router(PUBLIC_ROUTER)
