"""Clean-room P2/P3 Papermark data-room governance.

Documented/public behaviour implemented from scratch (no upstream source copied,
no external service contacted):

- PM-050: a data room supports permissioned documents, visitors, links and an
  append-only audit event stream, end to end.
- PM-057: nested room folders can be created, listed and deleted.
- PM-058: room item ordering persists across reads.
- PM-059: a viewer group is scoped to one room and can be bound to a link.
- PM-060: email/domain membership rules admit exactly the intended viewers.
- PM-061: per-item group view/download permissions are enforced.
- PM-062: updating a link's permission set immediately changes visibility.
- PM-064: room-scoped entitlement checks cannot read another room's data.
- PM-065: room invitation acceptance grants only the invited room.
- PM-066: a frozen room rejects attach/detach/move operations.

All new state lives in additive ``drg_*`` tables; existing document, link and
room records are reused by reference and are never copied or altered.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import User, new_id, now
from ..permissions import DOCUMENT_ADMIN, DOCUMENT_READ, DOCUMENT_WRITE, has_permission

ROOM_CREATED = "dataroom_governance.room_created"
ROOM_EVENT = "dataroom_governance.room_event"
register_event_types(ROOM_CREATED, ROOM_EVENT)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/data-rooms",
    tags=["data-room-governance"],
)


# ---------------------------------------------------------------------------
# Tables (all additive)
# ---------------------------------------------------------------------------


class RoomSetting(Base):
    __tablename__ = "drg_room_settings"
    __table_args__ = (UniqueConstraint("workspace_id", "room_id", name="uq_drg_room_setting"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoomEvent(Base):
    """PM-050: append-only audit stream for one room."""
    __tablename__ = "drg_room_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    actor_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoomFolder(Base):
    """PM-057: nested folder tree inside one room."""
    __tablename__ = "drg_room_folders"
    __table_args__ = (UniqueConstraint("workspace_id", "room_id", "path", name="uq_drg_room_folder_path"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("drg_room_folders.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoomItemOrder(Base):
    """PM-058: stable, persisted ordering for room items."""
    __tablename__ = "drg_room_item_orders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "room_id", "item_type", "item_id", name="uq_drg_item_order"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # document|folder
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ViewerGroup(Base):
    """PM-059: a viewer group scoped to exactly one room."""
    __tablename__ = "drg_viewer_groups"
    __table_args__ = (UniqueConstraint("workspace_id", "room_id", "name", name="uq_drg_viewer_group"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GroupRule(Base):
    """PM-060: email/domain allow or block rules for a viewer group."""
    __tablename__ = "drg_group_rules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "group_id", "effect", "kind", "value", name="uq_drg_group_rule"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("drg_viewer_groups.id"), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(10), nullable=False)  # allow|block
    kind: Mapped[str] = mapped_column(String(20), nullable=False)    # email|domain
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    include_subdomains: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GroupItemPermission(Base):
    """PM-061: per-item view/download grant for a viewer group."""
    __tablename__ = "drg_group_item_permissions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "group_id", "document_id", name="uq_drg_group_item"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("drg_viewer_groups.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_download: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LinkItemPermission(Base):
    """PM-062: per-file permission set for one document link."""
    __tablename__ = "drg_link_item_permissions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "link_id", "document_id", name="uq_drg_link_item"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_download: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LinkGroupBinding(Base):
    """PM-059: bind a room-scoped viewer group to a document link."""
    __tablename__ = "drg_link_groups"
    __table_args__ = (UniqueConstraint("workspace_id", "link_id", name="uq_drg_link_group"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("drg_viewer_groups.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoomInvitation(Base):
    """PM-065: accepted invitation grants only the named room."""
    __tablename__ = "drg_room_invitations"
    __table_args__ = (UniqueConstraint("workspace_id", "room_id", "email", name="uq_drg_room_invite"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(30), default="viewer", nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AccessDecision(Base):
    """PM-064: every entitlement check leaves a reviewable decision record."""
    __tablename__ = "drg_access_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class RoomItemAttach(BaseModel):
    document_id: str = Field(min_length=1)


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[dict] = Field(min_length=1)

    @field_validator("entries")
    @classmethod
    def valid_entries(cls, v: list[dict]) -> list[dict]:
        for e in v:
            if e.get("item_type") not in ("document", "folder") or not e.get("item_id"):
                raise ValueError("entry needs item_type of document/folder and item_id")
            try:
                int(e.get("position"))
            except (TypeError, ValueError):
                raise ValueError("entry position must be an integer")
        return v


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GroupRuleCreate(BaseModel):
    effect: str
    kind: str
    value: str = Field(min_length=1, max_length=320)
    include_subdomains: bool = True

    @field_validator("effect")
    @classmethod
    def valid_effect(cls, v: str) -> str:
        if v not in ("allow", "block"):
            raise ValueError("effect must be allow or block")
        return v

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in ("email", "domain"):
            raise ValueError("kind must be email or domain")
        return v


class ItemPermission(BaseModel):
    document_id: str = Field(min_length=1)
    can_view: bool = True
    can_download: bool = False


class ViewerCheck(BaseModel):
    email: str = Field(min_length=1, max_length=320)


class LinkGroupBind(BaseModel):
    link_id: str = Field(min_length=1)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    role: str = "viewer"

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("a valid email is required")
        return v.lower()


class InvitationAccept(BaseModel):
    token: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _room(db: Session, workspace_id: str, room_id: str):
    from .documents import DataRoom
    row = db.execute(select(DataRoom).where(
        DataRoom.workspace_id == workspace_id, DataRoom.id == room_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="room not found")
    return row


def _document(db: Session, workspace_id: str, document_id: str):
    from .documents import Document
    row = db.execute(select(Document).where(
        Document.workspace_id == workspace_id, Document.id == document_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return row


def _link(db: Session, workspace_id: str, link_id: str):
    from .document_links import DocumentLink
    row = db.execute(select(DocumentLink).where(
        DocumentLink.workspace_id == workspace_id, DocumentLink.id == link_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="link not found")
    return row


def _setting(db: Session, workspace_id: str, room_id: str) -> RoomSetting:
    row = db.execute(select(RoomSetting).where(
        RoomSetting.workspace_id == workspace_id, RoomSetting.room_id == room_id,
    )).scalar_one_or_none()
    if row is None:
        row = RoomSetting(workspace_id=workspace_id, room_id=room_id, frozen=False)
        db.add(row)
        db.flush()
    return row


def _ensure_unfrozen(db: Session, workspace_id: str, room_id: str) -> RoomSetting:
    setting = _setting(db, workspace_id, room_id)
    if setting.frozen:
        raise HTTPException(status_code=409, detail="room is frozen")
    return setting


def _group(db: Session, workspace_id: str, room_id: str, group_id: str) -> ViewerGroup:
    row = db.execute(select(ViewerGroup).where(
        ViewerGroup.workspace_id == workspace_id,
        ViewerGroup.room_id == room_id,
        ViewerGroup.id == group_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="viewer group not found in room")
    return row


def _record(db: Session, workspace_id: str, room_id: str, event_type: str,
            entity_type: str, entity_id: str | None, actor_id: str | None,
            payload: dict | None = None) -> RoomEvent:
    ev = RoomEvent(
        workspace_id=workspace_id, room_id=room_id, event_type=event_type,
        entity_type=entity_type, entity_id=entity_id, actor_id=actor_id,
        payload=payload or {},
    )
    db.add(ev)
    publish_event(db, workspace_id=workspace_id, event_type=ROOM_EVENT,
                  entity_id=room_id, actor_id=actor_id,
                  payload={"room_event": event_type, "entity_type": entity_type})
    return ev


def _is_privileged(principal: Principal) -> bool:
    if principal.role.startswith("custom:"):
        return has_permission(principal.role, DOCUMENT_ADMIN)
    return principal.role in ("owner", "admin") or has_permission(principal.role, DOCUMENT_ADMIN)


def _granted(db: Session, workspace_id: str, room_id: str, principal: Principal) -> bool:
    if _is_privileged(principal):
        return True
    user = db.execute(select(User).where(User.id == principal.user.id)).scalar_one_or_none()
    if user is None:
        return False
    inv = db.execute(select(RoomInvitation).where(
        RoomInvitation.workspace_id == workspace_id,
        RoomInvitation.room_id == room_id,
        RoomInvitation.email == user.email.lower(),
        RoomInvitation.accepted_at.is_not(None),
    )).scalar_one_or_none()
    return inv is not None


def _rule_matches(rules: list[GroupRule], email: str) -> tuple[bool, str]:
    """Returns (admitted, reason). A matching block always wins; otherwise an
    explicit allow is required. No rules means nobody is admitted."""
    email = email.lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""

    def matches(rule: GroupRule) -> bool:
        if rule.kind == "email":
            return email == rule.value.lower()
        base = rule.value.lower()
        if domain == base:
            return True
        return bool(rule.include_subdomains and domain.endswith("." + base))

    for rule in rules:
        if rule.effect == "block" and matches(rule):
            return False, "blocked_by_rule"
    for rule in rules:
        if rule.effect == "allow" and matches(rule):
            return True, "allowed_by_rule"
    return False, "no_matching_allow_rule"


# ---------------------------------------------------------------------------
# PM-050 Room lifecycle + audit stream
# ---------------------------------------------------------------------------


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
def create_room(
    workspace_id: str, body: RoomCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    from .documents import DataRoom
    exists = db.execute(select(DataRoom).where(
        DataRoom.workspace_id == workspace_id, DataRoom.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="room name exists")
    room = DataRoom(
        workspace_id=workspace_id, name=body.name, description=body.description,
        created_by=principal.user.id,
    )
    db.add(room)
    db.flush()
    _setting(db, workspace_id, room.id)
    _record(db, workspace_id, room.id, "room.created", "room", room.id,
            principal.user.id, {"name": body.name})
    publish_event(db, workspace_id=workspace_id, event_type=ROOM_CREATED,
                  entity_id=room.id, actor_id=principal.user.id, payload={"name": body.name})
    db.commit(); db.refresh(room)
    return {"id": room.id, "name": room.name, "description": room.description}


@router.get("/rooms")
def list_rooms(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    from .documents import DataRoom
    rows = db.execute(select(DataRoom).where(
        DataRoom.workspace_id == workspace_id,
    ).order_by(DataRoom.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.get("/rooms/{room_id}")
def get_room(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    room = _room(db, workspace_id, room_id)
    setting = _setting(db, workspace_id, room_id)
    docs = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id,
        RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == "document",
    ).order_by(RoomItemOrder.position)).scalars().all()
    link_doc_ids = [d.item_id for d in docs] or [""]
    from .document_links import DocumentLink, LinkVisit
    links = db.execute(select(DocumentLink).where(
        DocumentLink.workspace_id == workspace_id,
        DocumentLink.document_id.in_(link_doc_ids),
    )).scalars().all()
    link_ids = [x.id for x in links] or [""]
    visitors = db.execute(select(LinkVisit).where(
        LinkVisit.workspace_id == workspace_id,
        LinkVisit.link_id.in_(link_ids),
    )).scalars().all()
    return {
        "id": room.id, "name": room.name, "description": room.description,
        "frozen": setting.frozen,
        "documents": [d.item_id for d in docs],
        "link_count": len(links),
        "visitor_count": len(visitors),
    }


@router.get("/rooms/{room_id}/events")
def room_events(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    rows = db.execute(select(RoomEvent).where(
        RoomEvent.workspace_id == workspace_id, RoomEvent.room_id == room_id,
    ).order_by(RoomEvent.created_at)).scalars().all()
    return [{
        "event_type": e.event_type, "entity_type": e.entity_type,
        "entity_id": e.entity_id, "actor_id": e.actor_id,
        "payload": e.payload, "created_at": e.created_at,
    } for e in rows]


@router.post("/rooms/{room_id}/documents", status_code=status.HTTP_201_CREATED)
def attach_document(
    workspace_id: str, room_id: str, body: RoomItemAttach,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    doc = _document(db, workspace_id, body.document_id)
    from .documents import DocumentRoomMembership
    exists = db.execute(select(DocumentRoomMembership).where(
        DocumentRoomMembership.workspace_id == workspace_id,
        DocumentRoomMembership.document_id == doc.id,
        DocumentRoomMembership.room_id == room_id,
    )).scalar_one_or_none()
    if exists is None:
        db.add(DocumentRoomMembership(
            workspace_id=workspace_id, document_id=doc.id, room_id=room_id,
            created_by=principal.user.id,
        ))
    existing_order = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id,
        RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == "document",
        RoomItemOrder.item_id == doc.id,
    )).scalar_one_or_none()
    if existing_order is None:
        pos = db.execute(select(RoomItemOrder).where(
            RoomItemOrder.workspace_id == workspace_id,
            RoomItemOrder.room_id == room_id,
        )).scalars().all()
        db.add(RoomItemOrder(
            workspace_id=workspace_id, room_id=room_id, item_type="document",
            item_id=doc.id, position=len(pos),
        ))
    _record(db, workspace_id, room_id, "document.attached", "document", doc.id,
            principal.user.id, {"title": doc.title})
    db.commit()
    return {"room_id": room_id, "document_id": doc.id, "attached": True}


@router.delete("/rooms/{room_id}/documents/{document_id}")
def detach_document(
    workspace_id: str, room_id: str, document_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    from .documents import DocumentRoomMembership
    row = db.execute(select(DocumentRoomMembership).where(
        DocumentRoomMembership.workspace_id == workspace_id,
        DocumentRoomMembership.room_id == room_id,
        DocumentRoomMembership.document_id == document_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document not attached to room")
    db.delete(row)
    order = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id,
        RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == "document",
        RoomItemOrder.item_id == document_id,
    )).scalar_one_or_none()
    if order:
        db.delete(order)
    _record(db, workspace_id, room_id, "document.detached", "document", document_id,
            principal.user.id)
    db.commit()
    return {"room_id": room_id, "document_id": document_id, "detached": True}


# ---------------------------------------------------------------------------
# PM-057 Room folders
# ---------------------------------------------------------------------------


@router.post("/rooms/{room_id}/folders", status_code=status.HTTP_201_CREATED)
def create_folder(
    workspace_id: str, room_id: str, body: FolderCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    parent_path = ""
    if body.parent_id:
        parent = db.execute(select(RoomFolder).where(
            RoomFolder.workspace_id == workspace_id,
            RoomFolder.room_id == room_id, RoomFolder.id == body.parent_id,
        )).scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="parent folder not found")
        parent_path = parent.path + "/"
    path = parent_path + body.name
    exists = db.execute(select(RoomFolder).where(
        RoomFolder.workspace_id == workspace_id,
        RoomFolder.room_id == room_id, RoomFolder.path == path,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="folder path exists")
    row = RoomFolder(
        workspace_id=workspace_id, room_id=room_id, parent_id=body.parent_id,
        name=body.name, path=path, created_by=principal.user.id,
    )
    db.add(row); db.flush()
    order_count = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id, RoomItemOrder.room_id == room_id,
    )).scalars().all()
    db.add(RoomItemOrder(
        workspace_id=workspace_id, room_id=room_id, item_type="folder",
        item_id=row.id, position=len(order_count),
    ))
    _record(db, workspace_id, room_id, "folder.created", "folder", row.id,
            principal.user.id, {"path": path})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "path": row.path, "parent_id": row.parent_id}


@router.get("/rooms/{room_id}/folders")
def list_folders(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    rows = db.execute(select(RoomFolder).where(
        RoomFolder.workspace_id == workspace_id, RoomFolder.room_id == room_id,
    ).order_by(RoomFolder.path)).scalars().all()
    return [{"id": f.id, "name": f.name, "path": f.path, "parent_id": f.parent_id} for f in rows]


@router.delete("/rooms/{room_id}/folders/{folder_id}")
def delete_folder(
    workspace_id: str, room_id: str, folder_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    row = db.execute(select(RoomFolder).where(
        RoomFolder.workspace_id == workspace_id,
        RoomFolder.room_id == room_id, RoomFolder.id == folder_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="folder not found")
    children = db.execute(select(RoomFolder).where(
        RoomFolder.workspace_id == workspace_id,
        RoomFolder.room_id == room_id, RoomFolder.parent_id == folder_id,
    )).scalars().all()
    if children:
        raise HTTPException(status_code=409, detail="folder has child folders")
    db.delete(row)
    order = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id,
        RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == "folder",
        RoomItemOrder.item_id == folder_id,
    )).scalar_one_or_none()
    if order:
        db.delete(order)
    _record(db, workspace_id, room_id, "folder.deleted", "folder", folder_id,
            principal.user.id)
    db.commit()
    return {"id": folder_id, "deleted": True}


# ---------------------------------------------------------------------------
# PM-058 Ordering
# ---------------------------------------------------------------------------


@router.put("/rooms/{room_id}/order")
def set_order(
    workspace_id: str, room_id: str, body: OrderUpdate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    for entry in body.entries:
        item_id = entry["item_id"]
        item_type = entry["item_type"]
        if item_type == "document":
            _document(db, workspace_id, item_id)
            from .documents import DocumentRoomMembership
            attached = db.execute(select(DocumentRoomMembership).where(
                DocumentRoomMembership.workspace_id == workspace_id,
                DocumentRoomMembership.room_id == room_id,
                DocumentRoomMembership.document_id == item_id,
            )).scalar_one_or_none()
            if attached is None:
                raise HTTPException(status_code=404, detail="document not attached to room")
        else:
            folder = db.execute(select(RoomFolder).where(
                RoomFolder.workspace_id == workspace_id,
                RoomFolder.room_id == room_id, RoomFolder.id == item_id,
            )).scalar_one_or_none()
            if folder is None:
                raise HTTPException(status_code=404, detail="folder not found")
        row = db.execute(select(RoomItemOrder).where(
            RoomItemOrder.workspace_id == workspace_id,
            RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == item_type,
            RoomItemOrder.item_id == item_id,
        )).scalar_one_or_none()
        if row is None:
            row = RoomItemOrder(
                workspace_id=workspace_id, room_id=room_id,
                item_type=item_type, item_id=item_id, position=0,
            )
            db.add(row)
        row.position = int(entry["position"])
        row.updated_at = now()
    _record(db, workspace_id, room_id, "order.updated", "room", room_id,
            principal.user.id, {"count": len(body.entries)})
    db.commit()
    return {"room_id": room_id, "updated": len(body.entries)}


@router.get("/rooms/{room_id}/items")
def list_items(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    rows = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id, RoomItemOrder.room_id == room_id,
    ).order_by(RoomItemOrder.position, RoomItemOrder.id)).scalars().all()
    return [{
        "item_type": r.item_type, "item_id": r.item_id, "position": r.position,
    } for r in rows]


# ---------------------------------------------------------------------------
# PM-059/060/061 Viewer groups, membership rules, per-item permissions
# ---------------------------------------------------------------------------


@router.post("/rooms/{room_id}/groups", status_code=status.HTTP_201_CREATED)
def create_group(
    workspace_id: str, room_id: str, body: GroupCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _ensure_unfrozen(db, workspace_id, room_id)
    exists = db.execute(select(ViewerGroup).where(
        ViewerGroup.workspace_id == workspace_id,
        ViewerGroup.room_id == room_id, ViewerGroup.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="group name exists in room")
    row = ViewerGroup(
        workspace_id=workspace_id, room_id=room_id, name=body.name,
        created_by=principal.user.id,
    )
    db.add(row); db.flush()
    _record(db, workspace_id, room_id, "group.created", "group", row.id,
            principal.user.id, {"name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "room_id": room_id}


@router.get("/rooms/{room_id}/groups")
def list_groups(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    rows = db.execute(select(ViewerGroup).where(
        ViewerGroup.workspace_id == workspace_id, ViewerGroup.room_id == room_id,
    ).order_by(ViewerGroup.name)).scalars().all()
    return [{"id": g.id, "name": g.name, "room_id": g.room_id} for g in rows]


@router.post("/rooms/{room_id}/groups/{group_id}/bind-link", status_code=status.HTTP_201_CREATED)
def bind_group_to_link(
    workspace_id: str, room_id: str, group_id: str, body: LinkGroupBind,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    group = _group(db, workspace_id, room_id, group_id)
    link = _link(db, workspace_id, body.link_id)
    from .documents import DocumentRoomMembership
    attached = db.execute(select(DocumentRoomMembership).where(
        DocumentRoomMembership.workspace_id == workspace_id,
        DocumentRoomMembership.room_id == room_id,
        DocumentRoomMembership.document_id == link.document_id,
    )).scalar_one_or_none()
    if attached is None:
        raise HTTPException(status_code=404, detail="link document is not in this room")
    existing = db.execute(select(LinkGroupBinding).where(
        LinkGroupBinding.workspace_id == workspace_id,
        LinkGroupBinding.link_id == link.id,
    )).scalar_one_or_none()
    if existing:
        existing.group_id = group.id
    else:
        db.add(LinkGroupBinding(
            workspace_id=workspace_id, link_id=link.id, group_id=group.id,
        ))
    _record(db, workspace_id, room_id, "group.bound_to_link", "link", link.id,
            principal.user.id, {"group_id": group.id})
    db.commit()
    return {"link_id": link.id, "group_id": group.id, "room_id": room_id}


@router.get("/links/{link_id}/group")
def link_group(
    workspace_id: str, link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _link(db, workspace_id, link_id)
    row = db.execute(select(LinkGroupBinding).where(
        LinkGroupBinding.workspace_id == workspace_id,
        LinkGroupBinding.link_id == link_id,
    )).scalar_one_or_none()
    if row is None:
        return {"link_id": link_id, "group_id": None}
    group = db.execute(select(ViewerGroup).where(
        ViewerGroup.workspace_id == workspace_id, ViewerGroup.id == row.group_id,
    )).scalar_one_or_none()
    return {"link_id": link_id, "group_id": row.group_id, "room_id": group.room_id if group else None}


@router.post("/rooms/{room_id}/groups/{group_id}/rules", status_code=status.HTTP_201_CREATED)
def add_group_rule(
    workspace_id: str, room_id: str, group_id: str, body: GroupRuleCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _group(db, workspace_id, room_id, group_id)
    value = body.value.lower()
    if body.kind == "email" and ("@" not in value or "." not in value):
        raise HTTPException(status_code=422, detail="a valid email rule value is required")
    if body.kind == "domain" and (not value or "." not in value):
        raise HTTPException(status_code=422, detail="a valid domain rule value is required")
    exists = db.execute(select(GroupRule).where(
        GroupRule.workspace_id == workspace_id, GroupRule.group_id == group_id,
        GroupRule.effect == body.effect, GroupRule.kind == body.kind,
        GroupRule.value == value,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="rule exists")
    row = GroupRule(
        workspace_id=workspace_id, group_id=group_id, effect=body.effect,
        kind=body.kind, value=value, include_subdomains=body.include_subdomains,
    )
    db.add(row); db.flush()
    _record(db, workspace_id, room_id, "group.rule_added", "group", group_id,
            principal.user.id, {"effect": body.effect, "kind": body.kind})
    db.commit(); db.refresh(row)
    return {"id": row.id, "effect": row.effect, "kind": row.kind, "value": row.value}


@router.post("/rooms/{room_id}/groups/{group_id}/membership-check")
def check_membership(
    workspace_id: str, room_id: str, group_id: str, body: ViewerCheck,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _group(db, workspace_id, room_id, group_id)
    rules = db.execute(select(GroupRule).where(
        GroupRule.workspace_id == workspace_id, GroupRule.group_id == group_id,
    )).scalars().all()
    admitted, reason = _rule_matches(list(rules), body.email)
    return {"email": body.email.lower(), "admitted": admitted, "reason": reason}


@router.put("/rooms/{room_id}/groups/{group_id}/items/{document_id}")
def set_group_item_permission(
    workspace_id: str, room_id: str, group_id: str, document_id: str,
    body: ItemPermission,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _group(db, workspace_id, room_id, group_id)
    if body.document_id != document_id:
        raise HTTPException(status_code=422, detail="body document_id must match the path")
    doc = _document(db, workspace_id, document_id)
    row = db.execute(select(GroupItemPermission).where(
        GroupItemPermission.workspace_id == workspace_id,
        GroupItemPermission.group_id == group_id,
        GroupItemPermission.document_id == doc.id,
    )).scalar_one_or_none()
    if row is None:
        row = GroupItemPermission(
            workspace_id=workspace_id, group_id=group_id, document_id=doc.id,
            can_view=body.can_view, can_download=body.can_download,
        )
        db.add(row)
    else:
        row.can_view = body.can_view
        row.can_download = body.can_download
        row.updated_at = now()
    _record(db, workspace_id, room_id, "group.item_permission", "document", doc.id,
            principal.user.id, {"can_view": body.can_view, "can_download": body.can_download})
    db.commit()
    return {"group_id": group_id, "document_id": doc.id,
            "can_view": body.can_view, "can_download": body.can_download}


@router.get("/rooms/{room_id}/groups/{group_id}/items")
def group_visible_items(
    workspace_id: str, room_id: str, group_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _group(db, workspace_id, room_id, group_id)
    rows = db.execute(select(GroupItemPermission).where(
        GroupItemPermission.workspace_id == workspace_id,
        GroupItemPermission.group_id == group_id, GroupItemPermission.can_view.is_(True),
    )).scalars().all()
    return [{
        "document_id": r.document_id, "can_view": r.can_view,
        "can_download": r.can_download,
    } for r in rows]


# ---------------------------------------------------------------------------
# PM-062 Link permissions
# ---------------------------------------------------------------------------


@router.put("/links/{link_id}/items/{document_id}")
def set_link_item_permission(
    workspace_id: str, link_id: str, document_id: str,
    body: ItemPermission,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    link = _link(db, workspace_id, link_id)
    if body.document_id != document_id:
        raise HTTPException(status_code=422, detail="body document_id must match the path")
    doc = _document(db, workspace_id, document_id)
    row = db.execute(select(LinkItemPermission).where(
        LinkItemPermission.workspace_id == workspace_id,
        LinkItemPermission.link_id == link.id, LinkItemPermission.document_id == doc.id,
    )).scalar_one_or_none()
    if row is None:
        row = LinkItemPermission(
            workspace_id=workspace_id, link_id=link.id, document_id=doc.id,
            can_view=body.can_view, can_download=body.can_download,
        )
        db.add(row)
    else:
        row.can_view = body.can_view
        row.can_download = body.can_download
        row.updated_at = now()
    db.commit()
    return {"link_id": link.id, "document_id": doc.id,
            "can_view": body.can_view, "can_download": body.can_download}


@router.get("/links/{link_id}/items")
def link_visible_items(
    workspace_id: str, link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    link = _link(db, workspace_id, link_id)
    rows = db.execute(select(LinkItemPermission).where(
        LinkItemPermission.workspace_id == workspace_id,
        LinkItemPermission.link_id == link.id, LinkItemPermission.can_view.is_(True),
    )).scalars().all()
    return [{
        "document_id": r.document_id, "can_view": r.can_view,
        "can_download": r.can_download,
    } for r in rows]


@router.get("/links/{link_id}/visibility/{document_id}")
def link_document_visibility(
    workspace_id: str, link_id: str, document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    """Immediately reflects the current permission set, with no cache."""
    verify_workspace(principal, workspace_id)
    link = _link(db, workspace_id, link_id)
    row = db.execute(select(LinkItemPermission).where(
        LinkItemPermission.workspace_id == workspace_id,
        LinkItemPermission.link_id == link.id, LinkItemPermission.document_id == document_id,
    )).scalar_one_or_none()
    if row is None or not row.can_view:
        return {"visible": False, "can_download": False}
    return {"visible": True, "can_download": row.can_download}


# ---------------------------------------------------------------------------
# PM-064 Entitlement checks
# ---------------------------------------------------------------------------


@router.get("/rooms/{room_id}/access/{document_id}")
def access_document(
    workspace_id: str, room_id: str, document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    doc = _document(db, workspace_id, document_id)
    attached = db.execute(select(RoomItemOrder).where(
        RoomItemOrder.workspace_id == workspace_id,
        RoomItemOrder.room_id == room_id, RoomItemOrder.item_type == "document",
        RoomItemOrder.item_id == doc.id,
    )).scalar_one_or_none()
    granted = _granted(db, workspace_id, room_id, principal)
    if attached is None:
        allowed, reason = False, "document_not_in_room"
    elif not granted:
        allowed, reason = False, "no_room_grant"
    else:
        allowed, reason = True, "room_grant_and_attached"
    db.add(AccessDecision(
        workspace_id=workspace_id, room_id=room_id, document_id=doc.id,
        actor_id=principal.user.id, allowed=allowed, reason=reason,
    ))
    _record(db, workspace_id, room_id, "access.checked", "document", doc.id,
            principal.user.id, {"allowed": allowed, "reason": reason})
    db.commit()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    return {"room_id": room_id, "document_id": doc.id, "allowed": True, "reason": reason}


@router.get("/rooms/{room_id}/access-decisions")
def access_decisions(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    rows = db.execute(select(AccessDecision).where(
        AccessDecision.workspace_id == workspace_id, AccessDecision.room_id == room_id,
    ).order_by(AccessDecision.created_at.desc())).scalars().all()
    return [{
        "document_id": r.document_id, "actor_id": r.actor_id,
        "allowed": r.allowed, "reason": r.reason, "created_at": r.created_at,
    } for r in rows]


# ---------------------------------------------------------------------------
# PM-065 Invitations
# ---------------------------------------------------------------------------


@router.post("/rooms/{room_id}/invitations", status_code=status.HTTP_201_CREATED)
def invite_to_room(
    workspace_id: str, room_id: str, body: InvitationCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    token = secrets.token_urlsafe(24)
    row = RoomInvitation(
        workspace_id=workspace_id, room_id=room_id, email=body.email.lower(),
        token_hash=hashlib.sha256(token.encode()).hexdigest(), role=body.role,
        created_by=principal.user.id,
    )
    db.add(row); db.flush()
    _record(db, workspace_id, room_id, "invitation.created", "invitation", row.id,
            principal.user.id, {"email": row.email})
    db.commit(); db.refresh(row)
    # The raw token is returned once; only its hash is persisted.
    return {"id": row.id, "email": row.email, "room_id": room_id, "token": token}


@router.post("/rooms/{room_id}/invitations/accept")
def accept_invitation(
    workspace_id: str, room_id: str, body: InvitationAccept,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    row = db.execute(select(RoomInvitation).where(
        RoomInvitation.workspace_id == workspace_id,
        RoomInvitation.room_id == room_id,
        RoomInvitation.token_hash == token_hash,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="invitation not found")
    if row.accepted_at is not None:
        return {"room_id": room_id, "granted": False, "already_accepted": True}
    user = db.execute(select(User).where(User.id == principal.user.id)).scalar_one_or_none()
    if user is None or user.email.lower() != row.email:
        raise HTTPException(status_code=403, detail="invitation is for a different email")
    row.accepted_at = now()
    _record(db, workspace_id, room_id, "invitation.accepted", "invitation", row.id,
            principal.user.id, {"email": row.email})
    db.commit()
    return {"room_id": room_id, "granted": True, "role": row.role}


@router.get("/my-rooms")
def my_rooms(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    user = db.execute(select(User).where(User.id == principal.user.id)).scalar_one_or_none()
    if user is None:
        return []
    rows = db.execute(select(RoomInvitation).where(
        RoomInvitation.workspace_id == workspace_id,
        RoomInvitation.email == user.email.lower(),
        RoomInvitation.accepted_at.is_not(None),
    )).scalars().all()
    return [{
        "room_id": r.room_id, "role": r.role, "accepted_at": r.accepted_at,
    } for r in rows]


# ---------------------------------------------------------------------------
# PM-066 Freeze
# ---------------------------------------------------------------------------


@router.post("/rooms/{room_id}/freeze")
def freeze_room(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _require_admin(db, workspace_id, principal)
    setting = _setting(db, workspace_id, room_id)
    setting.frozen = True
    setting.updated_at = now()
    _record(db, workspace_id, room_id, "room.frozen", "room", room_id, principal.user.id)
    db.commit()
    return {"room_id": room_id, "frozen": True}


@router.post("/rooms/{room_id}/unfreeze")
def unfreeze_room(
    workspace_id: str, room_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _room(db, workspace_id, room_id)
    _require_admin(db, workspace_id, principal)
    setting = _setting(db, workspace_id, room_id)
    setting.frozen = False
    setting.updated_at = now()
    _record(db, workspace_id, room_id, "room.unfrozen", "room", room_id, principal.user.id)
    db.commit()
    return {"room_id": room_id, "frozen": False}


def _require_admin(db: Session, workspace_id: str, principal: Principal) -> None:
    """Defence in depth: the route already uses require(DOCUMENT_ADMIN)."""
    if not _is_privileged(principal):
        raise HTTPException(status_code=403, detail="document admin role required")
