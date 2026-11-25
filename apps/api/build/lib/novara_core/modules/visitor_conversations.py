"""Visitor-started support conversations (CW-035).

A workspace administrator issues a revocable website token bound to one local
inbox. A visitor who holds that token can start a conversation and append
messages without a NOVARA account. The server, never the visitor, chooses the
channel (`web_form`), so the agent inbox shows a real origin rather than a
decorative channel badge. Every message is a genuine `TicketMessage` row and the
ticket is routed to the configured inbox, so it appears in the agent queue.

No network call, hosted widget or external messaging provider is involved.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, WORKSPACE_MANAGE
from ..security import hash_token
from .support import (
    TICKET_CREATED,
    TICKET_MESSAGE_ADDED,
    Ticket,
    TicketMessage,
    _inbox_is_valid,
    publish_event,
)

VISITOR_SITE_CREATED = "support.visitor_site_created"
VISITOR_SITE_REVOKED = "support.visitor_site_revoked"
VISITOR_CONVERSATION_STARTED = "support.visitor_conversation_started"
VISITOR_MESSAGE_ADDED = "support.visitor_message_added"
register_event_types(
    VISITOR_SITE_CREATED, VISITOR_SITE_REVOKED,
    VISITOR_CONVERSATION_STARTED, VISITOR_MESSAGE_ADDED,
)

VISITOR_CHANNEL = "web_form"
TOKEN_PREFIX = "vc_"

ADMIN_ROUTER = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/visitor-sites",
    tags=["visitor-conversations"],
)
PUBLIC_ROUTER = APIRouter(
    prefix="/api/v1/public/visitor-conversations",
    tags=["visitor-conversations"],
)
router = APIRouter()
router.include_router(ADMIN_ROUTER)
router.include_router(PUBLIC_ROUTER)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class VisitorSite(Base):
    __tablename__ = "support_visitor_sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_id: Mapped[str] = mapped_column(ForeignKey("support_inboxes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VisitorConversation(Base):
    """Binds a real support ticket to the site token that created it."""

    __tablename__ = "support_visitor_conversations"
    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_visitor_conversation_ticket"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("support_visitor_sites.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    inbox_id: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("site name is required")
        return value


class SiteOut(BaseModel):
    id: str
    workspace_id: str
    inbox_id: str
    name: str
    active: bool
    created_by: str
    created_at: object
    revoked_at: object | None

    model_config = ConfigDict(from_attributes=True)


class SiteIssuedOut(SiteOut):
    token: str


class VisitorStart(BaseModel):
    visitor_name: str = Field(min_length=1, max_length=120)
    visitor_email: str = Field(min_length=3, max_length=320)
    message: str = Field(min_length=1, max_length=10000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("visitor_name", "message")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("this field is required")
        return value

    @field_validator("visitor_email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("a valid visitor email is required")
        return value


class VisitorReply(BaseModel):
    message: str = Field(min_length=1, max_length=10000)

    model_config = ConfigDict(extra="forbid")


class ConversationOut(BaseModel):
    conversation_id: str
    workspace_id: str
    inbox_id: str
    origin_channel: str
    contact_id: str
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _site_by_token(db: Session, token: str) -> VisitorSite:
    site = db.execute(
        select(VisitorSite).where(VisitorSite.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if site is None or not site.active:
        raise HTTPException(status_code=401, detail="invalid or revoked visitor site token")
    return site


def _site_admin(db: Session, workspace_id: str, site_id: str) -> VisitorSite:
    site = db.execute(
        select(VisitorSite).where(
            VisitorSite.id == site_id,
            VisitorSite.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail="visitor site not found")
    return site


def _contact(db: Session, workspace_id: str, email: str, full_name: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == email)
    ).scalar_one_or_none()
    if contact is not None:
        return contact
    contact = Contact(
        id=new_id(), workspace_id=workspace_id, email=email, full_name=full_name,
        source="visitor_conversation", owner_id=None,
        created_at=now(), updated_at=now(),
    )
    db.add(contact)
    db.flush()
    return contact


def _message(db: Session, workspace_id: str, ticket_id: str, author_id: str, body: str) -> TicketMessage:
    row = TicketMessage(
        id=new_id(), workspace_id=workspace_id, ticket_id=ticket_id,
        author_id=author_id, body=body, direction="inbound",
        channel=VISITOR_CHANNEL, is_internal=False, created_at=now(),
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Administrator endpoints
# ---------------------------------------------------------------------------


@ADMIN_ROUTER.post("", response_model=SiteIssuedOut, status_code=status.HTTP_201_CREATED)
def create_visitor_site(
    workspace_id: str,
    body: SiteCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _inbox_is_valid(db, workspace_id, body.inbox_id)
    token = TOKEN_PREFIX + secrets.token_urlsafe(24)
    site = VisitorSite(
        id=new_id(), workspace_id=workspace_id, inbox_id=body.inbox_id,
        name=body.name, token_hash=hash_token(token), active=True,
        created_by=principal.user.id, created_at=now(), revoked_at=None,
    )
    db.add(site)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=VISITOR_SITE_CREATED,
        entity_id=site.id, actor_id=principal.user.id,
        payload={"name": site.name, "inbox_id": site.inbox_id},
    )
    db.commit()
    return {**SiteOut.model_validate(site).model_dump(), "token": token}


@ADMIN_ROUTER.get("", response_model=list[SiteOut])
def list_visitor_sites(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[VisitorSite]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(VisitorSite)
        .where(VisitorSite.workspace_id == workspace_id)
        .order_by(VisitorSite.created_at.desc())
    ).scalars().all()


@ADMIN_ROUTER.delete("/{site_id}")
def revoke_visitor_site(
    workspace_id: str,
    site_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    site = _site_admin(db, workspace_id, site_id)
    if site.active:
        site.active = False
        site.revoked_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=VISITOR_SITE_REVOKED,
            entity_id=site.id, actor_id=principal.user.id,
            payload={"name": site.name},
        )
        db.commit()
    return {"revoked": True, "id": site.id}


# ---------------------------------------------------------------------------
# Public visitor endpoints
# ---------------------------------------------------------------------------


@PUBLIC_ROUTER.post("/{token}/start", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_conversation(
    token: str,
    body: VisitorStart,
    db: Session = Depends(get_db),
) -> ConversationOut:
    site = _site_by_token(db, token)
    contact = _contact(db, site.workspace_id, body.visitor_email, body.visitor_name)
    ticket = Ticket(
        id=new_id(), workspace_id=site.workspace_id, contact_id=contact.id,
        subject=f"Visitor conversation with {body.visitor_name}",
        body=body.message, status="open", priority="normal",
        # The server fixes the real origin; the visitor cannot declare a channel.
        origin_channel=VISITOR_CHANNEL, conversation_type="question",
        inbox_id=site.inbox_id, created_at=now(), updated_at=now(),
    )
    db.add(ticket)
    db.flush()
    db.add(VisitorConversation(
        id=new_id(), workspace_id=site.workspace_id, ticket_id=ticket.id,
        site_id=site.id, created_at=now(),
    ))
    db.flush()
    _message(db, site.workspace_id, ticket.id, contact.id, body.message)
    publish_event(
        db, workspace_id=site.workspace_id, event_type=TICKET_CREATED,
        entity_id=ticket.id, actor_id=None,
        payload={"origin_channel": VISITOR_CHANNEL, "inbox_id": site.inbox_id,
                 "source": "visitor_conversation"},
    )
    publish_event(
        db, workspace_id=site.workspace_id, event_type=VISITOR_CONVERSATION_STARTED,
        entity_id=ticket.id, actor_id=None,
        payload={"inbox_id": site.inbox_id, "site_id": site.id},
    )
    db.commit()
    return ConversationOut(
        conversation_id=ticket.id, workspace_id=site.workspace_id,
        inbox_id=site.inbox_id, origin_channel=ticket.origin_channel,
        contact_id=contact.id, status=ticket.status,
    )


@PUBLIC_ROUTER.post("/{token}/threads/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
def reply_to_conversation(
    token: str,
    conversation_id: str,
    body: VisitorReply,
    db: Session = Depends(get_db),
) -> dict:
    site = _site_by_token(db, token)
    ticket = db.execute(
        select(Ticket)
        .join(VisitorConversation, VisitorConversation.ticket_id == Ticket.id)
        .where(
            Ticket.id == conversation_id,
            Ticket.workspace_id == site.workspace_id,
            Ticket.inbox_id == site.inbox_id,
            Ticket.origin_channel == VISITOR_CHANNEL,
            VisitorConversation.site_id == site.id,
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="visitor conversation not found")
    message = _message(db, site.workspace_id, ticket.id, ticket.contact_id or "visitor", body.message)
    ticket.updated_at = now()
    publish_event(
        db, workspace_id=site.workspace_id, event_type=TICKET_MESSAGE_ADDED,
        entity_id=ticket.id, actor_id=None,
        payload={"message_id": message.id, "channel": VISITOR_CHANNEL,
                 "direction": "inbound", "source": "visitor_conversation"},
    )
    publish_event(
        db, workspace_id=site.workspace_id, event_type=VISITOR_MESSAGE_ADDED,
        entity_id=ticket.id, actor_id=None, payload={"site_id": site.id},
    )
    db.commit()
    return {"message_id": message.id, "conversation_id": ticket.id,
            "origin_channel": VISITOR_CHANNEL, "direction": "inbound"}
