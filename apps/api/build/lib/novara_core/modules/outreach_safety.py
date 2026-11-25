"""Local outreach safety gates: opt-outs, suppression and pre-send decisions.

This module is review-only. It stores workspace-owned policy, records opt-outs
and suppressions with reasons, and evaluates whether a draft *could* be handed
to a future authorised delivery adapter. No adapter is invoked here and no
network client exists in this build.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import (
    Contact,
    OutreachDraft,
    SuppressionEntry,
    WorkspaceOutreachPolicy,
    new_id,
    now,
)
from ..permissions import OUTREACH_APPROVE, OUTREACH_READ

OPTOUT_RECORDED = "outreach.optout_recorded"
SUPPRESSION_ADDED = "outreach.suppression_added"
SUPPRESSION_REVOKED = "outreach.suppression_revoked"
FOOTER_UPDATED = "outreach.compliance_footer_updated"
GATE_REJECTED = "outreach.presend_gate_rejected"
register_event_types(
    OPTOUT_RECORDED, SUPPRESSION_ADDED, SUPPRESSION_REVOKED, FOOTER_UPDATED, GATE_REJECTED
)

# Placeholder wording only. The actual footer is an owner decision stored per
# workspace and appended to every draft by the drafting helper.
DEFAULT_COMPLIANCE_FOOTER = (
    "Prepared in NOVARA. To opt out of future messages, reply STOP."
)
OPT_OUT_REASON = "opt_out"
NO_DELIVERY_NOTE = (
    "Review and gate only: no delivery adapter, network call or external send is "
    "performed by this build."
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/outreach-safety",
    tags=["outreach-safety"],
)


class SuppressionDuplicate(ValueError):
    """A matching active suppression already exists in this workspace."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _required_text(value: str, label: str, limit: int) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError(f"{label} must not be blank")
    if len(cleaned) > limit:
        raise ValueError(f"{label} is too long")
    return cleaned


def normalise_email(value: str) -> str:
    email = _required_text(value, "email", 320).lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("email must be a valid address")
    return email


def normalise_domain(value: str) -> str:
    domain = _required_text(value, "domain", 253).lower().lstrip("@")
    if "@" in domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("domain must be a hostname without an address")
    return domain


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_active(row: SuppressionEntry) -> bool:
    return row.revoked_at is None and (
        row.expires_at is None or (_as_aware(row.expires_at) or now()) > now()
    )


def compliance_footer(db: Session, workspace_id: str) -> str:
    """Return the configured footer, falling back to the local placeholder."""
    policy = db.execute(
        select(WorkspaceOutreachPolicy).where(
            WorkspaceOutreachPolicy.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    return policy.compliance_footer if policy is not None else DEFAULT_COMPLIANCE_FOOTER


def set_compliance_footer(
    db: Session, *, workspace_id: str, footer: str, actor_id: str
) -> WorkspaceOutreachPolicy:
    text = _required_text(footer, "compliance footer", 1000)
    policy = db.execute(
        select(WorkspaceOutreachPolicy).where(
            WorkspaceOutreachPolicy.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if policy is None:
        policy = WorkspaceOutreachPolicy(
            id=new_id(), workspace_id=workspace_id, compliance_footer=text,
            updated_by=actor_id, created_at=now(), updated_at=now(),
        )
        db.add(policy)
    else:
        policy.compliance_footer = text
        policy.updated_by = actor_id
        policy.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=FOOTER_UPDATED,
        entity_id=policy.id,
        payload={"length": len(text), "source": "workspace_owner"},
        actor_id=actor_id,
    )
    return policy


def add_suppression(
    db: Session,
    *,
    workspace_id: str,
    recipient: str,
    scope: Literal["email", "domain"],
    reason: str,
    actor_id: str,
    expires_at: datetime | None = None,
) -> SuppressionEntry:
    if scope == "email":
        target = normalise_email(recipient)
    elif scope == "domain":
        target = normalise_domain(recipient)
    else:
        raise ValueError("scope must be email or domain")
    text = _required_text(reason, "reason", 200)
    if expires_at is not None and (_as_aware(expires_at) or now()) <= now():
        raise ValueError("expires_at must be in the future")

    existing = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.recipient == target,
            SuppressionEntry.scope == scope,
            SuppressionEntry.reason == text,
            SuppressionEntry.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise SuppressionDuplicate("a matching suppression is already active")

    entry = SuppressionEntry(
        id=new_id(),
        workspace_id=workspace_id,
        recipient=target,
        scope=scope,
        reason=text,
        expires_at=expires_at,
        created_at=now(),
        created_by=actor_id,
        revoked_at=None,
    )
    db.add(entry)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=SUPPRESSION_ADDED,
        entity_id=entry.id,
        payload={
            "recipient": entry.recipient,
            "scope": entry.scope,
            "reason": entry.reason,
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        },
        actor_id=actor_id,
    )
    return entry


def record_optout(
    db: Session,
    *,
    workspace_id: str,
    email: str,
    actor_id: str,
    reason: str | None = None,
) -> SuppressionEntry:
    """Honour an opt-out locally: set the contact flag and add an audited reason."""
    recipient = normalise_email(email)
    text = _required_text(reason or "contact requested opt-out", "reason", 200)
    contact = db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.email == recipient
        )
    ).scalar_one_or_none()
    if contact is not None:
        contact.do_not_contact = True
        contact.updated_at = now()
    for entry in db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.recipient == recipient,
            SuppressionEntry.scope == "email",
            SuppressionEntry.reason == OPT_OUT_REASON,
            SuppressionEntry.revoked_at.is_(None),
        )
    ).scalars():
        return entry

    # An opt-out is a permanent do-not-contact record in this build: no expiry.
    entry = SuppressionEntry(
        id=new_id(),
        workspace_id=workspace_id,
        recipient=recipient,
        scope="email",
        reason=OPT_OUT_REASON,
        expires_at=None,
        created_at=now(),
        created_by=actor_id,
        revoked_at=None,
    )
    db.add(entry)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=OPTOUT_RECORDED,
        entity_id=entry.id,
        payload={
            "recipient": recipient,
            "reason": text,
            "contact_id": contact.id if contact is not None else None,
            "do_not_contact": True,
        },
        actor_id=actor_id,
    )
    return entry


def revoke_suppression(
    db: Session, *, workspace_id: str, suppression_id: str, actor_id: str
) -> SuppressionEntry:
    entry = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.id == suppression_id,
            SuppressionEntry.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise LookupError("suppression not found")
    if entry.revoked_at is None:
        entry.revoked_at = now()
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=SUPPRESSION_REVOKED,
            entity_id=entry.id,
            payload={"recipient": entry.recipient, "reason": entry.reason},
            actor_id=actor_id,
        )
    return entry


def active_suppression(db: Session, workspace_id: str, recipient: str) -> dict | None:
    """Return the blocking reason for a recipient, or None when not suppressed.

    An explicit, recorded suppression reason wins over the generic contact flag
    so the gate can report *why* a recipient is blocked. The flag is a fallback
    for a do-not-contact set outside this module.
    """
    email = normalise_email(recipient)
    candidates = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.revoked_at.is_(None),
        )
    ).scalars().all()
    for entry in candidates:
        if not _is_active(entry):
            continue
        if entry.scope == "email" and entry.recipient == email:
            return {
                "reason": entry.reason,
                "scope": entry.scope,
                "recipient": entry.recipient,
                "source": "suppression",
                "suppression_id": entry.id,
            }
        if entry.scope == "domain" and email.endswith("@" + entry.recipient):
            return {
                "reason": entry.reason,
                "scope": entry.scope,
                "recipient": entry.recipient,
                "source": "suppression",
                "suppression_id": entry.id,
            }

    contact = db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.email == email
        )
    ).scalar_one_or_none()
    if contact is not None and contact.do_not_contact:
        return {
            "reason": "contact is flagged do_not_contact",
            "scope": "email",
            "recipient": email,
            "source": "contact",
        }
    return None


def evaluate_presend_gate(
    db: Session,
    *,
    workspace_id: str,
    draft_id: str,
    actor_id: str | None = None,
    require_approval: bool = True,
) -> dict:
    """Decide whether a draft passes the local safety gate.

    A pass is only a decision: there is no send step after it in this build.
    """
    draft = db.execute(
        select(OutreachDraft).where(
            OutreachDraft.id == draft_id,
            OutreachDraft.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if draft is None:
        raise LookupError("outreach draft not found")

    contact = db.get(Contact, draft.contact_id)
    recipient = contact.email if contact is not None and contact.workspace_id == workspace_id else None
    footer = compliance_footer(db, workspace_id)
    failures: list[str] = []

    fields_ok = bool(draft.subject and draft.subject.strip()) and bool(
        draft.body and draft.body.strip()
    )
    if not (draft.subject and draft.subject.strip()):
        failures.append("subject is required")
    if not (draft.body and draft.body.strip()):
        failures.append("body is required")
    if footer not in (draft.body or ""):
        failures.append("compliance footer is missing")
        fields_ok = False
    if not recipient:
        failures.append("recipient email is required")
        fields_ok = False

    approval_ok = draft.status == "approved"
    if require_approval and not approval_ok:
        failures.append("draft is not approved")

    suppression = active_suppression(db, workspace_id, recipient) if recipient else None
    if suppression is not None:
        failures.append(f"recipient is suppressed: {suppression['reason']}")

    allowed = not failures
    if not allowed:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=GATE_REJECTED,
            entity_id=draft.id,
            payload={
                "failures": failures,
                "suppression_reason": suppression["reason"] if suppression else None,
                "require_approval": require_approval,
            },
            actor_id=actor_id,
        )
    return {
        "draft_id": draft.id,
        "allowed": allowed,
        "failures": failures,
        "approval_ok": approval_ok,
        "required_fields_ok": fields_ok,
        "suppression_reason": suppression["reason"] if suppression else None,
        "delivery": "blocked_no_delivery_adapter",
        "notes": NO_DELIVERY_NOTE,
    }


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class PolicyOut(BaseModel):
    workspace_id: str
    compliance_footer: str
    updated_by: str | None
    updated_at: datetime | None
    notes: str = NO_DELIVERY_NOTE


class PolicyUpdate(BaseModel):
    compliance_footer: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("compliance_footer")
    @classmethod
    def footer_valid(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 1000:
            raise ValueError("compliance footer must be between 1 and 1000 characters")
        return text


class OptOutCreate(BaseModel):
    email: str
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class SuppressionCreate(BaseModel):
    recipient: str
    scope: Literal["email", "domain"] = "email"
    reason: str
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_valid(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 200:
            raise ValueError("reason must be between 1 and 200 characters")
        return text


class SuppressionOut(BaseModel):
    id: str
    recipient: str
    scope: str
    reason: str
    expires_at: datetime | None
    created_at: datetime
    created_by: str | None
    active: bool


class GateDecisionOut(BaseModel):
    draft_id: str
    allowed: bool
    failures: list[str]
    approval_ok: bool
    required_fields_ok: bool
    suppression_reason: str | None
    delivery: str
    notes: str = NO_DELIVERY_NOTE


class AuditResultOut(BaseModel):
    audited: bool
    recipient: str
    reason: str
    notes: str = NO_DELIVERY_NOTE


def _suppression_out(entry: SuppressionEntry) -> SuppressionOut:
    return SuppressionOut(
        id=entry.id,
        recipient=entry.recipient,
        scope=entry.scope,
        reason=entry.reason,
        expires_at=entry.expires_at,
        created_at=entry.created_at,
        created_by=entry.created_by,
        active=_is_active(entry),
    )


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("/policy", response_model=PolicyOut)
def get_policy(
    workspace_id: str,
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> PolicyOut:
    verify_workspace(principal, workspace_id)
    policy = db.execute(
        select(WorkspaceOutreachPolicy).where(
            WorkspaceOutreachPolicy.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    return PolicyOut(
        workspace_id=workspace_id,
        compliance_footer=policy.compliance_footer if policy else DEFAULT_COMPLIANCE_FOOTER,
        updated_by=policy.updated_by if policy else None,
        updated_at=policy.updated_at if policy else None,
    )


@router.put("/policy", response_model=PolicyOut)
def update_policy(
    workspace_id: str,
    body: PolicyUpdate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> PolicyOut:
    verify_workspace(principal, workspace_id)
    policy = set_compliance_footer(
        db, workspace_id=workspace_id, footer=body.compliance_footer,
        actor_id=principal.user.id,
    )
    db.commit()
    return PolicyOut(
        workspace_id=workspace_id,
        compliance_footer=policy.compliance_footer,
        updated_by=policy.updated_by,
        updated_at=policy.updated_at,
    )


@router.post("/opt-outs", response_model=AuditResultOut, status_code=status.HTTP_201_CREATED)
def opt_out(
    workspace_id: str,
    body: OptOutCreate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> AuditResultOut:
    verify_workspace(principal, workspace_id)
    try:
        entry = record_optout(
            db, workspace_id=workspace_id, email=body.email,
            actor_id=principal.user.id, reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return AuditResultOut(recipient=entry.recipient, reason=entry.reason, audited=True)


@router.get("/opt-outs", response_model=list[SuppressionOut])
def list_opt_outs(
    workspace_id: str,
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> list[SuppressionOut]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SuppressionEntry)
        .where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.reason == OPT_OUT_REASON,
        )
        .order_by(SuppressionEntry.created_at.desc(), SuppressionEntry.id)
    ).scalars().all()
    return [_suppression_out(row) for row in rows]


@router.post("/suppressions", response_model=SuppressionOut, status_code=status.HTTP_201_CREATED)
def suppress_recipient(
    workspace_id: str,
    body: SuppressionCreate,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> SuppressionOut:
    verify_workspace(principal, workspace_id)
    try:
        entry = add_suppression(
            db,
            workspace_id=workspace_id,
            recipient=body.recipient,
            scope=body.scope,
            reason=body.reason,
            actor_id=principal.user.id,
            expires_at=body.expires_at,
        )
    except SuppressionDuplicate as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _suppression_out(entry)


@router.get("/suppressions", response_model=list[SuppressionOut])
def list_suppressions(
    workspace_id: str,
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> list[SuppressionOut]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SuppressionEntry)
        .where(SuppressionEntry.workspace_id == workspace_id)
        .order_by(SuppressionEntry.created_at.desc(), SuppressionEntry.id)
    ).scalars().all()
    return [_suppression_out(row) for row in rows]


@router.post("/suppressions/{suppression_id}/revoke", response_model=SuppressionOut)
def revoke(
    workspace_id: str,
    suppression_id: str,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> SuppressionOut:
    verify_workspace(principal, workspace_id)
    try:
        entry = revoke_suppression(
            db, workspace_id=workspace_id, suppression_id=suppression_id,
            actor_id=principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return _suppression_out(entry)


@router.post("/drafts/{draft_id}/gate-check", response_model=GateDecisionOut)
def presend_check(
    workspace_id: str,
    draft_id: str,
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> GateDecisionOut:
    verify_workspace(principal, workspace_id)
    try:
        decision = evaluate_presend_gate(
            db, workspace_id=workspace_id, draft_id=draft_id,
            actor_id=principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return GateDecisionOut(**decision)
