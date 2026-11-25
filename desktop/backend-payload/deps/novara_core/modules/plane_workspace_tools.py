"""Clean-room P2/P3 Plane workspace tools.

Documented/public behaviour implemented from scratch (no upstream source copied,
no external service contacted):
- PL-089: intake forms -> a validated public submission creates exactly one
  intake request.
- PL-091: user assets -> metadata CRUD scoped to the owner and workspace.
- PL-092: workspace assets -> admin-controlled, workspace-isolated metadata CRUD.
- PL-093: stickies -> private per-user notes with formatting and colour.
- PL-107: themes -> per-user / per-workspace theme preference that persists
  (light theme only, per NOVARA governance).
- PL-137: PQL -> a safe work-item filter DSL parsed to a structured predicate
  tree, never to SQL; injection attempts are rejected.
- PL-138: customers and customer requests -> link a NOVARA contact to a work
  item with workspace permissions preserved.
- PL-139: releases -> release objects that link work items without data loss.
- PL-142: reactions and votes -> one toggle per user per item with correct
  counts.
- PL-145: workspace governance / navigation -> hidden navigation cannot be
  reached through its direct URL (server-side visibility + role guard).
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, WorkspaceMember, new_id, now
from ..permissions import (
    CONTACT_READ, CONTACT_WRITE, NOTE_WRITE, TASK_READ, TASK_WRITE,
    WORKSPACE_MANAGE, has_permission,
)

INTAKE_FORM_CREATED = "workspace_tools.intake_form_created"
INTAKE_REQUEST_CREATED = "workspace_tools.intake_request_created"
USER_ASSET_CREATED = "workspace_tools.user_asset_created"
WORKSPACE_ASSET_CREATED = "workspace_tools.workspace_asset_created"
STICKY_CREATED = "workspace_tools.sticky_created"
THEME_SAVED = "workspace_tools.theme_saved"
CUSTOMER_LINK_CREATED = "workspace_tools.customer_link_created"
RELEASE_CREATED = "workspace_tools.release_created"
RELEASE_ITEM_ADDED = "workspace_tools.release_item_added"
VOTE_TOGGLED = "workspace_tools.vote_toggled"
NAV_ITEM_CHANGED = "workspace_tools.nav_item_changed"
register_event_types(
    INTAKE_FORM_CREATED, INTAKE_REQUEST_CREATED,
    USER_ASSET_CREATED, WORKSPACE_ASSET_CREATED,
    STICKY_CREATED, THEME_SAVED,
    CUSTOMER_LINK_CREATED, RELEASE_CREATED, RELEASE_ITEM_ADDED,
    VOTE_TOGGLED, NAV_ITEM_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/workspace-tools",
    tags=["workspace-tools"],
)

# Token-scoped public router: an external form posts here with its form token,
# never with a bearer session. Only intake submission is exposed this way.
public_router = APIRouter(prefix="/api/v1/intake", tags=["intake-submission"])


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class IntakeForm(Base):
    __tablename__ = "pwt_intake_forms"
    __table_args__ = (UniqueConstraint("workspace_id", "token", name="uq_pwt_intake_token"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)  # [{key,type,required}]
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IntakeRequest(Base):
    __tablename__ = "pwt_intake_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("pwt_intake_forms.id"), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class UserAsset(Base):
    __tablename__ = "pwt_user_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False, default=0)
    ref: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkspaceAsset(Base):
    __tablename__ = "pwt_workspace_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False, default=0)
    ref: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Sticky(Base):
    __tablename__ = "pwt_stickies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="yellow", nullable=False)
    formatted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ThemePreference(Base):
    __tablename__ = "pwt_theme_preferences"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", "scope", name="uq_pwt_theme_scope"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # user/workspace
    mode: Mapped[str] = mapped_column(String(10), default="light", nullable=False)
    palette: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomerLink(Base):
    __tablename__ = "pwt_customer_links"
    __table_args__ = (UniqueConstraint("workspace_id", "contact_id", "item_id", name="uq_pwt_customer_link"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), default="request", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Release(Base):
    __tablename__ = "pwt_releases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReleaseItem(Base):
    __tablename__ = "pwt_release_items"
    __table_args__ = (UniqueConstraint("workspace_id", "release_id", "item_id", name="uq_pwt_release_item"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    release_id: Mapped[str] = mapped_column(ForeignKey("pwt_releases.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Vote(Base):
    __tablename__ = "pwt_votes"
    __table_args__ = (UniqueConstraint("workspace_id", "item_id", "user_id", name="uq_pwt_vote"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="vote", nullable=False)  # vote/reaction
    value: Mapped[str] = mapped_column(String(40), nullable=False)  # up/down or emoji
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class NavItem(Base):
    __tablename__ = "pwt_nav_items"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_pwt_nav_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    route: Mapped[str] = mapped_column(String(300), nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list)  # [] = all active members
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IntakeFormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    fields: list[dict] = Field(default_factory=list)

    @field_validator("fields")
    @classmethod
    def valid_fields(cls, v: list[dict]) -> list[dict]:
        for f in v:
            if not isinstance(f, dict) or not f.get("key") or f.get("type") not in ("text", "email", "number", "boolean"):
                raise ValueError("each field needs a key and a type of text/email/number/boolean")
        return v


class IntakeSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict = Field(default_factory=dict)


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(default="application/octet-stream", min_length=1, max_length=120)
    size_bytes: int = Field(default=0, ge=0)
    ref: str | None = None


class AssetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    ref: str | None = None


class StickyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    color: str = "yellow"
    formatted: bool = True


class StickyPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    color: str | None = None
    formatted: bool | None = None


class ThemeSave(BaseModel):
    scope: str
    palette: dict = Field(default_factory=dict)

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, v: str) -> str:
        if v not in ("user", "workspace"):
            raise ValueError("scope must be user or workspace")
        return v


class PqlRequest(BaseModel):
    expression: str = Field(min_length=1)
    records: list[dict] = Field(default_factory=list)


class CustomerLinkCreate(BaseModel):
    contact_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    kind: str = "request"


class ReleaseCreate(BaseModel):
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ReleaseItemCreate(BaseModel):
    item_id: str = Field(min_length=1)


class VoteToggle(BaseModel):
    item_id: str = Field(min_length=1)
    kind: str = "vote"
    value: str = Field(min_length=1, max_length=40)

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in ("vote", "reaction"):
            raise ValueError("kind must be vote or reaction")
        return v


class NavItemCreate(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    route: str = Field(min_length=1, max_length=300)
    visible: bool = True
    allowed_roles: list[str] = Field(default_factory=list)


class NavItemPatch(BaseModel):
    label: str | None = None
    route: str | None = None
    visible: bool | None = None
    allowed_roles: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _member(db: Session, workspace_id: str, user_id: str) -> WorkspaceMember | None:
    return db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == "active",
    )).scalar_one_or_none()


def _item_in_workspace(db: Session, workspace_id: str, item_id: str):
    """Resolve a work item lazily to avoid an import cycle with the projects module."""
    from .projects import ProjectItem
    return db.execute(select(ProjectItem).where(
        ProjectItem.workspace_id == workspace_id, ProjectItem.id == item_id,
    )).scalar_one_or_none()


def _user_asset_or_404(db: Session, workspace_id: str, owner_id: str, asset_id: str) -> UserAsset:
    row = db.execute(select(UserAsset).where(
        UserAsset.workspace_id == workspace_id, UserAsset.id == asset_id,
        UserAsset.owner_id == owner_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return row


def _workspace_asset_or_404(db: Session, workspace_id: str, asset_id: str) -> WorkspaceAsset:
    row = db.execute(select(WorkspaceAsset).where(
        WorkspaceAsset.workspace_id == workspace_id, WorkspaceAsset.id == asset_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return row


def _sticky_or_404(db: Session, workspace_id: str, owner_id: str, sticky_id: str) -> Sticky:
    row = db.execute(select(Sticky).where(
        Sticky.workspace_id == workspace_id, Sticky.id == sticky_id,
        Sticky.owner_id == owner_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="sticky not found")
    return row


def _release_or_404(db: Session, workspace_id: str, release_id: str) -> Release:
    row = db.execute(select(Release).where(
        Release.workspace_id == workspace_id, Release.id == release_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="release not found")
    return row


def _nav_or_404(db: Session, workspace_id: str, key: str) -> NavItem:
    row = db.execute(select(NavItem).where(
        NavItem.workspace_id == workspace_id, NavItem.key == key,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="navigation item not found")
    return row


# ---------------------------------------------------------------------------
# PL-137: safe PQL filter DSL (never compiles to SQL)
# ---------------------------------------------------------------------------

_PQL_FIELDS = frozenset({"status", "priority", "title", "assignee_id", "project_id", "label"})
_PQL_OPS = {">=": "ge", "<=": "le", "!=": "ne", "=": "eq", ">": "gt", "<": "lt", "CONTAINS": "contains"}
_TOKEN_RE = re.compile(
    r"\s*(?:(?P<lpar>\()|(?P<rpar>\))|(?P<str>\"[^\"]*\"|'[^']*')|"
    r"(?P<op>>=|<=|!=|=|>|<)|(?P<word>[A-Za-z_][A-Za-z0-9_]*)|(?P<num>-?\d+(?:\.\d+)?))"
)


def _pql_tokenize(expression: str) -> list[tuple[str, str]]:
    lowered = expression.lower()
    for marker in (";", "--", "/*", "*/", "drop ", "delete ", "insert ", "update ", "select "):
        if marker in lowered:
            raise ValueError("filter expression contains a forbidden token")
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expression):
        if expression[pos:].strip() == "":
            break
        m = _TOKEN_RE.match(expression, pos)
        if not m:
            raise ValueError("filter expression contains an invalid character")
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "word":
            value = value.upper() if value.upper() == "CONTAINS" else value
        tokens.append((kind, value))
        pos = m.end()
    return tokens


def _pql_parse(expression: str) -> dict:
    tokens = _pql_tokenize(expression)
    idx = 0

    def peek():
        return tokens[idx] if idx < len(tokens) else (None, None)

    def parse_cmp() -> dict:
        nonlocal idx
        kind, word = peek()
        if kind != "word" or word not in _PQL_FIELDS:
            raise ValueError("unknown or unsupported field")
        field = word
        idx += 1
        kind, value = peek()
        if kind == "word" and value == "CONTAINS":
            op_key = "CONTAINS"
            idx += 1
        elif kind == "op":
            op_key = value
            idx += 1
        else:
            raise ValueError("expected a comparison operator")
        kind, val = peek()
        if kind == "str":
            val = val[1:-1]
        elif kind == "num":
            val = float(val) if "." in val else int(val)
        elif kind == "word":
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            else:
                raise ValueError("unsupported value")
        else:
            raise ValueError("expected a literal value")
        idx += 1
        return {"type": "cmp", "field": field, "op": _PQL_OPS[op_key], "value": val}

    def parse_or() -> dict:
        nonlocal idx
        children = [parse_cmp()]
        while peek()[0] == "word" and peek()[1].upper() == "OR":
            idx += 1
            children.append(parse_cmp())
        return children[0] if len(children) == 1 else {"type": "group", "op": "or", "children": children}

    def parse_expr() -> dict:
        nonlocal idx
        if peek()[0] == "lpar":
            idx += 1
            node = parse_or()
            if peek()[0] != "rpar":
                raise ValueError("unbalanced parentheses")
            idx += 1
            return node
        return parse_or()

    # Full grammar: AND of OR-terms, with parenthesis grouping.
    parts = [parse_expr()]
    while peek()[0] == "word" and peek()[1].upper() == "AND":
        idx += 1
        parts.append(parse_expr())
    if idx != len(tokens):
        raise ValueError("unexpected token in filter expression")
    return parts[0] if len(parts) == 1 else {"type": "group", "op": "and", "children": parts}


def _pql_eval(node: dict, record: dict) -> bool:
    if node["type"] == "group":
        results = [_pql_eval(child, record) for child in node["children"]]
        return all(results) if node["op"] == "and" else any(results)
    actual = record.get(node["field"])
    expected = node["value"]
    op = node["op"]
    if op == "contains":
        return str(expected).lower() in str(actual or "").lower()
    if actual is None:
        return False
    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "gt":
            return actual > expected
        if op == "ge":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "le":
            return actual <= expected
    except TypeError:
        return False
    return False


# ---------------------------------------------------------------------------
# PL-089 Intake forms
# ---------------------------------------------------------------------------


@router.post("/intake/forms", status_code=status.HTTP_201_CREATED)
def create_intake_form(
    workspace_id: str, body: IntakeFormCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = IntakeForm(
        workspace_id=workspace_id, name=body.name, token=secrets.token_urlsafe(24),
        fields=body.fields, created_by=principal.user.id,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=INTAKE_FORM_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "token": row.token, "fields": row.fields}


@router.get("/intake/forms")
def list_intake_forms(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(IntakeForm).where(IntakeForm.workspace_id == workspace_id).order_by(IntakeForm.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "token": r.token, "fields": r.fields} for r in rows]


def _validate_intake_payload(fields: list[dict], payload: dict) -> dict:
    for f in fields:
        key = f["key"]
        ftype = f["type"]
        required = bool(f.get("required", False))
        if key not in payload or payload[key] in (None, ""):
            if required:
                raise HTTPException(status_code=422, detail=f"missing required field: {key}")
            continue
        value = payload[key]
        if ftype == "email" and ("@" not in str(value) or "." not in str(value)):
            raise HTTPException(status_code=422, detail=f"invalid email for field: {key}")
        if ftype == "number":
            try:
                float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"invalid number for field: {key}")
        if ftype == "boolean" and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"invalid boolean for field: {key}")
    allowed = {f["key"] for f in fields}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown fields: {sorted(unknown)}")
    return payload


@public_router.post("/{token}/submit", status_code=status.HTTP_201_CREATED)
def submit_intake(token: str, body: IntakeSubmit, db: Session = Depends(get_db)):
    form = db.execute(select(IntakeForm).where(IntakeForm.token == token)).scalar_one_or_none()
    if form is None:
        raise HTTPException(status_code=404, detail="intake form not found")
    payload = _validate_intake_payload(form.fields or [], body.payload)
    row = IntakeRequest(workspace_id=form.workspace_id, form_id=form.id, payload=payload)
    db.add(row)
    publish_event(db, workspace_id=form.workspace_id, event_type=INTAKE_REQUEST_CREATED,
                  entity_id=row.id, actor_id=None, payload={"form_id": form.id})
    db.commit(); db.refresh(row)
    return {"id": row.id, "form_id": form.id, "payload": row.payload, "created_at": row.created_at}


@router.get("/intake/requests")
def list_intake_requests(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(IntakeRequest).where(IntakeRequest.workspace_id == workspace_id).order_by(IntakeRequest.created_at.desc())).scalars().all()
    return [{"id": r.id, "form_id": r.form_id, "payload": r.payload, "created_at": r.created_at} for r in rows]


# ---------------------------------------------------------------------------
# PL-091 User assets
# ---------------------------------------------------------------------------


@router.post("/user-assets", status_code=status.HTTP_201_CREATED)
def create_user_asset(
    workspace_id: str, body: AssetCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = UserAsset(
        workspace_id=workspace_id, owner_id=principal.user.id, name=body.name,
        content_type=body.content_type, size_bytes=body.size_bytes, ref=body.ref,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=USER_ASSET_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "owner_id": row.owner_id, "content_type": row.content_type}


@router.get("/user-assets")
def list_user_assets(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(UserAsset).where(
        UserAsset.workspace_id == workspace_id, UserAsset.owner_id == principal.user.id,
    ).order_by(UserAsset.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "content_type": r.content_type, "size_bytes": r.size_bytes, "ref": r.ref} for r in rows]


@router.patch("/user-assets/{asset_id}")
def update_user_asset(
    workspace_id: str, asset_id: str, body: AssetPatch,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _user_asset_or_404(db, workspace_id, principal.user.id, asset_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "ref": row.ref}


@router.delete("/user-assets/{asset_id}", status_code=status.HTTP_200_OK)
def delete_user_asset(
    workspace_id: str, asset_id: str,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _user_asset_or_404(db, workspace_id, principal.user.id, asset_id)
    db.delete(row); db.commit()
    return {"id": asset_id, "deleted": True}


# ---------------------------------------------------------------------------
# PL-092 Workspace assets
# ---------------------------------------------------------------------------


@router.post("/workspace-assets", status_code=status.HTTP_201_CREATED)
def create_workspace_asset(
    workspace_id: str, body: AssetCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = WorkspaceAsset(
        workspace_id=workspace_id, name=body.name, content_type=body.content_type,
        size_bytes=body.size_bytes, ref=body.ref, uploaded_by=principal.user.id,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=WORKSPACE_ASSET_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "uploaded_by": row.uploaded_by}


@router.get("/workspace-assets")
def list_workspace_assets(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(WorkspaceAsset).where(WorkspaceAsset.workspace_id == workspace_id).order_by(WorkspaceAsset.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "content_type": r.content_type, "size_bytes": r.size_bytes, "uploaded_by": r.uploaded_by} for r in rows]


@router.patch("/workspace-assets/{asset_id}")
def update_workspace_asset(
    workspace_id: str, asset_id: str, body: AssetPatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _workspace_asset_or_404(db, workspace_id, asset_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "ref": row.ref}


@router.delete("/workspace-assets/{asset_id}", status_code=status.HTTP_200_OK)
def delete_workspace_asset(
    workspace_id: str, asset_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _workspace_asset_or_404(db, workspace_id, asset_id)
    db.delete(row); db.commit()
    return {"id": asset_id, "deleted": True}


# ---------------------------------------------------------------------------
# PL-093 Stickies
# ---------------------------------------------------------------------------


@router.post("/stickies", status_code=status.HTTP_201_CREATED)
def create_sticky(
    workspace_id: str, body: StickyCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = Sticky(
        workspace_id=workspace_id, owner_id=principal.user.id, title=body.title,
        body=body.body, color=body.color, formatted=body.formatted,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=STICKY_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"title": body.title})
    db.commit(); db.refresh(row)
    return {"id": row.id, "title": row.title, "color": row.color, "formatted": row.formatted}


@router.get("/stickies")
def list_stickies(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(Sticky).where(
        Sticky.workspace_id == workspace_id, Sticky.owner_id == principal.user.id,
    ).order_by(Sticky.updated_at.desc())).scalars().all()
    return [{"id": r.id, "title": r.title, "body": r.body, "color": r.color, "formatted": r.formatted} for r in rows]


@router.patch("/stickies/{sticky_id}")
def update_sticky(
    workspace_id: str, sticky_id: str, body: StickyPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _sticky_or_404(db, workspace_id, principal.user.id, sticky_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    row.updated_at = now()
    db.commit(); db.refresh(row)
    return {"id": row.id, "title": row.title, "body": row.body, "color": row.color, "formatted": row.formatted}


@router.delete("/stickies/{sticky_id}", status_code=status.HTTP_200_OK)
def delete_sticky(
    workspace_id: str, sticky_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _sticky_or_404(db, workspace_id, principal.user.id, sticky_id)
    db.delete(row); db.commit()
    return {"id": sticky_id, "deleted": True}


# ---------------------------------------------------------------------------
# PL-107 Themes (light theme only)
# ---------------------------------------------------------------------------


@router.put("/themes")
def save_theme(
    workspace_id: str, body: ThemeSave,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if body.scope == "workspace" and not _is_admin(principal):
        raise HTTPException(status_code=403, detail="workspace theme requires workspace manage")
    row = db.execute(select(ThemePreference).where(
        ThemePreference.workspace_id == workspace_id,
        ThemePreference.user_id == principal.user.id,
        ThemePreference.scope == body.scope,
    )).scalar_one_or_none()
    if row is None:
        row = ThemePreference(
            workspace_id=workspace_id, user_id=principal.user.id,
            scope=body.scope, mode="light", palette=body.palette,
        )
        db.add(row)
    else:
        row.palette = body.palette
        row.mode = "light"
        row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=THEME_SAVED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"scope": body.scope, "mode": "light"})
    db.commit(); db.refresh(row)
    return {"scope": row.scope, "mode": row.mode, "palette": row.palette}


@router.get("/themes")
def get_theme(
    workspace_id: str, scope: str = Query("user"),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if scope not in ("user", "workspace"):
        raise HTTPException(status_code=422, detail="scope must be user or workspace")
    row = db.execute(select(ThemePreference).where(
        ThemePreference.workspace_id == workspace_id,
        ThemePreference.user_id == principal.user.id,
        ThemePreference.scope == scope,
    )).scalar_one_or_none()
    if row is None:
        return {"scope": scope, "mode": "light", "palette": {}, "default": True}
    return {"scope": row.scope, "mode": row.mode, "palette": row.palette, "default": False}


def _is_admin(principal: Principal) -> bool:
    return principal.role in ("owner", "admin")


# ---------------------------------------------------------------------------
# PL-137 PQL
# ---------------------------------------------------------------------------


@router.post("/pql/parse")
def pql_parse(
    workspace_id: str, body: PqlRequest,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    try:
        ast = _pql_parse(body.expression)
    except (ValueError, IndexError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid filter expression: {exc}")
    return {"ast": ast, "sql_generated": False}


@router.post("/pql/evaluate")
def pql_evaluate(
    workspace_id: str, body: PqlRequest,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    try:
        ast = _pql_parse(body.expression)
    except (ValueError, IndexError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid filter expression: {exc}")
    matched = [r for r in body.records if _pql_eval(ast, r)]
    return {"matched": matched, "count": len(matched), "sql_generated": False}


# ---------------------------------------------------------------------------
# PL-138 Customers and customer requests
# ---------------------------------------------------------------------------


@router.post("/customers/links", status_code=status.HTTP_201_CREATED)
def link_customer(
    workspace_id: str, body: CustomerLinkCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    # Contact permissions are preserved: linking needs contact:read as well as
    # contact:write. Custom roles were already checked by require(CONTACT_WRITE).
    if not principal.role.startswith("custom:") and not has_permission(principal.role, CONTACT_READ):
        raise HTTPException(status_code=403, detail="contact read permission required")
    contact = db.execute(select(Contact).where(
        Contact.workspace_id == workspace_id, Contact.id == body.contact_id,
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found in workspace")
    if _item_in_workspace(db, workspace_id, body.item_id) is None:
        raise HTTPException(status_code=404, detail="work item not found in workspace")
    exists = db.execute(select(CustomerLink).where(
        CustomerLink.workspace_id == workspace_id,
        CustomerLink.contact_id == body.contact_id, CustomerLink.item_id == body.item_id,
    )).scalar_one_or_none()
    if exists:
        return {"id": exists.id, "contact_id": body.contact_id, "item_id": body.item_id, "linked": False}
    row = CustomerLink(
        workspace_id=workspace_id, contact_id=body.contact_id, item_id=body.item_id,
        kind=body.kind, created_by=principal.user.id,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=CUSTOMER_LINK_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"contact_id": body.contact_id, "item_id": body.item_id})
    db.commit(); db.refresh(row)
    return {"id": row.id, "contact_id": body.contact_id, "item_id": body.item_id, "linked": True}


@router.get("/customers/links")
def list_customer_links(
    workspace_id: str, contact_id: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = select(CustomerLink).where(CustomerLink.workspace_id == workspace_id)
    if contact_id:
        q = q.where(CustomerLink.contact_id == contact_id)
    rows = db.execute(q.order_by(CustomerLink.created_at.desc())).scalars().all()
    return [{"id": r.id, "contact_id": r.contact_id, "item_id": r.item_id, "kind": r.kind} for r in rows]


# ---------------------------------------------------------------------------
# PL-139 Releases
# ---------------------------------------------------------------------------


@router.post("/releases", status_code=status.HTTP_201_CREATED)
def create_release(
    workspace_id: str, body: ReleaseCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = Release(
        workspace_id=workspace_id, project_id=body.project_id, name=body.name,
        description=body.description, created_by=principal.user.id,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=RELEASE_CREATED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"project_id": body.project_id, "name": body.name})
    db.commit(); db.refresh(row)
    return {"id": row.id, "project_id": row.project_id, "name": row.name, "status": row.status}


@router.post("/releases/{release_id}/items", status_code=status.HTTP_201_CREATED)
def add_release_item(
    workspace_id: str, release_id: str, body: ReleaseItemCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    release = _release_or_404(db, workspace_id, release_id)
    if _item_in_workspace(db, workspace_id, body.item_id) is None:
        raise HTTPException(status_code=404, detail="work item not found in workspace")
    exists = db.execute(select(ReleaseItem).where(
        ReleaseItem.workspace_id == workspace_id,
        ReleaseItem.release_id == release_id, ReleaseItem.item_id == body.item_id,
    )).scalar_one_or_none()
    if exists:
        return {"release_id": release_id, "item_id": body.item_id, "added": False}
    db.add(ReleaseItem(workspace_id=workspace_id, release_id=release_id, item_id=body.item_id))
    publish_event(db, workspace_id=workspace_id, event_type=RELEASE_ITEM_ADDED,
                  entity_id=release_id, actor_id=principal.user.id, payload={"item_id": body.item_id})
    db.commit()
    return {"release_id": release_id, "item_id": body.item_id, "added": True}


@router.get("/releases")
def list_releases(
    workspace_id: str, project_id: str | None = None,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = select(Release).where(Release.workspace_id == workspace_id)
    if project_id:
        q = q.where(Release.project_id == project_id)
    rows = db.execute(q.order_by(Release.created_at.desc())).scalars().all()
    out = []
    for r in rows:
        items = db.execute(select(ReleaseItem.item_id).where(
            ReleaseItem.workspace_id == workspace_id, ReleaseItem.release_id == r.id,
        )).scalars().all()
        out.append({"id": r.id, "project_id": r.project_id, "name": r.name, "status": r.status, "item_ids": list(items)})
    return out


# ---------------------------------------------------------------------------
# PL-142 Reactions and votes
# ---------------------------------------------------------------------------


@router.post("/votes/toggle")
def toggle_vote(
    workspace_id: str, body: VoteToggle,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if _item_in_workspace(db, workspace_id, body.item_id) is None:
        raise HTTPException(status_code=404, detail="work item not found in workspace")
    existing = db.execute(select(Vote).where(
        Vote.workspace_id == workspace_id, Vote.item_id == body.item_id,
        Vote.user_id == principal.user.id,
    )).scalar_one_or_none()
    if existing is not None and existing.value == body.value and existing.kind == body.kind:
        db.delete(existing); db.commit()
        return {"item_id": body.item_id, "value": body.value, "active": False}
    if existing is None:
        db.add(Vote(workspace_id=workspace_id, item_id=body.item_id, user_id=principal.user.id,
                    kind=body.kind, value=body.value))
    else:
        existing.kind = body.kind; existing.value = body.value
    publish_event(db, workspace_id=workspace_id, event_type=VOTE_TOGGLED,
                  entity_id=body.item_id, actor_id=principal.user.id, payload={"value": body.value, "kind": body.kind})
    db.commit()
    return {"item_id": body.item_id, "value": body.value, "active": True}


@router.get("/votes/counts")
def vote_counts(
    workspace_id: str, item_id: str = Query(...),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(Vote).where(
        Vote.workspace_id == workspace_id, Vote.item_id == item_id,
    )).scalars().all()
    counts: dict[str, int] = {}
    for r in rows:
        key = f"{r.kind}:{r.value}"
        counts[key] = counts.get(key, 0) + 1
    return {"item_id": item_id, "counts": counts, "total": len(rows)}


# ---------------------------------------------------------------------------
# PL-145 Workspace governance / navigation
# ---------------------------------------------------------------------------


@router.post("/nav", status_code=status.HTTP_201_CREATED)
def create_nav_item(
    workspace_id: str, body: NavItemCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(NavItem).where(
        NavItem.workspace_id == workspace_id, NavItem.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="navigation key exists")
    row = NavItem(
        workspace_id=workspace_id, key=body.key, label=body.label, route=body.route,
        visible=body.visible, allowed_roles=body.allowed_roles,
    )
    db.add(row)
    publish_event(db, workspace_id=workspace_id, event_type=NAV_ITEM_CHANGED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"key": body.key, "visible": body.visible})
    db.commit(); db.refresh(row)
    return {"id": row.id, "key": row.key, "route": row.route, "visible": row.visible}


@router.get("/nav")
def list_nav(
    workspace_id: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(NavItem).where(NavItem.workspace_id == workspace_id).order_by(NavItem.key)).scalars().all()
    out = []
    for r in rows:
        role_ok = not r.allowed_roles or principal.role in r.allowed_roles or principal.role == "owner"
        if r.visible and role_ok:
            out.append({"key": r.key, "label": r.label, "route": r.route})
    return out


@router.patch("/nav/{key}")
def update_nav_item(
    workspace_id: str, key: str, body: NavItemPatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = _nav_or_404(db, workspace_id, key)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    row.updated_at = now()
    publish_event(db, workspace_id=workspace_id, event_type=NAV_ITEM_CHANGED,
                  entity_id=row.id, actor_id=principal.user.id, payload={"key": key, "fields": sorted(data)})
    db.commit(); db.refresh(row)
    return {"key": row.key, "route": row.route, "visible": row.visible, "allowed_roles": row.allowed_roles}


@router.get("/nav/target/{key}")
def nav_target(
    workspace_id: str, key: str,
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
):
    """Direct-URL guard: a hidden or disallowed navigation target is unreachable."""
    verify_workspace(principal, workspace_id)
    row = _nav_or_404(db, workspace_id, key)
    if not row.visible:
        raise HTTPException(status_code=404, detail="navigation target not available")
    role_ok = principal.role == "owner" or not row.allowed_roles or principal.role in row.allowed_roles
    if not role_ok:
        raise HTTPException(status_code=403, detail="navigation target forbidden for role")
    return {"key": row.key, "label": row.label, "route": row.route}
