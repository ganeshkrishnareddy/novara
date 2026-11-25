"""Workspace API keys / personal access tokens (PL-045, PL-070).

Keys are bearer-independent credentials for API clients. The full secret is
returned exactly once at creation or rotation; the database holds only its
SHA-256 hash plus a short, human-readable prefix. Every request made with a key
is constrained to the key's explicit permission scopes, its owning workspace,
and the lifetime/revocation state of the key itself. Key management is always
bearer-only: a key can never mint, rotate or revoke another key.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .. import permissions as permission_constants
from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import ALL, WORKSPACE_MANAGE, has_permission
from ..security import hash_token

API_KEY_CREATED = "api_key.created"
API_KEY_ROTATED = "api_key.rotated"
API_KEY_REVOKED = "api_key.revoked"
register_event_types(API_KEY_CREATED, API_KEY_ROTATED, API_KEY_REVOKED)

# Every string exposed by novara_core.permissions is a valid scope name; the
# wildcard ALL is deliberately excluded at validation time (a key is never a
# blanket grant, even for an owner).
KNOWN_PERMISSIONS: frozenset[str] = frozenset(
    value
    for name, value in vars(permission_constants).items()
    if name.isupper() and isinstance(value, str)
)

TOKEN_PREFIX = "nvk_"

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/api-keys",
    tags=["api-keys"],
)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class ApiKey(Base):
    """A scoped, revocable API credential. Plaintext secrets are never stored."""

    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("workspace_id", "prefix", name="uq_api_key_workspace_prefix"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("API key name must not be empty")
        return stripped


class ApiKeyRotate(BaseModel):
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ApiKeyOut(BaseModel):
    """Metadata only: no hash, no prefix-derived secret, no plaintext."""

    id: str
    workspace_id: str
    name: str
    prefix: str
    scopes: list[str]
    created_by: str
    created_at: object
    expires_at: object | None
    last_used_at: object | None
    revoked_at: object | None

    model_config = ConfigDict(from_attributes=True)


class ApiKeyIssuedOut(BaseModel):
    """Creation/rotation response: the one and only time a secret is shown."""

    id: str
    workspace_id: str
    name: str
    prefix: str
    scopes: list[str]
    created_by: str
    created_at: object
    expires_at: object | None
    secret: str


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise caller-supplied timestamps to UTC before persisting."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_scopes(scopes: list[str], role: str) -> list[str]:
    if not scopes:
        raise HTTPException(status_code=422, detail="at least one scope is required")
    if len(set(scopes)) != len(scopes):
        raise HTTPException(status_code=422, detail="duplicate API key scopes are not allowed")
    if ALL in scopes or any(scope not in KNOWN_PERMISSIONS for scope in scopes):
        raise HTTPException(status_code=422, detail="unknown or unsupported API key scope")
    for scope in scopes:
        if not has_permission(role, scope):
            raise HTTPException(status_code=403, detail=f"scope not held by caller: {scope}")
    return list(scopes)


def _bearer_only(principal: Principal) -> None:
    """Key management may only be performed by a live user session."""
    if principal.api_key_id is not None:
        raise HTTPException(
            status_code=403,
            detail="a bearer session is required to manage API keys",
        )


def _new_prefix(db: Session, workspace_id: str, exclude_id: str | None = None) -> str:
    """Return an unused short prefix for this workspace."""
    for _ in range(10):
        candidate = TOKEN_PREFIX + secrets.token_urlsafe(6)[:8]
        query = select(ApiKey.id).where(
            ApiKey.workspace_id == workspace_id,
            ApiKey.prefix == candidate,
        )
        if exclude_id is not None:
            query = query.where(ApiKey.id != exclude_id)
        if db.execute(query).scalar_one_or_none() is None:
            return candidate
    raise HTTPException(status_code=409, detail="could not allocate a unique API key prefix")


def _issue_secret(db: Session, workspace_id: str, exclude_id: str | None = None) -> tuple[str, str, str]:
    prefix = _new_prefix(db, workspace_id, exclude_id=exclude_id)
    secret = f"{prefix}_{secrets.token_urlsafe(32)}"
    return prefix, secret, hash_token(secret)


def _key_or_404(db: Session, workspace_id: str, key_id: str) -> ApiKey:
    row = db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiKeyIssuedOut, status_code=status.HTTP_201_CREATED)
def create_api_key(
    workspace_id: str,
    body: ApiKeyCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _bearer_only(principal)
    scopes = _validate_scopes(body.scopes, principal.role)
    prefix, secret, secret_hash = _issue_secret(db, workspace_id)
    created_at = now()
    row = ApiKey(
        id=new_id(),
        workspace_id=workspace_id,
        user_id=principal.user.id,
        name=body.name,
        prefix=prefix,
        secret_hash=secret_hash,
        scopes=scopes,
        created_by=principal.user.id,
        created_at=created_at,
        expires_at=_as_utc(body.expires_at),
        last_used_at=None,
        revoked_at=None,
    )
    db.add(row)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=API_KEY_CREATED,
        entity_id=row.id,
        payload={"name": row.name, "prefix": row.prefix, "scopes": row.scopes},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "prefix": row.prefix,
        "scopes": row.scopes,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "secret": secret,
    }


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ApiKey)
        .where(ApiKey.workspace_id == workspace_id)
        .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    ).scalars().all()


@router.get("/{key_id}", response_model=ApiKeyOut)
def get_api_key(
    workspace_id: str,
    key_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ApiKey:
    verify_workspace(principal, workspace_id)
    return _key_or_404(db, workspace_id, key_id)


@router.post("/{key_id}/rotate", response_model=ApiKeyIssuedOut)
def rotate_api_key(
    workspace_id: str,
    key_id: str,
    body: ApiKeyRotate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _bearer_only(principal)
    row = _key_or_404(db, workspace_id, key_id)
    prefix, secret, secret_hash = _issue_secret(db, workspace_id, exclude_id=row.id)
    row.prefix = prefix
    row.secret_hash = secret_hash
    row.created_at = now()
    row.revoked_at = None
    # An omitted expiry preserves the existing one; an explicit null clears it.
    if body.expires_at is not None:
        row.expires_at = _as_utc(body.expires_at)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=API_KEY_ROTATED,
        entity_id=row.id,
        payload={"name": row.name, "prefix": row.prefix},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "prefix": row.prefix,
        "scopes": row.scopes,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "secret": secret,
    }


@router.delete("/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(
    workspace_id: str,
    key_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ApiKey:
    verify_workspace(principal, workspace_id)
    _bearer_only(principal)
    row = _key_or_404(db, workspace_id, key_id)
    row.revoked_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=API_KEY_REVOKED,
        entity_id=row.id,
        payload={"name": row.name, "prefix": row.prefix},
        actor_id=principal.user.id,
    )
    db.commit()
    return row


__all__ = [
    "API_KEY_CREATED",
    "API_KEY_ROTATED",
    "API_KEY_REVOKED",
    "ApiKey",
    "KNOWN_PERMISSIONS",
    "router",
]
