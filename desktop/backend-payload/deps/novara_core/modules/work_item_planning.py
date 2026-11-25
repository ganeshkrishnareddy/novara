"""Work-item planning views and collaboration (Plane P2 cluster).

Clean-room implementation of PL-013 relations, PL-014 typed dependencies,
PL-016 estimates, PL-020 roadmaps, PL-023 calendar, PL-024 timeline,
PL-025 editable table, PL-035 status updates, PL-036 templates, PL-037
recurrence, PL-136 worklogs and PL-141 subscribers.

Every capability extends NOVARA's existing ``ProjectItem``, ``ProjectModule``
and ``ProjectPage`` models through additive, workspace-scoped tables. All views
are derived from persisted local rows. There is no Plane source, no Django or
React dependency, no hosted endpoint, no scheduler daemon and no outbound
traffic: recurrence materialisation is an explicit, audited local operation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
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
from ..models import User, WorkspaceMember, new_id, now
from ..permissions import TASK_READ, TASK_WRITE
from .projects import Project, ProjectItem, ProjectModule, ProjectPage

RELATION_CHANGED = "planning.relation_changed"
DEPENDENCY_CHANGED = "planning.dependency_changed"
ESTIMATE_CHANGED = "planning.estimate_changed"
ITEM_SCHEDULED = "planning.item_scheduled"
TABLE_CELL_CHANGED = "planning.table_cell_changed"
ITEM_UPDATED = "planning.item_update_posted"
TEMPLATE_CREATED = "planning.template_created"
TEMPLATE_INSTANTIATED = "planning.template_instantiated"
ITEM_RECURRED = "planning.item_recurred"
TIME_LOGGED = "planning.time_logged"
SUBSCRIBERS_CHANGED = "planning.subscribers_changed"
register_event_types(
    RELATION_CHANGED,
    DEPENDENCY_CHANGED,
    ESTIMATE_CHANGED,
    ITEM_SCHEDULED,
    TABLE_CELL_CHANGED,
    ITEM_UPDATED,
    TEMPLATE_CREATED,
    TEMPLATE_INSTANTIATED,
    ITEM_RECURRED,
    TIME_LOGGED,
    SUBSCRIBERS_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/work-item-planning",
    tags=["work-item-planning"],
)

RELATION_TYPES = ("relates_to", "duplicate_of", "implements", "implemented_by")
INVERSE_RELATION = {
    "relates_to": "relates_to",
    "duplicate_of": "duplicate_of",
    "implements": "implemented_by",
    "implemented_by": "implements",
}
DEPENDENCY_KINDS = ("blocked_by", "blocking", "start_after", "finish_before")
SCHEME_KINDS = ("points", "category", "hours")
TEMPLATE_KINDS = ("item", "project", "page")
TABLE_FIELDS = ("title", "status", "priority", "assignee_id", "due_at", "start_at")
ITEM_STATUSES = ("todo", "in_progress", "done")
ITEM_PRIORITIES = ("low", "medium", "high", "urgent")
PAGE_SCOPES = ("wiki", "readme", "draft")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value is not None else None


def _audit(db, workspace_id: str, event_type: str, entity_id: str,
           payload: dict, principal: Principal) -> None:
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _project(db, workspace_id: str, project_id: str) -> Project:
    row = db.execute(select(Project).where(
        Project.id == project_id, Project.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return row


def _item(db, workspace_id: str, item_id: str) -> ProjectItem:
    row = db.execute(select(ProjectItem).where(
        ProjectItem.id == item_id, ProjectItem.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="work item not found")
    return row


def _get(db, model, workspace_id: str, entity_id: str, label: str):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _item_summary(item: ProjectItem) -> dict:
    return {
        "id": item.id, "project_id": item.project_id, "title": item.title,
        "status": item.status, "priority": item.priority,
        "start_at": _iso(item.start_at), "due_at": _iso(item.due_at),
        "cycle_id": item.cycle_id,
    }


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class PlanningRelation(Base):
    __tablename__ = "planning_relations"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "relation_type", "target_item_id",
        name="uq_planning_relation",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningDependency(Base):
    __tablename__ = "planning_dependencies"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "depends_on_id", "kind",
        name="uq_planning_dependency",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningEstimateScheme(Base):
    __tablename__ = "planning_estimate_schemes"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_planning_estimate_scheme"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningEstimate(Base):
    __tablename__ = "planning_estimates"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "scheme_id", name="uq_planning_estimate",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("planning_estimate_schemes.id"), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningItemUpdate(Base):
    __tablename__ = "planning_item_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sub_items_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sub_items_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningTemplate(Base):
    __tablename__ = "planning_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_planning_template"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningRecurrence(Base):
    __tablename__ = "planning_recurrences"
    __table_args__ = (UniqueConstraint("workspace_id", "item_id", name="uq_planning_recurrence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningTimeLog(Base):
    __tablename__ = "planning_time_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class PlanningSubscriber(Base):
    __tablename__ = "planning_subscribers"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "user_id", name="uq_planning_subscriber",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RelationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_item_id: str
    relation_type: str
    note: str = Field(default="", max_length=500)

    @field_validator("relation_type")
    @classmethod
    def _relation(cls, value):
        if value not in RELATION_TYPES:
            raise ValueError("unsupported relation type")
        return value


class DependencyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    depends_on_id: str
    kind: str
    target_date: datetime | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in DEPENDENCY_KINDS:
            raise ValueError("unsupported dependency kind")
        return value


class SchemeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    kind: str
    values: dict = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in SCHEME_KINDS:
            raise ValueError("unsupported estimate scheme kind")
        return value


class EstimateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_id: str
    value: float = Field(default=0, ge=0, le=100000)
    category: str | None = Field(default=None, max_length=60)


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: datetime | None = None
    due_at: datetime | None = None


class CellIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    value: str = Field(max_length=500)

    @field_validator("field")
    @classmethod
    def _field(cls, value):
        if value not in TABLE_FIELDS:
            raise ValueError("unsupported table field")
        return value


class UpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    target_kind: str
    payload: dict = Field(default_factory=dict)

    @field_validator("target_kind")
    @classmethod
    def _kind(cls, value):
        if value not in TEMPLATE_KINDS:
            raise ValueError("unsupported template target")
        return value


class InstantiateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    title: str | None = Field(default=None, max_length=300)


class RecurrenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: str
    interval: int = Field(default=1, ge=1, le=365)
    next_at: datetime

    @field_validator("frequency")
    @classmethod
    def _frequency(cls, value):
        if value not in ("daily", "weekly", "monthly"):
            raise ValueError("unsupported recurrence frequency")
        return value


class MaterializeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: datetime | None = None


class TimeLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minutes: int = Field(gt=0, le=100000)
    note: str = Field(default="", max_length=2000)
    logged_at: datetime | None = None


class SubscriberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


# ---------------------------------------------------------------------------
# Contract (no legacy or hosted claims)
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="workItemPlanningContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "relation_types": list(RELATION_TYPES), "dependency_kinds": list(DEPENDENCY_KINDS),
        "scheme_kinds": list(SCHEME_KINDS), "template_kinds": list(TEMPLATE_KINDS),
        "table_fields": list(TABLE_FIELDS),
        "recurrence_frequencies": ["daily", "weekly", "monthly"],
        "month_length_days": 30,
        "external_calls": False, "external_delivery": False,
        "scheduler": "explicit local materialisation only",
        "router_prefix": "/api/v1/workspaces/{workspace_id}/work-item-planning",
    }


# ---------------------------------------------------------------------------
# PL-013 relations
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/relations", status_code=status.HTTP_201_CREATED,
             operation_id="createPlanningRelation")
def create_relation(workspace_id: str, item_id: str, body: RelationIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    source = _item(db, workspace_id, item_id)
    target = _item(db, workspace_id, body.target_item_id)
    if source.id == target.id:
        raise HTTPException(status_code=422, detail="an item cannot relate to itself")
    inverse = INVERSE_RELATION[body.relation_type]
    existing = db.execute(select(PlanningRelation.id).where(
        PlanningRelation.workspace_id == workspace_id,
        PlanningRelation.item_id == source.id,
        PlanningRelation.relation_type == body.relation_type,
        PlanningRelation.target_item_id == target.id,
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="relation already exists")
    created = []
    for owner, direction, other in (
        (source, body.relation_type, target), (target, inverse, source)
    ):
        pair = db.execute(select(PlanningRelation.id).where(
            PlanningRelation.workspace_id == workspace_id,
            PlanningRelation.item_id == owner.id,
            PlanningRelation.relation_type == direction,
            PlanningRelation.target_item_id == other.id,
        )).scalar_one_or_none()
        if pair:
            continue
        row = PlanningRelation(id=new_id(), workspace_id=workspace_id, item_id=owner.id,
                               relation_type=direction, target_item_id=other.id,
                               note=body.note, created_by=principal.user.id, created_at=now())
        db.add(row)
        created.append({"item_id": owner.id, "relation_type": direction,
                        "target_item_id": other.id})
    db.flush()
    _audit(db, workspace_id, RELATION_CHANGED, item_id,
           {"relation_type": body.relation_type, "target_item_id": target.id,
            "inverse_created": len(created) == 2}, principal)
    db.commit()
    return {"created": len(created), "rows": created}


@router.get("/items/{item_id}/relations", operation_id="listPlanningRelations")
def list_relations(workspace_id: str, item_id: str,
                   principal: Principal = Depends(require(TASK_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningRelation).where(
        PlanningRelation.workspace_id == workspace_id,
        PlanningRelation.item_id == item_id,
    ).order_by(PlanningRelation.created_at)).scalars().all()
    return [{"id": r.id, "item_id": r.item_id, "relation_type": r.relation_type,
             "target_item_id": r.target_item_id, "note": r.note} for r in rows]


# ---------------------------------------------------------------------------
# PL-014 typed dependencies and violation detection
# ---------------------------------------------------------------------------


def _violation(db, workspace_id: str, dep: PlanningDependency) -> tuple[bool, str]:
    source = _item(db, workspace_id, dep.item_id)
    prereq = _item(db, workspace_id, dep.depends_on_id)
    if dep.kind == "blocked_by":
        if prereq.status != "done":
            return True, f"{prereq.title} is not done"
    elif dep.kind == "blocking":
        if prereq.status == "done" and source.status != "done":
            return True, f"{source.title} still blocks a completed item"
    elif dep.kind == "start_after" and source.start_at and prereq.due_at:
        if _aware(source.start_at) < _aware(prereq.due_at):
            return True, "start precedes prerequisite due date"
    elif dep.kind == "finish_before" and source.due_at and prereq.due_at:
        if _aware(source.due_at) > _aware(prereq.due_at):
            return True, "finish follows prerequisite due date"
    return False, ""


def _dependency_json(db, workspace_id: str, dep: PlanningDependency) -> dict:
    violated, reason = _violation(db, workspace_id, dep)
    return {"id": dep.id, "item_id": dep.item_id, "depends_on_id": dep.depends_on_id,
            "kind": dep.kind, "target_date": _iso(dep.target_date),
            "violation": violated, "reason": reason}


@router.post("/items/{item_id}/dependencies", status_code=status.HTTP_201_CREATED,
             operation_id="createPlanningDependency")
def create_dependency(workspace_id: str, item_id: str, body: DependencyIn,
                      principal: Principal = Depends(require(TASK_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    source = _item(db, workspace_id, item_id)
    _item(db, workspace_id, body.depends_on_id)
    if source.id == body.depends_on_id:
        raise HTTPException(status_code=422, detail="an item cannot depend on itself")
    exists = db.execute(select(PlanningDependency.id).where(
        PlanningDependency.workspace_id == workspace_id,
        PlanningDependency.item_id == source.id,
        PlanningDependency.depends_on_id == body.depends_on_id,
        PlanningDependency.kind == body.kind,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="dependency already exists")
    row = PlanningDependency(id=new_id(), workspace_id=workspace_id, item_id=source.id,
                             depends_on_id=body.depends_on_id, kind=body.kind,
                             target_date=_aware(body.target_date),
                             created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, DEPENDENCY_CHANGED, source.id,
           {"depends_on_id": body.depends_on_id, "kind": body.kind}, principal)
    db.commit()
    return _dependency_json(db, workspace_id, row)


@router.get("/items/{item_id}/dependencies", operation_id="listPlanningDependencies")
def list_dependencies(workspace_id: str, item_id: str,
                      principal: Principal = Depends(require(TASK_READ)),
                      db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningDependency).where(
        PlanningDependency.workspace_id == workspace_id,
        PlanningDependency.item_id == item_id,
    ).order_by(PlanningDependency.created_at)).scalars().all()
    return [_dependency_json(db, workspace_id, row) for row in rows]


# ---------------------------------------------------------------------------
# PL-016 estimates
# ---------------------------------------------------------------------------


@router.post("/estimate-schemes", status_code=status.HTTP_201_CREATED,
             operation_id="createEstimateScheme")
def create_scheme(workspace_id: str, body: SchemeIn,
                  principal: Principal = Depends(require(TASK_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(PlanningEstimateScheme.id).where(
        PlanningEstimateScheme.workspace_id == workspace_id,
        PlanningEstimateScheme.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="scheme already exists")
    if body.kind == "category" and not body.values:
        raise HTTPException(status_code=422, detail="category schemes need allowed values")
    row = PlanningEstimateScheme(id=new_id(), workspace_id=workspace_id, name=body.name,
                                 kind=body.kind, values=body.values,
                                 created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ESTIMATE_CHANGED, row.id,
           {"scheme": body.name, "kind": body.kind}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "kind": row.kind, "values": row.values}


@router.get("/estimate-schemes", operation_id="listEstimateSchemes")
def list_schemes(workspace_id: str,
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(PlanningEstimateScheme).where(
        PlanningEstimateScheme.workspace_id == workspace_id
    ).order_by(PlanningEstimateScheme.name)).scalars().all()
    return [{"id": r.id, "name": r.name, "kind": r.kind, "values": r.values} for r in rows]


@router.post("/items/{item_id}/estimates", status_code=status.HTTP_201_CREATED,
             operation_id="setWorkItemEstimate")
def set_estimate(workspace_id: str, item_id: str, body: EstimateIn,
                 principal: Principal = Depends(require(TASK_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    scheme = _get(db, PlanningEstimateScheme, workspace_id, body.scheme_id, "estimate scheme")
    if scheme.kind == "category" and body.category not in scheme.values:
        raise HTTPException(status_code=422, detail="category is not in the scheme")
    if scheme.kind != "category" and body.category:
        raise HTTPException(status_code=422, detail="only category schemes accept a category")
    row = db.execute(select(PlanningEstimate).where(
        PlanningEstimate.workspace_id == workspace_id,
        PlanningEstimate.item_id == item.id, PlanningEstimate.scheme_id == scheme.id,
    )).scalar_one_or_none()
    if row is None:
        row = PlanningEstimate(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                               scheme_id=scheme.id, value=body.value,
                               category=body.category, updated_by=principal.user.id,
                               updated_at=now())
        db.add(row)
    else:
        row.value, row.category = body.value, body.category
        row.updated_by, row.updated_at = principal.user.id, now()
    db.flush()
    _audit(db, workspace_id, ESTIMATE_CHANGED, item.id,
           {"scheme": scheme.name, "value": body.value, "category": body.category}, principal)
    db.commit()
    return {"item_id": item.id, "scheme_id": scheme.id, "value": row.value,
            "category": row.category}


@router.get("/items/{item_id}/estimates", operation_id="listWorkItemEstimates")
def list_estimates(workspace_id: str, item_id: str,
                   principal: Principal = Depends(require(TASK_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningEstimate, PlanningEstimateScheme).join(
        PlanningEstimateScheme,
        PlanningEstimate.scheme_id == PlanningEstimateScheme.id,
    ).where(PlanningEstimate.workspace_id == workspace_id,
            PlanningEstimate.item_id == item.id)).all()
    return [{"scheme_id": scheme.id, "scheme": scheme.name, "kind": scheme.kind,
             "value": est.value, "category": est.category} for est, scheme in rows]


@router.get("/estimates/aggregate", operation_id="aggregatePlanningEstimates")
def aggregate_estimates(workspace_id: str,
                        project_id: str | None = Query(default=None),
                        cycle_id: str | None = Query(default=None),
                        principal: Principal = Depends(require(TASK_READ)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if project_id:
        _project(db, workspace_id, project_id)
    stmt = select(PlanningEstimate, PlanningEstimateScheme, ProjectItem).join(
        PlanningEstimateScheme,
        PlanningEstimate.scheme_id == PlanningEstimateScheme.id,
    ).join(ProjectItem, PlanningEstimate.item_id == ProjectItem.id).where(
        PlanningEstimate.workspace_id == workspace_id
    )
    if project_id:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    if cycle_id:
        stmt = stmt.where(ProjectItem.cycle_id == cycle_id)
    total_points = 0.0
    total_hours = 0.0
    by_category: dict[str, int] = {}
    items: list[dict] = []
    for est, scheme, item in db.execute(stmt).all():
        if scheme.kind == "points":
            total_points += est.value
        elif scheme.kind == "hours":
            total_hours += est.value
        elif est.category:
            by_category[est.category] = by_category.get(est.category, 0) + 1
        items.append({"item_id": item.id, "project_id": item.project_id,
                      "cycle_id": item.cycle_id, "scheme": scheme.name,
                      "value": est.value, "category": est.category})
    return {"project_id": project_id, "cycle_id": cycle_id, "items": len(items),
            "total_points": total_points, "total_hours": total_hours,
            "by_category": by_category, "rows": items}


# ---------------------------------------------------------------------------
# PL-023 calendar, PL-024 timeline, PL-020 roadmap, PL-025 table
# ---------------------------------------------------------------------------


def _date_key(value: datetime) -> str:
    return _aware(value).date().isoformat()


@router.get("/calendar", operation_id="workItemCalendar")
def calendar(workspace_id: str,
             from_date: str | None = Query(default=None, alias="from"),
             to_date: str | None = Query(default=None, alias="to"),
             principal: Principal = Depends(require(TASK_READ)),
             db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    stmt = select(ProjectItem).where(
        ProjectItem.workspace_id == workspace_id, ProjectItem.due_at.is_not(None)
    )
    if from_date:
        stmt = stmt.where(ProjectItem.due_at >= from_date)
    if to_date:
        stmt = stmt.where(ProjectItem.due_at <= to_date + "T23:59:59")
    rows = db.execute(stmt.order_by(ProjectItem.due_at)).scalars().all()
    grouped: dict[str, list[dict]] = {}
    for item in rows:
        grouped.setdefault(_date_key(item.due_at), []).append({
            "id": item.id, "title": item.title, "status": item.status,
            "project_id": item.project_id,
            "item_url": f"/local/projects/{item.project_id}/items/{item.id}",
        })
    return {"from": from_date, "to": to_date, "groups": grouped,
            "total": len(rows), "external_calls": False}


@router.get("/roadmap", operation_id="workItemRoadmap")
def roadmap(workspace_id: str,
            project_id: str | None = Query(default=None),
            principal: Principal = Depends(require(TASK_READ)),
            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if project_id:
        _project(db, workspace_id, project_id)
    stmt = select(ProjectItem, Project).join(
        Project, ProjectItem.project_id == Project.id
    ).where(ProjectItem.workspace_id == workspace_id,
            ProjectItem.due_at.is_not(None), ProjectItem.due_at >= now())
    if project_id:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    groups: dict[str, dict] = {}
    for item, project in db.execute(stmt.order_by(ProjectItem.due_at)).all():
        month = _date_key(item.due_at)[:7]
        key = f"{month}|{project.id}"
        bucket = groups.setdefault(key, {"month": month, "project_id": project.id,
                                         "project_name": project.name, "items": []})
        bucket["items"].append({"id": item.id, "title": item.title,
                                "due_at": _iso(item.due_at), "status": item.status})
    return {"groups": list(groups.values()), "total": sum(len(g["items"]) for g in groups.values()),
            "external_calls": False}


@router.get("/timeline", operation_id="workItemTimeline")
def timeline(workspace_id: str,
             project_id: str | None = Query(default=None),
             principal: Principal = Depends(require(TASK_READ)),
             db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if project_id:
        _project(db, workspace_id, project_id)
    item_stmt = select(ProjectItem).where(ProjectItem.workspace_id == workspace_id)
    module_stmt = select(ProjectModule).where(ProjectModule.workspace_id == workspace_id)
    if project_id:
        item_stmt = item_stmt.where(ProjectItem.project_id == project_id)
        module_stmt = module_stmt.where(ProjectModule.project_id == project_id)
    rows = []
    for item in db.execute(item_stmt).scalars().all():
        if item.start_at or item.due_at:
            rows.append({"kind": "item", "id": item.id, "label": item.title,
                         "project_id": item.project_id, "start_at": _iso(item.start_at),
                         "end_at": _iso(item.due_at)})
    for module in db.execute(module_stmt).scalars().all():
        if module.start_at or module.end_at:
            rows.append({"kind": "module", "id": module.id, "label": module.name,
                         "project_id": module.project_id,
                         "start_at": _iso(module.start_at), "end_at": _iso(module.end_at)})
    dep_stmt = select(PlanningDependency).where(
        PlanningDependency.workspace_id == workspace_id)
    if project_id:
        dep_stmt = dep_stmt.where(PlanningDependency.item_id.in_(
            select(ProjectItem.id).where(ProjectItem.project_id == project_id)))
    conflicts = [_dependency_json(db, workspace_id, dep)
                 for dep in db.execute(dep_stmt).scalars().all()
                 if _violation(db, workspace_id, dep)[0]]
    return {"rows": rows, "conflicts": conflicts,
            "dependency_markers": len(conflicts), "external_calls": False}


@router.patch("/items/{item_id}/schedule", operation_id="updateWorkItemSchedule")
def update_schedule(workspace_id: str, item_id: str, body: ScheduleIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    start, due = _aware(body.start_at), _aware(body.due_at)
    if start and due and start > due:
        raise HTTPException(status_code=422, detail="start must not follow due date")
    if body.start_at is not None:
        item.start_at = start
    if body.due_at is not None:
        item.due_at = due
    item.updated_at = now()
    db.flush()
    _audit(db, workspace_id, ITEM_SCHEDULED, item.id,
           {"start_at": _iso(item.start_at), "due_at": _iso(item.due_at)}, principal)
    db.commit()
    return {"item_id": item.id, "start_at": _iso(item.start_at), "due_at": _iso(item.due_at)}


@router.patch("/items/{item_id}/table-cell", operation_id="updatePlanningTableCell")
def update_table_cell(workspace_id: str, item_id: str, body: CellIn,
                      principal: Principal = Depends(require(TASK_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    value = body.value.strip()
    if body.field == "status":
        if value not in ITEM_STATUSES:
            raise HTTPException(status_code=422, detail="invalid item status")
        item.status = value
    elif body.field == "priority":
        if value not in ITEM_PRIORITIES:
            raise HTTPException(status_code=422, detail="invalid item priority")
        item.priority = value
    elif body.field == "title":
        if not value or len(value) > 300:
            raise HTTPException(status_code=422, detail="title must be 1-300 characters")
        item.title = value
    elif body.field in ("due_at", "start_at"):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid date") from exc
        setattr(item, body.field, _aware(parsed))
    else:
        if value:
            valid_user = db.execute(select(User.id).join(
                WorkspaceMember, WorkspaceMember.user_id == User.id
            ).where(User.id == value,
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.status == "active")).scalar_one_or_none()
            if valid_user is None:
                raise HTTPException(status_code=422, detail="assignee is not an active workspace member")
        item.assignee_id = value or None
    item.updated_at = now()
    db.flush()
    _audit(db, workspace_id, TABLE_CELL_CHANGED, item.id,
           {"field": body.field, "value": value}, principal)
    db.commit()
    return _item_summary(item)


# ---------------------------------------------------------------------------
# PL-035 status updates
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/updates", status_code=status.HTTP_201_CREATED,
             operation_id="postWorkItemUpdate")
def post_update(workspace_id: str, item_id: str, body: UpdateIn,
                principal: Principal = Depends(require(TASK_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    children = db.execute(select(ProjectItem).where(
        ProjectItem.workspace_id == workspace_id,
        ProjectItem.parent_item_id == item.id,
    )).scalars().all()
    row = PlanningItemUpdate(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                             project_id=item.project_id, author_id=principal.user.id,
                             body=body.body, status=item.status,
                             sub_items_done=sum(1 for c in children if c.status == "done"),
                             sub_items_total=len(children), created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ITEM_UPDATED, item.id,
           {"sub_items_done": row.sub_items_done, "sub_items_total": row.sub_items_total},
           principal)
    db.commit()
    return {"id": row.id, "item_id": item.id, "body": row.body, "status": row.status,
            "sub_items_done": row.sub_items_done, "sub_items_total": row.sub_items_total}


@router.get("/items/{item_id}/updates", operation_id="listWorkItemUpdates")
def list_updates(workspace_id: str, item_id: str,
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningItemUpdate).where(
        PlanningItemUpdate.workspace_id == workspace_id,
        PlanningItemUpdate.item_id == item_id,
    ).order_by(PlanningItemUpdate.created_at.desc())).scalars().all()
    return [{"id": r.id, "author_id": r.author_id, "body": r.body, "status": r.status,
             "sub_items_done": r.sub_items_done, "sub_items_total": r.sub_items_total,
             "created_at": r.created_at.isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# PL-036 templates
# ---------------------------------------------------------------------------


def _template_date(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _aware(value)
    return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


@router.post("/templates", status_code=status.HTTP_201_CREATED,
             operation_id="createPlanningTemplate")
def create_template(workspace_id: str, body: TemplateIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(PlanningTemplate.id).where(
        PlanningTemplate.workspace_id == workspace_id,
        PlanningTemplate.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="template already exists")
    row = PlanningTemplate(id=new_id(), workspace_id=workspace_id, name=body.name,
                           target_kind=body.target_kind, payload=body.payload,
                           created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CREATED, row.id,
           {"name": body.name, "target_kind": body.target_kind}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "target_kind": row.target_kind,
            "payload": row.payload}


@router.get("/templates", operation_id="listPlanningTemplates")
def list_templates(workspace_id: str,
                   principal: Principal = Depends(require(TASK_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(PlanningTemplate).where(
        PlanningTemplate.workspace_id == workspace_id
    ).order_by(PlanningTemplate.name)).scalars().all()
    return [{"id": r.id, "name": r.name, "target_kind": r.target_kind,
             "payload": r.payload} for r in rows]


@router.post("/templates/{template_id}/instantiate", status_code=status.HTTP_201_CREATED,
             operation_id="instantiatePlanningTemplate")
def instantiate_template(workspace_id: str, template_id: str, body: InstantiateIn,
                         principal: Principal = Depends(require(TASK_WRITE)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    template = _get(db, PlanningTemplate, workspace_id, template_id, "template")
    payload = dict(template.payload)
    if body.title:
        payload["title"] = body.title
    if template.target_kind == "item":
        project_id = body.project_id or payload.get("project_id")
        if not project_id:
            raise HTTPException(status_code=422, detail="project_id is required for items")
        project = _project(db, workspace_id, project_id)
        title = str(payload.get("title") or template.name)
        row = ProjectItem(id=new_id(), workspace_id=workspace_id,
                          project_id=project.id, title=title,
                          description=str(payload.get("description") or ""),
                          status=str(payload.get("status") or "todo"),
                          priority=str(payload.get("priority") or "medium"),
                          start_at=_template_date(payload.get("start_at")),
                          due_at=_template_date(payload.get("due_at")),
                          tags=[], created_at=now(), updated_at=now())
        if row.status not in ITEM_STATUSES or row.priority not in ITEM_PRIORITIES:
            raise HTTPException(status_code=422, detail="invalid templated status or priority")
        db.add(row)
        key, entity_id = "item_id", row.id
    elif template.target_kind == "project":
        row = Project(id=new_id(), workspace_id=workspace_id,
                      name=str(payload.get("name") or payload.get("title") or template.name),
                      description=str(payload.get("description") or ""),
                      status=str(payload.get("status") or "planning"),
                      owner_id=principal.user.id, restricted=False,
                      created_at=now(), updated_at=now())
        if row.status not in ("planning", "active", "on_hold", "completed"):
            raise HTTPException(status_code=422, detail="invalid templated project status")
        db.add(row)
        key, entity_id = "project_id", row.id
    else:
        project_id = body.project_id or payload.get("project_id")
        if not project_id:
            raise HTTPException(status_code=422, detail="project_id is required for pages")
        project = _project(db, workspace_id, project_id)
        scope = str(payload.get("scope") or "wiki")
        if scope not in PAGE_SCOPES:
            raise HTTPException(status_code=422, detail="invalid templated page scope")
        row = ProjectPage(id=new_id(), workspace_id=workspace_id, project_id=project.id,
                          scope=scope, title=str(payload.get("title") or template.name),
                          body=str(payload.get("body") or ""),
                          author_id=principal.user.id, created_at=now(), updated_at=now())
        db.add(row)
        key, entity_id = "page_id", row.id
    db.flush()
    _audit(db, workspace_id, TEMPLATE_INSTANTIATED, entity_id,
           {"template_id": template.id, "target_kind": template.target_kind}, principal)
    db.commit()
    return {"template_id": template.id, "target_kind": template.target_kind,
            key: entity_id, "title": getattr(row, "title", getattr(row, "name", ""))}


# ---------------------------------------------------------------------------
# PL-037 recurrence
# ---------------------------------------------------------------------------


def _next_at(current: datetime, frequency: str, interval: int) -> datetime:
    if frequency == "daily":
        return current + timedelta(days=interval)
    if frequency == "weekly":
        return current + timedelta(weeks=interval)
    return current + timedelta(days=30 * interval)  # documented 30-day months


@router.post("/items/{item_id}/recurrences", status_code=status.HTTP_201_CREATED,
             operation_id="createPlanningRecurrence")
def create_recurrence(workspace_id: str, item_id: str, body: RecurrenceIn,
                      principal: Principal = Depends(require(TASK_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    exists = db.execute(select(PlanningRecurrence.id).where(
        PlanningRecurrence.workspace_id == workspace_id,
        PlanningRecurrence.item_id == item.id,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="recurrence already exists")
    row = PlanningRecurrence(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                             frequency=body.frequency, interval=body.interval,
                             next_at=_aware(body.next_at), active=True,
                             created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ITEM_RECURRED, item.id,
           {"frequency": body.frequency, "next_at": _iso(row.next_at)}, principal)
    db.commit()
    return {"id": row.id, "item_id": item.id, "frequency": row.frequency,
            "interval": row.interval, "next_at": _iso(row.next_at)}


@router.get("/items/{item_id}/recurrences", operation_id="listPlanningRecurrences")
def list_recurrences(workspace_id: str, item_id: str,
                     principal: Principal = Depends(require(TASK_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningRecurrence).where(
        PlanningRecurrence.workspace_id == workspace_id,
        PlanningRecurrence.item_id == item_id,
    )).scalars().all()
    return [{"id": r.id, "frequency": r.frequency, "interval": r.interval,
             "next_at": _iso(r.next_at), "active": r.active,
             "last_created_at": _iso(r.last_created_at)} for r in rows]


@router.post("/recurrences/{recurrence_id}/materialize",
             operation_id="materializePlanningRecurrence")
def materialize_recurrence(workspace_id: str, recurrence_id: str, body: MaterializeIn,
                           principal: Principal = Depends(require(TASK_WRITE)),
                           db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    rule = _get(db, PlanningRecurrence, workspace_id, recurrence_id, "recurrence")
    source = _item(db, workspace_id, rule.item_id)
    as_of = _aware(body.as_of) or now()
    if not rule.active or _aware(rule.next_at) > as_of:
        return {"created": False, "item_id": None, "next_at": _iso(rule.next_at)}
    created = ProjectItem(id=new_id(), workspace_id=workspace_id,
                          project_id=source.project_id,
                          title=f"{source.title} (recurring)",
                          description=source.description, status="todo",
                          priority=source.priority, start_at=None,
                          due_at=_next_at(_aware(rule.next_at), rule.frequency, rule.interval),
                          tags=[], created_at=now(), updated_at=now())
    db.add(created)
    previous_due = _aware(rule.next_at)
    rule.next_at = _next_at(previous_due, rule.frequency, rule.interval)
    while _aware(rule.next_at) <= as_of:
        rule.next_at = _next_at(_aware(rule.next_at), rule.frequency, rule.interval)
    rule.last_created_at = now()
    db.flush()
    _audit(db, workspace_id, ITEM_RECURRED, created.id,
           {"rule_id": rule.id, "source_item_id": source.id,
            "next_at": _iso(rule.next_at)}, principal)
    db.commit()
    return {"created": True, "item_id": created.id,
            "next_at": _iso(rule.next_at), "scheduler": "explicit local materialisation only"}


# ---------------------------------------------------------------------------
# PL-136 worklogs and PL-141 subscribers
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/time-logs", status_code=status.HTTP_201_CREATED,
             operation_id="createWorklog")
def create_worklog(workspace_id: str, item_id: str, body: TimeLogIn,
                   principal: Principal = Depends(require(TASK_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    row = PlanningTimeLog(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                          project_id=item.project_id, author_id=principal.user.id,
                          minutes=body.minutes, note=body.note,
                          logged_at=_aware(body.logged_at) or now(), created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TIME_LOGGED, item.id,
           {"minutes": body.minutes, "worklog_id": row.id}, principal)
    db.commit()
    return {"id": row.id, "item_id": item.id, "minutes": row.minutes, "note": row.note}


@router.get("/items/{item_id}/time-logs", operation_id="listWorklogs")
def list_worklogs(workspace_id: str, item_id: str,
                  principal: Principal = Depends(require(TASK_READ)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(select(PlanningTimeLog).where(
        PlanningTimeLog.workspace_id == workspace_id,
        PlanningTimeLog.item_id == item_id,
    ).order_by(PlanningTimeLog.logged_at)).scalars().all()
    total = sum(row.minutes for row in rows)
    return {"item_id": item_id, "total_minutes": total, "total_hours": round(total / 60, 2),
            "entries": [{"id": r.id, "author_id": r.author_id, "minutes": r.minutes,
                         "note": r.note, "logged_at": _iso(r.logged_at)} for r in rows]}


@router.post("/items/{item_id}/subscribers", status_code=status.HTTP_201_CREATED,
             operation_id="subscribeToWorkItem")
def subscribe(workspace_id: str, item_id: str, body: SubscriberIn,
              principal: Principal = Depends(require(TASK_WRITE)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    user = db.execute(select(User.id).join(
        WorkspaceMember, WorkspaceMember.user_id == User.id
    ).where(User.id == body.user_id,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active")).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="workspace user not found")
    exists = db.execute(select(PlanningSubscriber.id).where(
        PlanningSubscriber.workspace_id == workspace_id,
        PlanningSubscriber.item_id == item.id,
        PlanningSubscriber.user_id == user,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="already subscribed")
    row = PlanningSubscriber(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                             user_id=user, created_at=now())
    db.add(row)
    db.flush()
    recipients = _recipients(db, workspace_id, item.id)
    _audit(db, workspace_id, SUBSCRIBERS_CHANGED, item.id,
           {"recipients": recipients}, principal)
    db.commit()
    return {"item_id": item.id, "user_id": user, "recipients": recipients}


def _recipients(db, workspace_id: str, item_id: str) -> list[str]:
    rows = db.execute(select(PlanningSubscriber.user_id).where(
        PlanningSubscriber.workspace_id == workspace_id,
        PlanningSubscriber.item_id == item_id,
    ).order_by(PlanningSubscriber.created_at)).scalars().all()
    return list(rows)


@router.delete("/items/{item_id}/subscribers/{user_id}",
               operation_id="unsubscribeFromWorkItem")
def unsubscribe(workspace_id: str, item_id: str, user_id: str,
                principal: Principal = Depends(require(TASK_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    row = db.execute(select(PlanningSubscriber).where(
        PlanningSubscriber.workspace_id == workspace_id,
        PlanningSubscriber.item_id == item.id,
        PlanningSubscriber.user_id == user_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="subscriber not found")
    db.delete(row)
    db.flush()
    recipients = _recipients(db, workspace_id, item.id)
    _audit(db, workspace_id, SUBSCRIBERS_CHANGED, item.id,
           {"recipients": recipients}, principal)
    db.commit()
    return {"item_id": item.id, "user_id": user_id, "removed": True,
            "recipients": recipients}


@router.get("/items/{item_id}/subscribers", operation_id="listWorkItemSubscribers")
def list_subscribers(workspace_id: str, item_id: str,
                     principal: Principal = Depends(require(TASK_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    return {"item_id": item_id, "subscribers": _recipients(db, workspace_id, item_id)}


@router.get("/items/{item_id}/notification-recipients",
            operation_id="workItemNotificationRecipients")
def notification_recipients(workspace_id: str, item_id: str,
                            principal: Principal = Depends(require(TASK_READ)),
                            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    return {"item_id": item_id, "recipients": _recipients(db, workspace_id, item_id),
            "source": "planning_subscribers", "external_delivery": False}
