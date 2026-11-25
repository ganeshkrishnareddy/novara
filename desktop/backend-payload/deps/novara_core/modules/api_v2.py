"""Versioned REST API v2 surface (GB-060, clean-room).

GrowthBook's REST v2 is represented here as NOVARA's *own* second, versioned
API surface on the one native application. It is not a copy of GrowthBook code
and it is not a second host. It adds the semantics that distinguish a v2 from
the v1 resource context in :mod:`api_resources`:

* a stable response envelope (``data`` + ``meta``) on every collection response;
* cursor-free offset pagination with returned total and page links;
* optimistic concurrency through an immutable ``version`` counter and a
  required ``If-Match`` header on updates (stale writes are rejected with 409);
* strict request validation (unknown fields and unknown operators are refused);
* role-based permission checks and hard workspace isolation on every route.

Every write publishes a named event on the shared event spine. Nothing here
calls an external service or vendors third-party source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    DateTime,
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
from ..models import new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

V2_RECORD_CREATED = "api_v2.record.created"
V2_RECORD_UPDATED = "api_v2.record.updated"
V2_RECORD_DELETED = "api_v2.record.deleted"
register_event_types(V2_RECORD_CREATED, V2_RECORD_UPDATED, V2_RECORD_DELETED)

API_VERSION = "2.0.0"
SUPPORTED_RESOURCE_TYPES = ("feature", "segment", "experiment", "metric")

router = APIRouter(
    prefix="/api/v2/workspaces/{workspace_id}",
    tags=["rest-api-v2"],
)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class V2Record(Base):
    """A versioned, workspace-scoped document on the v2 surface."""

    __tablename__ = "api_v2_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "resource_type", "key", name="uq_api_v2_record_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    body: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class V2RecordCreate(BaseModel):
    resource_type: str
    key: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=500)
    body: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("resource_type")
    @classmethod
    def type_allowed(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in SUPPORTED_RESOURCE_TYPES:
            raise ValueError("unsupported resource_type")
        return value

    @field_validator("key")
    @classmethod
    def key_allowed(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("key must be a non-empty token without whitespace")
        return value


class V2RecordEdit(BaseModel):
    label: str | None = Field(default=None, max_length=500)
    body: dict | None = None

    model_config = ConfigDict(extra="forbid")


class V2RecordOut(BaseModel):
    id: str
    workspace_id: str
    resource_type: str
    key: str
    label: str | None
    body: dict
    version: int
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class V2Meta(BaseModel):
    api_version: str
    surface: str
    supported_resource_types: list[str]
    concurrency: str


class V2ListEnvelope(BaseModel):
    data: list[V2RecordOut]
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one_or_404(db: Session, workspace_id: str, record_id: str) -> V2Record:
    row = db.execute(
        select(V2Record).where(
            V2Record.id == record_id, V2Record.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="record not found")
    return row


def _audit(db, *, workspace_id, verb, record: V2Record, actor_id: str) -> None:
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type={
            "create": V2_RECORD_CREATED,
            "update": V2_RECORD_UPDATED,
            "delete": V2_RECORD_DELETED,
        }[verb],
        entity_id=record.id,
        payload={"resource_type": record.resource_type, "key": record.key},
        actor_id=actor_id,
        idempotency_key=f"api-v2:{verb}:{record.id}:{record.version}",
    )


def _parse_if_match(if_match: str | None, expected: int) -> None:
    """A v2 write must carry the version it read, or it is a stale write."""
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match header is required")
    raw = if_match.strip().strip('"')
    try:
        supplied = int(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="If-Match must be a version number")
    if supplied != expected:
        raise HTTPException(
            status_code=409,
            detail=f"stale version: expected {expected}, got {supplied}",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/meta", response_model=V2Meta)
def api_v2_meta(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> V2Meta:
    """Describe the versioned surface. Still requires an authenticated principal."""
    verify_workspace(principal, workspace_id)
    return V2Meta(
        api_version=API_VERSION,
        surface="novara-rest-v2",
        supported_resource_types=list(SUPPORTED_RESOURCE_TYPES),
        concurrency="If-Match version on update; 428 when missing, 409 when stale",
    )


@router.get("/records", response_model=V2ListEnvelope)
def list_records(
    workspace_id: str,
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> V2ListEnvelope:
    """getList with a stable envelope, total count and page links."""
    verify_workspace(principal, workspace_id)
    if resource_type is not None and resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=422, detail="unsupported resource_type filter")

    base = select(V2Record).where(V2Record.workspace_id == workspace_id)
    count_stmt = select(func.count()).select_from(V2Record).where(
        V2Record.workspace_id == workspace_id
    )
    if resource_type is not None:
        base = base.where(V2Record.resource_type == resource_type)
        count_stmt = count_stmt.where(V2Record.resource_type == resource_type)

    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(
        base.order_by(V2Record.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    prefix = f"/api/v2/workspaces/{workspace_id}/records"
    meta = {
        "api_version": API_VERSION,
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "links": {
            "self": f"{prefix}?limit={limit}&offset={offset}",
            "next": (
                f"{prefix}?limit={limit}&offset={offset + limit}"
                if offset + limit < total
                else None
            ),
            "prev": f"{prefix}?limit={limit}&offset={max(0, offset - limit)}"
            if offset > 0
            else None,
        },
    }
    return V2ListEnvelope(data=rows, meta=meta)


@router.post(
    "/records",
    response_model=V2RecordOut,
    status_code=status.HTTP_201_CREATED,
)
def create_record(
    workspace_id: str,
    body: V2RecordCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> V2Record:
    """create — strict validation, workspace scoping and a named event."""
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(V2Record).where(
            V2Record.workspace_id == workspace_id,
            V2Record.resource_type == body.resource_type,
            V2Record.key == body.key,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="record key already exists")

    record = V2Record(
        id=new_id(),
        workspace_id=workspace_id,
        resource_type=body.resource_type,
        key=body.key,
        label=body.label,
        body=body.body,
        version=1,
        created_at=now(),
        updated_at=now(),
    )
    db.add(record)
    db.flush()
    _audit(db, workspace_id=workspace_id, verb="create", record=record,
           actor_id=principal.user.id)
    db.commit()
    return record


@router.get("/records/{record_id}", response_model=V2RecordOut)
def get_record(
    workspace_id: str,
    record_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> V2Record:
    verify_workspace(principal, workspace_id)
    return _one_or_404(db, workspace_id, record_id)


@router.patch("/records/{record_id}", response_model=V2RecordOut)
def update_record(
    workspace_id: str,
    record_id: str,
    body: V2RecordEdit,
    if_match: str | None = Header(default=None, alias="If-Match"),
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> V2Record:
    """edit — optimistic concurrency: a stale or missing version never writes."""
    verify_workspace(principal, workspace_id)
    record = _one_or_404(db, workspace_id, record_id)
    _parse_if_match(if_match, record.version)
    supplied = body.model_dump(exclude_unset=True)
    if not supplied:
        raise HTTPException(status_code=422, detail="no update fields supplied")
    for key, value in supplied.items():
        setattr(record, key, value)
    record.version += 1
    record.updated_at = now()
    _audit(db, workspace_id=workspace_id, verb="update", record=record,
           actor_id=principal.user.id)
    db.commit()
    return record


@router.delete("/records/{record_id}", response_model=dict)
def delete_record(
    workspace_id: str,
    record_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    record = _one_or_404(db, workspace_id, record_id)
    _parse_if_match(if_match, record.version)
    deleted = {"deleted": True, "surface": "v2", "id": record_id}
    db.delete(record)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=V2_RECORD_DELETED,
        entity_id=record.id,
        payload={"resource_type": record.resource_type, "key": record.key},
        actor_id=principal.user.id,
        idempotency_key=f"api-v2:delete:{record.id}",
    )
    db.commit()
    return deleted
