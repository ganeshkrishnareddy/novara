"""Clean-room P1 project extensions (PL-019/028/116/117).

This module deliberately implements the *behaviour* named in the parity matrix
without copying any upstream source:

* PL-019 milestones gain linked work items and a timeline view.
* PL-028 typed custom work-item properties with mandatory/value validation.
* PL-116 resource-level allow/deny grants layered over NOVARA's role RBAC.
* PL-117 an admin-only, filterable and exportable immutable audit view built on
  the existing append-only event spine.

Everything is workspace-scoped, persisted, permission-checked and audited. No
upstream plane source is embedded and no external service is contacted.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import Event, publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import TASK_READ, TASK_WRITE, WORKSPACE_MANAGE, has_permission
from .projects import ProjectItem, ProjectMilestone, _project_or_404

MILESTONE_LINKED = "milestone.work_linked"
MILESTONE_UNLINKED = "milestone.work_unlinked"
PROPERTY_DEFINED = "property.defined"
PROPERTY_VALUES_SET = "property.values_set"
GRANT_CHANGED = "access.grant_changed"
register_event_types(
    MILESTONE_LINKED, MILESTONE_UNLINKED, PROPERTY_DEFINED,
    PROPERTY_VALUES_SET, GRANT_CHANGED,
)

PROPERTY_TYPES = ("text", "number", "date", "boolean", "select")
EFFECTS = ("allow", "deny")

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/extensions",
    tags=["project-extensions"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class MilestoneWorkLink(Base):
    __tablename__ = "milestone_work_links"
    __table_args__ = (
        UniqueConstraint("workspace_id", "milestone_id", "item_id", name="uq_milestone_work_link"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    milestone_id: Mapped[str] = mapped_column(ForeignKey("project_milestones.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomPropertyDefinition(Base):
    __tablename__ = "custom_property_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_custom_property_workspace_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomPropertyValue(Base):
    __tablename__ = "custom_property_values"
    __table_args__ = (
        UniqueConstraint("workspace_id", "item_id", "definition_id", name="uq_custom_property_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("custom_property_definitions.id"), nullable=False, index=True
    )
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", "resource_type", "resource_id", "permission",
            name="uq_resource_grant",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(120), nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    effect: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


class WorkLinkBody(BaseModel):
    item_id: str

    model_config = ConfigDict(extra="forbid")


class PropertyDefinitionCreate(BaseModel):
    key: str
    name: str
    type: str
    required: bool = False
    options: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("key", "name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("key and name are required")
        return result

    @field_validator("type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value not in PROPERTY_TYPES:
            raise ValueError("unsupported property type")
        return value

    @field_validator("options")
    @classmethod
    def option_strings(cls, value: list[str]) -> list[str]:
        if any(not str(item).strip() for item in value):
            raise ValueError("options must be non-empty strings")
        return list(value)


class PropertyDefinitionOut(BaseModel):
    id: str
    key: str
    name: str
    type: str
    required: bool
    options: list[str]

    model_config = ConfigDict(from_attributes=True)


class PropertyValuesBody(BaseModel):
    item_id: str
    values: dict[str, object]

    model_config = ConfigDict(extra="forbid")


class GrantCreate(BaseModel):
    user_id: str
    resource_type: str
    resource_id: str
    permission: str
    effect: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("effect")
    @classmethod
    def valid_effect(cls, value: str) -> str:
        if value not in EFFECTS:
            raise ValueError("effect must be allow or deny")
        return value


class GrantOut(BaseModel):
    id: str
    user_id: str
    resource_type: str
    resource_id: str
    permission: str
    effect: str

    model_config = ConfigDict(from_attributes=True)


class AccessCheckBody(BaseModel):
    resource_type: str
    resource_id: str
    permission: str

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _milestone(db: Session, workspace_id: str, project_id: str, milestone_id: str):
    milestone = db.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.workspace_id == workspace_id,
            ProjectMilestone.project_id == project_id,
        )
    ).scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    return milestone


def _item(db: Session, workspace_id: str, item_id: str):
    item = db.execute(
        select(ProjectItem).where(
            ProjectItem.id == item_id, ProjectItem.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=422, detail="work item not found in this workspace")
    return item


def _typed_value(definition: CustomPropertyDefinition, value: object):
    if definition.type == "text":
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{definition.key} must be text")
        return value
    if definition.type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail=f"{definition.key} must be a number")
        return value
    if definition.type == "boolean":
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"{definition.key} must be a boolean")
        return value
    if definition.type == "date":
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{definition.key} must be a date string")
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{definition.key} must be an ISO date")
        return value
    if not isinstance(value, str) or value not in definition.options:
        raise HTTPException(status_code=422, detail=f"{definition.key} must be one of the options")
    return value


# ---------------------------------------------------------------------------
# PL-019 — milestone work links and timeline
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/milestones/{milestone_id}/work")
def milestone_work(
    workspace_id: str,
    project_id: str,
    milestone_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _milestone(db, workspace_id, project_id, milestone_id)
    links = db.execute(
        select(MilestoneWorkLink).where(
            MilestoneWorkLink.workspace_id == workspace_id,
            MilestoneWorkLink.milestone_id == milestone_id,
        )
    ).scalars().all()
    return [{"item_id": link.item_id, "linked_at": link.created_at} for link in links]


@router.post("/projects/{project_id}/milestones/{milestone_id}/work",
             status_code=status.HTTP_201_CREATED)
def link_milestone_work(
    workspace_id: str,
    project_id: str,
    milestone_id: str,
    body: WorkLinkBody,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _milestone(db, workspace_id, project_id, milestone_id)
    _item(db, workspace_id, body.item_id)
    existing = db.execute(
        select(MilestoneWorkLink).where(
            MilestoneWorkLink.workspace_id == workspace_id,
            MilestoneWorkLink.milestone_id == milestone_id,
            MilestoneWorkLink.item_id == body.item_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="work item already linked")
    link = MilestoneWorkLink(
        id=new_id(), workspace_id=workspace_id, milestone_id=milestone_id,
        item_id=body.item_id, created_at=now(),
    )
    db.add(link)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=MILESTONE_LINKED, entity_id=link.id,
        payload={"milestone_id": milestone_id, "item_id": body.item_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"item_id": body.item_id, "linked": True}


@router.get("/projects/{project_id}/milestones/timeline")
def milestone_timeline(
    workspace_id: str,
    project_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    milestones = db.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.workspace_id == workspace_id,
            ProjectMilestone.project_id == project_id,
        ).order_by(ProjectMilestone.due_at)
    ).scalars().all()
    rows = []
    for milestone in milestones:
        links = db.execute(
            select(MilestoneWorkLink.item_id).where(
                MilestoneWorkLink.workspace_id == workspace_id,
                MilestoneWorkLink.milestone_id == milestone.id,
            )
        ).scalars().all()
        rows.append({
            "id": milestone.id,
            "name": milestone.name,
            "due_at": milestone.due_at,
            "completed_at": milestone.completed_at,
            "work_item_ids": list(links),
        })
    return rows


# ---------------------------------------------------------------------------
# PL-028 — typed custom work-item properties
# ---------------------------------------------------------------------------


@router.get("/properties", response_model=list[PropertyDefinitionOut])
def list_property_definitions(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[CustomPropertyDefinition]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(CustomPropertyDefinition)
        .where(CustomPropertyDefinition.workspace_id == workspace_id)
        .order_by(CustomPropertyDefinition.created_at)
    ).scalars().all()


@router.post("/properties", response_model=PropertyDefinitionOut,
             status_code=status.HTTP_201_CREATED)
def create_property_definition(
    workspace_id: str,
    body: PropertyDefinitionCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> CustomPropertyDefinition:
    verify_workspace(principal, workspace_id)
    duplicate = db.execute(
        select(CustomPropertyDefinition.id).where(
            CustomPropertyDefinition.workspace_id == workspace_id,
            CustomPropertyDefinition.key == body.key,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="property key already exists")
    if body.type == "select" and not body.options:
        raise HTTPException(status_code=422, detail="select properties require options")
    definition = CustomPropertyDefinition(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        type=body.type, required=body.required, options=list(body.options),
        created_at=now(),
    )
    db.add(definition)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROPERTY_DEFINED,
        entity_id=definition.id, payload={"key": definition.key, "type": definition.type},
        actor_id=principal.user.id,
    )
    db.commit()
    return definition


@router.post("/properties/values")
def set_property_values(
    workspace_id: str,
    body: PropertyValuesBody,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, body.item_id)
    definitions = db.execute(
        select(CustomPropertyDefinition).where(
            CustomPropertyDefinition.workspace_id == workspace_id
        )
    ).scalars().all()
    by_key = {definition.key: definition for definition in definitions}
    unknown = set(body.values) - set(by_key)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown property keys: {sorted(unknown)}")
    missing = [key for key, definition in by_key.items()
               if definition.required and key not in body.values]
    if missing:
        raise HTTPException(status_code=422, detail=f"required properties missing: {sorted(missing)}")

    # Validate every value before mutating the session: a rejected field must
    # not leave earlier valid fields pending in the shared test/production session.
    resolved = [(by_key[key], _typed_value(by_key[key], raw))
                for key, raw in body.values.items()]
    for definition, value in resolved:
        existing = db.execute(
            select(CustomPropertyValue).where(
                CustomPropertyValue.workspace_id == workspace_id,
                CustomPropertyValue.item_id == body.item_id,
                CustomPropertyValue.definition_id == definition.id,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(CustomPropertyValue(
                id=new_id(), workspace_id=workspace_id, item_id=body.item_id,
                definition_id=definition.id, value=value, updated_at=now(),
            ))
        else:
            existing.value = value
            existing.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PROPERTY_VALUES_SET,
        entity_id=body.item_id, payload={"keys": sorted(body.values)},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"item_id": body.item_id, "saved": sorted(body.values)}


@router.get("/properties/values")
def get_property_values(
    workspace_id: str,
    item_id: str = Query(..., min_length=1),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _item(db, workspace_id, item_id)
    rows = db.execute(
        select(CustomPropertyDefinition.key, CustomPropertyValue.value)
        .join(CustomPropertyValue, CustomPropertyValue.definition_id == CustomPropertyDefinition.id)
        .where(
            CustomPropertyValue.workspace_id == workspace_id,
            CustomPropertyValue.item_id == item_id,
        )
    ).all()
    return {"item_id": item_id, "values": {key: value for key, value in rows}}


# ---------------------------------------------------------------------------
# PL-116 — resource-level grants
# ---------------------------------------------------------------------------


@router.post("/access/grants", response_model=GrantOut, status_code=status.HTTP_201_CREATED)
def create_resource_grant(
    workspace_id: str,
    body: GrantCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ResourceGrant:
    verify_workspace(principal, workspace_id)
    member = db.execute(
        select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == body.user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=422, detail="user is not a member of this workspace")
    duplicate = db.execute(
        select(ResourceGrant.id).where(
            ResourceGrant.workspace_id == workspace_id,
            ResourceGrant.user_id == body.user_id,
            ResourceGrant.resource_type == body.resource_type,
            ResourceGrant.resource_id == body.resource_id,
            ResourceGrant.permission == body.permission,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="grant already exists")
    grant = ResourceGrant(
        id=new_id(), workspace_id=workspace_id, user_id=body.user_id,
        resource_type=body.resource_type, resource_id=body.resource_id,
        permission=body.permission, effect=body.effect, created_at=now(),
    )
    db.add(grant)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=GRANT_CHANGED, entity_id=grant.id,
        payload={"resource_type": grant.resource_type, "effect": grant.effect},
        actor_id=principal.user.id,
    )
    db.commit()
    return grant


@router.get("/access/grants", response_model=list[GrantOut])
def list_resource_grants(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[ResourceGrant]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ResourceGrant).where(ResourceGrant.workspace_id == workspace_id)
    ).scalars().all()


@router.post("/access/check")
def check_resource_access(
    workspace_id: str,
    body: AccessCheckBody,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve one resource permission: explicit deny > allow > role default."""
    verify_workspace(principal, workspace_id)
    grant = db.execute(
        select(ResourceGrant.effect).where(
            ResourceGrant.workspace_id == workspace_id,
            ResourceGrant.user_id == principal.user.id,
            ResourceGrant.resource_type == body.resource_type,
            ResourceGrant.resource_id == body.resource_id,
            ResourceGrant.permission == body.permission,
        )
    ).scalar_one_or_none()
    if grant == "deny":
        return {"allowed": False, "source": "grant:deny"}
    if grant == "allow":
        return {"allowed": True, "source": "grant:allow"}
    allowed = has_permission(principal.role, body.permission)
    return {"allowed": allowed, "source": "role"}


# ---------------------------------------------------------------------------
# PL-117 — admin-only immutable audit view
# ---------------------------------------------------------------------------


@router.get("/audit")
def audit_events(
    workspace_id: str,
    event_type: str | None = None,
    entity_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    query = select(Event).where(Event.workspace_id == workspace_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if entity_id:
        query = query.where(Event.entity_id == entity_id)
    rows = db.execute(query.order_by(Event.seq).offset(skip).limit(limit)).scalars().all()
    return [
        {
            "id": row.id, "seq": row.seq, "event_type": row.event_type,
            "entity_id": row.entity_id,
            "actor_id": (row.payload or {}).get("actor_id"),
            "occurred_at": row.occurred_at, "payload": row.payload,
        }
        for row in rows
    ]


@router.get("/audit/export")
def export_audit_events(
    workspace_id: str,
    event_type: str | None = None,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Response:
    """CSV export of the same immutable rows; still admin-only and workspace-scoped."""
    verify_workspace(principal, workspace_id)
    query = select(Event).where(Event.workspace_id == workspace_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    rows = db.execute(query.order_by(Event.seq)).scalars().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["seq", "event_type", "entity_id", "actor_id", "occurred_at"])
    for row in rows:
        writer.writerow([
            row.seq, row.event_type, row.entity_id,
            (row.payload or {}).get("actor_id") or "", row.occurred_at,
        ])
    return Response(
        content=buffer.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="novara-audit.csv"'},
    )
