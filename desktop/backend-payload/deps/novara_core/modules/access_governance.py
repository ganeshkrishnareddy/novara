"""Clean-room access governance (CW-130/CW-139/PL-124/PL-125/NV-070).

Implements documented/public behaviour only:
- CW-130/PL-124: workspace-scoped custom roles with allow-listed permissions.
- PL-125: reusable permission schemes assignable to projects.
- NV-070: fine-grained notification/workflow/integration/webhook/billing
  permission mappings enforced by NOVARA's own checks.
- CW-139: immutable audit query/export over the real append-only event spine.

No upstream source is copied. No external service, licence server or hosted
control plane is contacted. IP data is never invented; only fields actually
stored in events are returned.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, get_principal, require, verify_workspace
from ..events import Event, publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import (
    ALL,
    AUDIT_READ,
    BILLING_READ,
    BILLING_WRITE,
    INTEGRATION_READ,
    INTEGRATION_WRITE,
    NOTIFICATION_WORKFLOW_READ,
    NOTIFICATION_WORKFLOW_WRITE,
    ROLE_PERMISSIONS,
    WEBHOOK_READ,
    WEBHOOK_WRITE,
    WORKSPACE_MANAGE,
    has_permission,
)

CUSTOM_ROLE_CREATED = "access.custom_role_created"
CUSTOM_ROLE_UPDATED = "access.custom_role_updated"
CUSTOM_ROLE_DELETED = "access.custom_role_deleted"
CUSTOM_ROLE_ASSIGNED = "access.custom_role_assigned"
CUSTOM_ROLE_REVOKED = "access.custom_role_revoked"
PERMISSION_SCHEME_CREATED = "access.permission_scheme_created"
PERMISSION_SCHEME_UPDATED = "access.permission_scheme_updated"
PERMISSION_SCHEME_ASSIGNED = "access.permission_scheme_assigned"
register_event_types(
    CUSTOM_ROLE_CREATED, CUSTOM_ROLE_UPDATED, CUSTOM_ROLE_DELETED,
    CUSTOM_ROLE_ASSIGNED, CUSTOM_ROLE_REVOKED,
    PERMISSION_SCHEME_CREATED, PERMISSION_SCHEME_UPDATED, PERMISSION_SCHEME_ASSIGNED,
)

# NV-070 fine-grained permissions are defined in novara_core.permissions.

GOVERNANCE_PERMISSIONS: frozenset[str] = frozenset({
    NOTIFICATION_WORKFLOW_READ, NOTIFICATION_WORKFLOW_WRITE,
    INTEGRATION_READ, INTEGRATION_WRITE,
    WEBHOOK_READ, WEBHOOK_WRITE,
    BILLING_READ, BILLING_WRITE,
    AUDIT_READ,
})

# All permissions a custom role may grant. Built from the fixed role matrix plus
# governance permissions; never allow "*" through the custom-role editor.
ALLOWED_CUSTOM_PERMISSIONS: frozenset[str] = frozenset(
    p for perms in ROLE_PERMISSIONS.values() for p in perms if p != ALL
) | GOVERNANCE_PERMISSIONS

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/access-governance",
    tags=["access-governance"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class CustomRole(Base):
    __tablename__ = "custom_roles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_custom_role_workspace_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PermissionScheme(Base):
    __tablename__ = "permission_schemes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_permission_scheme_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    # Mapping of built-in/custom role slug -> list of allowed permissions.
    grants: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PermissionSchemeAssignment(Base):
    __tablename__ = "permission_scheme_assignments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", name="uq_scheme_assignment_project"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("permission_schemes.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assigned_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CustomRoleCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "-")
        if not value or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_:" for c in value):
            raise ValueError("slug must contain only letters, numbers, -, _, :")
        if value in ROLE_PERMISSIONS:
            raise ValueError("slug conflicts with a built-in role")
        return value

    @field_validator("permissions")
    @classmethod
    def allow_listed(cls, value: list[str]) -> list[str]:
        unknown = [p for p in value if p not in ALLOWED_CUSTOM_PERMISSIONS]
        if unknown:
            raise ValueError(f"permissions not allow-listed: {sorted(unknown)}")
        # Deduplicate while preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for p in value:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out


class CustomRolePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = None

    @field_validator("permissions")
    @classmethod
    def allow_listed(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = [p for p in value if p not in ALLOWED_CUSTOM_PERMISSIONS]
        if unknown:
            raise ValueError(f"permissions not allow-listed: {sorted(unknown)}")
        return sorted(set(value))


class CustomRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    slug: str
    name: str
    description: str | None
    permissions: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


class RoleAssignBody(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=120)


class SchemeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    grants: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("grants")
    @classmethod
    def validate_grants(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        clean: dict[str, list[str]] = {}
        for role_slug, perms in value.items():
            if not role_slug or len(role_slug) > 120:
                raise ValueError("invalid role slug in grants")
            unknown = [p for p in perms if p not in ALLOWED_CUSTOM_PERMISSIONS]
            if unknown:
                raise ValueError(f"permissions not allow-listed for {role_slug}: {sorted(unknown)}")
            clean[role_slug] = sorted(set(perms))
        return clean


class SchemePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    grants: dict[str, list[str]] | None = None

    @field_validator("grants")
    @classmethod
    def validate_grants(cls, value: dict[str, list[str]] | None) -> dict[str, list[str]] | None:
        if value is None:
            return None
        return SchemeCreate.validate_grants(value)


class SchemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    name: str
    description: str | None
    grants: dict[str, list[str]]
    created_by: str
    created_at: datetime
    updated_at: datetime


class SchemeAssignBody(BaseModel):
    project_id: str = Field(min_length=1, max_length=36)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def custom_role_ref(role_id: str) -> str:
    return f"custom:{role_id}"


def is_custom_role_ref(role: str) -> bool:
    return role.startswith("custom:")


def resolve_role_permissions(db: Session, workspace_id: str, role: str) -> frozenset[str]:
    if role in ROLE_PERMISSIONS:
        return ROLE_PERMISSIONS[role]
    if is_custom_role_ref(role):
        role_id = role.split(":", 1)[1]
        row = db.execute(
            select(CustomRole).where(
                CustomRole.workspace_id == workspace_id,
                CustomRole.id == role_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return frozenset()
        return frozenset(p for p in (row.permissions or []) if p in ALLOWED_CUSTOM_PERMISSIONS)
    return frozenset()


def role_has_permission(db: Session, workspace_id: str, role: str, permission: str) -> bool:
    granted = resolve_role_permissions(db, workspace_id, role)
    return ALL in granted or permission in granted


def _custom_role_or_404(db: Session, workspace_id: str, role_id: str) -> CustomRole:
    row = db.execute(
        select(CustomRole).where(
            CustomRole.workspace_id == workspace_id,
            CustomRole.id == role_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="custom role not found")
    return row


def _scheme_or_404(db: Session, workspace_id: str, scheme_id: str) -> PermissionScheme:
    row = db.execute(
        select(PermissionScheme).where(
            PermissionScheme.workspace_id == workspace_id,
            PermissionScheme.id == scheme_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="permission scheme not found")
    return row


def _audit_row(event: Event) -> dict:
    payload = event.payload or {}
    return {
        "id": event.id,
        "seq": event.seq,
        "event_type": event.event_type,
        "entity_id": event.entity_id,
        "actor_id": payload.get("actor_id"),
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "correlation_id": event.correlation_id,
        "schema_version": event.schema_version,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Custom roles (CW-130 / PL-124)
# ---------------------------------------------------------------------------


@router.get("/permissions")
def list_allowed_permissions(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return {
        "built_in_roles": {k: sorted(v) for k, v in ROLE_PERMISSIONS.items()},
        "governance_permissions": sorted(GOVERNANCE_PERMISSIONS),
        "allow_list": sorted(ALLOWED_CUSTOM_PERMISSIONS),
    }


@router.post("/custom-roles", response_model=CustomRoleOut, status_code=status.HTTP_201_CREATED)
def create_custom_role(
    workspace_id: str,
    body: CustomRoleCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> CustomRole:
    verify_workspace(principal, workspace_id)
    existing = db.execute(
        select(CustomRole.id).where(
            CustomRole.workspace_id == workspace_id,
            CustomRole.slug == body.slug,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="custom role slug already exists")
    row = CustomRole(
        id=new_id(), workspace_id=workspace_id, slug=body.slug, name=body.name,
        description=body.description, permissions=body.permissions,
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_CREATED,
        entity_id=row.id, actor_id=principal.user.id,
        payload={"slug": row.slug, "permissions": row.permissions},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/custom-roles", response_model=list[CustomRoleOut])
def list_custom_roles(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[CustomRole]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(CustomRole).where(CustomRole.workspace_id == workspace_id).order_by(CustomRole.created_at)
    ).scalars().all()


@router.patch("/custom-roles/{role_id}", response_model=CustomRoleOut)
def update_custom_role(
    workspace_id: str,
    role_id: str,
    body: CustomRolePatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> CustomRole:
    verify_workspace(principal, workspace_id)
    row = _custom_role_or_404(db, workspace_id, role_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return row
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_UPDATED,
        entity_id=row.id, actor_id=principal.user.id,
        payload={"slug": row.slug, "fields": sorted(updates)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/custom-roles/{role_id}")
def delete_custom_role(
    workspace_id: str,
    role_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _custom_role_or_404(db, workspace_id, role_id)
    ref = custom_role_ref(row.id)
    # Revoke assignments that reference this role.
    members = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == ref,
            WorkspaceMember.status == "active",
        )
    ).scalars().all()
    for member in members:
        member.role = "read_only"
        publish_event(
            db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_REVOKED,
            entity_id=member.user_id, actor_id=principal.user.id,
            payload={"custom_role_id": row.id, "fallback_role": "read_only"},
        )
    db.delete(row)
    publish_event(
        db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_DELETED,
        entity_id=role_id, actor_id=principal.user.id,
        payload={"slug": row.slug, "revoked_assignments": len(members)},
    )
    db.commit()
    return {"deleted": True, "role_id": role_id, "revoked_assignments": len(members)}


@router.post("/custom-roles/{role_id}/assign")
def assign_custom_role(
    workspace_id: str,
    role_id: str,
    body: RoleAssignBody,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _custom_role_or_404(db, workspace_id, role_id)
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == body.user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="active workspace member not found")
    requested = body.role.strip()
    expected = custom_role_ref(row.id)
    if requested not in {row.id, row.slug, expected}:
        raise HTTPException(status_code=422, detail="role does not match target custom role")
    member.role = expected
    publish_event(
        db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_ASSIGNED,
        entity_id=member.user_id, actor_id=principal.user.id,
        payload={"custom_role_id": row.id, "slug": row.slug, "role_ref": expected},
    )
    db.commit()
    return {"user_id": member.user_id, "role": member.role, "custom_role_id": row.id}


@router.post("/custom-roles/{role_id}/revoke")
def revoke_custom_role(
    workspace_id: str,
    role_id: str,
    body: RoleAssignBody,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _custom_role_or_404(db, workspace_id, role_id)
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == body.user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="active workspace member not found")
    expected = custom_role_ref(row.id)
    if member.role != expected:
        raise HTTPException(status_code=409, detail="member is not assigned this custom role")
    member.role = "read_only"
    publish_event(
        db, workspace_id=workspace_id, event_type=CUSTOM_ROLE_REVOKED,
        entity_id=member.user_id, actor_id=principal.user.id,
        payload={"custom_role_id": row.id, "fallback_role": "read_only"},
    )
    db.commit()
    return {"user_id": member.user_id, "role": member.role, "revoked_custom_role_id": row.id}


@router.post("/permissions/check")
def check_permission(
    workspace_id: str,
    body: dict,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    permission = str(body.get("permission") or "").strip()
    user_id = str(body.get("user_id") or principal.user.id).strip()
    if not permission:
        raise HTTPException(status_code=422, detail="permission is required")
    if permission not in ALLOWED_CUSTOM_PERMISSIONS and permission != ALL:
        raise HTTPException(status_code=422, detail="permission not allow-listed")
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="active workspace member not found")
    # Non-managers may only check their own permissions.
    if user_id != principal.user.id and not role_has_permission(db, workspace_id, principal.role, WORKSPACE_MANAGE):
        raise HTTPException(status_code=403, detail="permission required: workspace:manage")
    allowed = role_has_permission(db, workspace_id, member.role, permission)
    return {
        "user_id": user_id,
        "role": member.role,
        "permission": permission,
        "allowed": allowed,
        "role_type": "custom" if is_custom_role_ref(member.role) else "built_in",
    }


# ---------------------------------------------------------------------------
# Permission schemes (PL-125)
# ---------------------------------------------------------------------------


@router.post("/schemes", response_model=SchemeOut, status_code=status.HTTP_201_CREATED)
def create_scheme(
    workspace_id: str,
    body: SchemeCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> PermissionScheme:
    verify_workspace(principal, workspace_id)
    existing = db.execute(
        select(PermissionScheme.id).where(
            PermissionScheme.workspace_id == workspace_id,
            PermissionScheme.name == body.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="permission scheme name already exists")
    row = PermissionScheme(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        description=body.description, grants=body.grants,
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=PERMISSION_SCHEME_CREATED,
        entity_id=row.id, actor_id=principal.user.id,
        payload={"name": row.name, "grant_roles": sorted(body.grants)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/schemes", response_model=list[SchemeOut])
def list_schemes(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[PermissionScheme]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(PermissionScheme).where(PermissionScheme.workspace_id == workspace_id).order_by(PermissionScheme.created_at)
    ).scalars().all()


@router.patch("/schemes/{scheme_id}", response_model=SchemeOut)
def update_scheme(
    workspace_id: str,
    scheme_id: str,
    body: SchemePatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> PermissionScheme:
    verify_workspace(principal, workspace_id)
    row = _scheme_or_404(db, workspace_id, scheme_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return row
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=PERMISSION_SCHEME_UPDATED,
        entity_id=row.id, actor_id=principal.user.id,
        payload={"name": row.name, "fields": sorted(updates)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/schemes/{scheme_id}/assign")
def assign_scheme(
    workspace_id: str,
    scheme_id: str,
    body: SchemeAssignBody,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _scheme_or_404(db, workspace_id, scheme_id)
    existing = db.execute(
        select(PermissionSchemeAssignment).where(
            PermissionSchemeAssignment.workspace_id == workspace_id,
            PermissionSchemeAssignment.project_id == body.project_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PermissionSchemeAssignment(
            id=new_id(), workspace_id=workspace_id, scheme_id=row.id,
            project_id=body.project_id, assigned_by=principal.user.id, created_at=now(),
        )
        db.add(existing)
    else:
        existing.scheme_id = row.id
        existing.assigned_by = principal.user.id
    publish_event(
        db, workspace_id=workspace_id, event_type=PERMISSION_SCHEME_ASSIGNED,
        entity_id=row.id, actor_id=principal.user.id,
        payload={"scheme_id": row.id, "project_id": body.project_id},
    )
    db.commit()
    return {"scheme_id": row.id, "project_id": body.project_id, "assigned": True}


@router.get("/schemes/{scheme_id}/assignments")
def list_scheme_assignments(
    workspace_id: str,
    scheme_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _scheme_or_404(db, workspace_id, scheme_id)
    rows = db.execute(
        select(PermissionSchemeAssignment).where(
            PermissionSchemeAssignment.workspace_id == workspace_id,
            PermissionSchemeAssignment.scheme_id == scheme_id,
        ).order_by(PermissionSchemeAssignment.created_at)
    ).scalars().all()
    return [
        {
            "id": r.id, "scheme_id": r.scheme_id, "project_id": r.project_id,
            "assigned_by": r.assigned_by, "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/projects/{project_id}/effective-permissions")
def effective_project_permissions(
    workspace_id: str,
    project_id: str,
    user_id: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    target_user_id = (user_id or principal.user.id).strip()
    if target_user_id != principal.user.id and not role_has_permission(db, workspace_id, principal.role, WORKSPACE_MANAGE):
        raise HTTPException(status_code=403, detail="permission required: workspace:manage")
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="active workspace member not found")

    assignment = db.execute(
        select(PermissionSchemeAssignment).where(
            PermissionSchemeAssignment.workspace_id == workspace_id,
            PermissionSchemeAssignment.project_id == project_id,
        )
    ).scalar_one_or_none()
    scheme = None
    if assignment is not None:
        scheme = db.get(PermissionScheme, assignment.scheme_id)
        if scheme is None or scheme.workspace_id != workspace_id:
            scheme = None

    base_permissions = resolve_role_permissions(db, workspace_id, member.role)
    effective = set(base_permissions)
    scheme_applied = False
    if scheme is not None:
        role_slug = member.role
        if is_custom_role_ref(role_slug):
            # custom:<id> - also try the slug
            custom = db.execute(
                select(CustomRole).where(CustomRole.workspace_id == workspace_id, CustomRole.id == role_slug.split(":", 1)[1])
            ).scalar_one_or_none()
            if custom is not None:
                role_slug = custom.slug
        grants = (scheme.grants or {}).get(role_slug)
        if grants is not None:
            effective &= set(grants) | GOVERNANCE_PERMISSIONS.intersection(effective)
            # Scheme narrows role-derived permissions; governance perms remain if role grants them.
            effective = (set(base_permissions) & set(grants)) | (set(base_permissions) & GOVERNANCE_PERMISSIONS)
            scheme_applied = True

    return {
        "project_id": project_id,
        "user_id": target_user_id,
        "role": member.role,
        "scheme_id": scheme.id if scheme else None,
        "scheme_applied": scheme_applied,
        "base_permissions": sorted(base_permissions),
        "effective_permissions": sorted(effective),
    }


# ---------------------------------------------------------------------------
# Audit log (CW-139)
# ---------------------------------------------------------------------------


@router.get("/audit")
def audit_events(
    workspace_id: str,
    event_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require(AUDIT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    query = select(Event).where(Event.workspace_id == workspace_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if entity_id:
        query = query.where(Event.entity_id == entity_id)
    rows = db.execute(query.order_by(Event.seq.desc()).offset(skip).limit(limit)).scalars().all()
    items = [_audit_row(r) for r in rows]
    if actor_id:
        items = [r for r in items if r["actor_id"] == actor_id]
    return {
        "items": items,
        "count": len(items),
        "fields_recorded": [
            "id", "seq", "event_type", "entity_id", "actor_id",
            "occurred_at", "correlation_id", "schema_version", "payload",
        ],
        "ip_recorded": False,
    }


@router.get("/audit/export")
def export_audit_events(
    workspace_id: str,
    event_type: str | None = Query(default=None),
    principal: Principal = Depends(require(AUDIT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    """CSV export of real stored audit fields only. No IP data is fabricated."""
    verify_workspace(principal, workspace_id)
    query = select(Event).where(Event.workspace_id == workspace_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    rows = db.execute(query.order_by(Event.seq)).scalars().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["seq", "event_type", "entity_id", "actor_id", "occurred_at", "correlation_id", "schema_version"])
    for row in rows:
        payload = row.payload or {}
        writer.writerow([
            row.seq, row.event_type, row.entity_id or "",
            payload.get("actor_id") or "", row.occurred_at.isoformat() if row.occurred_at else "",
            row.correlation_id, row.schema_version,
        ])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="novara-access-audit.csv"'},
    )
