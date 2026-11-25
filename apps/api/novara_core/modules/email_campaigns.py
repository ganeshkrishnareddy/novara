"""Email broadcast and unsubscribe infrastructure (MT-013, MT-019).

Clean-room implementation. No real email is sent: a deterministic local
adapter records delivery status. Unsubscribe tokens are genuine HMAC-signed
tokens. Suppression and consent are enforced before any recipient is queued.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    and_,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE, NOTE_WRITE, WORKSPACE_MANAGE

UNSUBSCRIBE_SECRET = os.getenv("NOVARA_UNSUBSCRIBE_SECRET", "novara-dev-unsub-secret").encode("utf-8")

# Outbound webhook destinations are allow-listed by host. Loopback stays allowed
# for local tests; deployments add their real receivers with the env var. This
# is a deliberate SSRF guard, not a claim that arbitrary external URLs work.
DEFAULT_WEBHOOK_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def allowed_webhook_hosts() -> frozenset[str]:
    configured = os.getenv("NOVARA_WEBHOOK_ALLOWED_HOSTS", "")
    extra = {host.strip().lower() for host in configured.split(",") if host.strip()}
    return frozenset(DEFAULT_WEBHOOK_ALLOWED_HOSTS | extra)

BROADCAST_CREATED = "broadcast.created"
BROADCAST_QUEUED = "broadcast.queued"
BROADCAST_SENT = "broadcast.sent"
UNSUBSCRIBE_RECORDED = "unsubscribe.recorded"
SUPPRESSION_ADDED = "suppression.added"
CONSENT_RECORDED = "consent.recorded"
RESUBSCRIBE_RECORDED = "resubscribe.recorded"
DNC_RECORDED = "dnc.recorded"
PREFERENCES_UPDATED = "preferences.updated"
register_event_types(
    BROADCAST_CREATED, BROADCAST_QUEUED, BROADCAST_SENT, UNSUBSCRIBE_RECORDED,
    SUPPRESSION_ADDED, CONSENT_RECORDED, RESUBSCRIBE_RECORDED, DNC_RECORDED,
    PREFERENCES_UPDATED,
)

# MT-016 / MT-042 / MT-045 / MT-046 / MT-050 — local channel and webhook events.
TOKENS_RENDERED = "email.tokens_rendered"
SMS_REPLY_RECORDED = "sms.reply_recorded"
SMS_DNC_RECORDED = "sms.dnc_recorded"
SMS_DELIVERY_BLOCKED = "sms.delivery_blocked"
CHANNEL_PREFERENCE_UPDATED = "channel.preference_updated"
CHANNEL_RULE_UPDATED = "channel.rule_updated"
MESSAGE_DELIVERED = "marketing_message.delivered"
MESSAGE_BLOCKED = "marketing_message.blocked"
WEBHOOK_SUBSCRIPTION_CREATED = "webhook.subscription_created"
WEBHOOK_DELIVERED = "webhook.delivered"
WEBHOOK_DELIVERY_FAILED = "webhook.delivery_failed"
register_event_types(
    TOKENS_RENDERED, SMS_REPLY_RECORDED, SMS_DNC_RECORDED, SMS_DELIVERY_BLOCKED,
    CHANNEL_PREFERENCE_UPDATED, CHANNEL_RULE_UPDATED, MESSAGE_DELIVERED,
    MESSAGE_BLOCKED, WEBHOOK_SUBSCRIPTION_CREATED, WEBHOOK_DELIVERED,
    WEBHOOK_DELIVERY_FAILED,
)
CONSENT_ACTIONS = ("unsubscribe", "resubscribe", "dnc", "preferences")
PREFERENCE_CHANNELS = ("email", "sms", "push")

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/email",
    tags=["email-campaigns"],
)

BroadcastStatus = Literal["draft", "scheduled", "queued", "sending", "sent", "cancelled"]
RecipientStatus = Literal["pending", "suppressed", "unsubscribed", "queued", "sent", "failed", "bounced"]


class BroadcastCampaign(Base):
    __tablename__ = "broadcast_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(36))
    segment_id: Mapped[str | None] = mapped_column(String(36))
    source_type: Mapped[str] = mapped_column(String(40), default="segment", nullable=False)
    builder_steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "contact_id", name="uq_broadcast_recipient"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("broadcast_campaigns.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SuppressionEntry(Base):
    __tablename__ = "suppression_list"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_suppression"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), default="unsubscribe", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), default="email", nullable=False)
    granted: Mapped[bool] = mapped_column(default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BroadcastCreate(BaseModel):
    name: str
    subject: str
    body: str
    template_id: str | None = None
    segment_id: str | None = None
    source_type: str = "segment"
    builder_steps: list = Field(default_factory=list)
    scheduled_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class BroadcastOut(BaseModel):
    id: str
    name: str
    subject: str
    status: str
    source_type: str
    segment_id: str | None
    scheduled_at: datetime | None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecipientAddRequest(BaseModel):
    contact_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class UnsubscribeRequest(BaseModel):
    token: str

    model_config = ConfigDict(extra="forbid")


class ConsentRequest(BaseModel):
    contact_id: str
    channel: str = "email"
    granted: bool = True
    source: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConsentTokenRequest(BaseModel):
    token: str

    model_config = ConfigDict(extra="forbid")


class PreferencesUpdateRequest(BaseModel):
    token: str
    channels: dict[str, bool]

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _broadcast_or_404(db, workspace_id, bid):
    b = db.execute(
        select(BroadcastCampaign).where(
            BroadcastCampaign.id == bid, BroadcastCampaign.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="broadcast not found")
    return b


def _is_suppressed(db, workspace_id, email) -> bool:
    return db.execute(
        select(SuppressionEntry.id).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == email,
        )
    ).scalar_one_or_none() is not None


def _has_consent(db, workspace_id, contact_id) -> bool:
    rec = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.contact_id == contact_id,
            ConsentRecord.channel == "email",
        ).order_by(ConsentRecord.recorded_at.desc())
    ).scalars().first()
    if rec is None:
        return True  # default allow unless explicitly revoked
    return bool(rec.granted)


def _unsub_token(workspace_id: str, email: str) -> str:
    expires = int(time.time()) + 60 * 60 * 24 * 365
    payload = f"unsub:{workspace_id}:{email}:{expires}"
    sig = hmac.new(UNSUBSCRIBE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_unsub_token(token: str):
    if token.count(":") < 4:
        return None
    # payload has colons in email? email has no colon; safe
    payload, sig = token.rsplit(":", 1)
    expected = hmac.new(UNSUBSCRIBE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    parts = payload.split(":")
    # unsub:workspace_id:email:expires
    if len(parts) != 4 or parts[0] != "unsub":
        return None
    if int(parts[3]) < int(time.time()):
        return None
    return parts[1], parts[2]


def _consent_token(workspace_id: str, email: str, action: str) -> str:
    """Signed, expiring link token for one preference-centre action (MT-019)."""
    if action not in CONSENT_ACTIONS:
        raise ValueError(f"unknown consent action: {action}")
    expires = int(time.time()) + 60 * 60 * 24 * 365
    payload = f"consent:{action}:{workspace_id}:{email}:{expires}"
    sig = hmac.new(UNSUBSCRIBE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_consent_token(token: str, expected_action: str):
    """Return (action, workspace_id, email) only for a valid signed token."""
    if expected_action not in CONSENT_ACTIONS or token.count(":") < 5:
        return None
    payload, sig = token.rsplit(":", 1)
    expected = hmac.new(UNSUBSCRIBE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    parts = payload.split(":")
    if len(parts) != 5 or parts[0] != "consent":
        return None
    _, action, workspace_id, email, expires = parts
    if action != expected_action:
        return None
    try:
        if int(expires) < int(time.time()):
            return None
    except ValueError:
        return None
    return action, workspace_id, email


def _contact_by_email(db, workspace_id: str, email: str):
    return db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.email == email
        )
    ).scalar_one_or_none()


def _record_consent(db, workspace_id: str, contact, *, channel: str, granted: bool, source: str):
    if contact is not None:
        record = ConsentRecord(
            id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
            channel=channel, granted=granted, source=source, recorded_at=now(),
        )
        db.add(record)
        db.flush()
        publish_event(
            db, workspace_id=workspace_id, event_type=CONSENT_RECORDED,
            entity_id=contact.id,
            payload={"channel": channel, "granted": granted, "source": source},
            actor_id=None,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/broadcasts", response_model=BroadcastOut, status_code=status.HTTP_201_CREATED)
def create_broadcast(
    workspace_id: str,
    body: BroadcastCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> BroadcastCampaign:
    verify_workspace(principal, workspace_id)
    b = BroadcastCampaign(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name.strip(),
        subject=body.subject.strip(),
        body=body.body.strip(),
        template_id=body.template_id,
        segment_id=body.segment_id,
        source_type=body.source_type,
        builder_steps=body.builder_steps,
        status="scheduled" if body.scheduled_at else "draft",
        scheduled_at=body.scheduled_at,
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(b)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=BROADCAST_CREATED,
        entity_id=b.id,
        payload={"name": b.name, "scheduled": b.scheduled_at is not None},
        actor_id=principal.user.id,
    )
    db.commit()
    return b


@router.get("/broadcasts", response_model=list[BroadcastOut])
def list_broadcasts(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[BroadcastCampaign]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(BroadcastCampaign).where(BroadcastCampaign.workspace_id == workspace_id).order_by(BroadcastCampaign.created_at.desc())
    ).scalars().all()


@router.post("/broadcasts/{broadcast_id}/recipients", response_model=dict)
def add_recipients(
    workspace_id: str,
    broadcast_id: str,
    body: RecipientAddRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    b = _broadcast_or_404(db, workspace_id, broadcast_id)
    added = 0
    skipped = 0
    for cid in body.contact_ids:
        contact = db.execute(
            select(Contact).where(Contact.id == cid, Contact.workspace_id == workspace_id)
        ).scalar_one_or_none()
        if contact is None:
            skipped += 1
            continue
        if contact.do_not_contact:
            # MT-019: a global do-not-contact flag blocks every channel.
            skipped += 1
            continue
        if _is_suppressed(db, workspace_id, contact.email):
            # record as suppressed
            existing = db.execute(
                select(BroadcastRecipient).where(
                    BroadcastRecipient.campaign_id == b.id, BroadcastRecipient.contact_id == contact.id
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(BroadcastRecipient(
                    id=new_id(), workspace_id=workspace_id, campaign_id=b.id,
                    contact_id=contact.id, email=contact.email, status="suppressed",
                    queued_at=now(),
                ))
            skipped += 1
            continue
        if not _has_consent(db, workspace_id, contact.id):
            skipped += 1
            continue
        existing = db.execute(
            select(BroadcastRecipient).where(
                BroadcastRecipient.campaign_id == b.id, BroadcastRecipient.contact_id == contact.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        db.add(BroadcastRecipient(
            id=new_id(), workspace_id=workspace_id, campaign_id=b.id,
            contact_id=contact.id, email=contact.email, status="pending",
        ))
        added += 1
    db.commit()
    return {"added": added, "skipped": skipped}


@router.post("/broadcasts/{broadcast_id}/queue", response_model=dict)
def queue_broadcast(
    workspace_id: str,
    broadcast_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    b = _broadcast_or_404(db, workspace_id, broadcast_id)
    recipients = db.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.campaign_id == b.id,
            BroadcastRecipient.status == "pending",
        )
    ).scalars().all()
    for r in recipients:
        r.status = "queued"
        r.queued_at = now()
    b.status = "queued"
    b.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=BROADCAST_QUEUED,
        entity_id=b.id, payload={"queued": len(recipients)}, actor_id=principal.user.id,
    )
    db.commit()
    return {"queued": len(recipients)}


@router.post("/broadcasts/{broadcast_id}/dispatch", response_model=dict)
def dispatch_broadcast(
    workspace_id: str,
    broadcast_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Local adapter: records sent status without any external delivery."""
    verify_workspace(principal, workspace_id)
    b = _broadcast_or_404(db, workspace_id, broadcast_id)
    recipients = db.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.campaign_id == b.id,
            BroadcastRecipient.status == "queued",
        )
    ).scalars().all()
    sent = 0
    for r in recipients:
        # simulate delivery; never touch a real provider
        r.status = "sent"
        r.sent_at = now()
        sent += 1
    b.status = "sent"
    b.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=BROADCAST_SENT,
        entity_id=b.id, payload={"sent": sent}, actor_id=principal.user.id,
    )
    db.commit()
    return {"sent": sent}


@router.post("/broadcasts/{broadcast_id}/cancel", response_model=dict)
def cancel_broadcast(
    workspace_id: str,
    broadcast_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    b = _broadcast_or_404(db, workspace_id, broadcast_id)
    b.status = "cancelled"
    b.updated_at = now()
    db.commit()
    return {"cancelled": True, "broadcast_id": b.id}


@router.get("/broadcasts/{broadcast_id}/recipients")
def list_recipients(
    workspace_id: str,
    broadcast_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _broadcast_or_404(db, workspace_id, broadcast_id)
    rows = db.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.workspace_id == workspace_id,
            BroadcastRecipient.campaign_id == broadcast_id,
        ).order_by(BroadcastRecipient.queued_at)
    ).scalars().all()
    return [
        {
            "id": r.id, "contact_id": r.contact_id, "email": r.email,
            "status": r.status, "error": r.error,
            "queued_at": r.queued_at, "sent_at": r.sent_at,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------


@router.get("/unsubscribe-token")
def generate_unsubscribe_token(
    workspace_id: str,
    email: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return {"token": _unsub_token(workspace_id, email), "email": email}


@router.post("/unsubscribe", response_model=dict)
def unsubscribe(
    workspace_id: str,
    body: UnsubscribeRequest,
    db: Session = Depends(get_db),
) -> dict:
    # Public-ish: token carries authorization
    result = _verify_unsub_token(body.token)
    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired unsubscribe token")
    tok_workspace, email = result
    if tok_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    # add to suppression list
    existing = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == email,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(SuppressionEntry(
            id=new_id(), workspace_id=workspace_id, email=email,
            reason="unsubscribe", created_at=now(),
        ))
    # MT-019 acceptance: the unsubscribe flow updates consent itself, so a
    # later consent lookup needs no separate manual record.
    contact = _contact_by_email(db, workspace_id, email)
    _record_consent(db, workspace_id, contact, channel="email",
                    granted=False, source="unsubscribe")
    publish_event(
        db, workspace_id=workspace_id, event_type=UNSUBSCRIBE_RECORDED,
        entity_id=email, payload={"email": email}, actor_id=None,
    )
    db.commit()
    return {"unsubscribed": True, "email": email}


@router.get("/consent-links")
def generate_consent_links(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Signed unsubscribe / resubscribe / DNC / preference-centre links.

    Tokens are HMAC-signed and workspace-bound; no email is sent by this call.
    """
    verify_workspace(principal, workspace_id)
    contact = db.execute(
        select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    base = f"/api/v1/workspaces/{workspace_id}/email"
    links = {"unsubscribe": _unsub_token(workspace_id, contact.email)}
    for action in ("resubscribe", "dnc", "preferences"):
        links[action] = _consent_token(workspace_id, contact.email, action)
    return {
        "contact_id": contact.id,
        "email": contact.email,
        "do_not_contact": contact.do_not_contact,
        "links": {
            name: {"token": token, "href": f"{base}/{name}?token={token}"}
            for name, token in links.items()
        },
    }


@router.post("/resubscribe", response_model=dict)
def resubscribe(
    workspace_id: str,
    body: ConsentTokenRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = _verify_consent_token(body.token, "resubscribe")
    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired resubscribe token")
    _, token_workspace, email = result
    if token_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    db.execute(
        SuppressionEntry.__table__.delete().where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == email,
        )
    )
    contact = _contact_by_email(db, workspace_id, email)
    if contact is not None:
        contact.do_not_contact = False
        contact.updated_at = now()
    _record_consent(db, workspace_id, contact, channel="email",
                    granted=True, source="resubscribe")
    publish_event(
        db, workspace_id=workspace_id, event_type=RESUBSCRIBE_RECORDED,
        entity_id=email, payload={"email": email}, actor_id=None,
    )
    db.commit()
    return {"resubscribed": True, "email": email}


@router.post("/dnc", response_model=dict)
def set_do_not_contact(
    workspace_id: str,
    body: ConsentTokenRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = _verify_consent_token(body.token, "dnc")
    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired do-not-contact token")
    _, token_workspace, email = result
    if token_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    # Suppression is unique per (workspace, email): an existing unsubscribe
    # entry already suppresses the address, so only add one when none exists.
    existing = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == email,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(SuppressionEntry(
            id=new_id(), workspace_id=workspace_id, email=email,
            reason="dnc", created_at=now(),
        ))
    contact = _contact_by_email(db, workspace_id, email)
    if contact is not None:
        contact.do_not_contact = True
        contact.updated_at = now()
    _record_consent(db, workspace_id, contact, channel="*",
                    granted=False, source="do_not_contact")
    publish_event(
        db, workspace_id=workspace_id, event_type=DNC_RECORDED,
        entity_id=email, payload={"email": email}, actor_id=None,
    )
    db.commit()
    return {"do_not_contact": True, "email": email}


@router.get("/preferences")
def get_preferences(
    workspace_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = _verify_consent_token(token, "preferences")
    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired preferences token")
    _, token_workspace, email = result
    if token_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    contact = _contact_by_email(db, workspace_id, email)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    records = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.contact_id == contact.id,
        ).order_by(ConsentRecord.recorded_at)
    ).scalars().all()
    channels: dict[str, bool] = {}
    for rec in records:
        channels[rec.channel] = bool(rec.granted)
    for channel in PREFERENCE_CHANNELS:
        channels.setdefault(channel, True)
    return {
        "email": email,
        "contact_id": contact.id,
        "do_not_contact": contact.do_not_contact,
        "channels": channels,
    }


@router.post("/preferences", response_model=dict)
def update_preferences(
    workspace_id: str,
    body: PreferencesUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = _verify_consent_token(body.token, "preferences")
    if result is None:
        raise HTTPException(status_code=400, detail="invalid or expired preferences token")
    _, token_workspace, email = result
    if token_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    unknown = set(body.channels) - set(PREFERENCE_CHANNELS)
    if unknown:
        raise HTTPException(status_code=422, detail="unsupported preference channel")
    contact = _contact_by_email(db, workspace_id, email)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    if contact.do_not_contact:
        raise HTTPException(status_code=409, detail="do-not-contact is active; resubscribe first")
    for channel, granted in body.channels.items():
        _record_consent(db, workspace_id, contact, channel=channel,
                        granted=granted, source="preference_center")
    publish_event(
        db, workspace_id=workspace_id, event_type=PREFERENCES_UPDATED,
        entity_id=email,
        payload={"email": email, "channels": sorted(body.channels)}, actor_id=None,
    )
    db.commit()
    return {"updated": True, "email": email, "channels": body.channels}


@router.get("/suppression")
def list_suppression(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SuppressionEntry).where(SuppressionEntry.workspace_id == workspace_id).order_by(SuppressionEntry.created_at.desc())
    ).scalars().all()
    return [{"id": r.id, "email": r.email, "reason": r.reason, "created_at": r.created_at} for r in rows]


@router.post("/suppression", status_code=status.HTTP_201_CREATED)
def add_suppression(
    workspace_id: str,
    email: str = Query(...),
    reason: str = Query(default="manual"),
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    existing = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == email,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(SuppressionEntry(
            id=new_id(), workspace_id=workspace_id, email=email,
            reason=reason, created_at=now(),
        ))
        publish_event(
            db, workspace_id=workspace_id, event_type=SUPPRESSION_ADDED,
            entity_id=email, payload={"email": email, "reason": reason}, actor_id=principal.user.id,
        )
        db.commit()
    return {"suppressed": True, "email": email}


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------


@router.post("/consent", status_code=status.HTTP_201_CREATED)
def record_consent(
    workspace_id: str,
    body: ConsentRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    db.add(ConsentRecord(
        id=new_id(), workspace_id=workspace_id, contact_id=body.contact_id,
        channel=body.channel, granted=body.granted, source=body.source,
        recorded_at=now(),
    ))
    publish_event(
        db, workspace_id=workspace_id, event_type=CONSENT_RECORDED,
        entity_id=body.contact_id,
        payload={"channel": body.channel, "granted": body.granted}, actor_id=principal.user.id,
    )
    db.commit()
    return {"recorded": True}


# ---------------------------------------------------------------------------
# MT-016 — safe token substitution (defaults, escaping, URL and date filters)
# ---------------------------------------------------------------------------

# Syntax: {{contact.first_name|default:Guest|urlencode}}. Substitution is one
# pass, so a value that itself looks like a token is never re-evaluated. Every
# result is HTML-escaped; URL encoding and date formatting run before escaping.
TOKEN_PATTERN = re.compile(
    r"\{\{\s*([a-z_][a-z0-9_.]*)\s*((?:\|[a-z_]+(?::[^}|]*)?)*)\s*\}\}", re.IGNORECASE
)
MAX_TEMPLATE_LENGTH = 20000
TOKEN_FILTERS = frozenset({"default", "urlencode", "date"})


def _token_lookup(source: dict | None, path: str):
    current = source or {}
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def render_tokens(template: str, values: dict, defaults: dict | None = None) -> str:
    """Render local tokens with defaults, URL encoding, date formatting and escaping.

    Raises ValueError for a bad template or an unsupported filter. No network,
    filesystem or template-language evaluation is performed.
    """
    if not isinstance(template, str):
        raise ValueError("template must be a string")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise ValueError("template is too large")
    if not isinstance(values, dict) or (defaults is not None and not isinstance(defaults, dict)):
        raise ValueError("token values must be objects")

    def replace(match: re.Match) -> str:
        path = match.group(1)
        raw = _token_lookup(values, path)
        if raw is None or raw == "":
            raw = _token_lookup(defaults, path)
        specs = [spec for spec in match.group(2).split("|") if spec]
        for spec in specs:
            name, _, argument = spec.partition(":")
            name = name.lower()
            if name not in TOKEN_FILTERS:
                raise ValueError("unsupported token filter")
            if name == "default":
                if raw is None or raw == "":
                    raw = argument
            elif name == "urlencode":
                raw = quote("" if raw is None else str(raw), safe="")
            else:
                parsed = None
                if isinstance(raw, datetime):
                    parsed = raw
                elif isinstance(raw, date):
                    parsed = datetime(raw.year, raw.month, raw.day)
                elif isinstance(raw, str):
                    try:
                        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
                    except ValueError:
                        parsed = None
                if parsed is None:
                    raise ValueError("date token needs an ISO date")
                raw = parsed.strftime(argument or "%Y-%m-%d")
        return html.escape("" if raw is None else str(raw), quote=True)

    return TOKEN_PATTERN.sub(replace, template)


class RenderRequest(BaseModel):
    template: str
    values: dict = Field(default_factory=dict)
    defaults: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


@router.post("/templates/render")
def render_email_tokens(
    workspace_id: str,
    body: RenderRequest,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    try:
        rendered = render_tokens(body.template, body.values, body.defaults)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    publish_event(
        db, workspace_id=workspace_id, event_type=TOKENS_RENDERED,
        entity_id=None,
        payload={"template_length": len(body.template), "token_keys": sorted(body.values)},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"rendered": rendered, "local_only": True}


# ---------------------------------------------------------------------------
# MT-042 / MT-045 / MT-046 — channel-level DNC, preference and frequency rules
# ---------------------------------------------------------------------------

STOP_WORDS = frozenset({"stop", "stopall", "cancel", "unsubscribe", "end", "quit"})


class SmsDncEntry(Base):
    __tablename__ = "sms_dnc_entries"
    __table_args__ = (UniqueConstraint("workspace_id", "contact_id", name="uq_sms_dnc_contact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(60), default="stop_reply", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SmsReply(Base):
    __tablename__ = "sms_replies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stop_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ChannelPreference(Base):
    __tablename__ = "channel_preferences"
    __table_args__ = (UniqueConstraint("workspace_id", "contact_id", name="uq_channel_pref_contact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ChannelRule(Base):
    __tablename__ = "channel_rules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "contact_id", "channel", name="uq_channel_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    max_per_day: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class LocalDelivery(Base):
    """A local-only delivery record. It never represents an external send."""

    __tablename__ = "local_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    message_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SmsReplyRequest(BaseModel):
    contact_id: str
    message: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("message")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("reply message is required and must be short")
        return value


class LocalDeliveryRequest(BaseModel):
    contact_id: str
    message: str
    message_key: str = "transactional"

    model_config = ConfigDict(extra="forbid")

    @field_validator("message", "message_key")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


class PreferenceRequest(BaseModel):
    contact_id: str
    channel: Literal["email", "sms", "push"]

    model_config = ConfigDict(extra="forbid")


class ChannelRuleRequest(BaseModel):
    contact_id: str
    channel: Literal["email", "sms", "push"]
    max_per_day: int = Field(default=3, ge=0, le=1000)
    paused: bool = False

    model_config = ConfigDict(extra="forbid")


def is_stop_reply(text: str) -> bool:
    """Recognise STOP-family opt-outs without matching words like 'stopped'."""
    cleaned = re.sub(r"[^a-z]+", " ", (text or "").lower()).strip()
    words = cleaned.split()
    return any(word in STOP_WORDS for word in words) or cleaned.replace(" ", "") in STOP_WORDS


def _channel_contact(db, workspace_id: str, contact_id: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact


def _email_channel_blocked(db, workspace_id: str, contact: Contact) -> bool:
    return bool(contact.do_not_contact) or _is_suppressed(db, workspace_id, contact.email) or not _has_consent(
        db, workspace_id, contact.id
    )


def _sms_channel_blocked(db, workspace_id: str, contact: Contact) -> bool:
    dnc = db.execute(
        select(SmsDncEntry.id).where(
            SmsDncEntry.workspace_id == workspace_id,
            SmsDncEntry.contact_id == contact.id,
        )
    ).scalar_one_or_none()
    if dnc is not None:
        return True
    latest = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.contact_id == contact.id,
            ConsentRecord.channel == "sms",
        ).order_by(ConsentRecord.recorded_at.desc())
    ).scalars().first()
    return latest is not None and not bool(latest.granted)


def _resolve_channel(db, workspace_id: str, contact_id: str) -> str:
    preference = db.execute(
        select(ChannelPreference).where(
            ChannelPreference.workspace_id == workspace_id,
            ChannelPreference.contact_id == contact_id,
        )
    ).scalar_one_or_none()
    return preference.channel if preference is not None else "email"


@router.post("/sms/reply")
def record_sms_reply(
    workspace_id: str,
    body: SmsReplyRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, body.contact_id)
    stop = is_stop_reply(body.message)
    reply = SmsReply(
        id=new_id(), workspace_id=workspace_id, contact_id=contact.id, phone=contact.phone,
        message=body.message, stop_detected=stop, created_at=now(),
    )
    db.add(reply)
    if stop:
        dnc = db.execute(
            select(SmsDncEntry).where(
                SmsDncEntry.workspace_id == workspace_id, SmsDncEntry.contact_id == contact.id
            )
        ).scalar_one_or_none()
        if dnc is None:
            db.add(SmsDncEntry(
                id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
                phone=contact.phone, reason="stop_reply", created_at=now(),
            ))
        _record_consent(
            db, workspace_id, contact, channel="sms", granted=False, source="sms_stop_reply"
        )
        publish_event(
            db, workspace_id=workspace_id, event_type=SMS_DNC_RECORDED,
            entity_id=contact.id, payload={"phone": contact.phone, "reply": body.message},
            actor_id=principal.user.id,
        )
    publish_event(
        db, workspace_id=workspace_id, event_type=SMS_REPLY_RECORDED,
        entity_id=reply.id, payload={"contact_id": contact.id, "stop_detected": stop},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"stop_detected": stop, "sms_do_not_contact": stop, "contact_id": contact.id}


@router.get("/sms/dnc")
def list_sms_dnc(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _channel_contact(db, workspace_id, contact_id)
    rows = db.execute(
        select(SmsDncEntry).where(
            SmsDncEntry.workspace_id == workspace_id, SmsDncEntry.contact_id == contact_id
        ).order_by(SmsDncEntry.created_at.desc())
    ).scalars().all()
    return [
        {"id": row.id, "contact_id": row.contact_id, "phone": row.phone,
         "reason": row.reason, "created_at": row.created_at}
        for row in rows
    ]


@router.post("/sms/deliver-local")
def deliver_sms_local(
    workspace_id: str,
    body: LocalDeliveryRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Local SMS adapter: records a queued item or blocks it before dispatch."""
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, body.contact_id)
    if _sms_channel_blocked(db, workspace_id, contact):
        publish_event(
            db, workspace_id=workspace_id, event_type=SMS_DELIVERY_BLOCKED,
            entity_id=contact.id, payload={"reason": "sms_dnc"}, actor_id=principal.user.id,
        )
        db.commit()
        return {"status": "blocked", "channel": "sms", "reason": "sms_dnc", "local_only": True}
    delivery = LocalDelivery(
        id=new_id(), workspace_id=workspace_id, contact_id=contact.id, channel="sms",
        message_key=body.message_key, status="queued_local",
        detail={"length": len(body.message)}, created_at=now(),
    )
    db.add(delivery)
    db.commit()
    return {"status": delivery.status, "channel": "sms", "delivery_id": delivery.id, "local_only": True}


@router.post("/channel-preferences")
def set_channel_preference(
    workspace_id: str,
    body: PreferenceRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, body.contact_id)
    preference = db.execute(
        select(ChannelPreference).where(
            ChannelPreference.workspace_id == workspace_id,
            ChannelPreference.contact_id == contact.id,
        )
    ).scalar_one_or_none()
    if preference is None:
        preference = ChannelPreference(
            id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
            channel=body.channel, updated_at=now(),
        )
        db.add(preference)
    else:
        preference.channel = body.channel
        preference.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CHANNEL_PREFERENCE_UPDATED,
        entity_id=contact.id, payload={"channel": body.channel}, actor_id=principal.user.id,
    )
    db.commit()
    return {"contact_id": contact.id, "channel": body.channel}


@router.get("/channel-preferences")
def get_channel_preference(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, contact_id)
    return {
        "contact_id": contact.id,
        "channel": _resolve_channel(db, workspace_id, contact.id),
        "is_default": db.execute(
            select(ChannelPreference.id).where(
                ChannelPreference.workspace_id == workspace_id,
                ChannelPreference.contact_id == contact.id,
            )
        ).scalar_one_or_none() is None,
    }


@router.put("/channel-rules")
def set_channel_rule(
    workspace_id: str,
    body: ChannelRuleRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, body.contact_id)
    rule = db.execute(
        select(ChannelRule).where(
            ChannelRule.workspace_id == workspace_id,
            ChannelRule.contact_id == contact.id,
            ChannelRule.channel == body.channel,
        )
    ).scalar_one_or_none()
    if rule is None:
        rule = ChannelRule(
            id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
            channel=body.channel, max_per_day=body.max_per_day, paused=body.paused,
            updated_at=now(),
        )
        db.add(rule)
    else:
        rule.max_per_day = body.max_per_day
        rule.paused = body.paused
        rule.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CHANNEL_RULE_UPDATED,
        entity_id=contact.id,
        payload={"channel": body.channel, "max_per_day": body.max_per_day, "paused": body.paused},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "contact_id": contact.id, "channel": body.channel,
        "max_per_day": body.max_per_day, "paused": body.paused,
    }


@router.get("/channel-rules")
def get_channel_rule(
    workspace_id: str,
    contact_id: str = Query(...),
    channel: Literal["email", "sms", "push"] = Query("email"),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, contact_id)
    rule = db.execute(
        select(ChannelRule).where(
            ChannelRule.workspace_id == workspace_id,
            ChannelRule.contact_id == contact.id,
            ChannelRule.channel == channel,
        )
    ).scalar_one_or_none()
    return {
        "contact_id": contact.id, "channel": channel,
        "max_per_day": rule.max_per_day if rule else None,
        "paused": bool(rule.paused) if rule else False,
    }


class MarketingMessageRequest(BaseModel):
    contact_id: str
    message_key: str
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("message_key", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


@router.post("/marketing-message/deliver-local")
def deliver_marketing_message_local(
    workspace_id: str,
    body: MarketingMessageRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve one channel and record exactly one local delivery or block it."""
    verify_workspace(principal, workspace_id)
    contact = _channel_contact(db, workspace_id, body.contact_id)
    channel = _resolve_channel(db, workspace_id, contact.id)
    rule = db.execute(
        select(ChannelRule).where(
            ChannelRule.workspace_id == workspace_id,
            ChannelRule.contact_id == contact.id,
            ChannelRule.channel == channel,
        )
    ).scalar_one_or_none()
    if rule is not None and rule.paused:
        publish_event(
            db, workspace_id=workspace_id, event_type=MESSAGE_BLOCKED,
            entity_id=contact.id,
            payload={"channel": channel, "reason": "paused", "message_key": body.message_key},
            actor_id=principal.user.id,
        )
        db.commit()
        raise HTTPException(status_code=409, detail=f"channel {channel} is paused")
    if channel == "sms" and _sms_channel_blocked(db, workspace_id, contact):
        publish_event(
            db, workspace_id=workspace_id, event_type=MESSAGE_BLOCKED,
            entity_id=contact.id,
            payload={"channel": channel, "reason": "sms_dnc", "message_key": body.message_key},
            actor_id=principal.user.id,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="sms do-not-contact is active")
    if channel == "email" and _email_channel_blocked(db, workspace_id, contact):
        publish_event(
            db, workspace_id=workspace_id, event_type=MESSAGE_BLOCKED,
            entity_id=contact.id,
            payload={"channel": channel, "reason": "email_suppressed", "message_key": body.message_key},
            actor_id=principal.user.id,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="email channel is suppressed")
    if rule is not None:
        window_start = now() - timedelta(days=1)
        delivered = db.execute(
            select(func.count(LocalDelivery.id)).where(
                LocalDelivery.workspace_id == workspace_id,
                LocalDelivery.contact_id == contact.id,
                LocalDelivery.channel == channel,
                LocalDelivery.status == "queued_local",
                LocalDelivery.created_at >= window_start,
            )
        ).scalar() or 0
        if delivered >= rule.max_per_day:
            publish_event(
                db, workspace_id=workspace_id, event_type=MESSAGE_BLOCKED,
                entity_id=contact.id,
                payload={"channel": channel, "reason": "frequency_cap", "message_key": body.message_key},
                actor_id=principal.user.id,
            )
            db.commit()
            raise HTTPException(status_code=409, detail=f"channel {channel} frequency cap reached")
    delivery = LocalDelivery(
        id=new_id(), workspace_id=workspace_id, contact_id=contact.id, channel=channel,
        message_key=body.message_key, status="queued_local",
        detail={"body_length": len(body.body), "local_only": True}, created_at=now(),
    )
    db.add(delivery)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=MESSAGE_DELIVERED,
        entity_id=delivery.id,
        payload={
            "contact_id": contact.id, "channel": channel,
            "message_key": body.message_key, "local_only": True,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "delivery_id": delivery.id, "contact_id": contact.id, "channel": channel,
        "status": delivery.status, "local_only": True,
    }


@router.get("/marketing-message/deliveries")
def list_local_deliveries(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _channel_contact(db, workspace_id, contact_id)
    rows = db.execute(
        select(LocalDelivery).where(
            LocalDelivery.workspace_id == workspace_id, LocalDelivery.contact_id == contact_id
        ).order_by(LocalDelivery.created_at)
    ).scalars().all()
    return [
        {"id": row.id, "channel": row.channel, "message_key": row.message_key,
         "status": row.status, "detail": row.detail, "created_at": row.created_at}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# MT-050 — signed outbound webhooks with real retries and delivery logs
# ---------------------------------------------------------------------------

WEBHOOK_EVENT_TYPES = frozenset({
    BROADCAST_SENT, MESSAGE_DELIVERED, SMS_DNC_RECORDED, "document.shared", "document.viewed",
})


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_webhook_subscription_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WebhookDelivery(Base):
    """One attempt in one delivery. Failed attempts are never deleted."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("webhook_subscriptions.id"), nullable=False, index=True
    )
    delivery_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    signature_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str = Field(min_length=16, max_length=256)
    event_types: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("subscription name is required")
        return value

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("webhook url must be an http(s) URL without credentials")
        host = (parsed.hostname or "").lower()
        if host not in allowed_webhook_hosts():
            raise ValueError("webhook host is not allowed")
        return value.strip()

    @field_validator("event_types")
    @classmethod
    def known_events(cls, value: list[str]) -> list[str]:
        if not value or len(set(value)) != len(value) or any(e not in WEBHOOK_EVENT_TYPES for e in value):
            raise ValueError("unsupported webhook event type")
        return value


class WebhookOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    url: str
    event_types: list[str]
    enabled: bool
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


def _webhook_or_404(db, workspace_id: str, subscription_id: str) -> WebhookSubscription:
    subscription = db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=404, detail="webhook subscription not found")
    return subscription


def webhook_signature(secret: str, delivery_id: str, body: str) -> str:
    """The exact signature a receiver verifies: HMAC-SHA256 of id + '.' + body."""
    signed = f"{delivery_id}.{body}".encode("utf-8")
    return "sha256=" + hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def deliver_webhook(
    db,
    *,
    workspace_id: str,
    subscription_id: str,
    event_type: str,
    payload: dict,
    max_attempts: int = 3,
) -> dict:
    """Deliver one signed payload over real HTTP with bounded retries.

    The only network calls are to the URL explicitly configured by the
    workspace. Every attempt is persisted; a non-2xx response or transport
    error is a failed attempt, never a claimed delivery.
    """
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("max_attempts must be between 1 and 5")
    subscription = db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if subscription is None:
        raise ValueError("webhook subscription not found")
    if not subscription.enabled or event_type not in subscription.event_types:
        raise ValueError("event is not subscribed")
    delivery_id = new_id()
    body = json.dumps(
        {"delivery_id": delivery_id, "event": event_type, "workspace_id": workspace_id,
         "payload": payload},
        sort_keys=True, separators=(",", ":"),
    )
    signature = webhook_signature(subscription.secret, delivery_id, body)
    request = urllib.request.Request(
        subscription.url,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-NOVARA-Event": event_type,
            "X-NOVARA-Delivery": delivery_id,
            "X-NOVARA-Signature": signature,
        },
    )
    # Ignore ambient proxies: the subscription URL is authoritative.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    status = "failed"
    status_code: int | None = None
    error: str | None = None
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        log = WebhookDelivery(
            id=new_id(), workspace_id=workspace_id, subscription_id=subscription.id,
            delivery_id=delivery_id, attempt=attempt, status="pending",
            signature_prefix=signature[:16], created_at=now(),
        )
        db.add(log)
        db.flush()
        try:
            with opener.open(request, timeout=3) as response:
                status_code = int(getattr(response, "status", response.getcode()))
            if 200 <= status_code < 300:
                log.status = "delivered"
                log.status_code = status_code
                status = "delivered"
                error = None
                break
            error = f"http {status_code}"
            log.status = "failed"
            log.status_code = status_code
            log.error = error
        except urllib.error.HTTPError as exc:
            # A non-2xx reply is a real delivery attempt, not a transport
            # failure: urllib raises HTTPError (a URLError subclass) here, so
            # capture its status before the generic transport handler runs.
            status_code = int(exc.code)
            error = f"http {status_code}"
            log.status = "failed"
            log.status_code = status_code
            log.error = error
        except (urllib.error.URLError, OSError, ValueError) as exc:
            error = str(exc)[:300]
            log.status = "failed"
            log.error = error
            status_code = None
    if status == "delivered":
        publish_event(
            db, workspace_id=workspace_id, event_type=WEBHOOK_DELIVERED,
            entity_id=delivery_id,
            payload={"subscription_id": subscription.id, "event": event_type, "attempts": attempts},
            idempotency_key=f"webhook-delivered:{delivery_id}", actor_id=None,
        )
    else:
        publish_event(
            db, workspace_id=workspace_id, event_type=WEBHOOK_DELIVERY_FAILED,
            entity_id=delivery_id,
            payload={"subscription_id": subscription.id, "event": event_type, "attempts": attempts},
            idempotency_key=f"webhook-failed:{delivery_id}", actor_id=None,
        )
    db.commit()
    return {
        "delivery_id": delivery_id, "status": status, "attempts": attempts,
        "status_code": status_code, "error": error,
    }


@router.post("/webhooks", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook_subscription(
    workspace_id: str,
    body: WebhookCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> WebhookSubscription:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(WebhookSubscription.id).where(
            WebhookSubscription.workspace_id == workspace_id,
            WebhookSubscription.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="webhook name already exists")
    subscription = WebhookSubscription(
        id=new_id(), workspace_id=workspace_id, name=body.name, url=body.url,
        secret=body.secret, event_types=body.event_types, enabled=True,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(subscription)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=WEBHOOK_SUBSCRIPTION_CREATED,
        entity_id=subscription.id,
        payload={"name": subscription.name, "event_types": subscription.event_types},
        actor_id=principal.user.id,
    )
    db.commit()
    return subscription


@router.get("/webhooks", response_model=list[WebhookOut])
def list_webhook_subscriptions(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[WebhookSubscription]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(WebhookSubscription).where(WebhookSubscription.workspace_id == workspace_id)
        .order_by(WebhookSubscription.created_at.desc())
    ).scalars().all()


@router.get("/webhooks/{subscription_id}/deliveries")
def list_webhook_deliveries(
    workspace_id: str,
    subscription_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _webhook_or_404(db, workspace_id, subscription_id)
    logs = db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.workspace_id == workspace_id,
            WebhookDelivery.subscription_id == subscription_id,
        ).order_by(WebhookDelivery.created_at, WebhookDelivery.attempt)
    ).scalars().all()
    return [
        {"id": log.id, "delivery_id": log.delivery_id, "attempt": log.attempt,
         "status": log.status, "status_code": log.status_code, "error": log.error,
         "signature_prefix": log.signature_prefix}
        for log in logs
    ]