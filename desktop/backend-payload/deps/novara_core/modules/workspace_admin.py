"""Workspace administration surface (PL-001, clean-room).

A workspace is the tenant boundary for members, projects and settings. This
module adds the missing administration pieces on top of the existing create,
switch and membership routes: a persistent, workspace-scoped settings record
and a live admin summary. Feature flags are owned by :mod:`feature_flags` and
members by the core app; both remain on the same one API surface.

Only non-sensitive settings are accepted. No global administrator exists and
every route verifies that the session's workspace matches the path.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, JSON, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Workspace, WorkspaceMember, new_id, now
from ..permissions import CONTACT_READ, WORKSPACE_MANAGE

WORKSPACE_SETTINGS_UPDATED = "workspace.settings_updated"
register_event_types(WORKSPACE_SETTINGS_UPDATED)

# Keys that may never be stored in a workspace settings record. The same
# non-sensitive-only rule is applied by the integrations module.
_SECRET_FIELD_NAMES = frozenset(
    {
        "apikey", "apikeys", "token", "tokens", "accesstoken", "refreshtoken",
        "secret", "secrets", "clientsecret", "password", "passwords",
        "credential", "credentials", "privatekey", "authorization",
    }
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/admin",
    tags=["workspaces"],
)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class WorkspaceSetting(Base):
    """One settings row per workspace; absent row means documented defaults."""

    __tablename__ = "workspace_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _normalise_key(key: object) -> str:
    return "".join(character for character in str(key).lower() if character.isalnum())


def _reject_secret_fields(value: object, path: str = "settings") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalise_key(key) in _SECRET_FIELD_NAMES:
                raise ValueError(f"secret field is not accepted: {path}.{key}")
            _reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, f"{path}[{index}]")


class SettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    settings: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("settings")
    @classmethod
    def settings_must_be_non_sensitive(cls, value: dict) -> dict:
        _reject_secret_fields(value)
        return value


class SettingsOut(BaseModel):
    workspace_id: str
    name: str
    settings: dict
    updated_at: datetime | None = None
    updated_by: str | None = None


class AdminSummaryOut(BaseModel):
    workspace_id: str
    name: str
    role: str
    active_members: int
    enabled_flags: int
    configured_integrations: int
    recorded_adapter_calls: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _workspace_or_404(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return workspace


def _settings_row(db: Session, workspace_id: str) -> WorkspaceSetting | None:
    return db.execute(
        select(WorkspaceSetting).where(WorkspaceSetting.workspace_id == workspace_id)
    ).scalar_one_or_none()


def _count(db: Session, statement) -> int:
    return int(db.execute(statement).scalar_one() or 0)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=SettingsOut)
def get_settings(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> SettingsOut:
    verify_workspace(principal, workspace_id)
    workspace = _workspace_or_404(db, workspace_id)
    row = _settings_row(db, workspace_id)
    return SettingsOut(
        workspace_id=workspace_id,
        name=workspace.name,
        settings=row.settings if row else {},
        updated_at=row.updated_at if row else None,
        updated_by=row.updated_by if row else None,
    )


@router.patch("/settings", response_model=SettingsOut)
def update_settings(
    workspace_id: str,
    body: SettingsUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> SettingsOut:
    verify_workspace(principal, workspace_id)
    workspace = _workspace_or_404(db, workspace_id)
    if body.name is not None:
        workspace.name = body.name.strip()
    row = _settings_row(db, workspace_id)
    if row is None:
        row = WorkspaceSetting(
            id=new_id(),
            workspace_id=workspace_id,
            settings=dict(body.settings),
            updated_by=principal.user.id,
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
    else:
        row.settings = dict(body.settings)
        row.updated_by = principal.user.id
        row.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=WORKSPACE_SETTINGS_UPDATED,
        entity_id=workspace.id,
        payload={"fields": sorted(k for k in ("name", "settings") if k in body.model_dump(exclude_unset=True))},
        actor_id=principal.user.id,
    )
    db.commit()
    return SettingsOut(
        workspace_id=workspace_id,
        name=workspace.name,
        settings=row.settings,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


@router.get("/summary", response_model=AdminSummaryOut)
def admin_summary(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> AdminSummaryOut:
    """Live counts from the shared tables; nothing cached or estimated."""
    verify_workspace(principal, workspace_id)
    workspace = _workspace_or_404(db, workspace_id)

    # Imports are local to avoid an import cycle with the module registry.
    from .adapters import AdapterCall
    from .feature_flags import FeatureFlag
    from .integrations import Integration

    return AdminSummaryOut(
        workspace_id=workspace_id,
        name=workspace.name,
        role=principal.role,
        active_members=_count(
            db,
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.status == "active",
            ),
        ),
        enabled_flags=_count(
            db,
            select(func.count())
            .select_from(FeatureFlag)
            .where(
                FeatureFlag.workspace_id == workspace_id,
                FeatureFlag.enabled.is_(True),
            ),
        ),
        configured_integrations=_count(
            db,
            select(func.count())
            .select_from(Integration)
            .where(
                Integration.workspace_id == workspace_id,
                Integration.status == "configured",
            ),
        ),
        recorded_adapter_calls=_count(
            db,
            select(func.count())
            .select_from(AdapterCall)
            .where(AdapterCall.workspace_id == workspace_id),
        ),
    )
