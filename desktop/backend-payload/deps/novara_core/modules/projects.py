"""Project management module: workspace-scoped projects and their items.

Includes a SQL-computed progress summary. Completion of an item writes an
explicit completed_at marker. No external side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import User, WorkspaceMember, new_id, now
from ..permissions import TASK_READ, TASK_WRITE

PROJECT_CREATED = "project.created"
PROJECT_UPDATED = "project.updated"
PROJECT_DELETED = "project.deleted"
PROJECT_ITEM_CREATED = "project.item_created"
PROJECT_ITEM_UPDATED = "project.item_updated"
PROJECT_STATE_CREATED = "project.state_created"
PROJECT_STATE_UPDATED = "project.state_updated"
PROJECT_MEMBER_ADDED = "project.member_added"
PROJECT_MEMBER_UPDATED = "project.member_updated"
PROJECT_MEMBER_REMOVED = "project.member_removed"
# P1 Plane surfaces: every one of these is written through publish_event(), so
# the shared append-only audit log is the single source of truth for activity.
PROJECT_ITEM_DESCRIPTION_UPDATED = "project.item_description_updated"
PROJECT_LABEL_CREATED = "project.label_created"
PROJECT_LABEL_ASSIGNED = "project.label_assigned"
PROJECT_CYCLE_UPDATED = "project.cycle_updated"
PROJECT_ITEM_CYCLE_ASSIGNED = "project.item_cycle_assigned"
PROJECT_MODULE_CREATED = "project.module_created"
PROJECT_MODULE_UPDATED = "project.module_updated"
PROJECT_MODULE_DELETED = "project.module_deleted"
PROJECT_ITEM_PARENT_CHANGED = "project.item_parent_changed"
PROJECT_ITEM_MOVED = "project.item_moved"
PROJECT_VIEW_CREATED = "project.view_created"
PROJECT_VIEW_UPDATED = "project.view_updated"
PROJECT_VIEW_DELETED = "project.view_deleted"
PROJECT_COMMENT_UPDATED = "project.comment_updated"
PROJECT_PAGE_CREATED = "project.page_created"
PROJECT_PAGE_UPDATED = "project.page_updated"
PROJECT_PAGE_DELETED = "project.page_deleted"
PROJECT_ITEM_ACTIVITY_RECORDED = "project.item_activity_recorded"
register_event_types(
    PROJECT_CREATED,
    PROJECT_UPDATED,
    PROJECT_DELETED,
    PROJECT_ITEM_CREATED,
    PROJECT_ITEM_UPDATED,
    PROJECT_STATE_CREATED,
    PROJECT_STATE_UPDATED,
    PROJECT_MEMBER_ADDED,
    PROJECT_MEMBER_UPDATED,
    PROJECT_MEMBER_REMOVED,
    PROJECT_ITEM_DESCRIPTION_UPDATED,
    PROJECT_LABEL_CREATED,
    PROJECT_LABEL_ASSIGNED,
    PROJECT_CYCLE_UPDATED,
    PROJECT_ITEM_CYCLE_ASSIGNED,
    PROJECT_MODULE_CREATED,
    PROJECT_MODULE_UPDATED,
    PROJECT_MODULE_DELETED,
    PROJECT_ITEM_PARENT_CHANGED,
    PROJECT_ITEM_MOVED,
    PROJECT_VIEW_CREATED,
    PROJECT_VIEW_UPDATED,
    PROJECT_VIEW_DELETED,
    PROJECT_COMMENT_UPDATED,
    PROJECT_PAGE_CREATED,
    PROJECT_PAGE_UPDATED,
    PROJECT_PAGE_DELETED,
    PROJECT_ITEM_ACTIVITY_RECORDED,
)

def project_access(
    request: Request,
    workspace_id: str,
    project_id: str | None = None,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> None:
    """PL-040: enforce project-level roles on every project route.

    Public projects keep the workspace-role fallback; restricted projects are
    reachable only through a project membership (or a workspace owner/admin).
    The HTTP verb selects the read/write permission, so every route on this
    router is covered without per-endpoint exceptions.
    """
    verify_workspace(principal, workspace_id)
    if project_id is None:
        return
    project = db.execute(
        select(Project.id, Project.restricted).where(
            Project.id == project_id, Project.workspace_id == workspace_id
        )
    ).first()
    if project is None or not project.restricted:
        return
    if principal.role in ("owner", "admin"):
        return
    membership = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == principal.user.id,
        )
    ).scalar_one_or_none()
    needed = "project:write" if request.method in WRITE_METHODS else "project:read"
    granted = PROJECT_PERMISSIONS.get(membership, frozenset())
    if needed not in granted:
        raise HTTPException(
            status_code=403,
            detail=f"project permission required: {needed}",
        )


router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects",
    tags=["projects"],
    dependencies=[Depends(project_access)],
)

PROJECT_STATUSES = ("planning", "active", "on_hold", "completed")
ITEM_STATUSES = ("todo", "in_progress", "done")
STATE_GROUPS = ("todo", "in_progress", "done")
BUILTIN_STATE_GROUPS = {name: name for name in ITEM_STATUSES}

# PL-040: project-scoped roles are separate from workspace roles. A restricted
# project is reachable only through one of these memberships (or a workspace
# owner/admin). Public projects keep the existing workspace-role fallback.
PROJECT_ROLES = ("lead", "member", "viewer")
PROJECT_PERMISSIONS: dict[str, frozenset[str]] = {
    "lead": frozenset({"project:read", "project:write", "project:admin"}),
    "member": frozenset({"project:read", "project:write"}),
    "viewer": frozenset({"project:read"}),
}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

ProjectStatus = Literal["planning", "active", "on_hold", "completed"]


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="planning", nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # PL-003/040: opt-in private project with its own membership and role map.
    restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectMember(Base):
    """One workspace member's role in one project (PL-003).

    ``is_default_assignee`` and ``subscribed`` carry the lead/default-assignee
    and subscriber semantics on the same row, so a project has one membership
    registry rather than three parallel tables.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    is_default_assignee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subscribed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectState(Base):
    """Workspace-configurable work-item states grouped into progress buckets."""

    __tablename__ = "project_states"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_project_state"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    group: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectItem(Base):
    __tablename__ = "project_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    parent_item_id: Mapped[str | None] = mapped_column(ForeignKey("project_items.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    # PL-005/007/018/010: description, priority, start date and cycle membership.
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cycle_id: Mapped[str | None] = mapped_column(ForeignKey("project_cycles.id"))
    assignee_id: Mapped[str | None] = mapped_column(String(36))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# P1 tables (module-owned; no external store)
# --------------------------------------------------------------------------


class ItemDescriptionVersion(Base):
    """PL-005: append-only description history for one work item."""

    __tablename__ = "project_item_description_versions"
    __table_args__ = (
        UniqueConstraint("item_id", "version", name="uq_item_description_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    editor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectLabel(Base):
    """PL-009: a project-scoped label, shared by many work items."""

    __tablename__ = "project_labels"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", "name", name="uq_project_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ItemLabel(Base):
    __tablename__ = "project_item_labels"
    __table_args__ = (
        UniqueConstraint("workspace_id", "item_id", "label_id", name="uq_item_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(ForeignKey("project_labels.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectModule(Base):
    """PL-011: a goal/feature grouping, with lead, dates and its own state."""

    __tablename__ = "project_modules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", "name", name="uq_project_module"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[str | None] = mapped_column(String(36))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), default="planning", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectModuleMember(Base):
    __tablename__ = "project_module_members"
    __table_args__ = (
        UniqueConstraint("module_id", "user_id", name="uq_module_member"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    module_id: Mapped[str] = mapped_column(ForeignKey("project_modules.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectModuleItem(Base):
    """An item may belong to several modules (PL-011 multi-module assignment)."""

    __tablename__ = "project_module_items"
    __table_args__ = (
        UniqueConstraint("module_id", "item_id", name="uq_module_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    module_id: Mapped[str] = mapped_column(ForeignKey("project_modules.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectView(Base):
    """PL-026/027: a saved filter/layout/sort configuration with explicit sharing."""

    __tablename__ = "project_views"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", "owner_id", "name", name="uq_project_view"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    layout: Mapped[str] = mapped_column(String(20), default="list", nullable=False)
    sort_by: Mapped[str] = mapped_column(String(40), default="created_at", nullable=False)
    sort_dir: Mapped[str] = mapped_column(String(10), default="asc", nullable=False)
    shared_with: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ItemActivity(Base):
    """PL-029/079: immutable before/after projection of a work-item change.

    There are no update/delete endpoints for this table. New rows are written
    in the same transaction as the mutation they describe.
    """

    __tablename__ = "project_item_activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field: Mapped[str] = mapped_column(String(60), nullable=False)
    old_value: Mapped[object] = mapped_column(JSON)
    new_value: Mapped[object] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectPage(Base):
    """PL-094: a document scoped to a project, wiki or teamspace."""

    __tablename__ = "project_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="project", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: ProjectStatus = "planning"
    owner_id: str | None = None
    restricted: bool = False
    start_at: datetime | None = None
    due_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("project name must not be empty")
        return stripped


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    owner_id: str | None = None
    restricted: bool | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("project name must not be empty")
        return stripped


class StateCreate(BaseModel):
    name: str
    group: str = "todo"
    position: int = 0

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("state name must not be empty")
        return stripped

    @field_validator("group")
    @classmethod
    def valid_group(cls, value: str) -> str:
        if value not in STATE_GROUPS:
            raise ValueError("invalid state group")
        return value


class StatePatch(BaseModel):
    name: str | None = None
    group: str | None = None
    position: int | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("group")
    @classmethod
    def valid_group(cls, value: str | None) -> str | None:
        if value is not None and value not in STATE_GROUPS:
            raise ValueError("invalid state group")
        return value


class StateOut(BaseModel):
    id: str
    name: str
    group: str
    position: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MemberOut(BaseModel):
    id: str
    display_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ProjectMemberCreate(BaseModel):
    user_id: str
    role: str = "member"
    is_default_assignee: bool = False
    subscribed: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in PROJECT_ROLES:
            raise ValueError("invalid project role")
        return value


class ProjectMemberPatch(BaseModel):
    role: str | None = None
    is_default_assignee: bool | None = None
    subscribed: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str | None) -> str | None:
        if value is not None and value not in PROJECT_ROLES:
            raise ValueError("invalid project role")
        return value


class ProjectMemberOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    display_name: str | None
    email: str | None
    role: str
    is_default_assignee: bool
    subscribed: bool

    model_config = ConfigDict(from_attributes=True)


class ItemCreate(BaseModel):
    title: str
    status: str = "todo"
    description: str | None = None
    priority: str = "medium"
    start_at: datetime | None = None
    cycle_id: str | None = None
    assignee_id: str | None = None
    due_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("item title must not be empty")
        return stripped


class ItemPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    description: str | None = None
    priority: str | None = None
    start_at: datetime | None = None
    cycle_id: str | None = None
    assignee_id: str | None = None
    due_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("item title must not be empty")
        return stripped


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    owner_id: str
    restricted: bool
    start_at: object
    due_at: object
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ItemOut(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    state_group: str = "todo"
    description: str | None = None
    priority: str = "medium"
    start_at: object = None
    cycle_id: str | None = None
    assignee_id: str | None
    due_at: object
    completed_at: object
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ProjectProgress(BaseModel):
    project_id: str
    total_items: int
    todo_items: int
    in_progress_items: int
    done_items: int
    completion_percent: float


# ---- P1 request/response schemas -----------------------------------------


class DescriptionPatch(BaseModel):
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be empty")
        return stripped


class DescriptionVersionOut(BaseModel):
    id: str
    version: int
    body: str
    editor_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class DescriptionOut(BaseModel):
    item_id: str
    body: str | None
    version: int
    versions: list[DescriptionVersionOut]


class LabelCreate(BaseModel):
    name: str
    color: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("label name must not be empty")
        return stripped


class LabelOut(BaseModel):
    id: str
    project_id: str
    name: str
    color: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class LabelAssign(BaseModel):
    label_id: str

    model_config = ConfigDict(extra="forbid")


class CyclePatch(BaseModel):
    name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("cycle name must not be empty")
        return stripped


class CycleAssign(BaseModel):
    item_id: str

    model_config = ConfigDict(extra="forbid")


class CycleProgress(BaseModel):
    cycle_id: str
    total_items: int
    todo_items: int
    in_progress_items: int
    done_items: int
    completion_percent: float
    dates_valid: bool


MODULE_STATES = ("planning", "active", "completed", "cancelled")


class ModuleCreate(BaseModel):
    name: str
    description: str | None = None
    lead_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    state: str = "planning"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("module name must not be empty")
        return stripped

    @field_validator("state")
    @classmethod
    def valid_state(cls, value: str) -> str:
        if value not in MODULE_STATES:
            raise ValueError("invalid module state")
        return value


class ModulePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    lead_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    state: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("module name must not be empty")
        return stripped

    @field_validator("state")
    @classmethod
    def valid_state(cls, value: str | None) -> str | None:
        if value is not None and value not in MODULE_STATES:
            raise ValueError("invalid module state")
        return value


class ModuleOut(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None
    lead_id: str | None
    start_at: object
    end_at: object
    state: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ModuleMemberCreate(BaseModel):
    user_id: str

    model_config = ConfigDict(extra="forbid")


class ModuleMemberOut(BaseModel):
    id: str
    module_id: str
    user_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ModuleAssign(BaseModel):
    item_id: str

    model_config = ConfigDict(extra="forbid")


class ModuleProgress(BaseModel):
    module_id: str
    total_items: int
    done_items: int
    completion_percent: float
    dates_valid: bool


class ParentSet(BaseModel):
    parent_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class ItemRollup(BaseModel):
    item_id: str
    total_items: int
    todo_items: int
    in_progress_items: int
    done_items: int
    completion_percent: float


class MoveItem(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid")


class BoardColumn(BaseModel):
    name: str
    group: str
    position: int
    items: list[ItemOut]


class BoardOut(BaseModel):
    project_id: str
    columns: list[BoardColumn]


class ViewCreate(BaseModel):
    name: str
    filters: dict = Field(default_factory=dict)
    layout: str = "list"
    sort_by: str = "created_at"
    sort_dir: str = "asc"
    shared_with: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("view name must not be empty")
        return stripped


class ViewPatch(BaseModel):
    name: str | None = None
    filters: dict | None = None
    layout: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = None
    shared_with: list[str] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("view name must not be empty")
        return stripped


class ViewOut(BaseModel):
    id: str
    project_id: str
    name: str
    owner_id: str
    filters: dict
    layout: str
    sort_by: str
    sort_dir: str
    shared_with: list[str]
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ActivityOut(BaseModel):
    id: str
    item_id: str
    event_type: str
    field: str
    old_value: object
    new_value: object
    actor_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


PAGE_SCOPES = ("project", "wiki", "teamspace")


class PageCreate(BaseModel):
    scope: str = "project"
    title: str
    body: str = ""

    model_config = ConfigDict(extra="forbid")

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str) -> str:
        if value not in PAGE_SCOPES:
            raise ValueError("invalid page scope")
        return value

    @field_validator("title")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("page title must not be empty")
        return stripped


class PagePatch(BaseModel):
    title: str | None = None
    body: str | None = None
    scope: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str | None) -> str | None:
        if value is not None and value not in PAGE_SCOPES:
            raise ValueError("invalid page scope")
        return value

    @field_validator("title")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("page title must not be empty")
        return stripped


class PageOut(BaseModel):
    id: str
    project_id: str
    scope: str
    title: str
    body: str
    author_id: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _project_or_404(db: Session, workspace_id: str, project_id: str) -> Project:
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _item_or_404(
    db: Session, workspace_id: str, project_id: str, item_id: str
) -> ProjectItem:
    item = db.execute(
        select(ProjectItem).where(
            ProjectItem.id == item_id,
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="project item not found")
    return item


def _user_is_valid(db: Session, workspace_id: str, user_id: str | None, label: str) -> None:
    if user_id is None:
        return
    exists = db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=422, detail=f"{label} must be an active workspace member")


def _membership_or_404(
    db: Session, workspace_id: str, project_id: str, user_id: str
) -> ProjectMember:
    row = db.execute(
        select(ProjectMember).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="project member not found")
    return row


def _require_project_admin(
    db: Session, workspace_id: str, project: Project, principal: Principal
) -> None:
    if principal.role in ("owner", "admin") or project.owner_id == principal.user.id:
        return
    row = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == principal.user.id,
        )
    ).scalar_one_or_none()
    if "project:admin" not in PROJECT_PERMISSIONS.get(row, frozenset()):
        raise HTTPException(status_code=403, detail="project admin permission required")


def _member_out(db: Session, row: ProjectMember) -> ProjectMemberOut:
    user = db.get(User, row.user_id)
    return ProjectMemberOut(
        id=row.id, project_id=row.project_id, user_id=row.user_id,
        display_name=user.display_name if user else None,
        email=user.email if user else None,
        role=row.role, is_default_assignee=row.is_default_assignee,
        subscribed=row.subscribed,
    )


def _state_rows(db: Session, workspace_id: str) -> list[ProjectState]:
    return db.execute(
        select(ProjectState)
        .where(ProjectState.workspace_id == workspace_id)
        .order_by(ProjectState.position, ProjectState.name)
    ).scalars().all()


def _group_map(db: Session, workspace_id: str) -> dict[str, str]:
    rows = _state_rows(db, workspace_id)
    if not rows:
        return dict(BUILTIN_STATE_GROUPS)
    return {row.name: row.group for row in rows}


def _validate_status(db: Session, workspace_id: str, status_value: str | None) -> None:
    if status_value is None:
        return
    groups = _group_map(db, workspace_id)
    if status_value not in groups:
        raise HTTPException(
            status_code=422,
            detail="status must be one of: " + ", ".join(sorted(groups)),
        )
    inactive = db.execute(
        select(ProjectState.id).where(
            ProjectState.workspace_id == workspace_id,
            ProjectState.name == status_value,
            ProjectState.is_active.is_(False),
        )
    ).scalar_one_or_none()
    if inactive is not None:
        raise HTTPException(status_code=422, detail="state is inactive")


def _item_out(
    db: Session, item: ProjectItem, groups: dict[str, str] | None = None
) -> ItemOut:
    payload = ItemOut.model_validate(item)
    mapping = groups if groups is not None else _group_map(db, item.workspace_id)
    payload.state_group = mapping.get(item.status, "todo")
    return payload


def _sync_completion(item: ProjectItem, groups: dict[str, str]) -> None:
    """Completion follows the state's progress group, not a hard-coded name."""
    if groups.get(item.status) == "done":
        if item.completed_at is None:
            item.completed_at = now()
    else:
        item.completed_at = None


# ---- P1 helpers ----------------------------------------------------------

PRIORITIES = ("low", "medium", "high", "urgent")
MAX_HIERARCHY_DEPTH = 5


def _naive(value: datetime | None) -> datetime | None:
    """Normalise aware/naive datetimes before comparisons (SQLite drops tz)."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _jsonable(value):
    if isinstance(value, datetime):
        naive = _naive(value)
        return naive.isoformat() if naive is not None else None
    return value


def _validate_priority(value: str | None) -> None:
    if value is not None and value not in PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid priority")


def _validate_range(start_at: datetime | None, end_at: datetime | None, label: str) -> None:
    start, end = _naive(start_at), _naive(end_at)
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail=f"{label} start must not be after its end")


def _activity(
    db: Session,
    *,
    workspace_id: str,
    project_id: str,
    item_id: str,
    event_type: str,
    field: str,
    old,
    new,
    actor_id: str,
) -> ItemActivity:
    """Append one immutable before/after record and mirror it on the audit bus."""
    old_value, new_value = _jsonable(old), _jsonable(new)
    row = ItemActivity(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        item_id=item_id, event_type=event_type, field=field,
        old_value=old_value, new_value=new_value, actor_id=actor_id,
        created_at=now(),
    )
    db.add(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_ACTIVITY_RECORDED,
        entity_id=item_id, actor_id=actor_id,
        payload={"field": field, "old": old_value, "new": new_value},
    )
    return row


def _validate_parent(
    db: Session, workspace_id: str, project_id: str, item_id: str, parent_id: str | None
) -> ProjectItem | None:
    if parent_id is None:
        return None
    if parent_id == item_id:
        raise HTTPException(status_code=422, detail="item cannot be its own parent")
    parent = db.execute(
        select(ProjectItem).where(
            ProjectItem.id == parent_id,
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
        )
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="parent item not found")
    seen = {item_id}
    current: ProjectItem | None = parent
    depth = 0
    while current is not None and current.parent_item_id is not None:
        if current.parent_item_id in seen:
            raise HTTPException(status_code=422, detail="parent cycle detected")
        seen.add(current.parent_item_id)
        depth += 1
        if depth >= MAX_HIERARCHY_DEPTH:
            raise HTTPException(status_code=422, detail="hierarchy is too deep")
        current = db.execute(
            select(ProjectItem).where(
                ProjectItem.id == current.parent_item_id,
                ProjectItem.workspace_id == workspace_id,
                ProjectItem.project_id == project_id,
            )
        ).scalar_one_or_none()
    return parent


def _descendants(
    db: Session, workspace_id: str, project_id: str, item_id: str
) -> list[ProjectItem]:
    """Breadth-first walk with a visited set: a child is never counted twice."""
    found: list[ProjectItem] = []
    seen = {item_id}
    frontier = [item_id]
    while frontier:
        rows = db.execute(
            select(ProjectItem).where(
                ProjectItem.workspace_id == workspace_id,
                ProjectItem.project_id == project_id,
                ProjectItem.parent_item_id.in_(frontier),
            )
        ).scalars().all()
        frontier = []
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            found.append(row)
            frontier.append(row.id)
    return found


def _rollup(db: Session, item: ProjectItem, groups: dict[str, str]) -> ItemRollup:
    rows = [item] + _descendants(db, item.workspace_id, item.project_id, item.id)
    bucket = {"todo": 0, "in_progress": 0, "done": 0}
    for row in rows:
        bucket[groups.get(row.status, "todo")] += 1
    total = len(rows)
    return ItemRollup(
        item_id=item.id,
        total_items=total,
        todo_items=bucket["todo"],
        in_progress_items=bucket["in_progress"],
        done_items=bucket["done"],
        completion_percent=round(100.0 * bucket["done"] / total, 2) if total else 0.0,
    )


def _bucket_progress(entity_id: str, rows: list[ProjectItem], groups: dict[str, str]):
    bucket = {"todo": 0, "in_progress": 0, "done": 0}
    for row in rows:
        bucket[groups.get(row.status, "todo")] += 1
    total = len(rows)
    return bucket, total, round(100.0 * bucket["done"] / total, 2) if total else 0.0


def _cycle_or_404(db: Session, workspace_id: str, project_id: str, cycle_id: str) -> Cycle:
    row = db.execute(
        select(Cycle).where(
            Cycle.id == cycle_id,
            Cycle.workspace_id == workspace_id,
            Cycle.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="cycle not found")
    return row


def _validate_cycle_assignment(
    db: Session,
    workspace_id: str,
    project_id: str,
    cycle_id: str | None,
    start_at: datetime | None,
    due_at: datetime | None,
) -> Cycle | None:
    if cycle_id is None:
        return None
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    start, due = _naive(start_at), _naive(due_at)
    cycle_start, cycle_end = _naive(cycle.start_at), _naive(cycle.end_at)
    if cycle_start is not None and start is not None and start < cycle_start:
        raise HTTPException(status_code=422, detail="item starts before its cycle")
    if cycle_end is not None and due is not None and due > cycle_end:
        raise HTTPException(status_code=422, detail="item is due after its cycle")
    return cycle


def _module_or_404(
    db: Session, workspace_id: str, project_id: str, module_id: str
) -> ProjectModule:
    row = db.execute(
        select(ProjectModule).where(
            ProjectModule.id == module_id,
            ProjectModule.workspace_id == workspace_id,
            ProjectModule.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="module not found")
    return row


def _label_or_404(
    db: Session, workspace_id: str, project_id: str, label_id: str
) -> ProjectLabel:
    row = db.execute(
        select(ProjectLabel).where(
            ProjectLabel.id == label_id,
            ProjectLabel.workspace_id == workspace_id,
            ProjectLabel.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="label not found")
    return row


def _view_or_404(
    db: Session, workspace_id: str, project_id: str, view_id: str
) -> ProjectView:
    row = db.execute(
        select(ProjectView).where(
            ProjectView.id == view_id,
            ProjectView.workspace_id == workspace_id,
            ProjectView.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="saved view not found")
    return row


def _page_or_404(
    db: Session, workspace_id: str, project_id: str, page_id: str
) -> ProjectPage:
    row = db.execute(
        select(ProjectPage).where(
            ProjectPage.id == page_id,
            ProjectPage.workspace_id == workspace_id,
            ProjectPage.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return row


def _visible_views(views: list[ProjectView], principal: Principal) -> list[ProjectView]:
    return [
        view for view in views
        if view.owner_id == principal.user.id
        or principal.role in ("owner", "admin")
        or principal.user.id in (view.shared_with or [])
    ]


def _validate_shared_with(db: Session, workspace_id: str, ids: list[str]) -> list[str]:
    result: list[str] = []
    for user_id in ids:
        if user_id in result:
            continue
        valid = db.execute(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "active",
            )
        ).scalar_one_or_none()
        if valid is None:
            raise HTTPException(status_code=422, detail="shared_with must be active workspace members")
        result.append(user_id)
    return result


def _filtered_items(
    db: Session, workspace_id: str, project_id: str, filters: dict
) -> list[ProjectItem]:
    """Apply any combination of supported filters to real work-item rows."""
    rows = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
        ).order_by(ProjectItem.created_at, ProjectItem.id)
    ).scalars().all()
    if not filters:
        return rows

    for key, value in filters.items():
        if value is None or value == "" or value is False:
            continue
        if key in ("status", "priority") or key.startswith("status_") or key.startswith("priority_"):
            field = key.split("_")[0]
            allowed = value if isinstance(value, list) else [value]
            rows = [row for row in rows if getattr(row, field) in allowed]
        elif key == "assignee_id":
            rows = [row for row in rows if row.assignee_id == value]
        elif key == "cycle_id":
            rows = [row for row in rows if row.cycle_id == value]
        elif key == "module_id":
            assigned = db.execute(
                select(ProjectModuleItem.item_id).where(
                    ProjectModuleItem.workspace_id == workspace_id,
                    ProjectModuleItem.project_id == project_id,
                    ProjectModuleItem.module_id == value,
                )
            ).scalars().all()
            rows = [row for row in rows if row.id in assigned]
        elif key == "label":
            names = value if isinstance(value, list) else [value]
            label_ids = db.execute(
                select(ProjectLabel.id).where(
                    ProjectLabel.workspace_id == workspace_id,
                    ProjectLabel.project_id == project_id,
                    ProjectLabel.name.in_(names),
                )
            ).scalars().all()
            assigned = db.execute(
                select(ItemLabel.item_id).where(
                    ItemLabel.workspace_id == workspace_id,
                    ItemLabel.project_id == project_id,
                    ItemLabel.label_id.in_(label_ids),
                )
            ).scalars().all()
            rows = [row for row in rows if row.id in assigned]
        elif key in ("start_from", "start_to", "due_from", "due_to"):
            prefix, bound = key.split("_")
            field = f"{prefix}_at"
            cutoff = _naive(value if isinstance(value, datetime) else datetime.fromisoformat(str(value)))
            if bound == "from":
                rows = [row for row in rows
                        if _naive(getattr(row, field)) is not None and _naive(getattr(row, field)) >= cutoff]
            else:
                rows = [row for row in rows
                        if _naive(getattr(row, field)) is not None and _naive(getattr(row, field)) <= cutoff]
        elif key == "q":
            needle = str(value).lower()
            rows = [row for row in rows
                    if needle in row.title.lower() or needle in (row.description or "").lower()]
        elif key == "overdue":
            groups = _group_map(db, workspace_id)
            done_states = {name for name, group in groups.items() if group == "done"}
            rows = [row for row in rows
                    if _naive(row.due_at) is not None
                    and _naive(row.due_at) < _naive(now())
                    and row.status not in done_states]
    return rows


def _sorted_items(items: list[ProjectItem], view: ProjectView) -> list[ProjectItem]:
    allowed = {"created_at", "updated_at", "title", "priority", "status"}
    field = view.sort_by if view.sort_by in allowed else "created_at"
    return sorted(
        items,
        key=lambda row: (getattr(row, field) is None, getattr(row, field)),
        reverse=view.sort_dir == "desc",
    )


def _sync_description_version(
    db: Session, item: ProjectItem, body: str, actor_id: str
) -> int:
    last = db.execute(
        select(func.max(ItemDescriptionVersion.version)).where(
            ItemDescriptionVersion.workspace_id == item.workspace_id,
            ItemDescriptionVersion.item_id == item.id,
        )
    ).scalar()
    version = int(last or 0) + 1
    db.add(ItemDescriptionVersion(
        id=new_id(), workspace_id=item.workspace_id, project_id=item.project_id,
        item_id=item.id, version=version, body=body, editor_id=actor_id,
        created_at=now(),
    ))
    return version


# --------------------------------------------------------------------------
# State endpoints
# --------------------------------------------------------------------------


@router.get("/states", response_model=list[StateOut])
def list_states(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectState]:
    verify_workspace(principal, workspace_id)
    return _state_rows(db, workspace_id)


@router.post("/states", response_model=StateOut, status_code=status.HTTP_201_CREATED)
def create_state(
    workspace_id: str,
    body: StateCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectState:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(ProjectState.id).where(
            ProjectState.workspace_id == workspace_id, ProjectState.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="state already exists")
    state = ProjectState(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        group=body.group, position=body.position,
        created_at=now(), updated_at=now(),
    )
    db.add(state)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_STATE_CREATED,
        entity_id=state.id, actor_id=principal.user.id,
        payload={"name": state.name, "group": state.group},
    )
    db.commit()
    return state


@router.patch("/states/{state_id}", response_model=StateOut)
def patch_state(
    workspace_id: str,
    state_id: str,
    body: StatePatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectState:
    verify_workspace(principal, workspace_id)
    state = db.execute(
        select(ProjectState).where(
            ProjectState.id == state_id, ProjectState.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="state not found")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        exists = db.execute(
            select(ProjectState.id).where(
                ProjectState.workspace_id == workspace_id,
                ProjectState.name == updates["name"],
                ProjectState.id != state.id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            raise HTTPException(status_code=409, detail="state already exists")
    for key, value in updates.items():
        setattr(state, key, value)
    state.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_STATE_UPDATED,
        entity_id=state.id, actor_id=principal.user.id,
        payload={"fields": sorted(updates.keys())},
    )
    db.commit()
    return state


@router.get("/assignees", response_model=list[MemberOut])
def list_project_assignees(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[User]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active",
        )
        .order_by(User.display_name)
    ).scalars().all()


# --------------------------------------------------------------------------
# Project endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[ProjectOut])
def list_projects(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[Project]:
    verify_workspace(principal, workspace_id)
    query = select(Project).where(Project.workspace_id == workspace_id)
    if principal.role not in ("owner", "admin"):
        member_projects = select(ProjectMember.project_id).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.user_id == principal.user.id,
        )
        query = query.where(
            (Project.restricted.is_(False)) | (Project.id.in_(member_projects))
        )
    if status_filter:
        if status_filter not in PROJECT_STATUSES:
            raise HTTPException(status_code=422, detail="invalid project status filter")
        query = query.where(Project.status == status_filter)
    return db.execute(query.order_by(Project.created_at.desc())).scalars().all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    workspace_id: str,
    body: ProjectCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Project:
    verify_workspace(principal, workspace_id)
    owner_id = body.owner_id or principal.user.id
    _user_is_valid(db, workspace_id, owner_id, "owner")
    project = Project(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name.strip(),
        description=body.description,
        status=body.status,
        owner_id=owner_id,
        restricted=body.restricted,
        start_at=body.start_at,
        due_at=body.due_at,
        created_at=now(),
        updated_at=now(),
    )
    db.add(project)
    db.flush()
    # The creator is always a project lead, so a restricted project remains
    # administrable by the person who created it.
    db.add(ProjectMember(
        id=new_id(), workspace_id=workspace_id, project_id=project.id,
        user_id=principal.user.id, role="lead", is_default_assignee=True,
        subscribed=True, created_at=now(), updated_at=now(),
    ))
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PROJECT_CREATED,
        entity_id=project.id,
        payload={"name": project.name, "status": project.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> Project:
    verify_workspace(principal, workspace_id)
    return _project_or_404(db, workspace_id, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    workspace_id: str,
    project_id: str,
    body: ProjectPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Project:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    updates = body.model_dump(exclude_unset=True)
    if "owner_id" in updates:
        if updates["owner_id"] is None:
            raise HTTPException(status_code=422, detail="owner is required")
        _user_is_valid(db, workspace_id, updates["owner_id"], "owner")
    for key, value in updates.items():
        setattr(project, key, value)
    project.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PROJECT_UPDATED,
        entity_id=project.id,
        payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    # Deleting a whole project is an administrative act; a plain member may
    # edit items but must not remove the project for everyone.
    _require_project_admin(db, workspace_id, project, principal)
    db.execute(
        delete(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project.id,
        )
    )
    db.execute(
        delete(ProjectMember).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project.id,
        )
    )
    db.delete(project)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PROJECT_DELETED,
        entity_id=project.id,
        payload={"name": project.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "project_id": project.id}


# --------------------------------------------------------------------------
# Project membership endpoints (PL-003 / PL-040)
# --------------------------------------------------------------------------


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_project_members(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectMemberOut]:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    _require_project_admin(db, workspace_id, project, principal)
    rows = db.execute(
        select(ProjectMember)
        .where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
        )
        .order_by(ProjectMember.created_at)
    ).scalars().all()
    return [_member_out(db, row) for row in rows]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    workspace_id: str,
    project_id: str,
    body: ProjectMemberCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectMemberOut:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    _require_project_admin(db, workspace_id, project, principal)
    _user_is_valid(db, workspace_id, body.user_id, "member")
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="member already in project")
    if body.is_default_assignee:
        db.execute(
            ProjectMember.__table__.update().where(
                ProjectMember.workspace_id == workspace_id,
                ProjectMember.project_id == project_id,
                ProjectMember.is_default_assignee.is_(True),
            ).values(is_default_assignee=False)
        )
    row = ProjectMember(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        user_id=body.user_id, role=body.role,
        is_default_assignee=body.is_default_assignee,
        subscribed=body.subscribed, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MEMBER_ADDED,
        entity_id=project_id,
        payload={"user_id": body.user_id, "role": body.role},
        actor_id=principal.user.id,
    )
    db.commit()
    return _member_out(db, row)


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberOut)
def update_project_member(
    workspace_id: str,
    project_id: str,
    user_id: str,
    body: ProjectMemberPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectMemberOut:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    _require_project_admin(db, workspace_id, project, principal)
    row = _membership_or_404(db, workspace_id, project_id, user_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="at least one field is required")
    if updates.get("is_default_assignee"):
        db.execute(
            ProjectMember.__table__.update().where(
                ProjectMember.workspace_id == workspace_id,
                ProjectMember.project_id == project_id,
                ProjectMember.is_default_assignee.is_(True),
            ).values(is_default_assignee=False)
        )
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MEMBER_UPDATED,
        entity_id=project_id,
        payload={"user_id": user_id, "fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return _member_out(db, row)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_project_member(
    workspace_id: str,
    project_id: str,
    user_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    _require_project_admin(db, workspace_id, project, principal)
    row = _membership_or_404(db, workspace_id, project_id, user_id)
    if project.owner_id == user_id:
        raise HTTPException(status_code=409, detail="project owner cannot be removed")
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MEMBER_REMOVED,
        entity_id=project_id, payload={"user_id": user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"removed": True, "user_id": user_id}


# --------------------------------------------------------------------------
# Item endpoints
# --------------------------------------------------------------------------


@router.get("/{project_id}/items", response_model=list[ItemOut])
def list_items(
    workspace_id: str,
    project_id: str,
    overdue: bool = Query(False),
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    assignee_id: str | None = Query(None),
    label: list[str] = Query(default=[]),
    cycle_id: str | None = Query(None),
    module_id: str | None = Query(None),
    start_from: datetime | None = Query(None),
    start_to: datetime | None = Query(None),
    due_from: datetime | None = Query(None),
    due_to: datetime | None = Query(None),
    q: str | None = Query(None),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    _validate_priority(priority)
    filters = {
        "overdue": overdue,
        "status": status_filter,
        "priority": priority,
        "assignee_id": assignee_id,
        "label": label or None,
        "cycle_id": cycle_id,
        "module_id": module_id,
        "start_from": start_from,
        "start_to": start_to,
        "due_from": due_from,
        "due_to": due_to,
        "q": q,
    }
    groups = _group_map(db, workspace_id)
    items = _filtered_items(db, workspace_id, project.id, filters)
    return [_item_out(db, item, groups) for item in items]


@router.post(
    "/{project_id}/items",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    workspace_id: str,
    project_id: str,
    body: ItemCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    groups = _group_map(db, workspace_id)
    _validate_status(db, workspace_id, body.status)
    _validate_priority(body.priority)
    _validate_range(body.start_at, body.due_at, "work item")
    _validate_cycle_assignment(db, workspace_id, project.id, body.cycle_id,
                               body.start_at, body.due_at)
    _user_is_valid(db, workspace_id, body.assignee_id, "assignee")
    item = ProjectItem(
        id=new_id(),
        workspace_id=workspace_id,
        project_id=project.id,
        title=body.title.strip(),
        status=body.status,
        description=body.description,
        priority=body.priority,
        start_at=_naive(body.start_at),
        cycle_id=body.cycle_id,
        assignee_id=body.assignee_id,
        due_at=_naive(body.due_at),
        tags=body.tags,
        created_at=now(),
        updated_at=now(),
    )
    _sync_completion(item, groups)
    db.add(item)
    db.flush()
    _activity(
        db, workspace_id=workspace_id, project_id=project.id, item_id=item.id,
        event_type=PROJECT_ITEM_CREATED, field="item", old=None, new=item.title,
        actor_id=principal.user.id,
    )
    if body.description is not None:
        _sync_description_version(db, item, body.description, principal.user.id)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PROJECT_ITEM_CREATED,
        entity_id=item.id,
        payload={
            "project_id": project.id,
            "title": item.title,
            "status": item.status,
            "state_group": groups.get(item.status, "todo"),
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return _item_out(db, item, groups)


@router.patch("/{project_id}/items/{item_id}", response_model=ItemOut)
def patch_item(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: ItemPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project.id, item_id)
    groups = _group_map(db, workspace_id)
    updates = body.model_dump(exclude_unset=True)
    if "status" in updates:
        _validate_status(db, workspace_id, updates["status"])
    if "priority" in updates:
        _validate_priority(updates["priority"])
    if "assignee_id" in updates:
        _user_is_valid(db, workspace_id, updates["assignee_id"], "assignee")
    previous = {key: getattr(item, key) for key in updates}
    new_start = updates.get("start_at", item.start_at)
    new_due = updates.get("due_at", item.due_at)
    new_cycle = updates.get("cycle_id", item.cycle_id)
    _validate_range(new_start, new_due, "work item")
    _validate_cycle_assignment(db, workspace_id, project.id, new_cycle, new_start, new_due)
    for key, value in updates.items():
        if key in ("start_at", "due_at"):
            value = _naive(value)
        setattr(item, key, value)
    _sync_completion(item, groups)
    item.updated_at = now()
    for key, old_value in previous.items():
        _activity(
            db, workspace_id=workspace_id, project_id=project.id, item_id=item.id,
            event_type=PROJECT_ITEM_UPDATED, field=key, old=old_value,
            new=getattr(item, key), actor_id=principal.user.id,
        )
    if "description" in updates and updates["description"] is not None:
        version = _sync_description_version(db, item, updates["description"], principal.user.id)
        publish_event(
            db, workspace_id=workspace_id,
            event_type=PROJECT_ITEM_DESCRIPTION_UPDATED, entity_id=item.id,
            payload={"version": version}, actor_id=principal.user.id,
        )
    if "cycle_id" in updates:
        publish_event(
            db, workspace_id=workspace_id,
            event_type=PROJECT_ITEM_CYCLE_ASSIGNED, entity_id=item.id,
            payload={"cycle_id": new_cycle}, actor_id=principal.user.id,
        )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PROJECT_ITEM_UPDATED,
        entity_id=item.id,
        payload={
            "project_id": project.id,
            "fields": sorted(updates.keys()),
            "status": item.status,
            "state_group": groups.get(item.status, "todo"),
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return _item_out(db, item, groups)


@router.get("/{project_id}/progress", response_model=ProjectProgress)
def project_progress(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ProjectProgress:
    verify_workspace(principal, workspace_id)
    project = _project_or_404(db, workspace_id, project_id)
    # Aggregation stays in SQL; the configurable state -> progress group mapping
    # is applied to those counts so renamed/custom states roll up correctly.
    by_status = db.execute(
        select(ProjectItem.status, func.count(ProjectItem.id))
        .where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project.id,
        )
        .group_by(ProjectItem.status)
    ).all()
    groups = _group_map(db, workspace_id)
    bucket = {"todo": 0, "in_progress": 0, "done": 0}
    for status_value, count in by_status:
        bucket[groups.get(status_value, "todo")] += int(count)
    total = sum(bucket.values())
    done = bucket["done"]
    return ProjectProgress(
        project_id=project.id,
        total_items=total,
        todo_items=bucket["todo"],
        in_progress_items=bucket["in_progress"],
        done_items=done,
        completion_percent=round(100.0 * done / total, 2) if total else 0.0,
    )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class ProjectComment(Base):
    __tablename__ = "project_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("project_items.id"))
    # PL-030: threaded replies and a single edited_at marker (never rewritten).
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("project_comments.id"))
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommentCreate(BaseModel):
    body: str
    item_id: str | None = None
    parent_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("comment body must not be empty")
        return stripped


class CommentOut(BaseModel):
    id: str
    project_id: str
    item_id: str | None
    parent_id: str | None = None
    author_id: str
    body: str
    created_at: object
    edited_at: object = None

    model_config = ConfigDict(from_attributes=True)


class CommentPatch(BaseModel):
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("comment body must not be empty")
        return stripped


@router.get("/{project_id}/comments", response_model=list[CommentOut])
def list_comments(
    workspace_id: str,
    project_id: str,
    item_id: str | None = Query(None),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectComment]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    query = select(ProjectComment).where(
        ProjectComment.workspace_id == workspace_id, ProjectComment.project_id == project_id
    )
    if item_id is not None:
        query = query.where(ProjectComment.item_id == item_id)
    return db.execute(query.order_by(ProjectComment.created_at)).scalars().all()


@router.post("/{project_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    workspace_id: str,
    project_id: str,
    body: CommentCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectComment:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item_id = body.item_id
    if item_id:
        item = db.execute(
            select(ProjectItem).where(
                ProjectItem.id == item_id, ProjectItem.workspace_id == workspace_id,
                ProjectItem.project_id == project_id,
            )
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="item not found")
    if body.parent_id:
        parent = db.execute(
            select(ProjectComment).where(
                ProjectComment.id == body.parent_id,
                ProjectComment.workspace_id == workspace_id,
                ProjectComment.project_id == project_id,
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="parent comment not found")
        if parent.item_id is not None and item_id is not None and parent.item_id != item_id:
            raise HTTPException(status_code=422, detail="reply must stay on the parent's work item")
        item_id = parent.item_id
    comment = ProjectComment(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        item_id=item_id, parent_id=body.parent_id, author_id=principal.user.id,
        body=body.body.strip(), created_at=now(),
    )
    db.add(comment)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_UPDATED,
        entity_id=comment.id,
        payload={"comment": True, "project_id": project_id, "parent_id": body.parent_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return comment


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MilestoneCreate(BaseModel):
    name: str
    due_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("milestone name must not be empty")
        return stripped


class MilestoneOut(BaseModel):
    id: str
    project_id: str
    name: str
    due_at: object
    completed_at: object
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectMilestone]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return db.execute(
        select(ProjectMilestone)
        .where(ProjectMilestone.workspace_id == workspace_id, ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.created_at)
    ).scalars().all()


@router.post("/{project_id}/milestones", response_model=MilestoneOut, status_code=status.HTTP_201_CREATED)
def create_milestone(
    workspace_id: str,
    project_id: str,
    body: MilestoneCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectMilestone:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    m = ProjectMilestone(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        name=body.name.strip(), due_at=body.due_at, created_at=now(),
    )
    db.add(m)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_CREATED,
        entity_id=m.id, payload={"milestone": True, "project_id": project_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return m


@router.post("/{project_id}/milestones/{milestone_id}/complete", response_model=MilestoneOut)
def complete_milestone(
    workspace_id: str,
    project_id: str,
    milestone_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectMilestone:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    m = db.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.workspace_id == workspace_id,
            ProjectMilestone.project_id == project_id,
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    m.completed_at = now()
    db.commit()
    return m


# ---------------------------------------------------------------------------
# Sub-issues / parent-child
# ---------------------------------------------------------------------------


@router.post("/{project_id}/items/{item_id}/sub-items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_sub_item(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: ItemCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    parent = db.execute(
        select(ProjectItem).where(ProjectItem.id == item_id, ProjectItem.workspace_id == workspace_id, ProjectItem.project_id == project_id)
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="parent item not found")
    groups = _group_map(db, workspace_id)
    _validate_status(db, workspace_id, body.status)
    _user_is_valid(db, workspace_id, body.assignee_id, "assignee")
    item = ProjectItem(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        parent_item_id=item_id, title=body.title.strip(), status=body.status,
        assignee_id=body.assignee_id, due_at=body.due_at, tags=body.tags,
        created_at=now(), updated_at=now(),
    )
    _sync_completion(item, groups)
    db.add(item)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=PROJECT_ITEM_CREATED,
                  entity_id=item.id, payload={"parent_item_id": item_id, "state_group": groups.get(item.status, "todo")}, actor_id=principal.user.id)
    db.commit()
    return _item_out(db, item, groups)


@router.get("/{project_id}/items/{item_id}/sub-items", response_model=list[ItemOut])
def list_sub_items(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    groups = _group_map(db, workspace_id)
    items = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
            ProjectItem.parent_item_id == item_id,
        ).order_by(ProjectItem.created_at)
    ).scalars().all()
    return [_item_out(db, item, groups) for item in items]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class ItemDependency(Base):
    __tablename__ = "item_dependencies"
    __table_args__ = (UniqueConstraint("item_id", "depends_on_id", name="uq_item_dep"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DependencyCreate(BaseModel):
    depends_on_id: str

    model_config = ConfigDict(extra="forbid")


@router.post("/{project_id}/items/{item_id}/dependencies", status_code=status.HTTP_201_CREATED)
def add_dependency(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: DependencyCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    if item_id == body.depends_on_id:
        raise HTTPException(status_code=422, detail="item cannot depend on itself")
    dep = ItemDependency(
        id=new_id(), workspace_id=workspace_id, item_id=item_id,
        depends_on_id=body.depends_on_id, created_at=now(),
    )
    db.add(dep)
    db.commit()
    return {"created": True, "item_id": item_id, "depends_on_id": body.depends_on_id}


@router.get("/{project_id}/items/{item_id}/dependencies")
def list_dependencies(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    rows = db.execute(
        select(ItemDependency).where(ItemDependency.workspace_id == workspace_id, ItemDependency.item_id == item_id)
    ).scalars().all()
    return [{"id": r.id, "depends_on_id": r.depends_on_id, "created_at": r.created_at} for r in rows]


# ---------------------------------------------------------------------------
# Cycles
# ---------------------------------------------------------------------------


class Cycle(Base):
    __tablename__ = "project_cycles"
    __table_args__ = (UniqueConstraint("workspace_id", "project_id", "name", name="uq_cycle"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CycleCreate(BaseModel):
    name: str
    start_at: datetime | None = None
    end_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("cycle name must not be empty")
        return stripped


class CycleOut(BaseModel):
    id: str
    project_id: str
    name: str
    start_at: object
    end_at: object
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/{project_id}/cycles", response_model=list[CycleOut])
def list_cycles(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[Cycle]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return db.execute(
        select(Cycle).where(Cycle.workspace_id == workspace_id, Cycle.project_id == project_id).order_by(Cycle.created_at)
    ).scalars().all()


@router.post("/{project_id}/cycles", response_model=CycleOut, status_code=status.HTTP_201_CREATED)
def create_cycle(
    workspace_id: str,
    project_id: str,
    body: CycleCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Cycle:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _validate_range(body.start_at, body.end_at, "cycle")
    c = Cycle(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        name=body.name.strip(), start_at=_naive(body.start_at),
        end_at=_naive(body.end_at), created_at=now(),
    )
    db.add(c)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_CYCLE_UPDATED,
        entity_id=c.id, payload={"name": c.name, "action": "created"},
        actor_id=principal.user.id,
    )
    db.commit()
    return c


# ===========================================================================
# P1 Plane endpoints
#
# Every route below is workspace-scoped by the router's project_access
# dependency, checks the project exists in that workspace, uses TASK_READ /
# TASK_WRITE, writes an append-only event and commits before returning.
# Static suffixes keep these routes out of the /{project_id} and
# /{project_id}/items/{item_id} shadowing paths.
# ===========================================================================


def _description_out(db: Session, item: ProjectItem) -> DescriptionOut:
    versions = db.execute(
        select(ItemDescriptionVersion).where(
            ItemDescriptionVersion.workspace_id == item.workspace_id,
            ItemDescriptionVersion.item_id == item.id,
        ).order_by(ItemDescriptionVersion.version)
    ).scalars().all()
    return DescriptionOut(
        item_id=item.id, body=item.description,
        version=len(versions), versions=versions,
    )


# ---- PL-005: descriptions with version history ---------------------------


@router.get("/{project_id}/items/{item_id}/description", response_model=DescriptionOut)
def get_item_description(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> DescriptionOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    return _description_out(db, item)


@router.patch("/{project_id}/items/{item_id}/description", response_model=DescriptionOut)
def edit_item_description(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: DescriptionPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> DescriptionOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    old = item.description
    item.description = body.body
    item.updated_at = now()
    version = _sync_description_version(db, item, body.body, principal.user.id)
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_DESCRIPTION_UPDATED, field="description",
        old=old, new=body.body, actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_DESCRIPTION_UPDATED,
        entity_id=item.id, payload={"version": version},
        actor_id=principal.user.id,
    )
    db.commit()
    return _description_out(db, item)


# ---- PL-009: labels ------------------------------------------------------


@router.get("/{project_id}/labels", response_model=list[LabelOut])
def list_labels(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectLabel]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return db.execute(
        select(ProjectLabel).where(
            ProjectLabel.workspace_id == workspace_id,
            ProjectLabel.project_id == project_id,
        ).order_by(ProjectLabel.name)
    ).scalars().all()


@router.post("/{project_id}/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
def create_label(
    workspace_id: str,
    project_id: str,
    body: LabelCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectLabel:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    exists = db.execute(
        select(ProjectLabel.id).where(
            ProjectLabel.workspace_id == workspace_id,
            ProjectLabel.project_id == project_id,
            ProjectLabel.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="label already exists")
    label = ProjectLabel(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        name=body.name, color=body.color, created_at=now(),
    )
    db.add(label)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_LABEL_CREATED,
        entity_id=label.id, payload={"name": label.name}, actor_id=principal.user.id,
    )
    db.commit()
    return label


@router.get("/{project_id}/items/{item_id}/labels", response_model=list[LabelOut])
def list_item_labels(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectLabel]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _item_or_404(db, workspace_id, project_id, item_id)
    return db.execute(
        select(ProjectLabel)
        .join(ItemLabel, ItemLabel.label_id == ProjectLabel.id)
        .where(
            ItemLabel.workspace_id == workspace_id,
            ItemLabel.project_id == project_id,
            ItemLabel.item_id == item_id,
        )
        .order_by(ProjectLabel.name)
    ).scalars().all()


@router.post(
    "/{project_id}/items/{item_id}/labels",
    response_model=LabelOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_label(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: LabelAssign,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectLabel:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    label = _label_or_404(db, workspace_id, project_id, body.label_id)
    exists = db.execute(
        select(ItemLabel.id).where(
            ItemLabel.workspace_id == workspace_id,
            ItemLabel.item_id == item_id,
            ItemLabel.label_id == label.id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="label already assigned")
    db.add(ItemLabel(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        item_id=item.id, label_id=label.id, created_at=now(),
    ))
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_LABEL_ASSIGNED, field="label", old=None, new=label.name,
        actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_LABEL_ASSIGNED,
        entity_id=item.id, payload={"label_id": label.id, "name": label.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return label


@router.delete("/{project_id}/items/{item_id}/labels/{label_id}", status_code=status.HTTP_200_OK)
def unassign_label(
    workspace_id: str,
    project_id: str,
    item_id: str,
    label_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    label = _label_or_404(db, workspace_id, project_id, label_id)
    row = db.execute(
        select(ItemLabel).where(
            ItemLabel.workspace_id == workspace_id,
            ItemLabel.item_id == item.id,
            ItemLabel.label_id == label.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="label is not assigned to this item")
    db.delete(row)
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_LABEL_ASSIGNED, field="label", old=label.name, new=None,
        actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_LABEL_ASSIGNED,
        entity_id=item.id, payload={"label_id": label.id, "removed": True},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"removed": True, "item_id": item.id, "label_id": label.id}


# ---- PL-010: cycles / sprints --------------------------------------------


@router.patch("/{project_id}/cycles/{cycle_id}", response_model=CycleOut)
def patch_cycle(
    workspace_id: str,
    project_id: str,
    cycle_id: str,
    body: CyclePatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Cycle:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    updates = body.model_dump(exclude_unset=True)
    start = updates.get("start_at", cycle.start_at)
    end = updates.get("end_at", cycle.end_at)
    _validate_range(start, end, "cycle")
    if "name" in updates:
        clash = db.execute(
            select(Cycle.id).where(
                Cycle.workspace_id == workspace_id, Cycle.project_id == project_id,
                Cycle.name == updates["name"], Cycle.id != cycle.id,
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(status_code=409, detail="cycle already exists")
    assigned = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
            ProjectItem.cycle_id == cycle.id,
        )
    ).scalars().all()
    for item in assigned:
        item_start = _naive(item.start_at) if "start_at" not in updates else _naive(start)
        item_due = _naive(item.due_at) if "end_at" not in updates else _naive(end)
        if (item_start is not None and _naive(start) is not None and item_start < _naive(start)) or (
            item_due is not None and _naive(end) is not None and item_due > _naive(end)
        ):
            raise HTTPException(status_code=422, detail="assigned item falls outside the cycle dates")
    for key, value in updates.items():
        setattr(cycle, key, _naive(value) if key in ("start_at", "end_at") else value)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_CYCLE_UPDATED,
        entity_id=cycle.id, payload={"fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return cycle


@router.post(
    "/{project_id}/cycles/{cycle_id}/items",
    status_code=status.HTTP_201_CREATED,
)
def assign_item_to_cycle(
    workspace_id: str,
    project_id: str,
    cycle_id: str,
    body: CycleAssign,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    item = _item_or_404(db, workspace_id, project_id, body.item_id)
    previous = item.cycle_id
    _validate_cycle_assignment(db, workspace_id, project_id, cycle.id,
                               item.start_at, item.due_at)
    item.cycle_id = cycle.id
    item.updated_at = now()
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_CYCLE_ASSIGNED, field="cycle_id", old=previous,
        new=cycle.id, actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_CYCLE_ASSIGNED,
        entity_id=item.id, payload={"cycle_id": cycle.id}, actor_id=principal.user.id,
    )
    db.commit()
    return {"item_id": item.id, "cycle_id": cycle.id}


@router.delete("/{project_id}/cycles/{cycle_id}/items/{item_id}", status_code=status.HTTP_200_OK)
def unassign_item_from_cycle(
    workspace_id: str,
    project_id: str,
    cycle_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    if item.cycle_id != cycle.id:
        raise HTTPException(status_code=404, detail="item is not in this cycle")
    item.cycle_id = None
    item.updated_at = now()
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_CYCLE_ASSIGNED, field="cycle_id", old=cycle.id,
        new=None, actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_CYCLE_ASSIGNED,
        entity_id=item.id, payload={"cycle_id": None}, actor_id=principal.user.id,
    )
    db.commit()
    return {"item_id": item.id, "cycle_id": None}


@router.get("/{project_id}/cycles/{cycle_id}/items", response_model=list[ItemOut])
def list_cycle_items(
    workspace_id: str,
    project_id: str,
    cycle_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    groups = _group_map(db, workspace_id)
    rows = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
            ProjectItem.cycle_id == cycle.id,
        ).order_by(ProjectItem.created_at)
    ).scalars().all()
    return [_item_out(db, row, groups) for row in rows]


@router.get("/{project_id}/cycles/{cycle_id}/progress", response_model=CycleProgress)
def cycle_progress(
    workspace_id: str,
    project_id: str,
    cycle_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> CycleProgress:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    cycle = _cycle_or_404(db, workspace_id, project_id, cycle_id)
    rows = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
            ProjectItem.cycle_id == cycle.id,
        )
    ).scalars().all()
    bucket, total, percent = _bucket_progress(cycle.id, rows, _group_map(db, workspace_id))
    start, end = _naive(cycle.start_at), _naive(cycle.end_at)
    return CycleProgress(
        cycle_id=cycle.id, total_items=total,
        todo_items=bucket["todo"], in_progress_items=bucket["in_progress"],
        done_items=bucket["done"], completion_percent=percent,
        dates_valid=start is None or end is None or start <= end,
    )


# ---- PL-011: modules -----------------------------------------------------


@router.get("/{project_id}/modules", response_model=list[ModuleOut])
def list_modules(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectModule]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return db.execute(
        select(ProjectModule).where(
            ProjectModule.workspace_id == workspace_id,
            ProjectModule.project_id == project_id,
        ).order_by(ProjectModule.created_at)
    ).scalars().all()


@router.post("/{project_id}/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    workspace_id: str,
    project_id: str,
    body: ModuleCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectModule:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _user_is_valid(db, workspace_id, body.lead_id, "lead")
    _validate_range(body.start_at, body.end_at, "module")
    exists = db.execute(
        select(ProjectModule.id).where(
            ProjectModule.workspace_id == workspace_id,
            ProjectModule.project_id == project_id,
            ProjectModule.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="module already exists")
    module = ProjectModule(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        name=body.name, description=body.description, lead_id=body.lead_id,
        start_at=_naive(body.start_at), end_at=_naive(body.end_at),
        state=body.state, created_at=now(), updated_at=now(),
    )
    db.add(module)
    if body.lead_id:
        db.add(ProjectModuleMember(
            id=new_id(), workspace_id=workspace_id, project_id=project_id,
            module_id=module.id, user_id=body.lead_id, created_at=now(),
        ))
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_CREATED,
        entity_id=module.id, payload={"name": module.name, "state": module.state},
        actor_id=principal.user.id,
    )
    db.commit()
    return module


@router.get("/{project_id}/modules/{module_id}", response_model=ModuleOut)
def get_module(
    workspace_id: str,
    project_id: str,
    module_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ProjectModule:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return _module_or_404(db, workspace_id, project_id, module_id)


@router.patch("/{project_id}/modules/{module_id}", response_model=ModuleOut)
def patch_module(
    workspace_id: str,
    project_id: str,
    module_id: str,
    body: ModulePatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectModule:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    updates = body.model_dump(exclude_unset=True)
    if "lead_id" in updates:
        _user_is_valid(db, workspace_id, updates["lead_id"], "lead")
    _validate_range(updates.get("start_at", module.start_at),
                    updates.get("end_at", module.end_at), "module")
    for key, value in updates.items():
        setattr(module, key, _naive(value) if key in ("start_at", "end_at") else value)
    module.updated_at = now()
    if "lead_id" in updates and updates["lead_id"]:
        existing = db.execute(
            select(ProjectModuleMember.id).where(
                ProjectModuleMember.workspace_id == workspace_id,
                ProjectModuleMember.module_id == module.id,
                ProjectModuleMember.user_id == updates["lead_id"],
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(ProjectModuleMember(
                id=new_id(), workspace_id=workspace_id, project_id=project_id,
                module_id=module.id, user_id=updates["lead_id"], created_at=now(),
            ))
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_UPDATED,
        entity_id=module.id, payload={"fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return module


@router.delete("/{project_id}/modules/{module_id}", status_code=status.HTTP_200_OK)
def delete_module(
    workspace_id: str,
    project_id: str,
    module_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    db.execute(delete(ProjectModuleItem).where(
        ProjectModuleItem.workspace_id == workspace_id, ProjectModuleItem.module_id == module.id))
    db.execute(delete(ProjectModuleMember).where(
        ProjectModuleMember.workspace_id == workspace_id, ProjectModuleMember.module_id == module.id))
    db.delete(module)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_DELETED,
        entity_id=module.id, payload={"name": module.name}, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "module_id": module.id}


@router.get("/{project_id}/modules/{module_id}/members", response_model=list[ModuleMemberOut])
def list_module_members(
    workspace_id: str,
    project_id: str,
    module_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectModuleMember]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _module_or_404(db, workspace_id, project_id, module_id)
    return db.execute(
        select(ProjectModuleMember).where(
            ProjectModuleMember.workspace_id == workspace_id,
            ProjectModuleMember.module_id == module_id,
        ).order_by(ProjectModuleMember.created_at)
    ).scalars().all()


@router.post(
    "/{project_id}/modules/{module_id}/members",
    response_model=ModuleMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_module_member(
    workspace_id: str,
    project_id: str,
    module_id: str,
    body: ModuleMemberCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectModuleMember:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _module_or_404(db, workspace_id, project_id, module_id)
    _user_is_valid(db, workspace_id, body.user_id, "member")
    exists = db.execute(
        select(ProjectModuleMember.id).where(
            ProjectModuleMember.workspace_id == workspace_id,
            ProjectModuleMember.module_id == module_id,
            ProjectModuleMember.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="member already in module")
    row = ProjectModuleMember(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        module_id=module_id, user_id=body.user_id, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_UPDATED,
        entity_id=module_id, payload={"member_added": body.user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return row


@router.delete("/{project_id}/modules/{module_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_module_member(
    workspace_id: str,
    project_id: str,
    module_id: str,
    user_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    row = db.execute(
        select(ProjectModuleMember).where(
            ProjectModuleMember.workspace_id == workspace_id,
            ProjectModuleMember.module_id == module_id,
            ProjectModuleMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="module member not found")
    if module.lead_id == user_id:
        raise HTTPException(status_code=409, detail="module lead cannot be removed as a member")
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_UPDATED,
        entity_id=module_id, payload={"member_removed": user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"removed": True, "user_id": user_id}


@router.get("/{project_id}/modules/{module_id}/items", response_model=list[ItemOut])
def list_module_items(
    workspace_id: str,
    project_id: str,
    module_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _module_or_404(db, workspace_id, project_id, module_id)
    groups = _group_map(db, workspace_id)
    rows = db.execute(
        select(ProjectItem)
        .join(ProjectModuleItem, ProjectModuleItem.item_id == ProjectItem.id)
        .where(
            ProjectModuleItem.workspace_id == workspace_id,
            ProjectModuleItem.project_id == project_id,
            ProjectModuleItem.module_id == module_id,
        )
        .order_by(ProjectItem.created_at)
    ).scalars().all()
    return [_item_out(db, row, groups) for row in rows]


@router.post("/{project_id}/modules/{module_id}/items", status_code=status.HTTP_201_CREATED)
def assign_item_to_module(
    workspace_id: str,
    project_id: str,
    module_id: str,
    body: ModuleAssign,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    item = _item_or_404(db, workspace_id, project_id, body.item_id)
    existing = db.execute(
        select(ProjectModuleItem.id).where(
            ProjectModuleItem.workspace_id == workspace_id,
            ProjectModuleItem.module_id == module.id,
            ProjectModuleItem.item_id == item.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="item already in module")
    db.add(ProjectModuleItem(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        module_id=module.id, item_id=item.id, created_at=now(),
    ))
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_MODULE_UPDATED, field="module", old=None, new=module.name,
        actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_UPDATED,
        entity_id=module.id, payload={"item_added": item.id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"item_id": item.id, "module_id": module.id}


@router.delete("/{project_id}/modules/{module_id}/items/{item_id}", status_code=status.HTTP_200_OK)
def unassign_item_from_module(
    workspace_id: str,
    project_id: str,
    module_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    row = db.execute(
        select(ProjectModuleItem).where(
            ProjectModuleItem.workspace_id == workspace_id,
            ProjectModuleItem.module_id == module.id,
            ProjectModuleItem.item_id == item.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="item is not in this module")
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_MODULE_UPDATED,
        entity_id=module.id, payload={"item_removed": item.id}, actor_id=principal.user.id,
    )
    db.commit()
    return {"removed": True, "item_id": item.id, "module_id": module.id}


@router.get("/{project_id}/modules/{module_id}/progress", response_model=ModuleProgress)
def module_progress(
    workspace_id: str,
    project_id: str,
    module_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ModuleProgress:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    module = _module_or_404(db, workspace_id, project_id, module_id)
    rows = db.execute(
        select(ProjectItem)
        .join(ProjectModuleItem, ProjectModuleItem.item_id == ProjectItem.id)
        .where(
            ProjectModuleItem.workspace_id == workspace_id,
            ProjectModuleItem.module_id == module.id,
        )
    ).scalars().all()
    bucket, total, percent = _bucket_progress(module.id, rows, _group_map(db, workspace_id))
    start, end = _naive(module.start_at), _naive(module.end_at)
    return ModuleProgress(
        module_id=module.id, total_items=total, done_items=bucket["done"],
        completion_percent=percent,
        dates_valid=start is None or end is None or start <= end,
    )


# ---- PL-012 / PL-015: hierarchy and rollup -------------------------------


@router.post("/{project_id}/items/{item_id}/parent", response_model=ItemOut)
def set_item_parent(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: ParentSet,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    _validate_parent(db, workspace_id, project_id, item.id, body.parent_id)
    previous = item.parent_item_id
    item.parent_item_id = body.parent_id
    item.updated_at = now()
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_PARENT_CHANGED, field="parent_item_id",
        old=previous, new=body.parent_id, actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_PARENT_CHANGED,
        entity_id=item.id, payload={"parent_item_id": body.parent_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return _item_out(db, item, _group_map(db, workspace_id))


@router.delete("/{project_id}/items/{item_id}/parent", response_model=ItemOut)
def remove_item_parent(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    previous = item.parent_item_id
    item.parent_item_id = None
    item.updated_at = now()
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_PARENT_CHANGED, field="parent_item_id",
        old=previous, new=None, actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_PARENT_CHANGED,
        entity_id=item.id, payload={"parent_item_id": None}, actor_id=principal.user.id,
    )
    db.commit()
    return _item_out(db, item, _group_map(db, workspace_id))


@router.get("/{project_id}/items/{item_id}/children", response_model=list[ItemOut])
def list_item_children(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _item_or_404(db, workspace_id, project_id, item_id)
    groups = _group_map(db, workspace_id)
    rows = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
            ProjectItem.parent_item_id == item_id,
        ).order_by(ProjectItem.created_at)
    ).scalars().all()
    return [_item_out(db, row, groups) for row in rows]


@router.get("/{project_id}/items/{item_id}/rollup", response_model=ItemRollup)
def item_rollup(
    workspace_id: str,
    project_id: str,
    item_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ItemRollup:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    return _rollup(db, item, _group_map(db, workspace_id))


# ---- PL-022: board move --------------------------------------------------


@router.post("/{project_id}/items/{item_id}/move", response_model=ItemOut)
def move_item(
    workspace_id: str,
    project_id: str,
    item_id: str,
    body: MoveItem,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ItemOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    item = _item_or_404(db, workspace_id, project_id, item_id)
    groups = _group_map(db, workspace_id)
    _validate_status(db, workspace_id, body.status)
    previous = item.status
    item.status = body.status
    _sync_completion(item, groups)
    item.updated_at = now()
    _activity(
        db, workspace_id=workspace_id, project_id=project_id, item_id=item.id,
        event_type=PROJECT_ITEM_MOVED, field="status", old=previous, new=item.status,
        actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_ITEM_MOVED,
        entity_id=item.id,
        payload={"from": previous, "to": item.status,
                 "state_group": groups.get(item.status, "todo")},
        actor_id=principal.user.id,
    )
    db.commit()
    return _item_out(db, item, groups)


@router.get("/{project_id}/board", response_model=BoardOut)
def project_board(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> BoardOut:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    groups = _group_map(db, workspace_id)
    states = [state for state in _state_rows(db, workspace_id) if state.is_active]
    columns_spec = (
        [(state.name, state.group, state.position) for state in states]
        if states else [(name, group, index) for index, (name, group)
                        in enumerate(BUILTIN_STATE_GROUPS.items())]
    )
    rows = db.execute(
        select(ProjectItem).where(
            ProjectItem.workspace_id == workspace_id,
            ProjectItem.project_id == project_id,
        ).order_by(ProjectItem.created_at)
    ).scalars().all()
    columns = [
        BoardColumn(
            name=name, group=group, position=position,
            items=[_item_out(db, row, groups) for row in rows if row.status == name],
        )
        for name, group, position in columns_spec
    ]
    return BoardOut(project_id=project_id, columns=columns)


# ---- PL-026 / PL-027: combined filters and saved views -------------------


@router.get("/{project_id}/views", response_model=list[ViewOut])
def list_views(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectView]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    rows = db.execute(
        select(ProjectView).where(
            ProjectView.workspace_id == workspace_id,
            ProjectView.project_id == project_id,
        ).order_by(ProjectView.created_at)
    ).scalars().all()
    return _visible_views(rows, principal)


@router.post("/{project_id}/views", response_model=ViewOut, status_code=status.HTTP_201_CREATED)
def create_view(
    workspace_id: str,
    project_id: str,
    body: ViewCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectView:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    shared = _validate_shared_with(db, workspace_id, body.shared_with)
    exists = db.execute(
        select(ProjectView.id).where(
            ProjectView.workspace_id == workspace_id,
            ProjectView.project_id == project_id,
            ProjectView.owner_id == principal.user.id,
            ProjectView.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="saved view already exists")
    _validate_priority(body.filters.get("priority"))
    view = ProjectView(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        name=body.name, owner_id=principal.user.id, filters=body.filters,
        layout=body.layout, sort_by=body.sort_by, sort_dir=body.sort_dir,
        shared_with=shared, created_at=now(), updated_at=now(),
    )
    db.add(view)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_VIEW_CREATED,
        entity_id=view.id, payload={"name": view.name, "filters": view.filters},
        actor_id=principal.user.id,
    )
    db.commit()
    return view


@router.get("/{project_id}/views/{view_id}", response_model=ViewOut)
def get_view(
    workspace_id: str,
    project_id: str,
    view_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ProjectView:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    view = _view_or_404(db, workspace_id, project_id, view_id)
    if view not in _visible_views([view], principal):
        raise HTTPException(status_code=404, detail="saved view not found")
    return view


@router.get("/{project_id}/views/{view_id}/items", response_model=list[ItemOut])
def view_items(
    workspace_id: str,
    project_id: str,
    view_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    view = _view_or_404(db, workspace_id, project_id, view_id)
    if view not in _visible_views([view], principal):
        raise HTTPException(status_code=404, detail="saved view not found")
    groups = _group_map(db, workspace_id)
    rows = _filtered_items(db, workspace_id, project_id, view.filters or {})
    return [_item_out(db, row, groups) for row in _sorted_items(rows, view)]


@router.patch("/{project_id}/views/{view_id}", response_model=ViewOut)
def patch_view(
    workspace_id: str,
    project_id: str,
    view_id: str,
    body: ViewPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectView:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    view = _view_or_404(db, workspace_id, project_id, view_id)
    if view.owner_id != principal.user.id and principal.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="only the view owner may edit it")
    updates = body.model_dump(exclude_unset=True)
    if "shared_with" in updates:
        updates["shared_with"] = _validate_shared_with(db, workspace_id, updates["shared_with"])
    if updates.get("filters"):
        _validate_priority(updates["filters"].get("priority"))
    for key, value in updates.items():
        setattr(view, key, value)
    view.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_VIEW_UPDATED,
        entity_id=view.id, payload={"fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return view


@router.delete("/{project_id}/views/{view_id}", status_code=status.HTTP_200_OK)
def delete_view(
    workspace_id: str,
    project_id: str,
    view_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    view = _view_or_404(db, workspace_id, project_id, view_id)
    if view.owner_id != principal.user.id and principal.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="only the view owner may delete it")
    db.delete(view)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_VIEW_DELETED,
        entity_id=view.id, payload={"name": view.name}, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "view_id": view.id}


# ---- PL-029 / PL-079: immutable per-item activity ------------------------


@router.get("/{project_id}/items/{item_id}/activity", response_model=list[ActivityOut])
def item_activity(
    workspace_id: str,
    project_id: str,
    item_id: str,
    field: str | None = Query(None),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ItemActivity]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    _item_or_404(db, workspace_id, project_id, item_id)
    query = select(ItemActivity).where(
        ItemActivity.workspace_id == workspace_id,
        ItemActivity.project_id == project_id,
        ItemActivity.item_id == item_id,
    )
    if field is not None:
        query = query.where(ItemActivity.field == field)
    return db.execute(query.order_by(ItemActivity.created_at, ItemActivity.id)).scalars().all()


# ---- PL-030: comment replies and edits -----------------------------------


@router.patch("/{project_id}/comments/{comment_id}", response_model=CommentOut)
def edit_comment(
    workspace_id: str,
    project_id: str,
    comment_id: str,
    body: CommentPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectComment:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    comment = db.execute(
        select(ProjectComment).where(
            ProjectComment.id == comment_id,
            ProjectComment.workspace_id == workspace_id,
            ProjectComment.project_id == project_id,
        )
    ).scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    if comment.author_id != principal.user.id and principal.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="only the author may edit a comment")
    old = comment.body
    comment.body = body.body
    comment.edited_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_COMMENT_UPDATED,
        entity_id=comment.id, payload={"old": old, "new": comment.body},
        actor_id=principal.user.id,
    )
    db.commit()
    return comment


# ---- PL-094: pages -------------------------------------------------------


@router.get("/{project_id}/pages", response_model=list[PageOut])
def list_pages(
    workspace_id: str,
    project_id: str,
    scope: str | None = Query(None),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[ProjectPage]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    query = select(ProjectPage).where(
        ProjectPage.workspace_id == workspace_id,
        ProjectPage.project_id == project_id,
    )
    if scope is not None:
        if scope not in PAGE_SCOPES:
            raise HTTPException(status_code=422, detail="invalid page scope")
        query = query.where(ProjectPage.scope == scope)
    return db.execute(query.order_by(ProjectPage.created_at)).scalars().all()


@router.post("/{project_id}/pages", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_page(
    workspace_id: str,
    project_id: str,
    body: PageCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectPage:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    page = ProjectPage(
        id=new_id(), workspace_id=workspace_id, project_id=project_id,
        scope=body.scope, title=body.title, body=body.body,
        author_id=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(page)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_PAGE_CREATED,
        entity_id=page.id, payload={"scope": page.scope, "title": page.title},
        actor_id=principal.user.id,
    )
    db.commit()
    return page


@router.get("/{project_id}/pages/{page_id}", response_model=PageOut)
def get_page(
    workspace_id: str,
    project_id: str,
    page_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> ProjectPage:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    return _page_or_404(db, workspace_id, project_id, page_id)


@router.patch("/{project_id}/pages/{page_id}", response_model=PageOut)
def patch_page(
    workspace_id: str,
    project_id: str,
    page_id: str,
    body: PagePatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> ProjectPage:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    page = _page_or_404(db, workspace_id, project_id, page_id)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(page, key, value)
    page.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_PAGE_UPDATED,
        entity_id=page.id, payload={"fields": sorted(updates)},
        actor_id=principal.user.id,
    )
    db.commit()
    return page


@router.delete("/{project_id}/pages/{page_id}", status_code=status.HTTP_200_OK)
def delete_page(
    workspace_id: str,
    project_id: str,
    page_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    page = _page_or_404(db, workspace_id, project_id, page_id)
    db.delete(page)
    publish_event(
        db, workspace_id=workspace_id, event_type=PROJECT_PAGE_DELETED,
        entity_id=page.id, payload={"title": page.title}, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "page_id": page.id}
