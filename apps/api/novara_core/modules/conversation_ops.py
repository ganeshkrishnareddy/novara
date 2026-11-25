"""Conversation operations for support inboxes (Chatwoot P2 cluster).

Clean-room implementation of CW-006 (agent presence), CW-010 (snoozed
conversations), CW-020 (@mentions in private notes), CW-021 (collision
detection and duplicate-reply prevention), CW-022 (read receipts), CW-025
(bulk actions), CW-029 (saved filter folders with live counts), CW-032
(conversation mute), CW-052/053/054/055 (timezone-aware business hours with
date overrides, holidays and split-shift slots) and CW-056 (away messages).

No Chatwoot source is copied. Everything is local: presence, typing and
receipts are persisted workspace-scoped rows, mentions notify through the
shared local event spine, and business-hours availability is computed from
stored schedules with the standard-library zoneinfo database. There is no
ActionCable/WebSocket transport, no outbound notification delivery and no
external holiday service.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .support import (
    TICKET_STATUSES, SupportLabel, Ticket, TicketInternalNote, TicketLabel, TicketMessage,
)

PRESENCE_CHANGED = "conversation.presence_changed"
SNOOZE_CHANGED = "conversation.snooze_changed"
MENTION_NOTIFIED = "conversation.mention_notified"
TYPING_CHANGED = "conversation.typing_changed"
RECEIPT_RECORDED = "conversation.receipt_recorded"
BULK_APPLIED = "conversation.bulk_applied"
FOLDER_CHANGED = "conversation.folder_changed"
MUTE_CHANGED = "conversation.mute_changed"
HOURS_CHANGED = "conversation.hours_changed"
register_event_types(
    PRESENCE_CHANGED, SNOOZE_CHANGED, MENTION_NOTIFIED, TYPING_CHANGED,
    RECEIPT_RECORDED, BULK_APPLIED, FOLDER_CHANGED, MUTE_CHANGED, HOURS_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/conversation-ops",
    tags=["conversation-ops"],
)

PRESENCE_STATES = frozenset({"online", "away", "offline"})
FOLDER_FIELDS = frozenset({"status", "priority", "assignee_id", "inbox_id"})
MAX_BULK = 100
MAX_TYPING_TTL = 120


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _ticket(db, workspace_id, ticket_id) -> Ticket:
    row = db.execute(select(Ticket).where(
        Ticket.id == ticket_id, Ticket.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return row


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _member_ids(db, workspace_id) -> set[str]:
    rows = db.execute(select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.status == "active",
    )).scalars().all()
    return set(rows)


# Windows builds without the ``tzdata`` wheel have no system IANA database.
# A documented fixed-offset fallback keeps local business hours usable; no
# external download occurs. DST is observed only when zoneinfo has real data.
FALLBACK_TZ_OFFSETS = {
    "UTC": 0, "Etc/UTC": 0, "GMT": 0,
    "Asia/Kolkata": 330, "Asia/Calcutta": 330,
    "Asia/Tokyo": 540, "Asia/Singapore": 480, "Asia/Dubai": 240,
    "Europe/London": 0, "Europe/Berlin": 60, "Europe/Paris": 60,
    "America/New_York": -300, "America/Chicago": -360,
    "America/Denver": -420, "America/Los_Angeles": -480,
    "Australia/Sydney": 600,
}


def _zone(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        pass
    if name in FALLBACK_TZ_OFFSETS:
        return timezone(timedelta(minutes=FALLBACK_TZ_OFFSETS[name]), name=name)
    if name.startswith("UTC") and len(name) >= 6 and name[3] in "+-":
        sign = 1 if name[3] == "+" else -1
        try:
            hours, minutes = name[4:].split(":")
            offset = timedelta(hours=int(hours), minutes=int(minutes))
        except ValueError:
            raise ValueError("unknown timezone")
        return timezone(sign * offset, name=name)
    raise ValueError("unknown timezone")


def _parse_dt(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{label} must be an ISO datetime")
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail=f"{label} must include a timezone offset")
    return parsed


# ---------------------------------------------------------------------------
# Tables (additive, workspace-scoped)
# ---------------------------------------------------------------------------


class AgentPresence(Base):
    __tablename__ = "agent_presence"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_agent_presence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[str] = mapped_column(String(10), default="offline", nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ConversationSnooze(Base):
    __tablename__ = "conversation_snoozes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "ticket_id", name="uq_conversation_snooze"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    snoozed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NoteMention(Base):
    __tablename__ = "note_mentions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "note_id", "mentioned_user_id", name="uq_note_mention"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    note_id: Mapped[str] = mapped_column(String(36), nullable=False)
    mentioned_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    notified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class TypingIndicator(Base):
    __tablename__ = "typing_indicators"
    __table_args__ = (
        UniqueConstraint("workspace_id", "ticket_id", "user_id", name="uq_typing_indicator"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageReceipt(Base):
    __tablename__ = "message_receipts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "message_id", "user_id", name="uq_message_receipt"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("ticket_messages.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMute(Base):
    __tablename__ = "conversation_mutes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "ticket_id", "user_id", name="uq_conversation_mute"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SavedFolder(Base):
    __tablename__ = "conversation_folders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_conversation_folder"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class InboxHours(Base):
    __tablename__ = "inbox_hours"
    __table_args__ = (
        UniqueConstraint("workspace_id", "inbox_key", name="uq_inbox_hours"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_key: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC", nullable=False)
    away_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HoursSlot(Base):
    __tablename__ = "hours_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_hours_id: Mapped[str] = mapped_column(ForeignKey("inbox_hours.id"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)


class HoursOverride(Base):
    __tablename__ = "hours_overrides"
    __table_args__ = (
        UniqueConstraint("workspace_id", "inbox_hours_id", "date", name="uq_hours_override"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_hours_id: Mapped[str] = mapped_column(ForeignKey("inbox_hours.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Holiday(Base):
    __tablename__ = "inbox_holidays"
    __table_args__ = (
        UniqueConstraint("workspace_id", "inbox_hours_id", "date", name="uq_inbox_holiday"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_hours_id: Mapped[str] = mapped_column(ForeignKey("inbox_hours.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str] = mapped_column(String(40), default="", nullable=False)


class ReplyDedup(Base):
    __tablename__ = "reply_dedup"
    __table_args__ = (
        UniqueConstraint("workspace_id", "ticket_id", "client_msg_id", name="uq_reply_dedup"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    client_msg_id: Mapped[str] = mapped_column(String(120), nullable=False)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PresenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str

    @field_validator("state")
    @classmethod
    def _state(cls, value):
        if value not in PRESENCE_STATES:
            raise ValueError("state must be online, away or offline")
        return value


class SnoozeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    until: str
    reason: str = Field(default="", max_length=300)


class MentionNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=10000)
    mentions: list[str] = Field(default_factory=list, max_length=20)


class TypingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttl_seconds: int = Field(default=30, ge=1, le=MAX_TYPING_TTL)


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=20000)
    client_msg_id: str | None = Field(default=None, max_length=120)
    force: bool = False


class ReceiptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    read: bool = False


class BulkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_ids: list[str] = Field(min_length=1, max_length=MAX_BULK)
    status: str | None = None
    assignee_id: str | None = None
    label: str | None = Field(default=None, max_length=100)

    @field_validator("status")
    @classmethod
    def _status(cls, value):
        if value is not None and value not in TICKET_STATUSES:
            raise ValueError("unsupported ticket status")
        return value


class FolderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    filters: dict = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def _filters(cls, value):
        for key in value:
            if key not in FOLDER_FIELDS:
                raise ValueError(f"unsupported folder filter: {key}")
        if "status" in value and value["status"] not in TICKET_STATUSES:
            raise ValueError("unsupported ticket status")
        return value


class MuteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    muted: bool = True


class SlotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_of_week: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)

    @field_validator("end_minute")
    @classmethod
    def _end(cls, value, info):
        start = info.data.get("start_minute")
        if start is not None and value <= start:
            raise ValueError("end_minute must be after start_minute")
        return value


class InboxHoursIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inbox_key: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="UTC", max_length=60)
    away_message: str = Field(default="", max_length=2000)
    slots: list[SlotIn] = Field(default_factory=list, max_length=42)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value):
        _zone(value)
        return value


class OverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str = Field(min_length=10, max_length=10)
    closed: bool = False
    start_minute: int | None = Field(default=None, ge=0, le=1439)
    end_minute: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("date")
    @classmethod
    def _date(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
        return value


class HolidayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str = Field(min_length=10, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    region: str = Field(default="", max_length=40)

    @field_validator("date")
    @classmethod
    def _date(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
        return value


class CloseRegionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: str = Field(min_length=1, max_length=40)
    dates: list[str] = Field(min_length=1, max_length=60)

    @field_validator("dates")
    @classmethod
    def _dates(cls, value):
        for item in value:
            try:
                datetime.strptime(item, "%Y-%m-%d")
            except ValueError:
                raise ValueError("dates must be YYYY-MM-DD")
        return value


# ---------------------------------------------------------------------------
# Routes - contract and presence (CW-006)
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="conversationOpsContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["presence", "snoozes", "mentions", "collision", "receipts",
                      "bulk", "folders", "mutes", "inboxHours"],
        "presence_states": sorted(PRESENCE_STATES),
        "max_bulk": MAX_BULK, "max_typing_ttl_seconds": MAX_TYPING_TTL,
        "external_calls": False, "external_delivery": False,
        "timezone_source": "zoneinfo when system data is available; documented fixed-offset fallback otherwise",
        "realtime_transport": "polling-only (no ActionCable/WebSocket)",
        "router_prefix": "/api/v1/workspaces/{workspace_id}/conversation-ops",
    }


@router.get("/presence", operation_id="listAgentPresence")
def list_presence(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AgentPresence).where(
        AgentPresence.workspace_id == workspace_id
    ).order_by(AgentPresence.user_id)).scalars().all()
    return [{"user_id": r.user_id, "state": r.state,
             "last_seen_at": r.last_seen_at.isoformat()} for r in rows]


@router.put("/presence", operation_id="setAgentPresence")
def set_presence(workspace_id: str, body: PresenceIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if principal.user.id not in _member_ids(db, workspace_id):
        raise HTTPException(status_code=403, detail="not an active workspace member")
    row = db.execute(select(AgentPresence).where(
        AgentPresence.workspace_id == workspace_id,
        AgentPresence.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = AgentPresence(id=new_id(), workspace_id=workspace_id,
                            user_id=principal.user.id, state=body.state, last_seen_at=now())
        db.add(row)
    else:
        row.state = body.state
        row.last_seen_at = now()
    db.flush()
    _audit(db, workspace_id, PRESENCE_CHANGED, row.id, {"state": body.state}, principal)
    db.commit()
    return {"user_id": principal.user.id, "state": row.state}


# ---------------------------------------------------------------------------
# Routes - snooze (CW-010)
# ---------------------------------------------------------------------------


@router.get("/snoozes", operation_id="listSnoozes")
def list_snoozes(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ConversationSnooze).where(
        ConversationSnooze.workspace_id == workspace_id,
        ConversationSnooze.active.is_(True),
    )).scalars().all()
    return [{"id": r.id, "ticket_id": r.ticket_id,
             "snoozed_until": r.snoozed_until.isoformat(), "reason": r.reason} for r in rows]


@router.post("/tickets/{ticket_id}/snooze", status_code=status.HTTP_201_CREATED,
             operation_id="snoozeConversation")
def snooze(workspace_id: str, ticket_id: str, body: SnoozeIn,
           principal: Principal = Depends(require(NOTE_WRITE)),
           db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    until = _parse_dt(body.until, "until")
    if until <= now():
        raise HTTPException(status_code=422, detail="snooze time must be in the future")
    row = db.execute(select(ConversationSnooze).where(
        ConversationSnooze.workspace_id == workspace_id,
        ConversationSnooze.ticket_id == ticket_id,
    )).scalar_one_or_none()
    if row is None:
        row = ConversationSnooze(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                                 snoozed_until=until, reason=body.reason, active=True, created_at=now())
        db.add(row)
    else:
        row.snoozed_until = until
        row.reason = body.reason
        row.active = True
    db.flush()
    _audit(db, workspace_id, SNOOZE_CHANGED, row.id,
           {"ticket_id": ticket_id, "active": True}, principal)
    db.commit()
    return {"ticket_id": ticket_id, "snoozed_until": until.isoformat(), "active": True}


@router.post("/tickets/{ticket_id}/unsnooze", operation_id="unsnoozeConversation")
def unsnooze(workspace_id: str, ticket_id: str,
             principal: Principal = Depends(require(NOTE_WRITE)),
             db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    row = db.execute(select(ConversationSnooze).where(
        ConversationSnooze.workspace_id == workspace_id,
        ConversationSnooze.ticket_id == ticket_id,
        ConversationSnooze.active.is_(True),
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="conversation is not snoozed")
    row.active = False
    db.flush()
    _audit(db, workspace_id, SNOOZE_CHANGED, row.id,
           {"ticket_id": ticket_id, "active": False}, principal)
    db.commit()
    return {"ticket_id": ticket_id, "active": False}


@router.post("/snoozes/expire-due", operation_id="expireDueSnoozes")
def expire_due(workspace_id: str,
               principal: Principal = Depends(require(NOTE_WRITE)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ConversationSnooze).where(
        ConversationSnooze.workspace_id == workspace_id,
        ConversationSnooze.active.is_(True),
        ConversationSnooze.snoozed_until <= now(),
    )).scalars().all()
    for row in rows:
        row.active = False
    db.flush()
    if rows:
        _audit(db, workspace_id, SNOOZE_CHANGED, workspace_id,
               {"expired": len(rows)}, principal)
    db.commit()
    return {"expired": len(rows), "returned_to_queue": [r.ticket_id for r in rows]}


# ---------------------------------------------------------------------------
# Routes - mentions (CW-020)
# ---------------------------------------------------------------------------


@router.post("/tickets/{ticket_id}/mention-note", status_code=status.HTTP_201_CREATED,
             operation_id="createMentionNote")
def mention_note(workspace_id: str, ticket_id: str, body: MentionNoteIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    members = _member_ids(db, workspace_id)
    targets = list(dict.fromkeys(body.mentions))
    for user_id in targets:
        if user_id not in members:
            raise HTTPException(status_code=422, detail=f"mentioned user {user_id} is not an active member")
    note = TicketInternalNote(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                              author_id=principal.user.id, body=body.body, created_at=now())
    db.add(note)
    db.flush()
    for user_id in targets:
        db.add(NoteMention(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                           note_id=note.id, mentioned_user_id=user_id, notified_at=now()))
        _audit(db, workspace_id, MENTION_NOTIFIED, note.id,
               {"mentioned_user_id": user_id, "ticket_id": ticket_id}, principal)
    db.commit()
    return {"note_id": note.id, "mentioned": targets, "notification_delivery": "local-event-only"}


@router.get("/mentions", operation_id="listMentions")
def list_mentions(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(NoteMention).where(
        NoteMention.workspace_id == workspace_id,
        NoteMention.mentioned_user_id == principal.user.id,
    ).order_by(NoteMention.notified_at.desc()).limit(100)).scalars().all()
    return [{"note_id": r.note_id, "ticket_id": r.ticket_id,
             "notified_at": r.notified_at.isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# Routes - collision detection and receipts (CW-021, CW-022)
# ---------------------------------------------------------------------------


@router.post("/tickets/{ticket_id}/typing", operation_id="setTypingIndicator")
def set_typing(workspace_id: str, ticket_id: str, body: TypingIn,
               principal: Principal = Depends(require(NOTE_WRITE)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    expires = now() + timedelta(seconds=body.ttl_seconds)
    row = db.execute(select(TypingIndicator).where(
        TypingIndicator.workspace_id == workspace_id,
        TypingIndicator.ticket_id == ticket_id,
        TypingIndicator.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = TypingIndicator(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                              user_id=principal.user.id, expires_at=expires)
        db.add(row)
    else:
        row.expires_at = expires
    db.flush()
    _audit(db, workspace_id, TYPING_CHANGED, row.id, {"ticket_id": ticket_id}, principal)
    db.commit()
    return {"ticket_id": ticket_id, "expires_at": expires.isoformat()}


@router.get("/tickets/{ticket_id}/collision", operation_id="conversationCollision")
def collision(workspace_id: str, ticket_id: str,
              principal: Principal = Depends(require(CONTACT_READ)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    ticket = _ticket(db, workspace_id, ticket_id)
    typing = db.execute(select(TypingIndicator).where(
        TypingIndicator.workspace_id == workspace_id,
        TypingIndicator.ticket_id == ticket_id,
        TypingIndicator.user_id != principal.user.id,
        TypingIndicator.expires_at > now(),
    )).scalars().all()
    presence = db.execute(select(AgentPresence).where(
        AgentPresence.workspace_id == workspace_id,
        AgentPresence.user_id.in_([t.user_id for t in typing] or [""]),
    )).scalars().all()
    states = {p.user_id: p.state for p in presence}
    return {
        "ticket_id": ticket_id,
        "others_typing": [{"user_id": t.user_id,
                           "presence": states.get(t.user_id, "offline"),
                           "expires_at": t.expires_at.isoformat()} for t in typing],
        "warning": bool(typing),
        "assignee_id": ticket.assignee_id,
        "realtime_transport": "polling-only",
    }


@router.post("/tickets/{ticket_id}/reply", status_code=status.HTTP_201_CREATED,
             operation_id="collisionSafeReply")
def reply(workspace_id: str, ticket_id: str, body: ReplyIn,
          principal: Principal = Depends(require(NOTE_WRITE)),
          db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    if body.client_msg_id:
        existing = db.execute(select(ReplyDedup).where(
            ReplyDedup.workspace_id == workspace_id,
            ReplyDedup.ticket_id == ticket_id,
            ReplyDedup.client_msg_id == body.client_msg_id,
        )).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="duplicate reply (client_msg_id already sent)")
    others = db.execute(select(TypingIndicator).where(
        TypingIndicator.workspace_id == workspace_id,
        TypingIndicator.ticket_id == ticket_id,
        TypingIndicator.user_id != principal.user.id,
        TypingIndicator.expires_at > now(),
    )).scalars().all()
    if others and not body.force:
        raise HTTPException(status_code=409,
                            detail="another agent is typing; retry with force=true to override")
    message = TicketMessage(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                            author_id=principal.user.id, body=body.body,
                            direction="outbound", channel="local", is_internal=False,
                            created_at=now())
    db.add(message)
    db.flush()
    if body.client_msg_id:
        db.add(ReplyDedup(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                          client_msg_id=body.client_msg_id, message_id=message.id, created_at=now()))
    db.flush()
    _audit(db, workspace_id, RECEIPT_RECORDED, message.id,
           {"ticket_id": ticket_id, "forced": bool(others and body.force)}, principal)
    db.commit()
    return {"message_id": message.id, "duplicate_prevented": True,
            "overrode_typing_warning": bool(others and body.force)}


@router.post("/messages/{message_id}/receipt", operation_id="recordMessageReceipt")
def record_receipt(workspace_id: str, message_id: str, body: ReceiptIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    message = db.execute(select(TicketMessage).where(
        TicketMessage.id == message_id, TicketMessage.workspace_id == workspace_id
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    row = db.execute(select(MessageReceipt).where(
        MessageReceipt.workspace_id == workspace_id,
        MessageReceipt.message_id == message_id,
        MessageReceipt.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = MessageReceipt(id=new_id(), workspace_id=workspace_id, message_id=message_id,
                             user_id=principal.user.id, delivered_at=now(),
                             read_at=now() if body.read else None)
        db.add(row)
    else:
        if body.read and row.read_at is None:
            row.read_at = now()
    db.flush()
    _audit(db, workspace_id, RECEIPT_RECORDED, row.id,
           {"message_id": message_id, "read": body.read}, principal)
    db.commit()
    return {"message_id": message_id, "delivered": True,
            "read_at": row.read_at.isoformat() if row.read_at else None}


@router.get("/messages/{message_id}/receipts", operation_id="listMessageReceipts")
def list_receipts(workspace_id: str, message_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    message = db.execute(select(TicketMessage).where(
        TicketMessage.id == message_id, TicketMessage.workspace_id == workspace_id
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    rows = db.execute(select(MessageReceipt).where(
        MessageReceipt.workspace_id == workspace_id,
        MessageReceipt.message_id == message_id,
    )).scalars().all()
    return [{"user_id": r.user_id, "delivered_at": r.delivered_at.isoformat(),
             "read_at": r.read_at.isoformat() if r.read_at else None} for r in rows]


# ---------------------------------------------------------------------------
# Routes - bulk actions, folders and mute (CW-025, CW-029, CW-032)
# ---------------------------------------------------------------------------


@router.post("/tickets/bulk", operation_id="bulkConversationActions")
def bulk_actions(workspace_id: str, body: BulkIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if body.status is None and body.assignee_id is None and body.label is None:
        raise HTTPException(status_code=422, detail="bulk action requires status, assignee_id or label")
    ids = list(dict.fromkeys(body.ticket_ids))
    rows = db.execute(select(Ticket).where(
        Ticket.workspace_id == workspace_id, Ticket.id.in_(ids)
    )).scalars().all()
    if len(rows) != len(ids):
        raise HTTPException(status_code=404, detail="one or more conversations not found in this workspace")
    label_row = None
    if body.label is not None:
        label_row = db.execute(select(SupportLabel).where(
            SupportLabel.workspace_id == workspace_id, SupportLabel.name == body.label
        )).scalar_one_or_none()
        if label_row is None:
            raise HTTPException(status_code=422, detail="label does not exist; create it first")
    if body.assignee_id is not None and body.assignee_id not in _member_ids(db, workspace_id):
        raise HTTPException(status_code=422, detail="assignee is not an active member")
    for ticket in rows:
        if body.status is not None:
            ticket.status = body.status
        if body.assignee_id is not None:
            ticket.assignee_id = body.assignee_id
        ticket.updated_at = now()
        if label_row is not None:
            linked = db.execute(select(TicketLabel.id).where(
                TicketLabel.ticket_id == ticket.id, TicketLabel.label_id == label_row.id
            )).scalar_one_or_none()
            if linked is None:
                db.add(TicketLabel(id=new_id(), workspace_id=workspace_id,
                                   ticket_id=ticket.id, label_id=label_row.id, created_at=now()))
    db.flush()
    _audit(db, workspace_id, BULK_APPLIED, workspace_id,
           {"updated": len(rows), "status": body.status, "label": body.label}, principal)
    db.commit()
    return {"updated": len(rows), "ticket_ids": [t.id for t in rows]}


def _folder_count(db, workspace_id, filters: dict) -> int:
    stmt = select(func.count(Ticket.id)).where(Ticket.workspace_id == workspace_id)
    if "status" in filters:
        stmt = stmt.where(Ticket.status == filters["status"])
    if "priority" in filters:
        stmt = stmt.where(Ticket.priority == filters["priority"])
    if "assignee_id" in filters:
        stmt = stmt.where(Ticket.assignee_id == filters["assignee_id"])
    if "inbox_id" in filters:
        stmt = stmt.where(Ticket.inbox_id == filters["inbox_id"])
    return db.execute(stmt).scalar_one()


@router.get("/folders", operation_id="listConversationFolders")
def list_folders(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(SavedFolder).where(
        SavedFolder.workspace_id == workspace_id
    ).order_by(SavedFolder.name)).scalars().all()
    return [{"id": r.id, "name": r.name, "filters": r.filters,
             "count": _folder_count(db, workspace_id, r.filters)} for r in rows]


@router.post("/folders", status_code=status.HTTP_201_CREATED,
             operation_id="createConversationFolder")
def create_folder(workspace_id: str, body: FolderIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(SavedFolder.id).where(
        SavedFolder.workspace_id == workspace_id, SavedFolder.name == body.name
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="folder already exists")
    row = SavedFolder(id=new_id(), workspace_id=workspace_id, name=body.name,
                      filters=body.filters, created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, FOLDER_CHANGED, row.id, {"filters": body.filters}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "filters": row.filters,
            "count": _folder_count(db, workspace_id, row.filters)}


@router.delete("/folders/{folder_id}", operation_id="removeConversationFolder")
def remove_folder(workspace_id: str, folder_id: str,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, SavedFolder, workspace_id, folder_id, "folder")
    db.delete(row)
    db.flush()
    _audit(db, workspace_id, FOLDER_CHANGED, folder_id, {"removed": True}, principal)
    db.commit()
    return {"id": folder_id, "removed": True}


@router.post("/tickets/{ticket_id}/mute", operation_id="muteConversation")
def mute(workspace_id: str, ticket_id: str, body: MuteIn,
         principal: Principal = Depends(require(NOTE_WRITE)),
         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _ticket(db, workspace_id, ticket_id)
    row = db.execute(select(ConversationMute).where(
        ConversationMute.workspace_id == workspace_id,
        ConversationMute.ticket_id == ticket_id,
        ConversationMute.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = ConversationMute(id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
                               user_id=principal.user.id, muted=body.muted)
        db.add(row)
    else:
        row.muted = body.muted
    db.flush()
    _audit(db, workspace_id, MUTE_CHANGED, row.id,
           {"ticket_id": ticket_id, "muted": body.muted}, principal)
    db.commit()
    return {"ticket_id": ticket_id, "muted": row.muted,
            "notifications": "suppressed-locally" if row.muted else "enabled"}


@router.get("/mutes", operation_id="listConversationMutes")
def list_mutes(workspace_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ConversationMute).where(
        ConversationMute.workspace_id == workspace_id,
        ConversationMute.user_id == principal.user.id,
        ConversationMute.muted.is_(True),
    )).scalars().all()
    return [{"ticket_id": r.ticket_id} for r in rows]


# ---------------------------------------------------------------------------
# Routes - business hours (CW-052/053/054/055/056)
# ---------------------------------------------------------------------------


def _hours(db, workspace_id, hours_id) -> InboxHours:
    return _get(db, InboxHours, workspace_id, hours_id, "inbox hours")


def _availability(db, hours: InboxHours, at: datetime) -> dict:
    local = at.astimezone(_zone(hours.timezone))
    date_key = local.date().isoformat()
    minute = local.hour * 60 + local.minute
    result = {"open": False, "local_time": local.isoformat(), "reason": "outside-hours",
              "away_message": hours.away_message}
    if not hours.enabled:
        result["reason"] = "hours-disabled"
        return result
    holiday = db.execute(select(Holiday).where(
        Holiday.workspace_id == hours.workspace_id,
        Holiday.inbox_hours_id == hours.id, Holiday.date == date_key,
    )).scalar_one_or_none()
    if holiday is not None:
        result["reason"] = f"holiday:{holiday.name}"
        return result
    override = db.execute(select(HoursOverride).where(
        HoursOverride.workspace_id == hours.workspace_id,
        HoursOverride.inbox_hours_id == hours.id, HoursOverride.date == date_key,
    )).scalar_one_or_none()
    if override is not None:
        if override.closed:
            result["reason"] = "date-override-closed"
            return result
        if override.start_minute is not None and override.end_minute is not None:
            if override.start_minute <= minute < override.end_minute:
                result.update(open=True, reason="date-override")
            return result
    slots = db.execute(select(HoursSlot).where(
        HoursSlot.workspace_id == hours.workspace_id,
        HoursSlot.inbox_hours_id == hours.id,
        HoursSlot.day_of_week == local.weekday(),
    )).scalars().all()
    for slot in slots:
        if slot.start_minute <= minute < slot.end_minute:
            result.update(open=True, reason="scheduled")
            break
    return result


@router.get("/inbox-hours", operation_id="listInboxHours")
def list_inbox_hours(workspace_id: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(InboxHours).where(
        InboxHours.workspace_id == workspace_id
    ).order_by(InboxHours.inbox_key)).scalars().all()
    out = []
    for row in rows:
        slots = db.execute(select(HoursSlot).where(
            HoursSlot.inbox_hours_id == row.id
        ).order_by(HoursSlot.day_of_week, HoursSlot.start_minute)).scalars().all()
        out.append({"id": row.id, "inbox_key": row.inbox_key, "timezone": row.timezone,
                    "away_message": row.away_message, "enabled": row.enabled,
                    "slots": [{"day_of_week": s.day_of_week, "start_minute": s.start_minute,
                               "end_minute": s.end_minute} for s in slots]})
    return out


@router.post("/inbox-hours", status_code=status.HTTP_201_CREATED,
             operation_id="createInboxHours")
def create_inbox_hours(workspace_id: str, body: InboxHoursIn,
                       principal: Principal = Depends(require(NOTE_WRITE)),
                       db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(InboxHours.id).where(
        InboxHours.workspace_id == workspace_id, InboxHours.inbox_key == body.inbox_key
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="inbox hours already exist for this inbox")
    row = InboxHours(id=new_id(), workspace_id=workspace_id, inbox_key=body.inbox_key,
                     timezone=body.timezone, away_message=body.away_message, enabled=True)
    db.add(row)
    db.flush()
    for slot in body.slots:
        db.add(HoursSlot(id=new_id(), workspace_id=workspace_id, inbox_hours_id=row.id,
                         day_of_week=slot.day_of_week, start_minute=slot.start_minute,
                         end_minute=slot.end_minute))
    db.flush()
    _audit(db, workspace_id, HOURS_CHANGED, row.id,
           {"inbox_key": body.inbox_key, "slots": len(body.slots)}, principal)
    db.commit()
    return {"id": row.id, "inbox_key": row.inbox_key, "timezone": row.timezone,
            "slots": len(body.slots)}


@router.post("/inbox-hours/{hours_id}/overrides", status_code=status.HTTP_201_CREATED,
             operation_id="addHoursOverride")
def add_override(workspace_id: str, hours_id: str, body: OverrideIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _hours(db, workspace_id, hours_id)
    if not body.closed and (body.start_minute is None or body.end_minute is None):
        raise HTTPException(status_code=422, detail="open overrides require start_minute and end_minute")
    if body.start_minute is not None and body.end_minute is not None and body.end_minute <= body.start_minute:
        raise HTTPException(status_code=422, detail="end_minute must be after start_minute")
    exists = db.execute(select(HoursOverride.id).where(
        HoursOverride.workspace_id == workspace_id,
        HoursOverride.inbox_hours_id == hours_id, HoursOverride.date == body.date,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="override already exists for this date")
    row = HoursOverride(id=new_id(), workspace_id=workspace_id, inbox_hours_id=hours_id,
                        date=body.date, closed=body.closed,
                        start_minute=body.start_minute, end_minute=body.end_minute)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, HOURS_CHANGED, row.id, {"date": body.date, "closed": body.closed}, principal)
    db.commit()
    return {"id": row.id, "date": body.date, "closed": body.closed}


@router.post("/inbox-hours/{hours_id}/holidays", status_code=status.HTTP_201_CREATED,
             operation_id="addInboxHoliday")
def add_holiday(workspace_id: str, hours_id: str, body: HolidayIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _hours(db, workspace_id, hours_id)
    exists = db.execute(select(Holiday.id).where(
        Holiday.workspace_id == workspace_id,
        Holiday.inbox_hours_id == hours_id, Holiday.date == body.date,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="holiday already exists for this date")
    row = Holiday(id=new_id(), workspace_id=workspace_id, inbox_hours_id=hours_id,
                  date=body.date, name=body.name, region=body.region)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, HOURS_CHANGED, row.id, {"date": body.date, "region": body.region}, principal)
    db.commit()
    return {"id": row.id, "date": body.date, "name": body.name, "region": body.region}


@router.post("/inbox-hours/{hours_id}/holidays/close-region", operation_id="closeRegionDates")
def close_region(workspace_id: str, hours_id: str, body: CloseRegionIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _hours(db, workspace_id, hours_id)
    created = 0
    for date in dict.fromkeys(body.dates):
        exists = db.execute(select(Holiday.id).where(
            Holiday.workspace_id == workspace_id,
            Holiday.inbox_hours_id == hours_id, Holiday.date == date,
        )).scalar_one_or_none()
        if exists:
            continue
        db.add(Holiday(id=new_id(), workspace_id=workspace_id, inbox_hours_id=hours_id,
                       date=date, name=f"{body.region} closure", region=body.region))
        created += 1
    db.flush()
    _audit(db, workspace_id, HOURS_CHANGED, hours_id,
           {"region": body.region, "closed_dates": created}, principal)
    db.commit()
    return {"region": body.region, "closed_dates": created, "source": "operator-supplied-list"}


@router.get("/inbox-hours/{hours_id}/availability", operation_id="inboxAvailability")
def availability(workspace_id: str, hours_id: str,
                 at: str | None = Query(default=None),
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    hours = _hours(db, workspace_id, hours_id)
    moment = _parse_dt(at, "at") if at else now()
    result = _availability(db, hours, moment)
    result.update(inbox_key=hours.inbox_key, timezone=hours.timezone,
                  external_calls=False)
    if not result["open"] and not result["away_message"]:
        result["away_message"] = "We are currently unavailable. Please leave a message."
    return result