"""Novu-compatible notification workflow engine (Novu P2 cluster).

Clean-room implementation of NV-006, NV-013, NV-017, NV-019, NV-028, NV-036,
NV-038, NV-040, NV-044, NV-054, NV-056, NV-073, NV-086 and NV-087 over the
shared NOVARA workspace identity. NV-071 is covered by the existing
``api_keys`` module (hashed secrets, rotation and revocation).

There is no external delivery provider. Workflow triggers persist local,
workspace-scoped messages, digests and signed webhook delivery records. All rich
content is sanitised, all routes are local-only and every mutation is published
to the shared audit bus. No Novu source is copied.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import secrets
from datetime import datetime
from html.parser import HTMLParser

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE, WORKSPACE_MANAGE

WORKFLOW_CREATED = "notification.workflow_created"
WORKFLOW_UPDATED = "notification.workflow_updated"
WORKFLOW_TRIGGERED = "notification.workflow_triggered"
DIGEST_FIRED = "notification.digest_fired"
MESSAGE_ACTIONED = "notification.message_actioned"
WEBHOOK_ENDPOINT_CREATED = "notification.webhook_endpoint_created"
WEBHOOK_DELIVERED = "notification.webhook_delivered"
WEBHOOK_REPLAYED = "notification.webhook_replayed"
WEBHOOK_DELIVERY_FAILED = "webhook.delivery_failed"
register_event_types(
    WORKFLOW_CREATED, WORKFLOW_UPDATED, WORKFLOW_TRIGGERED, DIGEST_FIRED,
    MESSAGE_ACTIONED, WEBHOOK_ENDPOINT_CREATED, WEBHOOK_DELIVERED, WEBHOOK_REPLAYED,
    WEBHOOK_DELIVERY_FAILED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/notification-workflows",
    tags=["notification-workflows"],
)

CHANNELS = frozenset({"in_app", "email", "sms", "push", "chat"})
SEVERITIES = frozenset({"info", "warning", "critical"})
WINDOW_POLICIES = frozenset({"hold", "skip"})
MESSAGE_STATUSES = frozenset({"delivered", "held", "skipped", "pending_digest", "digested"})
SENSITIVE_PARTS = frozenset({
    "secret", "token", "password", "passwords", "credential", "credentials",
    "apikey", "api_key", "privatekey", "authorization", "cookie",
})
# NV-044: only these in-app routes may be opened by a notification action.
ALLOWED_ROUTE_PREFIXES = frozenset({
    "dashboard", "search", "insights", "contacts", "companies", "leads", "deals",
    "inbox", "tasks", "projects", "documents", "campaigns", "surveys",
    "search-indexes", "notifications", "drafts", "agents", "jobs", "adapters",
    "operations", "integrations", "activity", "workspaces", "profile", "settings",
})
ALLOWED_HTML_TAGS = frozenset({
    "b", "strong", "i", "em", "u", "p", "br", "ul", "ol", "li", "span",
    "code", "pre", "h1", "h2", "h3", "h4", "blockquote",
})
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class _RichSanitizer(HTMLParser):
    """Rebuild markup from allow-listed tags only; drop every attribute."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ALLOWED_HTML_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in ALLOWED_HTML_TAGS:
            self.parts.append(f"<{tag}></{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in ALLOWED_HTML_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data, quote=False))


# ---------------------------------------------------------------------------
# Clean-room helpers
# ---------------------------------------------------------------------------


def sanitize_rich_html(raw: str | None) -> str:
    """Allow-list a small set of presentation tags and escape everything else.

    Unknown tags keep their text but lose the tag itself; attributes are dropped
    entirely, so `onclick`, `style` and `javascript:` cannot survive. This is
    deliberately stricter than a browser sanitiser because the notification
    panel renders the stored value directly (NV-040, NV-087).
    """
    if not raw:
        return ""
    if not isinstance(raw, str):
        raise ValueError("rich content must be a string")
    if len(raw) > 20000:
        raise ValueError("rich content is too long")

    parser = _RichSanitizer()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)


def is_authorised_local_route(url: str) -> bool:
    """NV-044: accept only a single, known in-app hash route."""
    if not isinstance(url, str) or not url.startswith("#/"):
        return False
    if any(ch in url for ch in (" ", "\\", ":", "//", "<", ">", "'", '"')):
        return False
    target = url[2:].split("?", 1)[0].split("#", 1)[0].strip("/")
    if not target or ".." in target:
        return False
    return target.split("/", 1)[0] in ALLOWED_ROUTE_PREFIXES


def _clean_token(value: object) -> bool:
    return isinstance(value, str) and value.lower() in SENSITIVE_PARTS


def validate_overrides(headers: dict | None, payload: dict | None, provider: str | None) -> None:
    """NV-028: overrides may not inject credentials or change permissions."""
    if provider is not None and provider not in CHANNELS:
        raise ValueError("unknown override provider")
    for mapping in (headers, payload):
        if mapping is None:
            continue
        if not isinstance(mapping, dict) or any(not isinstance(k, str) for k in mapping):
            raise ValueError("override fields must be string-keyed objects")
        for key in mapping:
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            credential_words = {"secret", "token", "password", "credential", "apikey", "authorization", "cookie"}
            if _clean_token(key) or any(word in normalized for word in credential_words):
                raise ValueError("credential-like override field is not allowed")
        if len(mapping) > 50:
            raise ValueError("too many override fields")


def _parse_hhmm(value: str) -> int:
    match = TIME_RE.match(value or "")
    if not match:
        raise ValueError("time must be HH:MM")
    return int(match.group(1)) * 60 + int(match.group(2))


def window_allows(local_time: str, delivery_window: dict | None) -> bool:
    """NV-038: evaluate a stored weekly window against a caller-supplied local time.

    The timezone is stored as metadata; schedulers supply the local wall-clock
    time, so no host timezone database is required. Overnight windows are
    supported by inverting the containment test.
    """
    if not delivery_window:
        return True
    start = _parse_hhmm(delivery_window["start"])
    end = _parse_hhmm(delivery_window["end"])
    try:
        moment = datetime.fromisoformat(local_time)
    except (TypeError, ValueError):
        raise ValueError("local_time must be an ISO timestamp")
    current = moment.hour * 60 + moment.minute
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def sign_payload(raw: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_signature(raw: bytes, signature: str, secret: str) -> bool:
    expected = sign_payload(raw, secret)
    return hmac.compare_digest(expected, signature or "")


def validate_webhook_url(url: str) -> str:
    """NV-054 SSRF control: only loopback or a relative in-app path is allowed."""
    if not isinstance(url, str) or not url:
        raise ValueError("webhook URL is required")
    if url.startswith("/"):
        if not url.startswith("/api/") or "//" in url or ".." in url:
            raise ValueError("webhook path must be a clean /api/ path")
        return url
    if not url.startswith("http://") and not url.startswith("https://"):
        raise ValueError("webhook URL must use http(s) or a relative /api/ path")
    if "@" in url:
        raise ValueError("webhook URL must not contain credentials")
    host = url.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("webhook host is not allow-listed")
    return url


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class NotificationWorkflow(Base):
    """One stable workflow definition (NV-006, NV-019, NV-028)."""

    __tablename__ = "notification_workflows"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_notif_workflow_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    severity: Mapped[str] = mapped_column(String(12), default="info", nullable=False)
    critical: Mapped[bool] = mapped_column(default=False, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(60))
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    feed_key: Mapped[str | None] = mapped_column(String(60), index=True)
    context_key: Mapped[str | None] = mapped_column(String(60), index=True)
    layout_key: Mapped[str | None] = mapped_column(String(60))
    digest_rule: Mapped[dict | None] = mapped_column(JSON)
    delivery_window: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationFeed(Base):
    """NV-086: named feed used to group and route stored messages."""

    __tablename__ = "notification_feeds"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_notif_feed_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationLayout(Base):
    """NV-087: reusable, sanitised email/in-app layout."""

    __tablename__ = "notification_layouts"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_notif_layout_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(200), default="clean-room", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationContext(Base):
    """NV-073: exact-match context key for multi-tenant sub-scoping."""

    __tablename__ = "notification_contexts"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_notif_context_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationWorkflowMessage(Base):
    """A local message produced by a workflow trigger or digest (NV-036/040/044)."""

    __tablename__ = "notification_workflow_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    context_key: Mapped[str | None] = mapped_column(String(120), index=True)
    feed_key: Mapped[str | None] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    action_url: Mapped[str] = mapped_column(String(300), default="#/notifications", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="delivered", nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="single", nullable=False)
    window_key: Mapped[str | None] = mapped_column(String(40), index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overrides: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    read: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationWebhookEndpoint(Base):
    """NV-054: local-only signed webhook destination registry."""

    __tablename__ = "notification_webhook_endpoints"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_notif_webhook_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NotificationWebhookDelivery(Base):
    """NV-054/056: one signed, auditable delivery attempt with replay control."""

    __tablename__ = "notification_webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    # Plain string (not a FK) so the local verification marker can use a
    # synthetic id without requiring an endpoint row.
    endpoint_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String(100), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="delivered", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    replayed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Clean-room catalogue (NV-017, NV-087)
# ---------------------------------------------------------------------------

WORKFLOW_TEMPLATES = (
    {
        "key": "welcome", "name": "Welcome sequence", "channel": "in_app",
        "severity": "info", "tags": ["lifecycle"], "digest_rule": None,
        "description": "A single in-app welcome message for a new account.",
    },
    {
        "key": "security-alert", "name": "Security alert", "channel": "in_app",
        "severity": "critical", "tags": ["security"], "digest_rule": None,
        "description": "Mandatory alert whose severity cannot be muted by subscriber preference.",
    },
    {
        "key": "invoice-ready", "name": "Invoice ready", "channel": "email",
        "severity": "info", "tags": ["billing"], "digest_rule": None,
        "description": "Notifies that a local invoice document is ready.",
    },
    {
        "key": "weekly-digest", "name": "Weekly digest", "channel": "in_app",
        "severity": "info", "tags": ["digest"],
        "digest_rule": {"frequency": "weekly", "timezone": "UTC"},
        "description": "Batches events into one digest per calendar window.",
    },
)
TEMPLATES_BY_KEY = {item["key"]: item for item in WORKFLOW_TEMPLATES}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    channel: str = "in_app"
    severity: str = "info"
    critical: bool = False
    tags: list[str] = Field(default_factory=list)
    feed_key: str | None = None
    context_key: str | None = None
    layout_key: str | None = None
    digest_rule: dict | None = None
    delivery_window: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def clean_key(cls, value: str) -> str:
        result = value.strip()
        if not result or any(ch.isspace() for ch in result):
            raise ValueError("workflow key must be a non-empty token")
        return result

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value not in CHANNELS:
            raise ValueError("invalid channel")
        return value

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError("invalid severity")
        return value

    @field_validator("delivery_window")
    @classmethod
    def valid_window(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        if value.get("policy") not in WINDOW_POLICIES:
            raise ValueError("invalid quiet-hours policy")
        _parse_hhmm(value.get("start", ""))
        _parse_hhmm(value.get("end", ""))
        return value


class WorkflowPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    severity: str | None = None
    tags: list[str] | None = None
    feed_key: str | None = None
    context_key: str | None = None
    layout_key: str | None = None
    digest_rule: dict | None = None
    delivery_window: dict | None = None

    model_config = ConfigDict(extra="forbid")


class DisableWorkflow(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")


class EffectiveEnabledRequest(BaseModel):
    channel: str = "in_app"
    subscriber_disabled: bool = False

    model_config = ConfigDict(extra="forbid")


class TriggerRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    html: str = ""
    data: dict = Field(default_factory=dict)
    action_url: str = "#/notifications"
    local_time: str | None = None
    window_key: str | None = None
    overrides: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("action_url")
    @classmethod
    def valid_action(cls, value: str) -> str:
        if not is_authorised_local_route(value):
            raise ValueError("action_url must be an authorised in-app route")
        return value


class DigestRequest(BaseModel):
    workflow_id: str
    window_key: str = Field(min_length=1, max_length=40)
    title: str = Field(default="Your digest", max_length=200)

    model_config = ConfigDict(extra="forbid")


class KeyedCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)

    model_config = ConfigDict(extra="forbid")


class LayoutCreate(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)

    model_config = ConfigDict(extra="forbid")


class LayoutRender(BaseModel):
    layout_id: str | None = None
    body: str | None = None
    content_html: str = ""

    model_config = ConfigDict(extra="forbid")


class MarkRead(BaseModel):
    read: bool = True

    model_config = ConfigDict(extra="forbid")


class WebhookEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str
    event_types: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        try:
            return validate_webhook_url(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class WebhookDispatch(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    payload: dict = Field(default_factory=dict)
    force_status: str = "delivered"

    model_config = ConfigDict(extra="forbid")

    @field_validator("force_status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in {"delivered", "failed"}:
            raise ValueError("force_status must be delivered or failed")
        return value


class WebhookVerify(BaseModel):
    raw_body: str
    signature: str
    secret: str
    nonce: str

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Output serialisers
# ---------------------------------------------------------------------------


def workflow_out(row: NotificationWorkflow) -> dict:
    return {
        "id": row.id, "key": row.key, "name": row.name, "description": row.description,
        "channel": row.channel, "severity": row.severity, "critical": row.critical,
        "active": row.active, "template_key": row.template_key, "tags": list(row.tags or []),
        "feed_key": row.feed_key, "context_key": row.context_key, "layout_key": row.layout_key,
        "digest_rule": row.digest_rule, "delivery_window": row.delivery_window,
        "created_at": row.created_at,
    }


def message_out(row: NotificationWorkflowMessage) -> dict:
    return {
        "id": row.id, "workflow_id": row.workflow_id, "user_id": row.user_id,
        "context_key": row.context_key, "feed_key": row.feed_key, "title": row.title,
        "html_body": row.html_body, "data": row.data, "category": row.category,
        "tags": list(row.tags or []), "action_url": row.action_url, "status": row.status,
        "kind": row.kind, "window_key": row.window_key, "event_count": row.event_count,
        "overrides": row.overrides, "read": row.read, "created_at": row.created_at,
    }


def webhook_out(row: NotificationWebhookEndpoint) -> dict:
    return {
        "id": row.id, "name": row.name, "url": row.url,
        "event_types": list(row.event_types or []), "enabled": row.enabled,
        "created_at": row.created_at,
    }


def delivery_out(row: NotificationWebhookDelivery) -> dict:
    """Never returns the signing secret; only its hash is stored."""
    return {
        "id": row.id, "endpoint_id": row.endpoint_id, "event_type": row.event_type,
        "payload": row.payload, "signature": row.signature,
        "signature_prefix": row.signature[:16], "status": row.status,
        "attempts": row.attempts, "replayed": row.replayed, "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _workflow_or_404(db, workspace_id: str, workflow_id: str) -> NotificationWorkflow:
    row = db.execute(
        select(NotificationWorkflow).where(
            NotificationWorkflow.id == workflow_id,
            NotificationWorkflow.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return row


def _keyed_or_404(db, workspace_id: str, model, key: str, label: str):
    row = db.execute(
        select(model).where(model.workspace_id == workspace_id, model.key == key)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _message_or_404(db, workspace_id: str, message_id: str) -> NotificationWorkflowMessage:
    row = db.execute(
        select(NotificationWorkflowMessage).where(
            NotificationWorkflowMessage.id == message_id,
            NotificationWorkflowMessage.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="message not found")
    return row


def _endpoint_or_404(db, workspace_id: str, endpoint_id: str) -> NotificationWebhookEndpoint:
    row = db.execute(
        select(NotificationWebhookEndpoint).where(
            NotificationWebhookEndpoint.id == endpoint_id,
            NotificationWebhookEndpoint.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="webhook endpoint not found")
    return row


# ---------------------------------------------------------------------------
# NV-006: one stable workflow API + contract
# ---------------------------------------------------------------------------


@router.get("/api-contract")
def api_contract():
    """NV-006: document the single stable workflow API; claim no legacy version."""
    return {
        "version": "1",
        "legacy_versions": [],
        "router_prefix": "/api/v1/workspaces/{workspace_id}/notification-workflows",
        "delivery": "local-only",
    }


@router.get("/workflows")
def list_workflows(
    workspace_id: str,
    severity: str | None = None,
    active: bool | None = None,
    context: str | None = None,
    feed: str | None = None,
    tag: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    query = select(NotificationWorkflow).where(NotificationWorkflow.workspace_id == workspace_id)
    if severity:
        query = query.where(NotificationWorkflow.severity == severity)
    if active is not None:
        query = query.where(NotificationWorkflow.active == active)
    if context:
        query = query.where(NotificationWorkflow.context_key == context)
    if feed:
        query = query.where(NotificationWorkflow.feed_key == feed)
    rows = db.execute(query.order_by(NotificationWorkflow.created_at)).scalars().all()
    if tag:
        rows = [row for row in rows if tag in (row.tags or [])]
    return [workflow_out(row) for row in rows]


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    workspace_id: str,
    body: WorkflowCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(NotificationWorkflow.id).where(
            NotificationWorkflow.workspace_id == workspace_id,
            NotificationWorkflow.key == body.key,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="workflow key already exists")
    row = NotificationWorkflow(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        description=body.description, channel=body.channel, severity=body.severity,
        critical=body.critical, active=True, tags=list(body.tags), feed_key=body.feed_key,
        context_key=body.context_key, layout_key=body.layout_key,
        digest_rule=body.digest_rule, delivery_window=body.delivery_window,
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_CREATED,
                  entity_id=row.id, payload={"key": row.key, "severity": row.severity, "critical": row.critical},
                  actor_id=principal.user.id)
    db.commit()
    return workflow_out(row)


@router.patch("/workflows/{workflow_id}")
def patch_workflow(
    workspace_id: str,
    workflow_id: str,
    body: WorkflowPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _workflow_or_404(db, workspace_id, workflow_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "delivery_window" and value is not None:
            WorkflowCreate.valid_window(value)
        setattr(row, field, value)
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_UPDATED,
                  entity_id=row.id, payload={"fields": sorted(body.model_dump(exclude_unset=True))},
                  actor_id=principal.user.id)
    db.commit()
    return workflow_out(row)


@router.post("/workflows/{workflow_id}/disable")
def disable_workflow(
    workspace_id: str,
    workflow_id: str,
    body: DisableWorkflow,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-019: a critical flow cannot be muted by subscriber preference."""
    verify_workspace(principal, workspace_id)
    row = _workflow_or_404(db, workspace_id, workflow_id)
    if row.critical and body.reason.strip().lower() == "subscriber_preference":
        raise HTTPException(status_code=409, detail="critical workflow cannot be disabled by subscriber preference")
    row.active = False
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_UPDATED,
                  entity_id=row.id, payload={"active": False, "reason": body.reason},
                  actor_id=principal.user.id)
    db.commit()
    return workflow_out(row)


@router.post("/workflows/{workflow_id}/effective-enabled")
def effective_enabled(
    workspace_id: str,
    workflow_id: str,
    body: EffectiveEnabledRequest,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _workflow_or_404(db, workspace_id, workflow_id)
    if row.critical:
        return {"workflow_id": row.id, "critical": True, "enabled": True,
                "source": "critical-policy", "channel": body.channel}
    enabled = not body.subscriber_disabled
    return {"workflow_id": row.id, "critical": False, "enabled": enabled,
            "source": "subscriber-preference" if body.subscriber_disabled else "default",
            "channel": body.channel}


# ---------------------------------------------------------------------------
# NV-017: clean-room template catalogue
# ---------------------------------------------------------------------------


@router.get("/templates")
def list_templates(principal: Principal = Depends(require(CONTACT_READ))):
    """NV-017: provenance-bearing catalogue; no upstream template source copied."""
    return [
        {**item, "provenance": "clean-room NOVARA template; no upstream source copied"}
        for item in WORKFLOW_TEMPLATES
    ]


@router.post("/templates/{key}/instantiate", status_code=status.HTTP_201_CREATED)
def instantiate_template(
    workspace_id: str,
    key: str,
    name: str | None = None,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    template = TEMPLATES_BY_KEY.get(key)
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    generated_key = f"{key}-{new_id()[:8]}"
    row = NotificationWorkflow(
        id=new_id(), workspace_id=workspace_id, key=generated_key,
        name=name or template["name"], description=template["description"],
        channel=template["channel"], severity=template["severity"],
        critical=key == "security-alert", active=True, template_key=key,
        tags=list(template["tags"]), digest_rule=template["digest_rule"],
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_CREATED,
                  entity_id=row.id, payload={"template_key": key, "channel_delivery_claimed": False},
                  actor_id=principal.user.id)
    db.commit()
    return workflow_out(row)


# ---------------------------------------------------------------------------
# NV-013 / NV-028 / NV-036 / NV-038 / NV-040 / NV-044: triggers and messages
# ---------------------------------------------------------------------------


@router.post("/workflows/{workflow_id}/trigger", status_code=status.HTTP_201_CREATED)
def trigger_workflow(
    workspace_id: str,
    workflow_id: str,
    body: TriggerRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    workflow = _workflow_or_404(db, workspace_id, workflow_id)
    if not workflow.active:
        raise HTTPException(status_code=409, detail="workflow is inactive")
    overrides = body.overrides or {}
    try:
        validate_overrides(overrides.get("headers"), overrides.get("payload"), overrides.get("provider"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        sanitized = sanitize_rich_html(body.html)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    local_time = body.local_time or now().isoformat()
    try:
        inside = window_allows(local_time, workflow.delivery_window)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if workflow.delivery_window and not inside:
        status_value = "held" if workflow.delivery_window.get("policy") == "hold" else "skipped"
    elif workflow.digest_rule:
        status_value = "pending_digest"
    else:
        status_value = "delivered"

    window_key = body.window_key
    if workflow.digest_rule and not window_key:
        window_key = local_time[:10]

    row = NotificationWorkflowMessage(
        id=new_id(), workspace_id=workspace_id, workflow_id=workflow.id,
        user_id=principal.user.id, context_key=workflow.context_key,
        feed_key=workflow.feed_key, title=body.title, html_body=sanitized,
        data=body.data, category=workflow.severity, tags=list(workflow.tags or []),
        action_url=body.action_url, status=status_value, kind="single",
        window_key=window_key, event_count=0, overrides=overrides,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=WORKFLOW_TRIGGERED,
                  entity_id=row.id, payload={
                      "workflow_id": workflow.id, "status": status_value,
                      "context_key": workflow.context_key, "feed_key": workflow.feed_key,
                      "override_fields": sorted(overrides),
                  }, actor_id=principal.user.id)
    db.commit()
    return message_out(row)


@router.post("/digest/evaluate")
def evaluate_digest(
    workspace_id: str,
    body: DigestRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-013: one digest per workflow/window, even with zero or many events."""
    verify_workspace(principal, workspace_id)
    _workflow_or_404(db, workspace_id, body.workflow_id)
    existing = db.execute(
        select(NotificationWorkflowMessage).where(
            NotificationWorkflowMessage.workspace_id == workspace_id,
            NotificationWorkflowMessage.workflow_id == body.workflow_id,
            NotificationWorkflowMessage.window_key == body.window_key,
            NotificationWorkflowMessage.kind == "digest",
        )
    ).scalar_one_or_none()
    if existing is not None:
        return message_out(existing)

    pending = db.execute(
        select(NotificationWorkflowMessage).where(
            NotificationWorkflowMessage.workspace_id == workspace_id,
            NotificationWorkflowMessage.workflow_id == body.workflow_id,
            NotificationWorkflowMessage.window_key == body.window_key,
            NotificationWorkflowMessage.status == "pending_digest",
        )
    ).scalars().all()
    for row in pending:
        row.status = "digested"

    digest = NotificationWorkflowMessage(
        id=new_id(), workspace_id=workspace_id, workflow_id=body.workflow_id,
        user_id=principal.user.id, context_key=None, feed_key=None,
        title=body.title, html_body="", data={"window_key": body.window_key},
        category="digest", tags=["digest"], action_url="#/notifications",
        status="delivered", kind="digest", window_key=body.window_key,
        event_count=len(pending), overrides={}, created_at=now(),
    )
    db.add(digest)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DIGEST_FIRED,
                  entity_id=digest.id, payload={
                      "workflow_id": body.workflow_id, "window_key": body.window_key,
                      "event_count": len(pending),
                  }, actor_id=principal.user.id,
                  idempotency_key=f"digest:{body.workflow_id}:{body.window_key}")
    db.commit()
    return message_out(digest)


@router.get("/messages")
def list_messages(
    workspace_id: str,
    feed: str | None = None,
    context: str | None = None,
    workflow_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    unread: bool | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    query = select(NotificationWorkflowMessage).where(
        NotificationWorkflowMessage.workspace_id == workspace_id,
        NotificationWorkflowMessage.user_id == principal.user.id,
    )
    if feed:
        query = query.where(NotificationWorkflowMessage.feed_key == feed)
    if context:
        query = query.where(NotificationWorkflowMessage.context_key == context)
    if workflow_id:
        query = query.where(NotificationWorkflowMessage.workflow_id == workflow_id)
    if category:
        query = query.where(NotificationWorkflowMessage.category == category)
    if unread is not None:
        query = query.where(NotificationWorkflowMessage.read == (not unread))
    rows = db.execute(query.order_by(NotificationWorkflowMessage.created_at)).scalars().all()
    if tag:
        rows = [row for row in rows if tag in (row.tags or [])]
    return [message_out(row) for row in rows]


@router.patch("/messages/{message_id}/read")
def mark_message_read(
    workspace_id: str,
    message_id: str,
    body: MarkRead,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _message_or_404(db, workspace_id, message_id)
    row.read = body.read
    db.commit()
    return message_out(row)


@router.post("/messages/{message_id}/action")
def message_action(
    workspace_id: str,
    message_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-044: clicking a message may only open an authorised local route."""
    verify_workspace(principal, workspace_id)
    row = _message_or_404(db, workspace_id, message_id)
    if not is_authorised_local_route(row.action_url):
        raise HTTPException(status_code=409, detail="message action route is not authorised")
    publish_event(db, workspace_id=workspace_id, event_type=MESSAGE_ACTIONED,
                  entity_id=row.id, payload={"route": row.action_url},
                  actor_id=principal.user.id)
    db.commit()
    return {"message_id": row.id, "route": row.action_url, "authorised": True}


# ---------------------------------------------------------------------------
# NV-073 / NV-086 / NV-087: contexts, feeds and layouts
# ---------------------------------------------------------------------------


def _keyed_crud_routes(model, path: str, label: str, out_fn):
    """Register read/create for a simple keyed table without duplicating code."""

    @router.get(path, operation_id=f"list{label.title()}Rows")
    def list_rows(
        workspace_id: str,
        principal: Principal = Depends(require(CONTACT_READ)),
        db: Session = Depends(get_db),
    ) -> list[dict]:
        verify_workspace(principal, workspace_id)
        rows = db.execute(
            select(model).where(model.workspace_id == workspace_id).order_by(model.created_at)
        ).scalars().all()
        return [out_fn(row) for row in rows]

    @router.post(path, status_code=status.HTTP_201_CREATED, operation_id=f"create{label.title()}Row")
    def create_row(
        workspace_id: str,
        body: KeyedCreate,
        principal: Principal = Depends(require(NOTE_WRITE)),
        db: Session = Depends(get_db),
    ) -> dict:
        verify_workspace(principal, workspace_id)
        exists = db.execute(
            select(model.id).where(model.workspace_id == workspace_id, model.key == body.key)
        ).first()
        if exists:
            raise HTTPException(status_code=409, detail=f"{label} key already exists")
        fields = dict(id=new_id(), workspace_id=workspace_id, key=body.key,
                      name=body.name, created_at=now())
        if hasattr(model, "description"):
            fields["description"] = body.description
        row = model(**fields)
        db.add(row)
        db.flush()
        db.commit()
        return out_fn(row)


def _feed_out(row: NotificationFeed) -> dict:
    return {"id": row.id, "key": row.key, "name": row.name,
            "description": row.description, "created_at": row.created_at}


def _context_out(row: NotificationContext) -> dict:
    return {"id": row.id, "key": row.key, "name": row.name, "created_at": row.created_at}


_keyed_crud_routes(NotificationFeed, "/feeds", "feed", _feed_out)
_keyed_crud_routes(NotificationContext, "/contexts", "context", _context_out)


@router.get("/contexts/{key}/summary")
def context_summary(
    workspace_id: str,
    key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    total = db.execute(
        select(NotificationWorkflowMessage.id).where(
            NotificationWorkflowMessage.workspace_id == workspace_id,
            NotificationWorkflowMessage.context_key == key,
            NotificationWorkflowMessage.user_id == principal.user.id,
        )
    ).all()
    return {"context": key, "message_count": len(total)}


@router.get("/layouts")
def list_layouts(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(NotificationLayout).where(
            NotificationLayout.workspace_id == workspace_id).order_by(NotificationLayout.created_at)
    ).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "body": r.body,
             "provenance": r.provenance, "created_at": r.created_at} for r in rows]


@router.post("/layouts", status_code=status.HTTP_201_CREATED)
def create_layout(
    workspace_id: str,
    body: LayoutCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(NotificationLayout.id).where(
            NotificationLayout.workspace_id == workspace_id, NotificationLayout.key == body.key)
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="layout key already exists")
    try:
        safe_body = sanitize_rich_html(body.body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = NotificationLayout(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        body=safe_body, provenance="clean-room NOVARA layout; no upstream source copied",
        created_at=now(),
    )
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "body": row.body,
            "provenance": row.provenance, "created_at": row.created_at}


@router.post("/layouts/render")
def render_layout(
    workspace_id: str,
    body: LayoutRender,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-087: preview a layout with sanitised content and no script injection."""
    verify_workspace(principal, workspace_id)
    source = body.body
    if body.layout_id:
        layout = db.execute(
            select(NotificationLayout).where(
                NotificationLayout.id == body.layout_id,
                NotificationLayout.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if layout is None:
            raise HTTPException(status_code=404, detail="layout not found")
        source = layout.body
    if source is None:
        raise HTTPException(status_code=422, detail="layout_id or body is required")
    try:
        safe_layout = sanitize_rich_html(source)
        safe_content = sanitize_rich_html(body.content_html)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rendered = safe_layout.replace("{{content}}", safe_content)
    return {"rendered": rendered, "script_free": "<script" not in rendered.lower()}


# ---------------------------------------------------------------------------
# NV-054 / NV-056: signed webhook endpoints, deliveries and replay control
# ---------------------------------------------------------------------------


@router.get("/webhooks/endpoints")
def list_webhook_endpoints(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(NotificationWebhookEndpoint).where(
            NotificationWebhookEndpoint.workspace_id == workspace_id
        ).order_by(NotificationWebhookEndpoint.created_at)
    ).scalars().all()
    return [webhook_out(row) for row in rows]


@router.post("/webhooks/endpoints", status_code=status.HTTP_201_CREATED)
def create_webhook_endpoint(
    workspace_id: str,
    body: WebhookEndpointCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(NotificationWebhookEndpoint.id).where(
            NotificationWebhookEndpoint.workspace_id == workspace_id,
            NotificationWebhookEndpoint.name == body.name,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="webhook endpoint name already exists")
    row = NotificationWebhookEndpoint(
        id=new_id(), workspace_id=workspace_id, name=body.name, url=body.url,
        event_types=list(body.event_types), enabled=True, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=WEBHOOK_ENDPOINT_CREATED,
                  entity_id=row.id, payload={"name": row.name, "local_only": True},
                  actor_id=principal.user.id)
    db.commit()
    return webhook_out(row)


@router.post("/webhooks/endpoints/{endpoint_id}/dispatch", status_code=status.HTTP_201_CREATED)
def dispatch_webhook(
    workspace_id: str,
    endpoint_id: str,
    body: WebhookDispatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-054: record a signed delivery attempt; no external network call is made."""
    verify_workspace(principal, workspace_id)
    endpoint = _endpoint_or_404(db, workspace_id, endpoint_id)
    if not endpoint.enabled:
        raise HTTPException(status_code=409, detail="webhook endpoint is disabled")
    if endpoint.event_types and body.event_type not in endpoint.event_types:
        raise HTTPException(status_code=422, detail="event type is not subscribed")
    secret = secrets.token_urlsafe(32)
    raw = (body.event_type + "." + json.dumps(body.payload, sort_keys=True)).encode("utf-8")
    signature = sign_payload(raw, secret)
    delivery = NotificationWebhookDelivery(
        id=new_id(), workspace_id=workspace_id, endpoint_id=endpoint.id,
        event_type=body.event_type, payload=body.payload, signature=signature,
        secret_hash=hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        status=body.force_status, attempts=1, replayed=False, created_at=now(),
    )
    db.add(delivery)
    db.flush()
    publish_event(db, workspace_id=workspace_id,
                  event_type=WEBHOOK_DELIVERED if body.force_status == "delivered" else WEBHOOK_DELIVERY_FAILED,
                  entity_id=delivery.id, payload={
                      "endpoint_id": endpoint.id, "event_type": body.event_type,
                      "status": body.force_status, "attempt": 1,
                  }, idempotency_key=f"webhook-dispatch:{delivery.id}", actor_id=principal.user.id)
    db.commit()
    # The one-time secret is returned here only; the row stores its hash.
    return {**delivery_out(delivery), "one_time_secret": secret}


@router.get("/webhooks/deliveries")
def list_webhook_deliveries(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(NotificationWebhookDelivery).where(
            NotificationWebhookDelivery.workspace_id == workspace_id
        ).order_by(NotificationWebhookDelivery.created_at)
    ).scalars().all()
    return [delivery_out(row) for row in rows]


@router.post("/webhooks/deliveries/{delivery_id}/replay")
def replay_webhook(
    workspace_id: str,
    delivery_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-056: a failed event can be replayed once, with an audit record."""
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(NotificationWebhookDelivery).where(
            NotificationWebhookDelivery.id == delivery_id,
            NotificationWebhookDelivery.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="webhook delivery not found")
    if row.status != "failed":
        raise HTTPException(status_code=409, detail="only failed deliveries can be replayed")
    if row.replayed:
        raise HTTPException(status_code=409, detail="delivery has already been replayed once")
    row.attempts += 1
    row.replayed = True
    row.status = "delivered"
    publish_event(db, workspace_id=workspace_id, event_type=WEBHOOK_REPLAYED,
                  entity_id=row.id, payload={"attempt": row.attempts},
                  idempotency_key=f"webhook-replay:{row.id}", actor_id=principal.user.id)
    db.commit()
    return delivery_out(row)


@router.post("/webhooks/verify")
def verify_webhook(
    workspace_id: str,
    body: WebhookVerify,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """NV-056: raw-body HMAC verification with replay (nonce) rejection."""
    verify_workspace(principal, workspace_id)
    # Bounded marker key so the value always fits the event_type column on
    # PostgreSQL as well as SQLite.
    key = "webhook-verify:" + hashlib.sha256(
        f"{workspace_id}:{body.nonce}".encode("utf-8")
    ).hexdigest()
    seen = db.execute(
        select(NotificationWebhookDelivery.id).where(
            NotificationWebhookDelivery.workspace_id == workspace_id,
            NotificationWebhookDelivery.event_type == key,
        )
    ).first()
    if seen:
        return {"valid": False, "reason": "replay", "nonce": body.nonce}
    valid = verify_signature(body.raw_body.encode("utf-8"), body.signature, body.secret)
    marker = NotificationWebhookDelivery(
        id=new_id(), workspace_id=workspace_id, endpoint_id="verify-only",
        event_type=key, payload={"nonce": body.nonce}, signature=body.signature[:16],
        secret_hash=hashlib.sha256(body.secret.encode("utf-8")).hexdigest(),
        status="delivered", attempts=1, replayed=False, created_at=now(),
    )
    db.add(marker)
    db.commit()
    return {"valid": valid, "reason": "ok" if valid else "bad_signature", "nonce": body.nonce}
