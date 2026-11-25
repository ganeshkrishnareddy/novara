"""Experimentation platform API governance and default roles (GrowthBook P2).

Clean-room implementation of GB-061 (generated OpenAPI contract), GB-062
(broad REST route surface), GB-065/066 (personal and server API credentials via
NOVARA's existing scoped API-key layer) and GB-067 (default experimentation
roles).

This module does not copy GrowthBook source and does not contact a hosted
platform. It reports the real NOVARA OpenAPI schema, stores workspace-scoped
role bindings and reuses the existing one-time-secret API-key implementation.
No secret, key hash or full credential is ever returned by these endpoints.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import (
    ALL,
    CONTACT_READ,
    CONTACT_WRITE,
    EVENT_READ,
    NOTE_WRITE,
    WORKSPACE_MANAGE,
)

ROLE_BOUND = "experiment.role_bound"
register_event_types(ROLE_BOUND)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-platform",
    tags=["experiment-platform"],
)

# The six default roles use NOVARA's existing permission vocabulary. They are
# intentionally narrower than the global admin role: experimentation access
# never implies membership management or outreach delivery.
DEFAULT_ROLES: dict[str, frozenset[str]] = {
    "noaccess": frozenset(),
    "readonly": frozenset({CONTACT_READ, EVENT_READ}),
    "collaborator": frozenset({CONTACT_READ, CONTACT_WRITE, NOTE_WRITE, EVENT_READ}),
    "engineer": frozenset(
        {CONTACT_READ, CONTACT_WRITE, NOTE_WRITE, EVENT_READ, WORKSPACE_MANAGE}
    ),
    "analyst": frozenset({CONTACT_READ, NOTE_WRITE, EVENT_READ}),
    "admin": frozenset({ALL}),
}

ROUTE_PREFIXES = (
    "experiment-platform",
    "experiment-ops",
    "experiment-queries",
    "experiment-stats",
    "flags",
    "api-keys",
    "analytics",
    "jobs",
)


class ExperimentRoleBinding(Base):
    __tablename__ = "experiment_role_bindings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_experiment_role_workspace_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class RoleBindingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=36)
    role: str

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        role = (value or "").strip().lower()
        if role not in DEFAULT_ROLES:
            raise ValueError("unsupported experimentation role")
        return role


def _openapi_status() -> dict:
    """Inspect the real generated OpenAPI document; never a hand-written list."""
    from ..main import app

    spec = app.openapi()
    paths = [path for path in spec.get("paths", {}) if any(
        f"/{prefix}" in path for prefix in ROUTE_PREFIXES
    )]
    operations: list[str] = []
    for path, methods in spec.get("paths", {}).items():
        if not any(f"/{prefix}" in path for prefix in ROUTE_PREFIXES):
            continue
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operations.append(operation.get("operationId") or f"{method}:{path}")
    present = sorted({prefix for prefix in ROUTE_PREFIXES if any(
        f"/{prefix}" in path for path in paths
    )})
    return {
        "openapi_version": spec.get("openapi"),
        "generated_from_live_app": True,
        "route_prefixes": list(ROUTE_PREFIXES),
        "present_route_modules": present,
        "path_count": len(paths),
        "operation_count": len(operations),
        "unique_operation_ids": len(set(operations)) == len(operations),
        "clean": bool(spec.get("openapi")) and len(set(operations)) == len(operations),
    }


@router.get("/api-contract", operation_id="experimentPlatformContract")
def api_contract() -> dict:
    return {
        "version": "1",
        "legacy_versions": [],
        "delivery": "local-only",
        "resources": ["openapiStatus", "restRouteInventory", "credentials", "roleBindings"],
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-platform",
        "default_roles": sorted(DEFAULT_ROLES),
        "credential_layers": ["personal_access_token", "server_api_key"],
    }


@router.get("/openapi-status", operation_id="experimentOpenApiStatus")
def openapi_status() -> dict:
    """GB-061: the generated document is the authority, not a static claim."""
    return _openapi_status()


@router.get("/rest-inventory", operation_id="experimentRestInventory")
def rest_inventory() -> dict:
    """GB-062: count real operations across the experimentation route modules."""
    result = _openapi_status()
    return {
        "operation_count": result["operation_count"],
        "path_count": result["path_count"],
        "unique_operation_ids": result["unique_operation_ids"],
        "route_modules": result["present_route_modules"],
        "minimum_expected_operations": 40,
        "meets_minimum": result["operation_count"] >= 40,
    }


@router.get("/credentials", operation_id="experimentCredentialPolicies")
def credential_policies() -> dict:
    """GB-065/066: describe the existing local credential layers honestly."""
    return {
        "personal_access_token": {
            "implementation": "novara_core.modules.api_keys.ApiKey",
            "user_owned": True,
            "secret_returned_once": True,
            "stored_form": "SHA-256 hash plus short prefix",
            "management": "bearer-only; a key cannot mint, rotate or revoke another key",
            "external_provider": False,
        },
        "server_api_key": {
            "implementation": "novara_core.modules.api_keys.ApiKey",
            "issuer": "workspace manager",
            "secret_returned_once": True,
            "stored_form": "SHA-256 hash plus short prefix",
            "scopes": "explicit permission list; wildcard is never granted",
            "external_provider": False,
        },
    }


@router.get("/roles", operation_id="listExperimentRoles")
def list_roles() -> list[dict]:
    """GB-067: the six default experimentation roles and their permissions."""
    return [
        {"role": role, "permissions": sorted(permissions)}
        for role, permissions in DEFAULT_ROLES.items()
    ]


@router.get("/roles/can", operation_id="checkExperimentRolePermission")
def role_can(
    role: str = Query(min_length=1, max_length=32),
    permission: str = Query(min_length=1, max_length=64),
) -> dict:
    normalized = role.strip().lower()
    if normalized not in DEFAULT_ROLES:
        raise HTTPException(status_code=422, detail="unsupported experimentation role")
    permissions = DEFAULT_ROLES[normalized]
    allowed = ALL in permissions or permission in permissions
    return {"role": normalized, "permission": permission, "allowed": allowed}


@router.post("/roles/bindings", status_code=status.HTTP_201_CREATED,
             operation_id="bindExperimentRole")
def bind_role(workspace_id: str, body: RoleBindingIn,
              principal: Principal = Depends(require(WORKSPACE_MANAGE)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    from ..models import WorkspaceMember

    member = db.execute(select(WorkspaceMember).where(
        WorkspaceMember.user_id == body.user_id,
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.status == "active",
    )).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="workspace member not found")
    existing = db.execute(select(ExperimentRoleBinding).where(
        ExperimentRoleBinding.workspace_id == workspace_id,
        ExperimentRoleBinding.user_id == body.user_id,
    )).scalar_one_or_none()
    if existing is not None:
        existing.role = body.role
        row = existing
    else:
        row = ExperimentRoleBinding(
            id=new_id(), workspace_id=workspace_id, user_id=body.user_id,
            role=body.role, created_at=now(),
        )
        db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=ROLE_BOUND,
        entity_id=row.id, payload={"user_id": row.user_id, "role": row.role},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": row.id, "user_id": row.user_id, "role": row.role}


@router.get("/roles/bindings", operation_id="listExperimentRoleBindings")
def list_bindings(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentRoleBinding).where(
        ExperimentRoleBinding.workspace_id == workspace_id
    ).order_by(ExperimentRoleBinding.role, ExperimentRoleBinding.user_id)).scalars().all()
    return [{"id": r.id, "user_id": r.user_id, "role": r.role} for r in rows]
