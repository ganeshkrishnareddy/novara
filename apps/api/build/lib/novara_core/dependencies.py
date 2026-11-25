"""FastAPI dependencies that establish an authenticated, workspace-scoped
principal. Client-supplied user ids are never accepted as identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Session as SessionModel
from .models import User, WorkspaceMember, now
from .permissions import has_permission
from .security import hash_token, session_by_access


@dataclass(frozen=True)
class Principal:
    user: User
    workspace_id: str
    role: str
    member: WorkspaceMember
    session: SessionModel | None
    # Set only for an X-API-Key principal. Bearer sessions always leave these
    # as None, so existing role semantics are unchanged.
    api_key_id: str | None = None
    api_key_scopes: tuple[str, ...] | None = None


def bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _expired(value: datetime | None) -> bool:
    """Compare expiry with the current UTC time across naive/aware values.

    SQLite drops timezone info on DATETIME columns, so a stored timestamp may
    come back naive while ``now()`` is timezone-aware. Treat both as UTC.
    """
    if value is None:
        return False
    current = now()
    if value.tzinfo is None and current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    elif value.tzinfo is not None and current.tzinfo is None:
        value = value.replace(tzinfo=None)
    return value <= current


def _api_key_principal(db: Session, raw_key: str) -> Principal:
    # Local import keeps the module dependency acyclic: api_keys.py consumes
    # this module's Principal/require contracts.
    from .modules.api_keys import ApiKey

    row = db.execute(
        select(ApiKey).where(ApiKey.secret_hash == hash_token(raw_key))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None or _expired(row.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="account is inactive")
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == row.workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=403, detail="no active membership in this workspace")
    row.last_used_at = now()
    db.commit()
    return Principal(
        user=user,
        workspace_id=row.workspace_id,
        role=member.role,
        member=member,
        session=None,
        api_key_id=row.id,
        api_key_scopes=tuple(row.scopes or ()),
    )


def get_principal(
    db: Session = Depends(get_db),
    token: str | None = Depends(bearer_token),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    session = session_by_access(db, token)
    if session is None:
        if x_api_key is not None:
            return _api_key_principal(db, x_api_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="account is inactive")
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == session.workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=403, detail="no active membership in this workspace")
    return Principal(
        user=user,
        workspace_id=session.workspace_id,
        role=member.role,
        member=member,
        session=session,
    )


def require(permission: str):
    """Build a dependency that checks a workspace-scoped permission."""

    def dependency(
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        if principal.api_key_id is not None and permission not in (principal.api_key_scopes or ()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"permission required: {permission}",
            )
        role = principal.role
        allowed = False
        if role.startswith("custom:"):
            try:
                from .modules.access_governance import role_has_permission
                allowed = role_has_permission(db, principal.workspace_id, role, permission)
            except Exception:
                allowed = False
        else:
            allowed = has_permission(role, permission)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"permission required: {permission}",
            )
        return principal

    return dependency


def verify_workspace(principal: Principal, workspace_id: str) -> None:
    """Fail closed when a route's workspace path does not match the verified
    workspace of the session. Every workspace-scoped endpoint must call this."""
    if principal.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="cross-workspace access is denied")
