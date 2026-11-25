"""Clean-room project governance P2 (PL-034/095/106/119/120/128/129/140).

Documented/public behaviour implemented from scratch:
- PL-034: project status updates/posts with health, reactions and comments.
- PL-095: workspace wiki pages with NOVARA workspace permissions.
- PL-106: teamspaces grouping members and linked projects (no ownership change).
- PL-119: multiple workflows (state machines) per project; transitions follow rules.
- PL-120: work-item approvals with authorized approver decisions and audit events.
- PL-128: private dashboards visible only to owner.
- PL-129: published dashboards with read-only token, invalidate/regenerate.
- PL-140: epics as large-work grouping via clean-room parent/child type model.

No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import TASK_READ, TASK_WRITE, WORKSPACE_MANAGE

PROJECT_UPDATE_CREATED = "project_governance.update_created"
PROJECT_UPDATE_REACTED = "project_governance.update_reacted"
PROJECT_UPDATE_COMMENTED = "project_governance.update_commented"
WIKI_PAGE_CREATED = "project_governance.wiki_created"
WIKI_PAGE_UPDATED = "project_governance.wiki_updated"
TEAMSPACE_CREATED = "project_governance.teamspace_created"
TEAMSPACE_MEMBER_ADDED = "project_governance.teamspace_member_added"
TEAMSPACE_PROJECT_LINKED = "project_governance.teamspace_project_linked"
WORKFLOW_CREATED = "project_governance.workflow_created"
WORKFLOW_TRANSITIONED = "project_governance.workflow_transitioned"
APPROVAL_REQUESTED = "project_governance.approval_requested"
APPROVAL_DECIDED = "project_governance.approval_decided"
DASHBOARD_CREATED = "project_governance.dashboard_created"
DASHBOARD_PUBLISHED = "project_governance.dashboard_published"
DASHBOARD_INVALIDATED = "project_governance.dashboard_invalidated"
EPIC_CREATED = "project_governance.epic_created"
EPIC_CHILD_ADDED = "project_governance.epic_child_added"
register_event_types(
    PROJECT_UPDATE_CREATED, PROJECT_UPDATE_REACTED, PROJECT_UPDATE_COMMENTED,
    WIKI_PAGE_CREATED, WIKI_PAGE_UPDATED,
    TEAMSPACE_CREATED, TEAMSPACE_MEMBER_ADDED, TEAMSPACE_PROJECT_LINKED,
    WORKFLOW_CREATED, WORKFLOW_TRANSITIONED,
    APPROVAL_REQUESTED, APPROVAL_DECIDED,
    DASHBOARD_CREATED, DASHBOARD_PUBLISHED, DASHBOARD_INVALIDATED,
    EPIC_CREATED, EPIC_CHILD_ADDED,
)

HEALTH = ("on_track", "at_risk", "off_track")
APPROVAL_STATUS = ("pending", "approved", "rejected")

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/project-governance",
    tags=["project-governance"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class ProjectUpdate(Base):
    __tablename__ = "pg_project_updates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    health: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectUpdateReaction(Base):
    __tablename__ = "pg_project_update_reactions"
    __table_args__ = (UniqueConstraint("workspace_id", "update_id", "user_id", "emoji", name="uq_pg_update_reaction"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    update_id: Mapped[str] = mapped_column(ForeignKey("pg_project_updates.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectUpdateComment(Base):
    __tablename__ = "pg_project_update_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    update_id: Mapped[str] = mapped_column(ForeignKey("pg_project_updates.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WikiPage(Base):
    __tablename__ = "pg_wiki_pages"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_pg_wiki_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Teamspace(Base):
    __tablename__ = "pg_teamspaces"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_pg_teamspace_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TeamspaceMember(Base):
    __tablename__ = "pg_teamspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "teamspace_id", "user_id", name="uq_pg_teamspace_member"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    teamspace_id: Mapped[str] = mapped_column(ForeignKey("pg_teamspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TeamspaceProject(Base):
    __tablename__ = "pg_teamspace_projects"
    __table_args__ = (UniqueConstraint("workspace_id", "teamspace_id", "project_id", name="uq_pg_teamspace_project"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    teamspace_id: Mapped[str] = mapped_column(ForeignKey("pg_teamspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectWorkflow(Base):
    __tablename__ = "pg_workflows"
    __table_args__ = (UniqueConstraint("workspace_id", "project_id", "name", name="uq_pg_workflow_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    states: Mapped[list] = mapped_column(JSON, default=list)  # [{key,label}]
    transitions: Mapped[list] = mapped_column(JSON, default=list)  # [{from,to}]
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowRun(Base):
    __tablename__ = "pg_workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("pg_workflows.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ApprovalRequest(Base):
    __tablename__ = "pg_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GovernanceDashboard(Base):
    __tablename__ = "pg_dashboards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)  # private/published
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    publish_token: Mapped[str | None] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Epic(Base):
    __tablename__ = "pg_epics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EpicChild(Base):
    __tablename__ = "pg_epic_children"
    __table_args__ = (UniqueConstraint("workspace_id", "epic_id", "item_id", name="uq_pg_epic_child"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    epic_id: Mapped[str] = mapped_column(ForeignKey("pg_epics.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProjectUpdateCreate(BaseModel):
    project_id: str = Field(min_length=1)
    health: str
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)

    @field_validator("health")
    @classmethod
    def valid_health(cls, v: str) -> str:
        if v not in HEALTH:
            raise ValueError(f"health must be one of {sorted(HEALTH)}")
        return v


class ReactionCreate(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class WikiCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class WikiPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class TeamspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class TeamspaceMemberCreate(BaseModel):
    user_id: str = Field(min_length=1)


class TeamspaceProjectCreate(BaseModel):
    project_id: str = Field(min_length=1)


class WorkflowCreate(BaseModel):
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    states: list[dict] = Field(default_factory=list)
    transitions: list[dict] = Field(default_factory=list)


class TransitionBody(BaseModel):
    item_id: str = Field(min_length=1)
    from_state: str = Field(min_length=1)
    to_state: str = Field(min_length=1)


class ApprovalCreate(BaseModel):
    project_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    approver_id: str = Field(min_length=1)


class ApprovalDecision(BaseModel):
    decision: str
    note: str | None = None

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, v: str) -> str:
        if v not in ("approved", "rejected"):
            raise ValueError("decision must be approved or rejected")
        return v


class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)


class EpicCreate(BaseModel):
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class EpicChildCreate(BaseModel):
    item_id: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _member(db: Session, workspace_id: str, user_id: str) -> WorkspaceMember | None:
    return db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == "active",
    )).scalar_one_or_none()


def _dashboard_or_404(db: Session, workspace_id: str, dashboard_id: str) -> GovernanceDashboard:
    row = db.execute(select(GovernanceDashboard).where(
        GovernanceDashboard.workspace_id == workspace_id,
        GovernanceDashboard.id == dashboard_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    return row


# ---------------------------------------------------------------------------
# PL-034 Project updates
# ---------------------------------------------------------------------------


@router.post("/updates", status_code=status.HTTP_201_CREATED)
def create_project_update(
    workspace_id: str, body: ProjectUpdateCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = ProjectUpdate(
        workspace_id=workspace_id, project_id=body.project_id, author_id=principal.user.id,
        health=body.health, title=body.title, body=body.body,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=PROJECT_UPDATE_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"project_id": body.project_id, "health": body.health})
    db.commit(); db.refresh(row)
    return {"id": row.id, "project_id": row.project_id, "health": row.health, "title": row.title, "body": row.body, "author_id": row.author_id, "created_at": row.created_at}


@router.get("/updates")
def list_project_updates(
    workspace_id: str, project_id: str = Query(...),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ProjectUpdate).where(ProjectUpdate.workspace_id == workspace_id, ProjectUpdate.project_id == project_id).order_by(ProjectUpdate.created_at.desc())).scalars().all()
    return [{"id": r.id, "project_id": r.project_id, "health": r.health, "title": r.title, "body": r.body, "author_id": r.author_id, "created_at": r.created_at} for r in rows]


@router.post("/updates/{update_id}/reactions", status_code=status.HTTP_201_CREATED)
def react_project_update(
    workspace_id: str, update_id: str, body: ReactionCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    upd = db.execute(select(ProjectUpdate).where(ProjectUpdate.workspace_id == workspace_id, ProjectUpdate.id == update_id)).scalar_one_or_none()
    if upd is None:
        raise HTTPException(status_code=404, detail="update not found")
    existing = db.execute(select(ProjectUpdateReaction).where(ProjectUpdateReaction.workspace_id==workspace_id, ProjectUpdateReaction.update_id==update_id, ProjectUpdateReaction.user_id==principal.user.id, ProjectUpdateReaction.emoji==body.emoji)).scalar_one_or_none()
    if existing:
        return {"id": existing.id, "update_id": update_id, "emoji": existing.emoji, "user_id": existing.user_id}
    row = ProjectUpdateReaction(workspace_id=workspace_id, update_id=update_id, user_id=principal.user.id, emoji=body.emoji)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=PROJECT_UPDATE_REACTED, entity_id=update_id, actor_id=principal.user.id, payload={"emoji": body.emoji})
    db.commit(); db.refresh(row)
    return {"id": row.id, "update_id": update_id, "emoji": row.emoji, "user_id": row.user_id}


@router.post("/updates/{update_id}/comments", status_code=status.HTTP_201_CREATED)
def comment_project_update(
    workspace_id: str, update_id: str, body: CommentCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    upd = db.execute(select(ProjectUpdate).where(ProjectUpdate.workspace_id == workspace_id, ProjectUpdate.id == update_id)).scalar_one_or_none()
    if upd is None:
        raise HTTPException(status_code=404, detail="update not found")
    row = ProjectUpdateComment(workspace_id=workspace_id, update_id=update_id, author_id=principal.user.id, body=body.body)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=PROJECT_UPDATE_COMMENTED, entity_id=update_id, actor_id=principal.user.id, payload={"comment_id": row.id})
    db.commit(); db.refresh(row)
    return {"id": row.id, "update_id": update_id, "author_id": row.author_id, "body": row.body, "created_at": row.created_at}


@router.get("/updates/{update_id}/comments")
def list_project_update_comments(
    workspace_id: str, update_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ProjectUpdateComment).where(ProjectUpdateComment.workspace_id==workspace_id, ProjectUpdateComment.update_id==update_id).order_by(ProjectUpdateComment.created_at)).scalars().all()
    return [{"id": r.id, "update_id": r.update_id, "author_id": r.author_id, "body": r.body, "created_at": r.created_at} for r in rows]


# ---------------------------------------------------------------------------
# PL-095 Workspace Wiki
# ---------------------------------------------------------------------------


@router.post("/wiki", status_code=status.HTTP_201_CREATED)
def create_wiki_page(
    workspace_id: str, body: WikiCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(WikiPage).where(WikiPage.workspace_id==workspace_id, WikiPage.slug==body.slug)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="wiki slug already exists")
    row = WikiPage(workspace_id=workspace_id, slug=body.slug, title=body.title, body=body.body, created_by=principal.user.id)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=WIKI_PAGE_CREATED, entity_id=row.id, actor_id=principal.user.id, payload={"slug": body.slug})
    db.commit(); db.refresh(row)
    return {"id": row.id, "slug": row.slug, "title": row.title, "body": row.body, "created_by": row.created_by, "updated_at": row.updated_at}


@router.get("/wiki")
def list_wiki_pages(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(WikiPage).where(WikiPage.workspace_id==workspace_id).order_by(WikiPage.updated_at.desc())).scalars().all()
    return [{"id": r.id, "slug": r.slug, "title": r.title, "updated_at": r.updated_at, "created_by": r.created_by} for r in rows]


@router.get("/wiki/{slug}")
def get_wiki_page(
    workspace_id: str, slug: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = db.execute(select(WikiPage).where(WikiPage.workspace_id==workspace_id, WikiPage.slug==slug)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="wiki page not found")
    return {"id": row.id, "slug": row.slug, "title": row.title, "body": row.body, "created_by": row.created_by, "updated_at": row.updated_at}


@router.patch("/wiki/{slug}")
def update_wiki_page(
    workspace_id: str, slug: str, body: WikiPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = db.execute(select(WikiPage).where(WikiPage.workspace_id==workspace_id, WikiPage.slug==slug)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="wiki page not found")
    data = body.model_dump(exclude_unset=True)
    for k,v in data.items(): setattr(row,k,v)
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=WIKI_PAGE_UPDATED, entity_id=row.id, actor_id=principal.user.id, payload={"slug": slug, "fields": sorted(data)})
    db.commit(); db.refresh(row)
    return {"id": row.id, "slug": row.slug, "title": row.title, "body": row.body, "updated_at": row.updated_at}


# ---------------------------------------------------------------------------
# PL-106 Teamspaces
# ---------------------------------------------------------------------------


@router.post("/teamspaces", status_code=status.HTTP_201_CREATED)
def create_teamspace(
    workspace_id: str, body: TeamspaceCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(Teamspace).where(Teamspace.workspace_id==workspace_id, Teamspace.name==body.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="teamspace name exists")
    row = Teamspace(workspace_id=workspace_id, name=body.name, description=body.description, created_by=principal.user.id)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=TEAMSPACE_CREATED, entity_id=row.id, actor_id=principal.user.id, payload={"name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "description": row.description}


@router.post("/teamspaces/{teamspace_id}/members", status_code=status.HTTP_201_CREATED)
def add_teamspace_member(
    workspace_id: str, teamspace_id: str, body: TeamspaceMemberCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    ts = db.execute(select(Teamspace).where(Teamspace.workspace_id==workspace_id, Teamspace.id==teamspace_id)).scalar_one_or_none()
    if ts is None: raise HTTPException(status_code=404, detail="teamspace not found")
    if _member(db, workspace_id, body.user_id) is None:
        raise HTTPException(status_code=404, detail="active workspace member not found")
    exists = db.execute(select(TeamspaceMember).where(TeamspaceMember.workspace_id==workspace_id, TeamspaceMember.teamspace_id==teamspace_id, TeamspaceMember.user_id==body.user_id)).scalar_one_or_none()
    if exists: return {"teamspace_id": teamspace_id, "user_id": body.user_id, "added": False}
    db.add(TeamspaceMember(workspace_id=workspace_id, teamspace_id=teamspace_id, user_id=body.user_id))
    publish_event(db, workspace_id=workspace_id, event_type=TEAMSPACE_MEMBER_ADDED, entity_id=teamspace_id, actor_id=principal.user.id, payload={"user_id": body.user_id})
    db.commit()
    return {"teamspace_id": teamspace_id, "user_id": body.user_id, "added": True}


@router.post("/teamspaces/{teamspace_id}/projects", status_code=status.HTTP_201_CREATED)
def link_teamspace_project(
    workspace_id: str, teamspace_id: str, body: TeamspaceProjectCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    ts = db.execute(select(Teamspace).where(Teamspace.workspace_id==workspace_id, Teamspace.id==teamspace_id)).scalar_one_or_none()
    if ts is None: raise HTTPException(status_code=404, detail="teamspace not found")
    exists = db.execute(select(TeamspaceProject).where(TeamspaceProject.workspace_id==workspace_id, TeamspaceProject.teamspace_id==teamspace_id, TeamspaceProject.project_id==body.project_id)).scalar_one_or_none()
    if exists: return {"teamspace_id": teamspace_id, "project_id": body.project_id, "linked": False}
    db.add(TeamspaceProject(workspace_id=workspace_id, teamspace_id=teamspace_id, project_id=body.project_id))
    publish_event(db, workspace_id=workspace_id, event_type=TEAMSPACE_PROJECT_LINKED, entity_id=teamspace_id, actor_id=principal.user.id, payload={"project_id": body.project_id})
    db.commit()
    return {"teamspace_id": teamspace_id, "project_id": body.project_id, "linked": True}


@router.get("/teamspaces")
def list_teamspaces(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(Teamspace).where(Teamspace.workspace_id==workspace_id).order_by(Teamspace.created_at)).scalars().all()
    out = []
    for t in rows:
        members = db.execute(select(TeamspaceMember.user_id).where(TeamspaceMember.workspace_id==workspace_id, TeamspaceMember.teamspace_id==t.id)).scalars().all()
        projects = db.execute(select(TeamspaceProject.project_id).where(TeamspaceProject.workspace_id==workspace_id, TeamspaceProject.teamspace_id==t.id)).scalars().all()
        out.append({"id": t.id, "name": t.name, "description": t.description, "member_ids": list(members), "project_ids": list(projects)})
    return out


# ---------------------------------------------------------------------------
# PL-119 Multiple workflows
# ---------------------------------------------------------------------------


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    workspace_id: str, body: WorkflowCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(ProjectWorkflow).where(ProjectWorkflow.workspace_id==workspace_id, ProjectWorkflow.project_id==body.project_id, ProjectWorkflow.name==body.name)).scalar_one_or_none()
    if exists: raise HTTPException(status_code=409, detail="workflow name exists for project")
    state_keys = [s.get("key") for s in body.states if isinstance(s, dict)]
    if not state_keys: raise HTTPException(status_code=422, detail="at least one state required")
    for tr in body.transitions:
        if not isinstance(tr, dict) or tr.get("from") not in state_keys or tr.get("to") not in state_keys:
            raise HTTPException(status_code=422, detail="transitions must reference declared states")
    row = ProjectWorkflow(workspace_id=workspace_id, project_id=body.project_id, name=body.name, states=body.states, transitions=body.transitions, created_by=principal.user.id)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_CREATED, entity_id=row.id, actor_id=principal.user.id, payload={"project_id": body.project_id, "name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "project_id": row.project_id, "name": row.name, "states": row.states, "transitions": row.transitions}


@router.post("/workflows/{workflow_id}/transition")
def transition_workflow(
    workspace_id: str, workflow_id: str, body: TransitionBody,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    wf = db.execute(select(ProjectWorkflow).where(ProjectWorkflow.workspace_id==workspace_id, ProjectWorkflow.id==workflow_id)).scalar_one_or_none()
    if wf is None: raise HTTPException(status_code=404, detail="workflow not found")
    allowed = any(tr.get("from")==body.from_state and tr.get("to")==body.to_state for tr in (wf.transitions or []))
    if not allowed:
        raise HTTPException(status_code=409, detail="transition not allowed by workflow")
    run = db.execute(select(WorkflowRun).where(WorkflowRun.workspace_id==workspace_id, WorkflowRun.workflow_id==workflow_id, WorkflowRun.item_id==body.item_id)).scalar_one_or_none()
    if run is None:
        run = WorkflowRun(workspace_id=workspace_id, workflow_id=workflow_id, item_id=body.item_id, current_state=body.to_state)
        db.add(run)
    else:
        if run.current_state != body.from_state:
            raise HTTPException(status_code=409, detail="item is not in from_state")
        run.current_state = body.to_state
        run.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_TRANSITIONED, entity_id=workflow_id, actor_id=principal.user.id, payload={"item_id": body.item_id, "from": body.from_state, "to": body.to_state})
    db.commit()
    return {"workflow_id": workflow_id, "item_id": body.item_id, "current_state": body.to_state}


# ---------------------------------------------------------------------------
# PL-120 Approvals
# ---------------------------------------------------------------------------


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
def create_approval(
    workspace_id: str, body: ApprovalCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if _member(db, workspace_id, body.approver_id) is None:
        raise HTTPException(status_code=404, detail="approver not found in workspace")
    row = ApprovalRequest(workspace_id=workspace_id, project_id=body.project_id, item_id=body.item_id, requested_by=principal.user.id, approver_id=body.approver_id)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=APPROVAL_REQUESTED, entity_id=row.id, actor_id=principal.user.id, payload={"item_id": body.item_id, "approver_id": body.approver_id})
    db.commit(); db.refresh(row)
    return {"id": row.id, "item_id": row.item_id, "approver_id": row.approver_id, "status": row.status}


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    workspace_id: str, approval_id: str, body: ApprovalDecision,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = db.execute(select(ApprovalRequest).where(ApprovalRequest.workspace_id==workspace_id, ApprovalRequest.id==approval_id)).scalar_one_or_none()
    if row is None: raise HTTPException(status_code=404, detail="approval not found")
    if row.approver_id != principal.user.id:
        raise HTTPException(status_code=403, detail="only assigned approver can decide")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="approval already decided")
    row.status = body.decision
    row.decision_note = body.note
    row.decided_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=APPROVAL_DECIDED, entity_id=row.id, actor_id=principal.user.id, payload={"decision": body.decision, "item_id": row.item_id})
    db.commit(); db.refresh(row)
    return {"id": row.id, "status": row.status, "decision_note": row.decision_note, "decided_at": row.decided_at}


@router.get("/approvals")
def list_approvals(
    workspace_id: str, project_id: str | None = None,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = select(ApprovalRequest).where(ApprovalRequest.workspace_id==workspace_id)
    if project_id: q = q.where(ApprovalRequest.project_id==project_id)
    rows = db.execute(q.order_by(ApprovalRequest.created_at.desc())).scalars().all()
    return [{"id": r.id, "project_id": r.project_id, "item_id": r.item_id, "approver_id": r.approver_id, "requested_by": r.requested_by, "status": r.status, "decision_note": r.decision_note} for r in rows]


# ---------------------------------------------------------------------------
# PL-128/129 Dashboards
# ---------------------------------------------------------------------------


@router.post("/dashboards", status_code=status.HTTP_201_CREATED)
def create_dashboard(
    workspace_id: str, body: DashboardCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = GovernanceDashboard(workspace_id=workspace_id, name=body.name, owner_id=principal.user.id, visibility="private", config=body.config)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=DASHBOARD_CREATED, entity_id=row.id, actor_id=principal.user.id, payload={"name": body.name, "visibility": "private"})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "owner_id": row.owner_id, "visibility": row.visibility, "publish_token": row.publish_token}


@router.get("/dashboards")
def list_dashboards(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(GovernanceDashboard).where(GovernanceDashboard.workspace_id==workspace_id).order_by(GovernanceDashboard.created_at.desc())).scalars().all()
    out = []
    for r in rows:
        if r.visibility == "private" and r.owner_id != principal.user.id:
            continue
        out.append({"id": r.id, "name": r.name, "owner_id": r.owner_id, "visibility": r.visibility, "publish_token": r.publish_token if r.owner_id == principal.user.id else None})
    return out


@router.post("/dashboards/{dashboard_id}/release")
def publish_dashboard(
    workspace_id: str, dashboard_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _dashboard_or_404(db, workspace_id, dashboard_id)
    if row.owner_id != principal.user.id:
        raise HTTPException(status_code=403, detail="only owner can publish dashboard")
    row.visibility = "published"
    row.publish_token = secrets.token_urlsafe(24)
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=DASHBOARD_PUBLISHED, entity_id=row.id, actor_id=principal.user.id, payload={"visibility": "published"})
    db.commit(); db.refresh(row)
    return {"id": row.id, "visibility": row.visibility, "publish_token": row.publish_token}


@router.post("/dashboards/{dashboard_id}/invalidate")
def invalidate_dashboard(
    workspace_id: str, dashboard_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _dashboard_or_404(db, workspace_id, dashboard_id)
    if row.owner_id != principal.user.id:
        raise HTTPException(status_code=403, detail="only owner can invalidate dashboard")
    row.visibility = "private"
    row.publish_token = None
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=DASHBOARD_INVALIDATED, entity_id=row.id, actor_id=principal.user.id, payload={"visibility": "private"})
    db.commit(); db.refresh(row)
    return {"id": row.id, "visibility": row.visibility, "publish_token": row.publish_token}


@router.get("/dashboards/shared/{token}")
def get_published_dashboard(
    workspace_id: str, token: str,
    db: Session = Depends(get_db),
):
    row = db.execute(select(GovernanceDashboard).where(
        GovernanceDashboard.workspace_id==workspace_id,
        GovernanceDashboard.publish_token==token,
        GovernanceDashboard.visibility=="published",
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="published dashboard not found")
    return {"id": row.id, "name": row.name, "config": row.config, "visibility": row.visibility, "read_only": True}


# ---------------------------------------------------------------------------
# PL-140 Epics
# ---------------------------------------------------------------------------


@router.post("/epics", status_code=status.HTTP_201_CREATED)
def create_epic(
    workspace_id: str, body: EpicCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = Epic(workspace_id=workspace_id, project_id=body.project_id, title=body.title, description=body.description, created_by=principal.user.id)
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=EPIC_CREATED, entity_id=row.id, actor_id=principal.user.id, payload={"project_id": body.project_id, "title": body.title})
    db.commit(); db.refresh(row)
    return {"id": row.id, "project_id": row.project_id, "title": row.title, "description": row.description}


@router.post("/epics/{epic_id}/children", status_code=status.HTTP_201_CREATED)
def add_epic_child(
    workspace_id: str, epic_id: str, body: EpicChildCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    epic = db.execute(select(Epic).where(Epic.workspace_id==workspace_id, Epic.id==epic_id)).scalar_one_or_none()
    if epic is None: raise HTTPException(status_code=404, detail="epic not found")
    exists = db.execute(select(EpicChild).where(EpicChild.workspace_id==workspace_id, EpicChild.epic_id==epic_id, EpicChild.item_id==body.item_id)).scalar_one_or_none()
    if exists: return {"epic_id": epic_id, "item_id": body.item_id, "added": False}
    db.add(EpicChild(workspace_id=workspace_id, epic_id=epic_id, item_id=body.item_id))
    publish_event(db, workspace_id=workspace_id, event_type=EPIC_CHILD_ADDED, entity_id=epic_id, actor_id=principal.user.id, payload={"item_id": body.item_id})
    db.commit()
    return {"epic_id": epic_id, "item_id": body.item_id, "added": True}


@router.get("/epics")
def list_epics(
    workspace_id: str, project_id: str | None = None,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = select(Epic).where(Epic.workspace_id==workspace_id)
    if project_id: q = q.where(Epic.project_id==project_id)
    rows = db.execute(q.order_by(Epic.created_at.desc())).scalars().all()
    out = []
    for e in rows:
        children = db.execute(select(EpicChild.item_id).where(EpicChild.workspace_id==workspace_id, EpicChild.epic_id==e.id)).scalars().all()
        out.append({"id": e.id, "project_id": e.project_id, "title": e.title, "description": e.description, "child_item_ids": list(children)})
    return out
