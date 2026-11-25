"""Outbound adapter architecture — local mock/sandbox implementations only.

This module is the single seam through which an external provider *could* be
called. In this build every adapter is a deterministic local stub: it records an
AdapterCall row, publishes an audit event and returns a response that explicitly
states nothing was delivered. There is no network client, no credential use and
no fabricated provider output.

Status values are deliberately distinct and never conflated:
- ``not_configured``: no integration setting recorded for this workspace.
- ``configured``: a non-sensitive setting was recorded; the adapter itself is
  still a local mock and has NOT contacted the provider.
- ``disabled``: the integration was disabled by a workspace manager.
- ``blocked``: the requested provider/kind has no local adapter at all.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import EVENT_READ, WORKSPACE_MANAGE
from .integrations import (
    NOT_CONFIGURED_NOTE,
    RECORDED_NOTE,
    Integration,
    SUPPORTED_PROVIDERS,
)

ADAPTER_INVOKED = "adapter.invoked"
ADAPTER_REJECTED = "adapter.rejected"
MESSAGE_RECORDED = "message.recorded"
register_event_types(ADAPTER_INVOKED, ADAPTER_REJECTED, MESSAGE_RECORDED)

ADAPTER_NOTES = (
    "All adapters are local mocks in this build. No outbound network call is "
    "made, no credential is used, and no external delivery is claimed."
)

PROVIDER_KINDS = {
    "gmail": "email",
    "outlook": "email",
    "whatsapp": "whatsapp",
    "sms": "sms",
    "openai": "ai",
    "local_llm": "ai",
    "meilisearch": "search",
    "growthbook": "flags",
    "chatwoot": "support",
    "novu": "notification",
    "plane": "project_management",
}

# Providers that exist in the source ecosystem but have NO local adapter. They
# are reported as blocked rather than counted as supported capabilities. This
# keeps the advertised provider count honest (NV-025).
BLOCKED_PROVIDERS = {
    "sendgrid": "email",
    "mailgun": "email",
    "twilio": "sms",
    "pushpad": "push",
    "firebase": "push",
    "slack": "chat",
    "telegram": "chat",
    "discord": "chat",
    "pagerduty": "tool",
    "opsgenie": "tool",
}

CAPABILITY_STATES = ("configured", "disabled", "not_configured", "blocked")

# Mautic/Plane context verbs (PL-043, MT-072). These name the operation the
# caller asks the *local* adapter to record; none of them performs an outbound
# call or embeds the external product's source.
CRUD_OPERATIONS = frozenset({"get", "getlist", "create", "edit", "delete"})
VALID_OPERATIONS = frozenset(
    {"send", "draft", "generate", "search", "evaluate", "notify", "test"}
) | CRUD_OPERATIONS

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/adapters",
    tags=["adapters"],
)


# --------------------------------------------------------------------------
# Table
# --------------------------------------------------------------------------


class AdapterCall(Base):
    __tablename__ = "adapter_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    request_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    note: Mapped[str] = mapped_column(String(300), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class MessageRecord(Base):
    """A per-channel message ledger row (NV-085).

    Local messages are recorded for audit and in-app delivery only. A local
    mock send never sets ``delivered`` to true and never claims provider
    acceptance.
    """

    __tablename__ = "message_records"
    __table_args__ = (
        Index("ix_message_records_lookup", "workspace_id", "channel", "subscriber_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    subscriber_id: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(60), nullable=False, default="local")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="recorded")
    delivered: Mapped[bool] = mapped_column(default=False, nullable=False)
    note: Mapped[str] = mapped_column(String(300), nullable=False, default="local message record; no external delivery claimed")
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Local mock implementations
# --------------------------------------------------------------------------


def _mock_response(kind: str, provider: str, request: dict) -> dict:
    """Deterministic local response. Never marks an external action as delivered."""
    base = {
        "provider": provider,
        "kind": kind,
        "mode": "local_mock",
        "delivered": False,
    }
    if kind in {"email", "sms", "whatsapp", "notification", "support"}:
        base.update(
            {
                "message_id": f"mock-{provider}-{new_id()[:8]}",
                "recipient": request.get("to") or request.get("recipient"),
                "subject": str(request.get("subject", ""))[:200],
            }
        )
    elif kind == "ai":
        base.update({"output": None, "tokens": 0})
    elif kind == "search":
        base.update({"results": [], "total": 0})
    elif kind == "flags":
        base.update({"variation": None})
    elif kind == "project_management":
        base.update(
            {
                "context": request.get("context"),
                "entity": request.get("entity"),
                "entity_id": request.get("entity_id"),
                "external": False,
            }
        )
    base["note"] = "local mock only; nothing was sent externally and no output was fabricated"
    return base


def _integration_status(db: Session, workspace_id: str, provider: str) -> str:
    row = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == provider,
        )
    ).scalar_one_or_none()
    if row is None:
        return "not_configured"
    if row.status == "disabled":
        return "disabled"
    if row.status == "disconnected":
        return "not_configured"
    return "configured"


def provider_capabilities(db: Session, workspace_id: str) -> dict:
    """One honest capability view with four distinct states and exact counts."""
    rows = db.execute(
        select(Integration).where(Integration.workspace_id == workspace_id)
    ).scalars().all()
    by_provider = {row.provider: row for row in rows}
    entries = []
    for provider, display_name in SUPPORTED_PROVIDERS.items():
        row = by_provider.get(provider)
        state = _integration_status(db, workspace_id, provider)
        entries.append(
            {
                "provider": provider,
                "display_name": display_name,
                "kind": PROVIDER_KINDS.get(provider, "unknown"),
                "status": state,
                "local_mock_available": provider in PROVIDER_KINDS,
                "notes": RECORDED_NOTE if state == "configured" else (
                    "integration was disabled by a workspace manager" if state == "disabled"
                    else NOT_CONFIGURED_NOTE
                ),
            }
        )
    for provider, kind in BLOCKED_PROVIDERS.items():
        entries.append(
            {
                "provider": provider,
                "display_name": provider,
                "kind": kind,
                "status": "blocked",
                "local_mock_available": False,
                "notes": "known provider with no local adapter; no outbound call is possible",
            }
        )
    counts = {state: 0 for state in CAPABILITY_STATES}
    for entry in entries:
        counts[entry["status"]] += 1
    return {
        "workspace_id": workspace_id,
        "providers": entries,
        "states": list(CAPABILITY_STATES),
        "counts": counts,
        "configurable_provider_count": len(SUPPORTED_PROVIDERS),
        "blocked_provider_count": len(BLOCKED_PROVIDERS),
        "local_adapter_count": len(PROVIDER_KINDS),
        "notes": ADAPTER_NOTES,
    }


def invoke_adapter(
    db: Session,
    *,
    workspace_id: str,
    provider: str,
    operation: str,
    request: dict,
    actor_id: str,
    correlation_id: str | None = None,
) -> dict:
    """Run a local mock adapter if the workspace has an active configuration.

    Returns a plain dict so both tests and the API can consume the same result.
    A rejected call is still recorded in AdapterCall and the audit log.
    """
    provider = provider.strip().lower()
    kind = PROVIDER_KINDS.get(provider)
    request_summary = {
        key: (str(value)[:120] if not isinstance(value, (int, float, bool)) else value)
        for key, value in request.items()
    }
    if kind is None:
        status_value = "blocked"
        note = "no local adapter exists for this provider"
        response = {"provider": provider, "mode": "blocked", "delivered": False, "note": note}
    else:
        integration_status = _integration_status(db, workspace_id, provider)
        if integration_status != "configured":
            status_value = "rejected"
            note = f"adapter {integration_status}; no outbound call is made"
            response = {
                "provider": provider,
                "kind": kind,
                "mode": "blocked",
                "delivered": False,
                "status": integration_status,
                "note": note,
            }
        else:
            status_value = "recorded"
            note = "local mock invoked; nothing was sent externally"
            response = _mock_response(kind, provider, request)

    call = AdapterCall(
        id=new_id(),
        workspace_id=workspace_id,
        provider=provider,
        kind=kind or "unknown",
        operation=operation,
        status=status_value,
        request_summary=request_summary,
        response_summary=response,
        note=note,
        correlation_id=correlation_id or new_id(),
        actor_id=actor_id,
        created_at=now(),
    )
    db.add(call)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=ADAPTER_INVOKED if status_value == "recorded" else ADAPTER_REJECTED,
        entity_id=call.id,
        payload={
            "provider": provider,
            "kind": call.kind,
            "operation": operation,
            "status": status_value,
            "delivered": False,
        },
        correlation_id=call.correlation_id,
        actor_id=actor_id,
    )
    return {
        "call_id": call.id,
        "provider": provider,
        "kind": call.kind,
        "operation": operation,
        "status": status_value,
        "response": response,
        "notes": ADAPTER_NOTES,
    }


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class AdapterInvokeRequest(BaseModel):
    operation: str = "test"
    request: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("operation")
    @classmethod
    def operation_allowed(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_OPERATIONS:
            raise ValueError("unsupported adapter operation")
        return value


class AdapterCapability(BaseModel):
    provider: str
    display_name: str
    kind: str
    status: str
    local_mock_available: bool


class AdapterCapabilityList(BaseModel):
    workspace_id: str
    providers: list[AdapterCapability]
    notes: str = ADAPTER_NOTES


class AdapterCallOut(BaseModel):
    id: str
    workspace_id: str
    provider: str
    kind: str
    operation: str
    status: str
    request_summary: dict
    response_summary: dict
    note: str
    correlation_id: str
    actor_id: str
    created_at: object


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=AdapterCapabilityList)
def list_adapters(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> AdapterCapabilityList:
    verify_workspace(principal, workspace_id)
    providers = [
        AdapterCapability(
            provider=provider,
            display_name=display_name,
            kind=PROVIDER_KINDS.get(provider, "unknown"),
            status=_integration_status(db, workspace_id, provider),
            local_mock_available=provider in PROVIDER_KINDS,
        )
        for provider, display_name in SUPPORTED_PROVIDERS.items()
    ]
    return AdapterCapabilityList(workspace_id=workspace_id, providers=providers)


@router.get("/calls", response_model=list[AdapterCallOut])
def list_calls(
    workspace_id: str,
    provider: str | None = None,
    limit: int = 100,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[AdapterCall]:
    verify_workspace(principal, workspace_id)
    query = select(AdapterCall).where(AdapterCall.workspace_id == workspace_id)
    if provider:
        query = query.where(AdapterCall.provider == provider.strip().lower())
    return db.execute(
        query.order_by(AdapterCall.created_at.desc()).limit(limit)
    ).scalars().all()


@router.post("/{provider}/invoke")
def invoke(
    workspace_id: str,
    provider: str,
    body: AdapterInvokeRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    result = invoke_adapter(
        db,
        workspace_id=workspace_id,
        provider=provider,
        operation=body.operation,
        request=body.request,
        actor_id=principal.user.id,
    )
    db.commit()
    return result


# --------------------------------------------------------------------------
# NV-025: explicit four-state capability view
# --------------------------------------------------------------------------


class CapabilityStateOut(BaseModel):
    workspace_id: str
    providers: list[dict]
    states: list[str]
    counts: dict[str, int]
    configurable_provider_count: int
    blocked_provider_count: int
    local_adapter_count: int
    notes: str = ADAPTER_NOTES


@router.get("/capabilities", response_model=CapabilityStateOut)
def capabilities(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> CapabilityStateOut:
    verify_workspace(principal, workspace_id)
    return CapabilityStateOut(**provider_capabilities(db, workspace_id))


# --------------------------------------------------------------------------
# NV-085: per-channel message records API
# --------------------------------------------------------------------------


class MessageRecordCreate(BaseModel):
    channel: str
    subscriber_id: str
    transaction_id: str
    provider: str = "local"
    content: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("channel")
    @classmethod
    def channel_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or len(value) > 30:
            raise ValueError("channel must be a non-empty string")
        return value

    @field_validator("subscriber_id", "transaction_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be blank")
        return value[:200]


class MessageRecordOut(BaseModel):
    id: str
    workspace_id: str
    channel: str
    subscriber_id: str
    transaction_id: str
    provider: str
    status: str
    delivered: bool
    note: str
    correlation_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.post("/messages/record", response_model=MessageRecordOut, status_code=status.HTTP_201_CREATED)
def record_message(
    workspace_id: str,
    body: MessageRecordCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> MessageRecord:
    verify_workspace(principal, workspace_id)
    duplicate = db.execute(
        select(MessageRecord).where(
            MessageRecord.workspace_id == workspace_id,
            MessageRecord.transaction_id == body.transaction_id,
            MessageRecord.channel == body.channel,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="transaction_id already recorded for this channel")
    row = MessageRecord(
        id=new_id(), workspace_id=workspace_id, channel=body.channel,
        subscriber_id=body.subscriber_id, transaction_id=body.transaction_id,
        provider=body.provider, status="recorded", delivered=False,
        note="local message record; no external delivery claimed",
        correlation_id=new_id(), created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=MESSAGE_RECORDED, entity_id=row.id,
        payload={"channel": row.channel, "transaction_id": row.transaction_id, "delivered": False},
        correlation_id=row.correlation_id, actor_id=principal.user.id,
    )
    db.commit()
    return row


@router.get("/messages", response_model=list[MessageRecordOut])
def list_messages(
    workspace_id: str,
    channel: str | None = None,
    subscriber_id: str | None = None,
    transaction_id: str | None = None,
    limit: int = 100,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[MessageRecord]:
    verify_workspace(principal, workspace_id)
    query = select(MessageRecord).where(MessageRecord.workspace_id == workspace_id)
    if channel:
        query = query.where(MessageRecord.channel == channel.strip().lower())
    if subscriber_id:
        query = query.where(MessageRecord.subscriber_id == subscriber_id)
    if transaction_id:
        query = query.where(MessageRecord.transaction_id == transaction_id)
    return db.execute(
        query.order_by(MessageRecord.created_at.desc()).limit(limit)
    ).scalars().all()


@router.get("/messages/{message_id}", response_model=MessageRecordOut)
def get_message(
    workspace_id: str,
    message_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> MessageRecord:
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(MessageRecord).where(
            MessageRecord.id == message_id, MessageRecord.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="message record not found")
    return row


@router.delete("/messages/{message_id}")
def delete_message(
    workspace_id: str,
    message_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(MessageRecord).where(
            MessageRecord.id == message_id, MessageRecord.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="message record not found")
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=MESSAGE_RECORDED, entity_id=row.id,
        payload={"action": "deleted", "transaction_id": row.transaction_id},
        correlation_id=row.correlation_id, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "message_id": row.id}
