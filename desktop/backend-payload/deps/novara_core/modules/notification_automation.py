"""Notification automation and delivery governance (Novu P2 cluster).

Clean-room implementation of NV-009 (sandboxed code steps), NV-015 (HTTP
request steps resolved only against registered local stubs), NV-026
(provider routing with primary/fallback priority), NV-027 (demo providers
with explicit quotas), NV-031 (subscriber channel endpoints with hashed
secrets), NV-103 (documented workspace-scoped platform limits), NV-104
(authorised local broadcast), NV-107 (subscriber search and bulk create)
and NV-118 (workspace feature flags).

No Novu source is copied. There is no outbound HTTP, no real email/SMS/push
delivery and no hosted provider: HTTP steps resolve against local stub
records, demo sends persist simulated local delivery rows, and broadcasts
create local in-app records only. Channel secrets are stored as SHA-256
hashes and never returned.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE, WORKSPACE_MANAGE

SUBSCRIBER_CHANGED = "automation.subscriber_changed"
ENDPOINT_CHANGED = "automation.endpoint_changed"
CODE_STEP_CHANGED = "automation.code_step_changed"
HTTP_STEP_CHANGED = "automation.http_step_changed"
ROUTING_CHANGED = "automation.routing_changed"
DEMO_SENT = "automation.demo_sent"
BROADCAST_FIRED = "automation.broadcast_fired"
QUOTA_CHANGED = "automation.quota_changed"
FLAG_CHANGED = "automation.flag_changed"
register_event_types(
    SUBSCRIBER_CHANGED, ENDPOINT_CHANGED, CODE_STEP_CHANGED, HTTP_STEP_CHANGED,
    ROUTING_CHANGED, DEMO_SENT, BROADCAST_FIRED, QUOTA_CHANGED, FLAG_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/notification-automation",
    tags=["notification-automation"],
)

CHANNELS = frozenset({"email", "sms", "push", "chat"})
DEMO_PROVIDERS = frozenset({"demo_email", "demo_sms"})
ROUTE_PROVIDERS = frozenset({"demo_email", "demo_sms", "in_app"})
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
CONDITION_SOURCES = frozenset({"subscriber", "context", "data"})
BULK_CREATE_LIMIT = 500
DEFAULT_QUOTAS = {
    "max_payload_bytes": 65536,
    "max_subscribers": 10000,
    "max_bulk_create": BULK_CREATE_LIMIT,
    "max_broadcasts_per_minute": 5,
}
DEFAULT_FLAGS = {
    "experimental_code_steps": True,
    "experimental_http_steps": True,
    "experimental_broadcast": False,
    "experimental_routing": True,
}
DEMO_QUOTA_DEFAULTS = {"demo_email": 100, "demo_sms": 20}


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


# ---------------------------------------------------------------------------
# Tables (additive, workspace-scoped)
# ---------------------------------------------------------------------------


class AutomationSubscriber(Base):
    __tablename__ = "automation_subscribers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "subscriber_key", name="uq_automation_subscriber"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    subscriber_key: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SubscriberChannelEndpoint(Base):
    __tablename__ = "subscriber_channel_endpoints"
    __table_args__ = (
        UniqueConstraint("workspace_id", "subscriber_id", "channel", "endpoint",
                         name="uq_subscriber_channel_endpoint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    subscriber_id: Mapped[str] = mapped_column(ForeignKey("automation_subscribers.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(300), nullable=False)
    secret_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WorkflowCodeStep(Base):
    __tablename__ = "workflow_code_steps"
    __table_args__ = (
        UniqueConstraint("workspace_id", "workflow_key", "step_key", name="uq_workflow_code_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(120), nullable=False)
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(2000), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class LocalHttpStub(Base):
    __tablename__ = "local_http_stubs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "path", "method", name="uq_local_http_stub"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WorkflowHttpStep(Base):
    __tablename__ = "workflow_http_steps"
    __table_args__ = (
        UniqueConstraint("workspace_id", "workflow_key", "step_key", name="uq_workflow_http_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(120), nullable=False)
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ProviderRoutingRule(Base):
    __tablename__ = "provider_routing_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DemoProviderQuota(Base):
    __tablename__ = "demo_provider_quotas"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_demo_provider_quota"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_date: Mapped[str] = mapped_column(String(10), nullable=False)


class DemoDelivery(Base):
    __tablename__ = "demo_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    subscriber_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_key: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="simulated", nullable=False)
    broadcast_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class AutomationQuota(Base):
    __tablename__ = "automation_quotas"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_automation_quota"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


class AutomationFeatureFlag(Base):
    __tablename__ = "automation_feature_flags"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_automation_feature_flag"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    env_default: Mapped[str] = mapped_column(String(200), default="", nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SubscriberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscriber_key: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=320)
    name: str = Field(default="", max_length=200)


class BulkSubscribersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscribers: list[SubscriberIn] = Field(min_length=1)


class EndpointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: str
    endpoint: str = Field(min_length=1, max_length=300)
    secret: str | None = Field(default=None, max_length=300)

    @field_validator("channel")
    @classmethod
    def _channel(cls, value):
        if value not in CHANNELS:
            raise ValueError("unsupported channel")
        return value


class CodeStepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_key: str = Field(min_length=1, max_length=120)
    step_key: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=2000)
    publish: bool = False


class CodeEvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict = Field(default_factory=dict)
    steps: dict = Field(default_factory=dict)


class HttpStubIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=300)
    method: str = "GET"
    response: dict = Field(default_factory=dict)

    @field_validator("method")
    @classmethod
    def _method(cls, value):
        upper = value.upper()
        if upper not in HTTP_METHODS:
            raise ValueError("unsupported HTTP method")
        return upper

    @field_validator("path")
    @classmethod
    def _path(cls, value):
        if not value.startswith("/local/"):
            raise ValueError("stub path must start with /local/ (no outbound URLs)")
        return value


class HttpStepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_key: str = Field(min_length=1, max_length=120)
    step_key: str = Field(min_length=1, max_length=120)
    method: str = "GET"
    path: str = Field(min_length=1, max_length=300)
    authorized: bool = False

    @field_validator("method")
    @classmethod
    def _method(cls, value):
        upper = value.upper()
        if upper not in HTTP_METHODS:
            raise ValueError("unsupported HTTP method")
        return upper


class RoutingCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    key: str = Field(min_length=1, max_length=120)
    equals: str = Field(max_length=300)

    @field_validator("source")
    @classmethod
    def _source(cls, value):
        if value not in CONDITION_SOURCES:
            raise ValueError("unsupported condition source")
        return value


class RoutingRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_key: str = Field(min_length=1, max_length=120)
    provider: str
    priority: int = Field(default=100, ge=0, le=10000)
    conditions: list[RoutingCondition] = Field(default_factory=list)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value):
        if value not in ROUTE_PROVIDERS:
            raise ValueError("unsupported routing provider")
        return value


class RoutingEvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_key: str = Field(min_length=1, max_length=120)
    subscriber_key: str | None = None
    context: dict = Field(default_factory=dict)
    data: dict = Field(default_factory=dict)


class DemoSendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    subscriber_key: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value):
        if value not in DEMO_PROVIDERS:
            raise ValueError("unsupported demo provider")
        return value


class BroadcastIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_key: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    authorized: bool = False


class QuotaOverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    value: int = Field(ge=1)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        if value not in DEFAULT_QUOTAS:
            raise ValueError("unknown quota key")
        return value


class FlagPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quota(db, workspace_id, key: str) -> int:
    row = db.execute(select(AutomationQuota).where(
        AutomationQuota.workspace_id == workspace_id, AutomationQuota.key == key
    )).scalar_one_or_none()
    return row.value if row is not None else DEFAULT_QUOTAS[key]


def _flag(db, workspace_id, key: str) -> bool:
    row = db.execute(select(AutomationFeatureFlag).where(
        AutomationFeatureFlag.workspace_id == workspace_id, AutomationFeatureFlag.key == key
    )).scalar_one_or_none()
    if row is not None:
        return row.enabled
    return DEFAULT_FLAGS.get(key, False)


def _require_flag(db, workspace_id, key: str):
    if not _flag(db, workspace_id, key):
        raise HTTPException(status_code=409, detail=f"feature flag {key} is disabled")


def _subscriber_by_key(db, workspace_id, subscriber_key: str) -> AutomationSubscriber:
    row = db.execute(select(AutomationSubscriber).where(
        AutomationSubscriber.workspace_id == workspace_id,
        AutomationSubscriber.subscriber_key == subscriber_key,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="subscriber not found")
    return row


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return value[:2] + "***" + value[-4:]


def _payload_bytes(payload: dict) -> int:
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


# Restricted expression sandbox for NV-009 code steps: a whitelisted AST walk,
# never exec/eval of arbitrary Python. Only literals, payload/steps lookups,
# arithmetic, comparisons, boolean logic and a fixed function set are allowed.
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant, ast.Attribute, ast.Subscript, ast.IfExp,
    ast.Dict, ast.List, ast.Tuple,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)
_ALLOWED_FUNCS = {
    "len": len, "abs": abs, "round": round, "min": min, "max": max,
    "str": str, "int": int, "float": float,
    "upper": lambda v: str(v).upper(), "lower": lambda v: str(v).lower(),
    "strip": lambda v: str(v).strip(),
}


def _sandbox_compile(code: str):
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=422, detail=f"code step syntax error: {exc.msg}")
    nodes = list(ast.walk(tree))
    if len(nodes) > 200:
        raise HTTPException(status_code=422, detail="code step too complex")
    for node in nodes:
        if not isinstance(node, _ALLOWED_NODES):
            raise HTTPException(status_code=422,
                                detail=f"disallowed expression element: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise HTTPException(status_code=422, detail="dunder attribute access is not allowed")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise HTTPException(status_code=422, detail="function not allowed in code steps")
            if node.keywords:
                raise HTTPException(status_code=422, detail="keyword arguments not allowed")
    return tree


def _sandbox_eval(code: str, context: dict):
    tree = _sandbox_compile(code)

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool)) or node.value is None:
                return node.value
            raise HTTPException(status_code=422, detail="unsupported literal")
        if isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            raise HTTPException(status_code=422, detail=f"unknown name: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise HTTPException(status_code=422, detail="dunder attribute access is not allowed")
            base = ev(node.value)
            if isinstance(base, dict):
                return base.get(node.attr)
            raise HTTPException(status_code=422, detail="attribute access only on objects")
        if isinstance(node, ast.Subscript):
            base = ev(node.value)
            key = ev(node.slice)
            if isinstance(base, (dict, list, str)):
                try:
                    return base[key]
                except (KeyError, IndexError, TypeError):
                    return None
            raise HTTPException(status_code=422, detail="subscript only on objects/lists")
        if isinstance(node, ast.Dict):
            return {ev(k): ev(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [ev(v) for v in node.elts]
            return values if isinstance(node, ast.List) else tuple(values)
        if isinstance(node, ast.UnaryOp):
            operand = ev(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            return not operand
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left), ev(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.Mod):
                return left % right
            return left // right
        if isinstance(node, ast.BoolOp):
            values = [ev(v) for v in node.values]
            if isinstance(node.op, ast.And):
                result = True
                for v in values:
                    result = v
                    if not v:
                        break
                return result
            result = False
            for v in values:
                result = v
                if v:
                    break
            return result
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = ev(comparator)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                elif isinstance(op, ast.In):
                    ok = left in right
                else:
                    ok = left not in right
                if not ok:
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return ev(node.body) if ev(node.test) else ev(node.orelse)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise HTTPException(status_code=422, detail="function not allowed in code steps")
            if node.keywords:
                raise HTTPException(status_code=422, detail="keyword arguments not allowed")
            args = [ev(a) for a in node.args]
            try:
                return _ALLOWED_FUNCS[node.func.id](*args)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"code step evaluation error: {exc}")
        raise HTTPException(status_code=422, detail="unsupported expression")

    try:
        return ev(tree)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"code step evaluation error: {exc}")


def _demo_quota_row(db, workspace_id, provider: str) -> DemoProviderQuota:
    row = db.execute(select(DemoProviderQuota).where(
        DemoProviderQuota.workspace_id == workspace_id, DemoProviderQuota.provider == provider
    )).scalar_one_or_none()
    today = now().date().isoformat()
    if row is None:
        row = DemoProviderQuota(id=new_id(), workspace_id=workspace_id, provider=provider,
                                daily_limit=DEMO_QUOTA_DEFAULTS[provider], used=0, window_date=today)
        db.add(row)
        db.flush()
    elif row.window_date != today:
        row.used = 0
        row.window_date = today
    return row


def _condition_matches(condition: dict, subscriber: AutomationSubscriber | None,
                       context: dict, data: dict) -> bool:
    source, key, expected = condition["source"], condition["key"], condition["equals"]
    if source == "subscriber":
        if subscriber is None:
            return False
        if key == "email_domain":
            actual = subscriber.email.split("@", 1)[1].lower() if "@" in subscriber.email else ""
        else:
            actual = getattr(subscriber, key, None)
            actual = "" if actual is None else str(actual)
        return str(actual).lower() == str(expected).lower()
    bag = context if source == "context" else data
    return str(bag.get(key, "")) == str(expected)


# ---------------------------------------------------------------------------
# Routes - contract, quotas and feature flags
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="notificationAutomationContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["subscribers", "endpoints", "codeSteps", "httpStubs", "httpSteps",
                      "routing", "demoProviders", "broadcast", "quotas", "featureFlags"],
        "channels": sorted(CHANNELS), "demo_providers": sorted(DEMO_PROVIDERS),
        "default_quotas": DEFAULT_QUOTAS, "default_flags": DEFAULT_FLAGS,
        "external_calls": False, "external_delivery": False,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/notification-automation",
    }


@router.get("/quotas", operation_id="automationQuotas")
def get_quotas(workspace_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    overrides = db.execute(select(AutomationQuota).where(
        AutomationQuota.workspace_id == workspace_id
    )).scalars().all()
    override_map = {r.key: r.value for r in overrides}
    return {
        "documented": DEFAULT_QUOTAS,
        "effective": {k: override_map.get(k, v) for k, v in DEFAULT_QUOTAS.items()},
        "overrides": override_map,
        "workspace_scoped": True,
    }


@router.put("/quotas", operation_id="setAutomationQuota")
def set_quota(workspace_id: str, body: QuotaOverrideIn,
              principal: Principal = Depends(require(WORKSPACE_MANAGE)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(AutomationQuota).where(
        AutomationQuota.workspace_id == workspace_id, AutomationQuota.key == body.key
    )).scalar_one_or_none()
    if row is None:
        row = AutomationQuota(id=new_id(), workspace_id=workspace_id, key=body.key, value=body.value)
        db.add(row)
    else:
        row.value = body.value
    db.flush()
    _audit(db, workspace_id, QUOTA_CHANGED, row.id, {"key": body.key, "value": body.value}, principal)
    db.commit()
    return {"key": body.key, "value": body.value}


@router.get("/feature-flags", operation_id="listAutomationFlags")
def list_flags(workspace_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AutomationFeatureFlag).where(
        AutomationFeatureFlag.workspace_id == workspace_id
    )).scalars().all()
    stored = {r.key: r for r in rows}
    result = []
    for key, default in sorted(DEFAULT_FLAGS.items()):
        row = stored.get(key)
        result.append({
            "key": key,
            "enabled": row.enabled if row is not None else default,
            "env_default": row.env_default if row is not None else f"NOVARA_{key.upper()}={str(default).lower()}",
            "overridden": row is not None,
        })
    return result


@router.patch("/feature-flags/{key}", operation_id="setAutomationFlag")
def set_flag(workspace_id: str, key: str, body: FlagPatchIn,
             principal: Principal = Depends(require(NOTE_WRITE)),
             db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if key not in DEFAULT_FLAGS:
        raise HTTPException(status_code=404, detail="feature flag not found")
    row = db.execute(select(AutomationFeatureFlag).where(
        AutomationFeatureFlag.workspace_id == workspace_id, AutomationFeatureFlag.key == key
    )).scalar_one_or_none()
    if row is None:
        row = AutomationFeatureFlag(id=new_id(), workspace_id=workspace_id, key=key,
                                    enabled=body.enabled,
                                    env_default=f"NOVARA_{key.upper()}={str(DEFAULT_FLAGS[key]).lower()}")
        db.add(row)
    else:
        row.enabled = body.enabled
    db.flush()
    _audit(db, workspace_id, FLAG_CHANGED, row.id, {"key": key, "enabled": body.enabled}, principal)
    db.commit()
    return {"key": key, "enabled": body.enabled}


# ---------------------------------------------------------------------------
# Routes - subscribers, search, bulk create and channel endpoints
# ---------------------------------------------------------------------------


@router.get("/subscribers", operation_id="searchAutomationSubscribers")
def search_subscribers(workspace_id: str,
                       q: str = Query(default="", max_length=200),
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    stmt = select(AutomationSubscriber).where(AutomationSubscriber.workspace_id == workspace_id)
    if q.strip():
        needle = q.strip().lower()
        stmt = stmt.where(
            func.lower(AutomationSubscriber.subscriber_key).contains(needle)
            | func.lower(AutomationSubscriber.email).contains(needle)
            | func.lower(AutomationSubscriber.name).contains(needle)
        )
    rows = db.execute(stmt.order_by(AutomationSubscriber.subscriber_key)).scalars().all()
    return [{"id": r.id, "subscriber_key": r.subscriber_key, "email": r.email, "name": r.name}
            for r in rows]


@router.post("/subscribers", status_code=status.HTTP_201_CREATED,
             operation_id="createAutomationSubscriber")
def create_subscriber(workspace_id: str, body: SubscriberIn,
                      principal: Principal = Depends(require(NOTE_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    count = db.execute(select(func.count(AutomationSubscriber.id)).where(
        AutomationSubscriber.workspace_id == workspace_id
    )).scalar_one()
    if count >= _quota(db, workspace_id, "max_subscribers"):
        raise HTTPException(status_code=429, detail="subscriber quota exceeded")
    exists = db.execute(select(AutomationSubscriber.id).where(
        AutomationSubscriber.workspace_id == workspace_id,
        AutomationSubscriber.subscriber_key == body.subscriber_key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="subscriber already exists")
    row = AutomationSubscriber(id=new_id(), workspace_id=workspace_id,
                               subscriber_key=body.subscriber_key, email=body.email,
                               name=body.name, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, SUBSCRIBER_CHANGED, row.id, {"created": True}, principal)
    db.commit()
    return {"id": row.id, "subscriber_key": row.subscriber_key}


@router.post("/subscribers/bulk", status_code=status.HTTP_201_CREATED,
             operation_id="bulkCreateAutomationSubscribers")
def bulk_create(workspace_id: str, body: BulkSubscribersIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    limit = min(BULK_CREATE_LIMIT, _quota(db, workspace_id, "max_bulk_create"))
    if len(body.subscribers) > limit:
        raise HTTPException(status_code=422, detail=f"bulk create limited to {limit} subscribers")
    keys = [s.subscriber_key for s in body.subscribers]
    if len(set(keys)) != len(keys):
        raise HTTPException(status_code=422, detail="duplicate subscriber_key in request")
    existing = db.execute(select(AutomationSubscriber.subscriber_key).where(
        AutomationSubscriber.workspace_id == workspace_id,
        AutomationSubscriber.subscriber_key.in_(keys),
    )).scalars().all()
    if existing:
        raise HTTPException(status_code=409, detail=f"subscribers already exist: {sorted(existing)}")
    count = db.execute(select(func.count(AutomationSubscriber.id)).where(
        AutomationSubscriber.workspace_id == workspace_id
    )).scalar_one()
    if count + len(body.subscribers) > _quota(db, workspace_id, "max_subscribers"):
        raise HTTPException(status_code=429, detail="subscriber quota exceeded")
    created = []
    for item in body.subscribers:
        row = AutomationSubscriber(id=new_id(), workspace_id=workspace_id,
                                   subscriber_key=item.subscriber_key, email=item.email,
                                   name=item.name, created_at=now())
        db.add(row)
        created.append({"id": row.id, "subscriber_key": row.subscriber_key})
    db.flush()
    _audit(db, workspace_id, SUBSCRIBER_CHANGED, workspace_id,
           {"bulk_created": len(created)}, principal)
    db.commit()
    return {"created": len(created), "subscribers": created}


@router.get("/subscribers/{subscriber_id}/endpoints", operation_id="listSubscriberEndpoints")
def list_endpoints(workspace_id: str, subscriber_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _get(db, AutomationSubscriber, workspace_id, subscriber_id, "subscriber")
    rows = db.execute(select(SubscriberChannelEndpoint).where(
        SubscriberChannelEndpoint.workspace_id == workspace_id,
        SubscriberChannelEndpoint.subscriber_id == subscriber_id,
    )).scalars().all()
    return [{"id": r.id, "channel": r.channel, "endpoint_masked": _mask(r.endpoint),
             "has_secret": r.secret_hash is not None} for r in rows]


@router.post("/subscribers/{subscriber_id}/endpoints", status_code=status.HTTP_201_CREATED,
             operation_id="addSubscriberEndpoint")
def add_endpoint(workspace_id: str, subscriber_id: str, body: EndpointIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    subscriber = _get(db, AutomationSubscriber, workspace_id, subscriber_id, "subscriber")
    exists = db.execute(select(SubscriberChannelEndpoint.id).where(
        SubscriberChannelEndpoint.workspace_id == workspace_id,
        SubscriberChannelEndpoint.subscriber_id == subscriber.id,
        SubscriberChannelEndpoint.channel == body.channel,
        SubscriberChannelEndpoint.endpoint == body.endpoint,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="endpoint already exists")
    secret_hash = hashlib.sha256(body.secret.encode("utf-8")).hexdigest() if body.secret else None
    row = SubscriberChannelEndpoint(id=new_id(), workspace_id=workspace_id,
                                    subscriber_id=subscriber.id, channel=body.channel,
                                    endpoint=body.endpoint, secret_hash=secret_hash, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ENDPOINT_CHANGED, row.id,
           {"channel": body.channel, "has_secret": secret_hash is not None}, principal)
    db.commit()
    return {"id": row.id, "channel": row.channel, "endpoint_masked": _mask(row.endpoint),
            "has_secret": secret_hash is not None}


@router.delete("/subscribers/{subscriber_id}/endpoints/{endpoint_id}",
               operation_id="removeSubscriberEndpoint")
def remove_endpoint(workspace_id: str, subscriber_id: str, endpoint_id: str,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(SubscriberChannelEndpoint).where(
        SubscriberChannelEndpoint.id == endpoint_id,
        SubscriberChannelEndpoint.workspace_id == workspace_id,
        SubscriberChannelEndpoint.subscriber_id == subscriber_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="endpoint not found")
    db.delete(row)
    db.flush()
    _audit(db, workspace_id, ENDPOINT_CHANGED, endpoint_id, {"removed": True}, principal)
    db.commit()
    return {"id": endpoint_id, "removed": True}


# ---------------------------------------------------------------------------
# Routes - code steps and HTTP steps
# ---------------------------------------------------------------------------


@router.get("/code-steps", operation_id="listCodeSteps")
def list_code_steps(workspace_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(WorkflowCodeStep).where(
        WorkflowCodeStep.workspace_id == workspace_id
    ).order_by(WorkflowCodeStep.workflow_key, WorkflowCodeStep.step_key)).scalars().all()
    return [{"id": r.id, "workflow_key": r.workflow_key, "step_key": r.step_key,
             "version": r.version, "published": r.published} for r in rows]


@router.post("/code-steps", status_code=status.HTTP_201_CREATED,
             operation_id="createCodeStep")
def create_code_step(workspace_id: str, body: CodeStepIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_code_steps")
    _sandbox_compile(body.code)
    row = db.execute(select(WorkflowCodeStep).where(
        WorkflowCodeStep.workspace_id == workspace_id,
        WorkflowCodeStep.workflow_key == body.workflow_key,
        WorkflowCodeStep.step_key == body.step_key,
    )).scalar_one_or_none()
    if row is None:
        row = WorkflowCodeStep(id=new_id(), workspace_id=workspace_id,
                               workflow_key=body.workflow_key, step_key=body.step_key,
                               code=body.code, version=1, published=body.publish, created_at=now())
        db.add(row)
    else:
        row.code = body.code
        row.version += 1
        row.published = body.publish
    db.flush()
    _audit(db, workspace_id, CODE_STEP_CHANGED, row.id,
           {"version": row.version, "published": row.published}, principal)
    db.commit()
    return {"id": row.id, "version": row.version, "published": row.published}


@router.post("/code-steps/{step_id}/evaluate", operation_id="evaluateCodeStep")
def evaluate_code_step(workspace_id: str, step_id: str, body: CodeEvaluateIn,
                       principal: Principal = Depends(require(NOTE_WRITE)),
                       db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_code_steps")
    row = _get(db, WorkflowCodeStep, workspace_id, step_id, "code step")
    if not row.published:
        raise HTTPException(status_code=409, detail="code step is not published")
    result = _sandbox_eval(row.code, {"payload": body.payload, "steps": body.steps})
    return {"step_id": row.id, "result": result, "sandboxed": True, "external_calls": False}


@router.get("/http-stubs", operation_id="listHttpStubs")
def list_http_stubs(workspace_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(LocalHttpStub).where(
        LocalHttpStub.workspace_id == workspace_id
    ).order_by(LocalHttpStub.path)).scalars().all()
    return [{"id": r.id, "path": r.path, "method": r.method} for r in rows]


@router.post("/http-stubs", status_code=status.HTTP_201_CREATED,
             operation_id="createHttpStub")
def create_http_stub(workspace_id: str, body: HttpStubIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(LocalHttpStub.id).where(
        LocalHttpStub.workspace_id == workspace_id,
        LocalHttpStub.path == body.path, LocalHttpStub.method == body.method,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="stub already exists")
    row = LocalHttpStub(id=new_id(), workspace_id=workspace_id, path=body.path,
                        method=body.method, response=body.response, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, HTTP_STEP_CHANGED, row.id, {"stub": body.path}, principal)
    db.commit()
    return {"id": row.id, "path": row.path, "method": row.method}


@router.post("/http-steps", status_code=status.HTTP_201_CREATED,
             operation_id="createHttpStep")
def create_http_step(workspace_id: str, body: HttpStepIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_http_steps")
    if not body.path.startswith("/local/"):
        raise HTTPException(status_code=422, detail="HTTP steps may only target registered /local/ stubs")
    exists = db.execute(select(WorkflowHttpStep.id).where(
        WorkflowHttpStep.workspace_id == workspace_id,
        WorkflowHttpStep.workflow_key == body.workflow_key,
        WorkflowHttpStep.step_key == body.step_key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="http step already exists")
    row = WorkflowHttpStep(id=new_id(), workspace_id=workspace_id,
                           workflow_key=body.workflow_key, step_key=body.step_key,
                           method=body.method, path=body.path, authorized=body.authorized,
                           created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, HTTP_STEP_CHANGED, row.id,
           {"path": body.path, "authorized": body.authorized}, principal)
    db.commit()
    return {"id": row.id, "path": row.path, "authorized": row.authorized}


@router.post("/http-steps/{step_id}/run", operation_id="runHttpStep")
def run_http_step(workspace_id: str, step_id: str,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_http_steps")
    row = _get(db, WorkflowHttpStep, workspace_id, step_id, "http step")
    if not row.authorized:
        raise HTTPException(status_code=403, detail="http step requires explicit authorisation")
    stub = db.execute(select(LocalHttpStub).where(
        LocalHttpStub.workspace_id == workspace_id,
        LocalHttpStub.path == row.path, LocalHttpStub.method == row.method,
    )).scalar_one_or_none()
    if stub is None:
        raise HTTPException(status_code=422, detail="no registered local stub for this path/method")
    row.last_response = stub.response
    row.last_run_at = now()
    db.flush()
    _audit(db, workspace_id, HTTP_STEP_CHANGED, row.id, {"ran": True, "local_stub": stub.id}, principal)
    db.commit()
    return {"step_id": row.id, "response": stub.response,
            "resolved_against": "local-stub", "external_calls": False}


# ---------------------------------------------------------------------------
# Routes - provider routing, demo providers and broadcast
# ---------------------------------------------------------------------------


@router.get("/routing-rules", operation_id="listRoutingRules")
def list_routing_rules(workspace_id: str,
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ProviderRoutingRule).where(
        ProviderRoutingRule.workspace_id == workspace_id
    ).order_by(ProviderRoutingRule.workflow_key, ProviderRoutingRule.priority)).scalars().all()
    return [{"id": r.id, "workflow_key": r.workflow_key, "provider": r.provider,
             "priority": r.priority, "conditions": r.conditions} for r in rows]


@router.post("/routing-rules", status_code=status.HTTP_201_CREATED,
             operation_id="createRoutingRule")
def create_routing_rule(workspace_id: str, body: RoutingRuleIn,
                        principal: Principal = Depends(require(NOTE_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_routing")
    row = ProviderRoutingRule(id=new_id(), workspace_id=workspace_id,
                              workflow_key=body.workflow_key, provider=body.provider,
                              priority=body.priority,
                              conditions=[c.model_dump() for c in body.conditions], created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ROUTING_CHANGED, row.id,
           {"provider": body.provider, "priority": body.priority}, principal)
    db.commit()
    return {"id": row.id, "provider": row.provider, "priority": row.priority}


@router.delete("/routing-rules/{rule_id}", operation_id="removeRoutingRule")
def remove_routing_rule(workspace_id: str, rule_id: str,
                        principal: Principal = Depends(require(NOTE_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, ProviderRoutingRule, workspace_id, rule_id, "routing rule")
    db.delete(row)
    db.flush()
    _audit(db, workspace_id, ROUTING_CHANGED, rule_id, {"removed": True}, principal)
    db.commit()
    return {"id": rule_id, "removed": True}


@router.post("/routing/evaluate", operation_id="evaluateRouting")
def evaluate_routing(workspace_id: str, body: RoutingEvaluateIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_routing")
    subscriber = None
    if body.subscriber_key is not None:
        subscriber = _subscriber_by_key(db, workspace_id, body.subscriber_key)
    rules = db.execute(select(ProviderRoutingRule).where(
        ProviderRoutingRule.workspace_id == workspace_id,
        ProviderRoutingRule.workflow_key == body.workflow_key,
    ).order_by(ProviderRoutingRule.priority)).scalars().all()
    chain = []
    for rule in rules:
        if all(_condition_matches(c, subscriber, body.context, body.data) for c in rule.conditions):
            chain.append({"rule_id": rule.id, "provider": rule.provider, "priority": rule.priority})
    primary = chain[0]["provider"] if chain else "in_app"
    return {"workflow_key": body.workflow_key, "primary": primary,
            "fallbacks": [c["provider"] for c in chain[1:]],
            "matched_rules": len(chain), "default_provider": "in_app"}


@router.get("/demo-providers", operation_id="listDemoProviders")
def list_demo_providers(workspace_id: str,
                        principal: Principal = Depends(require(CONTACT_READ)),
                        db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    result = []
    for provider in sorted(DEMO_PROVIDERS):
        row = _demo_quota_row(db, workspace_id, provider)
        db.commit()
        result.append({"provider": provider, "daily_limit": row.daily_limit,
                       "used_today": row.used, "remaining": max(0, row.daily_limit - row.used),
                       "real_delivery": False})
    return result


@router.post("/demo-send", status_code=status.HTTP_201_CREATED,
             operation_id="demoSend")
def demo_send(workspace_id: str, body: DemoSendIn,
              principal: Principal = Depends(require(NOTE_WRITE)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    subscriber = _subscriber_by_key(db, workspace_id, body.subscriber_key)
    if _payload_bytes(body.payload) > _quota(db, workspace_id, "max_payload_bytes"):
        raise HTTPException(status_code=422, detail="payload exceeds documented size cap")
    quota = _demo_quota_row(db, workspace_id, body.provider)
    if quota.used >= quota.daily_limit:
        raise HTTPException(status_code=429, detail="demo provider daily quota exceeded")
    quota.used += 1
    delivery = DemoDelivery(id=new_id(), workspace_id=workspace_id, provider=body.provider,
                            subscriber_id=subscriber.id, workflow_key="demo",
                            payload=body.payload, status="simulated", created_at=now())
    db.add(delivery)
    db.flush()
    _audit(db, workspace_id, DEMO_SENT, delivery.id,
           {"provider": body.provider, "simulated": True}, principal)
    db.commit()
    return {"id": delivery.id, "provider": body.provider, "status": "simulated",
            "used_today": quota.used, "daily_limit": quota.daily_limit,
            "external_delivery": False}


@router.post("/broadcast", status_code=status.HTTP_201_CREATED,
             operation_id="broadcastEvent")
def broadcast(workspace_id: str, body: BroadcastIn,
              principal: Principal = Depends(require(NOTE_WRITE)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _require_flag(db, workspace_id, "experimental_broadcast")
    if not body.authorized:
        raise HTTPException(status_code=403, detail="broadcast requires explicit authorisation")
    if _payload_bytes(body.payload) > _quota(db, workspace_id, "max_payload_bytes"):
        raise HTTPException(status_code=422, detail="payload exceeds documented size cap")
    minute_ago = now().timestamp() - 60
    # Throughput cap counts broadcast batches recorded in the last minute.
    recent_batches = db.execute(select(DemoDelivery.broadcast_id).where(
        DemoDelivery.workspace_id == workspace_id,
        DemoDelivery.broadcast_id.is_not(None),
        DemoDelivery.created_at >= datetime.fromtimestamp(minute_ago, tz=now().tzinfo),
    ).distinct()).scalars().all()
    if len(recent_batches) >= _quota(db, workspace_id, "max_broadcasts_per_minute"):
        raise HTTPException(status_code=429, detail="broadcast throughput cap exceeded")
    subscribers = db.execute(select(AutomationSubscriber).where(
        AutomationSubscriber.workspace_id == workspace_id
    )).scalars().all()
    if not subscribers:
        raise HTTPException(status_code=422, detail="no subscribers to broadcast to")
    broadcast_id = new_id()
    for subscriber in subscribers:
        db.add(DemoDelivery(id=new_id(), workspace_id=workspace_id, provider="in_app",
                            subscriber_id=subscriber.id, workflow_key=body.workflow_key,
                            payload=body.payload, status="delivered_local",
                            broadcast_id=broadcast_id, created_at=now()))
    db.flush()
    _audit(db, workspace_id, BROADCAST_FIRED, broadcast_id,
           {"recipients": len(subscribers), "workflow_key": body.workflow_key}, principal)
    db.commit()
    return {"broadcast_id": broadcast_id, "recipients": len(subscribers),
            "status": "delivered_local", "external_delivery": False}


@router.get("/deliveries", operation_id="listAutomationDeliveries")
def list_deliveries(workspace_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(DemoDelivery).where(
        DemoDelivery.workspace_id == workspace_id
    ).order_by(DemoDelivery.created_at.desc()).limit(200)).scalars().all()
    return [{"id": r.id, "provider": r.provider, "workflow_key": r.workflow_key,
             "status": r.status, "broadcast_id": r.broadcast_id} for r in rows]