"""Workable local campaign delivery for the marketing workflow.

Audience -> Campaign -> Approval -> Local delivery adapter -> Analytics.

This module makes the five steps in the public marketing workflow executable in
one workspace-scoped run. It reuses the existing broadcast, recipient, consent
and local-delivery records, and adds a single run record that carries the
approval decision and a correlation id for the analytics trail.

Safety contract: the "delivery adapter" here is a deterministic local boundary.
It writes ``local_deliveries`` rows with ``local_only=True`` and
``external_delivery=False``. There is no HTTP client, provider SDK, mail client,
SMS gateway or WhatsApp client in this module, and no endpoint sends anything
outside the workspace. Approval is mandatory for every run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, Event, new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE, OUTREACH_APPROVE
from .email_campaigns import (
    BROADCAST_QUEUED,
    BROADCAST_SENT,
    BroadcastCampaign,
    BroadcastRecipient,
    ConsentRecord,
    LocalDelivery,
    _is_suppressed,
)

RUN_CREATED = "marketing.run_created"
RUN_APPROVED = "marketing.run_approved"
LOCAL_DELIVERED = "marketing.local_delivered"
LOCAL_BLOCKED = "marketing.local_delivery_blocked"
ANALYTICS_RECORDED = "marketing.analytics_recorded"
register_event_types(
    RUN_CREATED, RUN_APPROVED, LOCAL_DELIVERED, LOCAL_BLOCKED, ANALYTICS_RECORDED
)

NO_EXTERNAL_SEND = (
    "Local adapter only: no email, SMS or WhatsApp message leaves this workspace."
)


def _stamp(value: datetime | None) -> str | None:
    """Return one stable JSON timestamp shape for fresh and reloaded rows.

    SQLite drops timezone info on reload, so responses would otherwise differ
    between the first approval call and later reads of the same run.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/marketing-delivery",
    tags=["marketing-delivery"],
)



# ---------------------------------------------------------------------------
# Persistent run record
# ---------------------------------------------------------------------------


class MarketingLocalRun(Base):
    """One auditable, approval-gated local campaign run."""

    __tablename__ = "marketing_local_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "correlation_id", name="uq_marketing_run_correlation"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("broadcast_campaigns.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="awaiting_approval", nullable=False)
    audience_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String(36))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LocalRunCreate(BaseModel):
    name: str
    subject: str
    body: str
    contact_ids: list[str] = Field(default_factory=list)
    channel: Literal["email", "sms", "whatsapp"] = "email"
    correlation_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "subject", "body")
    @classmethod
    def text_valid(cls, value: str, info) -> str:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError(f"{info.field_name} must not be blank")
        limit = 200 if info.field_name == "name" else 300 if info.field_name == "subject" else 5000
        if len(cleaned) > limit:
            raise ValueError(f"{info.field_name} is too long")
        return cleaned

    @field_validator("contact_ids")
    @classmethod
    def audience_valid(cls, value: list[str]) -> list[str]:
        if not value or len(value) > 500:
            raise ValueError("audience must contain between 1 and 500 contacts")
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("contact ids must be non-empty strings")
            cleaned.append(item.strip())
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("duplicate contact ids are not allowed")
        return cleaned

    @field_validator("correlation_id")
    @classmethod
    def correlation_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 36:
            raise ValueError("correlation_id must be between 1 and 36 characters")
        return cleaned


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_or_404(db: Session, workspace_id: str, run_id: str) -> MarketingLocalRun:
    run = db.execute(
        select(MarketingLocalRun).where(
            MarketingLocalRun.id == run_id,
            MarketingLocalRun.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="marketing run not found")
    return run


def _consent_granted(db: Session, workspace_id: str, contact_id: str, channel: str) -> bool:
    """Channel-specific consent. No record means default allow, matching the
    existing broadcast consent rule."""
    record = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.contact_id == contact_id,
            ConsentRecord.channel == channel,
        )
    ).scalars().first()
    return True if record is None else bool(record.granted)


def _recipient_check(
    db: Session, workspace_id: str, contact_id: str, channel: str
) -> tuple[Contact | None, str | None]:
    """Return the live contact and the reason it cannot receive this channel."""
    contact = db.execute(
        select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if contact is None:
        return None, "contact_not_found"
    if contact.do_not_contact:
        return contact, "do_not_contact"
    if _is_suppressed(db, workspace_id, contact.email):
        return contact, "suppressed"
    if not _consent_granted(db, workspace_id, contact.id, channel):
        return contact, "consent_revoked"
    return contact, None


def _event_count(db: Session, workspace_id: str, correlation_id: str) -> int:
    return len(
        db.execute(
            select(Event.id).where(
                Event.workspace_id == workspace_id,
                Event.correlation_id == correlation_id,
            )
        ).all()
    )


def _run_out(db: Session, run: MarketingLocalRun) -> dict:
    approved = run.approved_at is not None
    executed = run.executed_at is not None
    return {
        "id": run.id,
        "correlation_id": run.correlation_id,
        "status": run.status,
        "name": run.name,
        "channel": run.channel,
        "campaign_id": run.campaign_id,
        "created_at": _stamp(run.created_at),
        "approved_by": run.approved_by,
        "approved_at": _stamp(run.approved_at),
        "executed_at": _stamp(run.executed_at),
        "counts": {
            "audience": run.audience_count,
            "blocked": run.blocked_count,
            "delivered": run.delivered_count,
            "events": _event_count(db, run.workspace_id, run.correlation_id),
        },
        "steps": {
            "audience": {"status": "recorded", "count": run.audience_count},
            "campaign": {"status": "recorded", "id": run.campaign_id},
            "approval": {
                "status": "approved" if approved else "awaiting_approval",
                "by": run.approved_by,
            },
            "delivery": {
                "status": "executed" if executed else "pending",
                "count": run.delivered_count,
                "local_only": True,
                "external_delivery": False,
            },
            "analytics": {
                "status": "recorded" if executed else "pending",
                "events": _event_count(db, run.workspace_id, run.correlation_id),
            },
        },
        "note": NO_EXTERNAL_SEND,
    }


def _execute_local(db: Session, run: MarketingLocalRun, principal: Principal) -> MarketingLocalRun:
    """Run the local adapter once. No provider, network client or real send."""
    pending = db.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.workspace_id == run.workspace_id,
            BroadcastRecipient.campaign_id == run.campaign_id,
            BroadcastRecipient.status == "pending",
        )
    ).scalars().all()

    # Consent can change between audience build and approval. Re-check every
    # recipient at the adapter boundary so a later opt-out cannot be overridden
    # by an older queued row.
    eligible = []
    blocked_now = 0
    for recipient in pending:
        contact, reason = _recipient_check(
            db, run.workspace_id, recipient.contact_id, run.channel
        )
        if reason is not None:
            recipient.status = "suppressed"
            recipient.error = reason
            blocked_now += 1
            continue
        recipient.email = contact.email
        eligible.append(recipient)

    if blocked_now:
        publish_event(
            db,
            workspace_id=run.workspace_id,
            event_type=LOCAL_BLOCKED,
            entity_id=run.id,
            payload={"blocked": blocked_now, "local_only": True},
            correlation_id=run.correlation_id,
            idempotency_key=f"marketing-blocked:{run.id}",
            actor_id=principal.user.id,
        )

    publish_event(
        db,
        workspace_id=run.workspace_id,
        event_type=BROADCAST_QUEUED,
        entity_id=run.campaign_id,
        payload={"queued": len(eligible), "correlation_id": run.correlation_id},
        correlation_id=run.correlation_id,
        idempotency_key=f"marketing-queued:{run.id}",
        actor_id=principal.user.id,
    )

    delivered = 0
    for recipient in eligible:
        recipient.status = "queued"
        recipient.queued_at = now()
        delivery = LocalDelivery(
            workspace_id=run.workspace_id,
            contact_id=recipient.contact_id,
            channel=run.channel,
            message_key=f"campaign:{run.campaign_id}",
            status="simulated",
            detail={
                "local_only": True,
                "external_delivery": False,
                "correlation_id": run.correlation_id,
                "campaign_id": run.campaign_id,
                "recipient_id": recipient.id,
                "note": NO_EXTERNAL_SEND,
            },
        )
        db.add(delivery)
        db.flush()
        recipient.status = "sent"
        recipient.sent_at = now()
        delivered += 1

    campaign = db.get(BroadcastCampaign, run.campaign_id)
    if campaign is not None and campaign.workspace_id == run.workspace_id:
        campaign.status = "sent" if delivered else "cancelled"
        campaign.updated_at = now()

    publish_event(
        db,
        workspace_id=run.workspace_id,
        event_type=BROADCAST_SENT,
        entity_id=run.campaign_id,
        payload={"sent": delivered, "correlation_id": run.correlation_id},
        correlation_id=run.correlation_id,
        idempotency_key=f"marketing-sent:{run.id}",
        actor_id=principal.user.id,
    )
    publish_event(
        db,
        workspace_id=run.workspace_id,
        event_type=LOCAL_DELIVERED,
        entity_id=run.id,
        payload={
            "delivered": delivered,
            "channel": run.channel,
            "local_only": True,
            "external_delivery": False,
        },
        correlation_id=run.correlation_id,
        idempotency_key=f"marketing-delivered:{run.id}",
        actor_id=principal.user.id,
    )
    publish_event(
        db,
        workspace_id=run.workspace_id,
        event_type=ANALYTICS_RECORDED,
        entity_id=run.id,
        payload={
            "audience": run.audience_count,
            "blocked": run.blocked_count + blocked_now,
            "delivered": delivered,
            "channel": run.channel,
        },
        correlation_id=run.correlation_id,
        idempotency_key=f"marketing-analytics:{run.id}",
        actor_id=principal.user.id,
    )

    run.blocked_count += blocked_now
    run.delivered_count = delivered
    run.status = "executed"
    run.executed_at = now()
    return run


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/runs", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_run(
    workspace_id: str,
    body: LocalRunCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Build the audience and campaign, then stop at the approval gate."""
    verify_workspace(principal, workspace_id)
    correlation_id = body.correlation_id or new_id()
    existing = db.execute(
        select(MarketingLocalRun).where(
            MarketingLocalRun.workspace_id == workspace_id,
            MarketingLocalRun.correlation_id == correlation_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _run_out(db, existing)

    campaign = BroadcastCampaign(
        workspace_id=workspace_id,
        name=body.name,
        subject=body.subject,
        body=body.body,
        source_type="local_run",
        status="draft",
        created_by=principal.user.id,
    )
    db.add(campaign)
    db.flush()

    audience = 0
    blocked = 0
    for contact_id in body.contact_ids:
        contact, reason = _recipient_check(db, workspace_id, contact_id, body.channel)
        if reason is not None:
            blocked += 1
            continue
        db.add(
            BroadcastRecipient(
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                contact_id=contact.id,
                email=contact.email,
                status="pending",
            )
        )
        audience += 1

    run = MarketingLocalRun(
        workspace_id=workspace_id,
        correlation_id=correlation_id,
        campaign_id=campaign.id,
        name=body.name,
        channel=body.channel,
        status="awaiting_approval",
        audience_count=audience,
        blocked_count=blocked,
        created_by=principal.user.id,
    )
    db.add(run)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=RUN_CREATED,
        entity_id=run.id,
        payload={
            "campaign_id": campaign.id,
            "audience": audience,
            "blocked": blocked,
            "channel": body.channel,
            "local_only": True,
        },
        correlation_id=correlation_id,
        idempotency_key=f"marketing-run-created:{run.id}",
        actor_id=principal.user.id,
    )
    db.commit()
    return _run_out(db, run)


@router.get("/runs", response_model=list[dict])
def list_runs(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(MarketingLocalRun)
        .where(MarketingLocalRun.workspace_id == workspace_id)
        .order_by(MarketingLocalRun.created_at.desc())
    ).scalars().all()
    return [_run_out(db, row) for row in rows]


@router.get("/runs/{run_id}", response_model=dict)
def get_run(
    workspace_id: str,
    run_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Full analytics trace: recipients, local deliveries and events."""
    verify_workspace(principal, workspace_id)
    run = _run_or_404(db, workspace_id, run_id)
    result = _run_out(db, run)
    recipients = db.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.workspace_id == workspace_id,
            BroadcastRecipient.campaign_id == run.campaign_id,
        )
    ).scalars().all()
    deliveries = db.execute(
        select(LocalDelivery).where(
            LocalDelivery.workspace_id == workspace_id,
            LocalDelivery.message_key == f"campaign:{run.campaign_id}",
        )
    ).scalars().all()
    events = db.execute(
        select(Event)
        .where(
            Event.workspace_id == workspace_id,
            Event.correlation_id == run.correlation_id,
        )
        .order_by(Event.seq)
    ).scalars().all()
    result["recipients"] = [
        {
            "id": row.id,
            "contact_id": row.contact_id,
            "email": row.email,
            "status": row.status,
            "error": row.error,
            "queued_at": _stamp(row.queued_at),
            "sent_at": _stamp(row.sent_at),
        }
        for row in recipients
    ]
    result["deliveries"] = [
        {
            "id": row.id,
            "contact_id": row.contact_id,
            "channel": row.channel,
            "status": row.status,
            "detail": row.detail,
        }
        for row in deliveries
    ]
    result["events"] = [
        {
            "seq": row.seq,
            "event_type": row.event_type,
            "occurred_at": _stamp(row.occurred_at),
            "payload": row.payload,
        }
        for row in events
    ]
    return result


@router.post("/runs/{run_id}/approve", response_model=dict)
def approve_run(
    workspace_id: str,
    run_id: str,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> dict:
    """Human gate. Only after approval does the local adapter record deliveries."""
    verify_workspace(principal, workspace_id)
    run = _run_or_404(db, workspace_id, run_id)
    if run.status == "executed":
        return _run_out(db, run)
    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run cannot be approved from status {run.status}",
        )
    run.approved_by = principal.user.id
    run.approved_at = now()
    run.status = "approved"
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=RUN_APPROVED,
        entity_id=run.id,
        payload={"approved_by": principal.user.id, "local_only": True},
        correlation_id=run.correlation_id,
        idempotency_key=f"marketing-approved:{run.id}",
        actor_id=principal.user.id,
    )
    _execute_local(db, run, principal)
    db.commit()
    return _run_out(db, run)
