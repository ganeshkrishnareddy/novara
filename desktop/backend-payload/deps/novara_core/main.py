"""NOVARA core API.

Every endpoint is workspace-scoped and, except for bootstrap/auth/invite acceptance,
requires a verified server-side session. There is intentionally no endpoint that
sends email or any other external message.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .dependencies import Principal, get_principal, require, verify_workspace
from .errors import install_safe_validation_errors
from .middleware import auth_limiter, install_security
from .events import (
    CONTACT_ARCHIVED,
    CONTACT_DELETED,
    CONTACT_RESTORED,
    CONTACT_UPDATED,
    CONTACT_EXTERNAL_ID_UPDATED,
    LEAD_CONVERTED,
    LEAD_QUALIFIED,
    LEAD_CREATED,
    COMPANY_CREATED,
    COMPANY_UPDATED,
    COMPANY_ARCHIVED,
    COMPANY_RESTORED,
    MEMBER_INVITED,
    MEMBER_JOINED,
    MEMBER_UPDATED,
    NOTE_CREATED,
    NOTIFICATION_READ as NOTIF_READ_EVENT,
    NOTIFICATION_READ_ALL as NOTIF_READ_ALL_EVENT,
    NOTIFICATION_SEEN as NOTIF_SEEN_EVENT,
    NOTIFICATION_SETTINGS_UPDATED as NOTIF_SETTINGS_EVENT,
    OUTREACH_DRAFT_CREATED,
    TASK_CREATED,
    TASK_UPDATED,
    publish_event,
)
from .modules import include_all
from .modules.outreach_safety import router as outreach_safety_router
from .models import (
    Company,
    Contact,
    Event,
    Lead,
    Note,
    Notification,
    OutreachDraft,
    PasswordResetToken,
    Session as SessionModel,
    Task,
    User,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceNotificationSettings,
    in_hours,
    new_id,
    now,
)
from .permissions import (
    CONTACT_ARCHIVE as P_CONTACT_ARCHIVE,
    CONTACT_DELETE as P_CONTACT_DELETE,
    CONTACT_READ,
    CONTACT_WRITE,
    COMPANY_READ,
    COMPANY_WRITE,
    EVENT_READ,
    LEAD_READ,
    LEAD_WRITE,
    MEMBER_INVITE,
    MEMBER_MANAGE,
    NOTE_WRITE,
    NOTIFICATION_READ,
    OUTREACH_APPROVE,
    OUTREACH_READ,
    TASK_READ,
    TASK_WRITE,
    WORKSPACE_MANAGE,
    ROLE_PERMISSIONS,
)
from .schemas import (
    AcceptInviteRequest,
    BootstrapRequest,
    ChangePasswordRequest,
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    ContactCreate,
    ContactOut,
    ContactUpdate,
    DraftOut,
    EmailCheckRequest,
    EmailVerifyRequest,
    EventOut,
    IntakeResult,
    InviteRequest,
    LeadCreate,
    LeadOut,
    LeadUpdate,
    LoginRequest,
    MeOut,
    MemberOut,
    MemberUpdateRequest,
    NoteCreate,
    NoteOut,
    NotificationCountsOut,
    NotificationOut,
    NotificationSettingsOut,
    NotificationSettingsUpdate,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TokenPair,
    UserOut,
    UserRegister,
    WebsiteSubmission,
    WorkspaceCreate,
)
from .security import (
    INVITE_HOURS,
    consume_one_time_token,
    create_session,
    hash_password,
    hash_token,
    issue_one_time_token,
    new_raw_token,
    revoke_session,
    rotate_session,
    session_by_access,
    verify_password,
)
from .workflow import (
    DraftCreateRequest,
    UnresolvedTemplateVariables,
    approve_outreach_draft,
    create_personalised_draft,
    handle_website_form,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="NOVARA Core", version="0.2.0", lifespan=lifespan)
API = "/api/v1"

# NV-057: the generated OpenAPI document describes the one native API surface.
# Auth is a shared bearer-session contract (.envelope/verify_workspace at runtime)
# and is now declared on every route that is not part of the public sign-in flow.
_PUBLIC_OPENAPI_PATHS = frozenset(
    {
        "/health",
        "/api/v1/setup/bootstrap",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/password-reset/request",
        "/api/v1/auth/password-reset/confirm",
        "/api/v1/auth/email/verify/request",
        "/api/v1/auth/email/verify/confirm",
    }
)


def _novara_openapi() -> dict:
    """Document bearer auth on all protected routes, including notifications."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    components = schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "session access token",
        "description": (
            "Access token issued by sign-in or bootstrap. Every protected route "
            "also verifies that the workspace in the path matches the session."
        ),
    }
    for path, operations in schema.get("paths", {}).items():
        if path in _PUBLIC_OPENAPI_PATHS:
            continue
        for operation in operations.values():
            if isinstance(operation, dict):
                operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _novara_openapi

# 422 responses must never reflect submitted configuration values (P2-8).
install_safe_validation_errors(app)
# Response headers, CORS allow-list and auth rate limiting (P2-8).
install_security(app)


def _validate_owner(db: Session, workspace_id: str, owner_id: str | None) -> None:
    """Ownership may only be assigned to an active member of this workspace."""
    if not owner_id:
        return
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == owner_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=422, detail="owner must be an active member of this workspace")


def _token_pair(session: SessionModel, access: str, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        workspace_id=session.workspace_id,
    )


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    parts = header.split()
    return parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else None


def _require_row(row, label: str):
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


# --------------------------------------------------------------------------
# Health and first-run setup
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "NOVARA"}


@app.post(API + "/setup/bootstrap", response_model=TokenPair, tags=["auth"])
def bootstrap(body: BootstrapRequest, db: Session = Depends(get_db)) -> TokenPair:
    count = db.execute(select(func.count()).select_from(User)).scalar()
    if count:
        raise HTTPException(status_code=409, detail="first-run setup has already been completed")
    user = User(
        id=new_id(),
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        email_verified=False,
        is_active=True,
    )
    workspace = Workspace(id=new_id(), name=body.workspace_name.strip())
    db.add_all([user, workspace])
    db.flush()
    member = WorkspaceMember(
        id=new_id(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
    )
    db.add(member)
    db.flush()
    session, access, refresh = create_session(db, user_id=user.id, workspace_id=workspace.id)
    db.commit()
    return _token_pair(session, access, refresh)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


@app.post(API + "/auth/register", response_model=TokenPair, tags=["auth"])
def register(body: UserRegister, db: Session = Depends(get_db)) -> TokenPair:
    exists = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="email is already registered")
    user = User(
        id=new_id(),
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    workspace = Workspace(id=new_id(), name=f"{body.display_name.strip()}'s workspace")
    db.add_all([user, workspace])
    db.flush()
    db.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
            status="active",
        )
    )
    db.flush()
    session, access, refresh = create_session(db, user_id=user.id, workspace_id=workspace.id)
    db.commit()
    return _token_pair(session, access, refresh)


# PL-056: a small per-client sliding-window guard. The endpoint intentionally
# returns the same response shape for every valid address, but a bounded number
# of checks per minute stops it being used as a bulk account-enumeration oracle.
_EMAIL_CHECK_WINDOW_SECONDS = 60
_EMAIL_CHECK_MAX = 8
_email_check_attempts: dict[str, list[float]] = {}
_email_check_lock = threading.Lock()


@app.post(API + "/auth/email/check", tags=["auth"])
def check_email(
    body: EmailCheckRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """PL-056: validate syntax and report sign-up availability.

    Read-only: it never creates a user, sends mail or starts a session. The
    response shape is identical for every valid address; malformed addresses
    are rejected by the request model before this handler runs. A per-client
    rate limit bounds how aggressively the availability bit can be queried.
    """
    import time

    client = request.client.host if request.client else "unknown"
    moment = time.monotonic()
    with _email_check_lock:
        hits = [t for t in _email_check_attempts.get(client, []) if moment - t < _EMAIL_CHECK_WINDOW_SECONDS]
        if len(hits) >= _EMAIL_CHECK_MAX:
            raise HTTPException(status_code=429, detail="too many email checks; try again shortly")
        hits.append(moment)
        _email_check_attempts[client] = hits
    exists = db.execute(select(User.id).where(User.email == body.email)).scalar_one_or_none()
    return {"email": body.email, "format_valid": True, "available": exists is None}


@app.post(API + "/auth/login", response_model=TokenPair, tags=["auth"])
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    query = select(WorkspaceMember).where(
        WorkspaceMember.user_id == user.id, WorkspaceMember.status == "active"
    )
    if body.workspace_id:
        query = query.where(WorkspaceMember.workspace_id == body.workspace_id)
    member = db.execute(query.order_by(WorkspaceMember.created_at)).scalars().first()
    if member is None:
        raise HTTPException(status_code=403, detail="no active workspace membership")
    session, access, refresh = create_session(
        db, user_id=user.id, workspace_id=member.workspace_id
    )
    user.last_login_at = now()
    db.commit()
    return _token_pair(session, access, refresh)


@app.post(API + "/auth/logout", tags=["auth"])
def logout(request: Request, db: Session = Depends(get_db)) -> dict:
    revoked = revoke_session(db, _bearer(request))
    db.commit()
    return {"revoked": revoked}


@app.post(API + "/auth/refresh", response_model=TokenPair, tags=["auth"])
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    rotated = rotate_session(db, body.refresh_token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    session, access, refresh_token = rotated
    db.commit()
    return _token_pair(session, access, refresh_token)


@app.get(API + "/auth/me", response_model=MeOut, tags=["auth"])
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> MeOut:
    granted = ROLE_PERMISSIONS.get(principal.role, frozenset())
    workspace = db.get(Workspace, principal.workspace_id)
    return MeOut(
        user=UserOut(
            id=principal.user.id,
            email=principal.user.email,
            display_name=principal.user.display_name,
            email_verified=principal.user.email_verified,
        ),
        workspace_id=principal.workspace_id,
        workspace_name=workspace.name,
        role=principal.role,
        permissions=sorted(granted),
    )


@app.post(API + "/auth/change-password", tags=["auth"])
def change_password(
    body: ChangePasswordRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(body.current_password, principal.user.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    principal.user.password_hash = hash_password(body.new_password)
    sessions = db.execute(select(SessionModel).where(SessionModel.user_id == principal.user.id)).scalars().all()
    for session in sessions:
        if session.id != principal.session.id and session.revoked_at is None:
            session.revoked_at = now()
    db.commit()
    return {"changed": True, "other_sessions_revoked": True}


@app.post(API + "/auth/password-reset/request", tags=["auth"])
def request_password_reset(body: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    response = {"accepted": True, "message": "If the account exists, a reset token was created."}
    if user is not None:
        raw = issue_one_time_token(db, "reset", user.id)
        db.commit()
        # No mail adapter is configured. A token is exposed only in explicit dev mode.
        if os.getenv("NOVARA_DEV_MODE", "").lower() in {"1", "true", "yes"}:
            response["development_token"] = raw
    return response


@app.post(API + "/auth/password-reset/confirm", tags=["auth"])
def confirm_password_reset(body: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    record = consume_one_time_token(db, "reset", body.token)
    if record is None:
        raise HTTPException(status_code=400, detail="invalid or expired reset token")
    user = db.get(User, record.user_id)
    user.password_hash = hash_password(body.new_password)
    sessions = db.execute(select(SessionModel).where(SessionModel.user_id == user.id)).scalars().all()
    for session in sessions:
        session.revoked_at = now()
    db.commit()
    return {"reset": True, "sessions_revoked": True}


@app.post(API + "/auth/email/verify/request", tags=["auth"])
def request_email_verification(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict:
    raw = issue_one_time_token(db, "verify", principal.user.id)
    db.commit()
    response = {"accepted": True}
    if os.getenv("NOVARA_DEV_MODE", "").lower() in {"1", "true", "yes"}:
        response["development_token"] = raw
    return response


@app.post(API + "/auth/email/verify/confirm", tags=["auth"])
def confirm_email_verification(body: EmailVerifyRequest, db: Session = Depends(get_db)) -> dict:
    record = consume_one_time_token(db, "verify", body.token)
    if record is None:
        raise HTTPException(status_code=400, detail="invalid or expired verification token")
    user = db.get(User, record.user_id)
    user.email_verified = True
    db.commit()
    return {"verified": True}


# --------------------------------------------------------------------------
# Workspaces and membership
# --------------------------------------------------------------------------


@app.post(API + "/workspaces", response_model=TokenPair, tags=["workspaces"])
def create_workspace(
    body: WorkspaceCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> TokenPair:
    workspace = Workspace(id=new_id(), name=body.name)
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=workspace.id,
            user_id=principal.user.id,
            role="owner",
            status="active",
        )
    )
    db.flush()
    session, access, refresh = create_session(
        db, user_id=principal.user.id, workspace_id=workspace.id
    )
    db.commit()
    return _token_pair(session, access, refresh)


@app.get(API + "/workspaces", tags=["workspaces"])
def list_my_workspaces(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == principal.user.id, WorkspaceMember.status == "active")
        .order_by(Workspace.created_at)
    ).all()
    return [
        {"id": workspace.id, "name": workspace.name, "role": role}
        for workspace, role in rows
    ]


@app.get(API + "/workspaces/{workspace_id}/members", response_model=list[MemberOut], tags=["workspaces"])
def list_members(
    workspace_id: str,
    principal: Principal = Depends(require(MEMBER_MANAGE)),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
    ).all()
    return [
        MemberOut(
            id=member.id,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=member.role,
            status=member.status,
        )
        for member, user in rows
    ]


@app.patch(API + "/workspaces/{workspace_id}/members/{user_id}", response_model=MemberOut, tags=["workspaces"])
def update_member(
    workspace_id: str,
    user_id: str,
    body: MemberUpdateRequest,
    principal: Principal = Depends(require(MEMBER_MANAGE)),
    db: Session = Depends(get_db),
) -> MemberOut:
    """Change one membership's role or lifecycle status (CW-129).

    Access checks read `WorkspaceMember.status` on every request, so suspending
    a member revokes their workspace access immediately even for an existing
    bearer token. The workspace always keeps at least one active owner.
    """
    verify_workspace(principal, workspace_id)
    if body.role is None and body.status is None:
        raise HTTPException(status_code=422, detail="role or status is required")
    row = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="member not found")
    member, user = row

    removing_owner = (
        member.role == "owner" and member.status == "active"
        and ((body.role is not None and body.role != "owner")
             or (body.status == "suspended"))
    )
    if removing_owner:
        active_owners = db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
                WorkspaceMember.status == "active",
            )
        ).scalar_one()
        if active_owners <= 1:
            raise HTTPException(status_code=409, detail="workspace must keep an active owner")

    changes: dict[str, str] = {}
    if body.role is not None and body.role != member.role:
        changes["role"] = body.role
        member.role = body.role
    if body.status is not None and body.status != member.status:
        changes["status"] = body.status
        member.status = body.status
    if changes:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=MEMBER_UPDATED,
            entity_id=user_id,
            payload={"changes": changes, "email": user.email},
            actor_id=principal.user.id,
        )
        db.commit()
    return MemberOut(
        id=member.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=member.role,
        status=member.status,
    )


@app.post(API + "/workspaces/{workspace_id}/invitations", tags=["workspaces"])
def invite_member(
    workspace_id: str,
    body: InviteRequest,
    principal: Principal = Depends(require(MEMBER_INVITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    existing_user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing_user is not None:
        already = db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == existing_user.id,
            )
        ).scalar_one_or_none()
        if already is not None:
            raise HTTPException(status_code=409, detail="user is already a member")
    raw = new_raw_token()
    db.add(
        WorkspaceInvitation(
            id=new_id(),
            workspace_id=workspace_id,
            email=body.email,
            role=body.role,
            token_hash=hash_token(raw),
            invited_by=principal.user.id,
            expires_at=in_hours(INVITE_HOURS),
        )
    )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=MEMBER_INVITED,
        entity_id=body.email,
        payload={"role": body.role, "email": body.email},
        actor_id=principal.user.id,
    )
    db.commit()
    # No mail adapter is configured, so the inviter must relay the token. It is
    # returned only to the authenticated inviter, never to another member.
    return {"invited": True, "email": body.email, "role": body.role, "invite_token": raw}


@app.post(API + "/invitations/accept", response_model=TokenPair, tags=["workspaces"])
def accept_invitation(
    body: AcceptInviteRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> TokenPair:
    invitation = db.execute(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == hash_token(body.token),
            WorkspaceInvitation.accepted_at.is_(None),
        )
    ).scalar_one_or_none()
    if invitation is None or invitation.expires_at.replace(tzinfo=None) <= now().replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="invalid or expired invitation")
    if invitation.email != principal.user.email:
        raise HTTPException(status_code=403, detail="invitation was issued for another email")
    db.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=invitation.workspace_id,
            user_id=principal.user.id,
            role=invitation.role,
            status="active",
            invited_by=invitation.invited_by,
        )
    )
    invitation.accepted_at = now()
    publish_event(
        db,
        workspace_id=invitation.workspace_id,
        event_type=MEMBER_JOINED,
        entity_id=principal.user.id,
        payload={"role": invitation.role},
        actor_id=principal.user.id,
    )
    session, access, refresh = create_session(
        db, user_id=principal.user.id, workspace_id=invitation.workspace_id
    )
    db.commit()
    return _token_pair(session, access, refresh)


# --------------------------------------------------------------------------
# Intake and outreach drafts
# --------------------------------------------------------------------------


@app.post(
    API + "/workspaces/{workspace_id}/intake/website-form",
    response_model=IntakeResult,
    status_code=status.HTTP_201_CREATED,
    tags=["workflow"],
)
def intake_website_form(
    workspace_id: str,
    body: WebsiteSubmission,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> IntakeResult:
    verify_workspace(principal, workspace_id)
    try:
        return handle_website_form(
            db,
            workspace_id=workspace_id,
            submission=body,
            actor_user_id=principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    API + "/workspaces/{workspace_id}/outreach-drafts",
    response_model=DraftOut,
    status_code=status.HTTP_201_CREATED,
    tags=["workflow"],
)
def create_draft(
    workspace_id: str,
    body: DraftCreateRequest,
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> OutreachDraft:
    """Write one personalised DRAFT from workspace-owned fields; never send."""
    verify_workspace(principal, workspace_id)
    try:
        draft = create_personalised_draft(
            db,
            workspace_id=workspace_id,
            contact_id=body.contact_id,
            subject_template=body.subject_template,
            body_template=body.body_template,
            actor_user_id=principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnresolvedTemplateVariables as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return draft


@app.get(API + "/workspaces/{workspace_id}/outreach-drafts", response_model=list[DraftOut], tags=["workflow"])
def list_drafts(
    workspace_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require(OUTREACH_READ)),
    db: Session = Depends(get_db),
) -> list[OutreachDraft]:
    """Review-only outbox: workspace-scoped, filterable, deterministic queue order."""
    verify_workspace(principal, workspace_id)
    query = select(OutreachDraft).where(OutreachDraft.workspace_id == workspace_id)
    if status_filter is not None:
        wanted = "draft" if status_filter == "pending" else status_filter
        if wanted not in {"draft", "approved"}:
            raise HTTPException(status_code=422, detail="status must be pending, draft or approved")
        query = query.where(OutreachDraft.status == wanted)
    # id is the tie-break so a queue order is stable even when timestamps tie.
    return db.execute(
        query.order_by(OutreachDraft.created_at, OutreachDraft.id)
    ).scalars().all()


@app.post(API + "/workspaces/{workspace_id}/outreach-drafts/{draft_id}/approve", response_model=DraftOut, tags=["workflow"])
def approve_draft(
    workspace_id: str,
    draft_id: str,
    principal: Principal = Depends(require(OUTREACH_APPROVE)),
    db: Session = Depends(get_db),
) -> OutreachDraft:
    verify_workspace(principal, workspace_id)
    try:
        return approve_outreach_draft(
            db,
            workspace_id=workspace_id,
            draft_id=draft_id,
            actor_user_id=principal.user.id,
        )
    except (LookupError, PermissionError) as exc:
        code = 404 if isinstance(exc, LookupError) else 403
        raise HTTPException(status_code=code, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------


def _contact_or_404(db: Session, workspace_id: str, contact_id: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    return _require_row(contact, "contact")


@app.get(API + "/workspaces/{workspace_id}/contacts", response_model=list[ContactOut], tags=["crm"])
def list_contacts(
    workspace_id: str,
    search: str | None = None,
    lifecycle_stage: str | None = None,
    tag: str | None = None,
    archived: bool = False,
    sort: str = "created_at",
    order: str = "desc",
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Contact]:
    verify_workspace(principal, workspace_id)
    query = select(Contact).where(Contact.workspace_id == workspace_id, Contact.archived == archived)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(Contact.email.ilike(pattern), Contact.full_name.ilike(pattern), Contact.company_name.ilike(pattern))
        )
    if lifecycle_stage:
        query = query.where(Contact.lifecycle_stage == lifecycle_stage)
    allowed_sort = {
        "created_at": Contact.created_at,
        "updated_at": Contact.updated_at,
        "email": Contact.email,
        "full_name": Contact.full_name,
    }
    column = allowed_sort.get(sort, Contact.created_at)
    query = query.order_by(column.asc() if order == "asc" else column.desc()).offset(skip).limit(limit)
    rows = db.execute(query).scalars().all()
    if tag:
        rows = [row for row in rows if tag in (row.tags or [])]
    return rows


@app.post(API + "/workspaces/{workspace_id}/contacts", response_model=ContactOut, status_code=201, tags=["crm"])
def create_contact(
    workspace_id: str,
    body: ContactCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == body.email)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="a contact with this email already exists")
    contact = Contact(
        id=new_id(),
        workspace_id=workspace_id,
        owner_id=principal.user.id,
        created_at=now(),
        updated_at=now(),
        **body.model_dump(),
    )
    db.add(contact)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CONTACT_UPDATED,
        entity_id=contact.id,
        payload={"email": contact.email, "action": "created"},
        actor_id=principal.user.id,
    )
    db.commit()
    return contact


@app.get(API + "/workspaces/{workspace_id}/contacts/{contact_id}", response_model=ContactOut, tags=["crm"])
def get_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    return _contact_or_404(db, workspace_id, contact_id)


@app.patch(API + "/workspaces/{workspace_id}/contacts/{contact_id}", response_model=ContactOut, tags=["crm"])
def update_contact(
    workspace_id: str,
    contact_id: str,
    body: ContactUpdate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    updates = body.model_dump(exclude_unset=True)
    external_changed = "external_id" in updates or "external_source" in updates
    if external_changed:
        external_id = updates.get("external_id", contact.external_id)
        source = updates.get("external_source", contact.external_source)
        if (external_id is None) != (source is None):
            raise HTTPException(status_code=422, detail="external_id and external_source must be set together")
        if external_id is not None:
            if not external_id.strip() or not source.strip():
                raise HTTPException(status_code=422, detail="external identity fields cannot be blank")
            clash = db.execute(
                select(Contact.id).where(
                    Contact.workspace_id == workspace_id,
                    Contact.external_source == source,
                    Contact.external_id == external_id,
                    Contact.id != contact.id,
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(status_code=409, detail="external id already linked to another contact")
    if "owner_id" in updates and updates["owner_id"]:
        member = db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == updates["owner_id"],
                WorkspaceMember.status == "active",
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(status_code=400, detail="owner must be an active member")
    for key, value in updates.items():
        setattr(contact, key, value)
    contact.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CONTACT_UPDATED,
        entity_id=contact.id,
        payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    if external_changed:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=CONTACT_EXTERNAL_ID_UPDATED,
            entity_id=contact.id,
            payload={
                "external_id": contact.external_id,
                "external_source": contact.external_source,
            },
            actor_id=principal.user.id,
        )
    db.commit()
    return contact


@app.post(API + "/workspaces/{workspace_id}/contacts/{contact_id}/archive", response_model=ContactOut, tags=["crm"])
def archive_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(P_CONTACT_ARCHIVE)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    contact.archived = True
    contact.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CONTACT_ARCHIVED,
        entity_id=contact.id,
        actor_id=principal.user.id,
    )
    db.commit()
    return contact


@app.post(API + "/workspaces/{workspace_id}/contacts/{contact_id}/restore", response_model=ContactOut, tags=["crm"])
def restore_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(P_CONTACT_ARCHIVE)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    contact.archived = False
    contact.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CONTACT_RESTORED,
        entity_id=contact.id,
        actor_id=principal.user.id,
    )
    db.commit()
    return contact


@app.delete(API + "/workspaces/{workspace_id}/contacts/{contact_id}", tags=["crm"])
def delete_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(P_CONTACT_DELETE)),
    db: Session = Depends(get_db),
) -> dict:
    """Hard delete is deliberately guarded: the contact must be archived and
    must have no dependent records."""
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    if not contact.archived:
        raise HTTPException(status_code=409, detail="archive the contact before deleting it")
    counts = {
        "leads": db.execute(select(func.count()).select_from(Lead).where(Lead.contact_id == contact_id)).scalar(),
        "tasks": db.execute(select(func.count()).select_from(Task).where(Task.contact_id == contact_id)).scalar(),
        "notes": db.execute(select(func.count()).select_from(Note).where(Note.contact_id == contact_id)).scalar(),
        "drafts": db.execute(select(func.count()).select_from(OutreachDraft).where(OutreachDraft.contact_id == contact_id)).scalar(),
    }
    blocking = {key: value for key, value in counts.items() if value}
    if blocking:
        raise HTTPException(status_code=409, detail={"dependent_records": blocking})
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CONTACT_DELETED,
        entity_id=contact_id,
        payload={"email": contact.email},
        actor_id=principal.user.id,
    )
    db.delete(contact)
    db.commit()
    return {"deleted": True, "contact_id": contact_id}


# --------------------------------------------------------------------------
# Companies, leads, notes, tasks
# --------------------------------------------------------------------------


@app.get(API + "/workspaces/{workspace_id}/companies", response_model=list[CompanyOut], tags=["crm"])
def list_companies(
    workspace_id: str,
    archived: bool = False,
    principal: Principal = Depends(require(COMPANY_READ)),
    db: Session = Depends(get_db),
) -> list[Company]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Company).where(Company.workspace_id == workspace_id, Company.archived == archived)
    ).scalars().all()


@app.post(API + "/workspaces/{workspace_id}/companies", response_model=CompanyOut, status_code=201, tags=["crm"])
def create_company(
    workspace_id: str,
    body: CompanyCreate,
    principal: Principal = Depends(require(COMPANY_WRITE)),
    db: Session = Depends(get_db),
) -> Company:
    verify_workspace(principal, workspace_id)
    _validate_owner(db, workspace_id, body.owner_id)
    exists = db.execute(
        select(Company).where(Company.workspace_id == workspace_id, Company.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="company already exists")
    company = Company(id=new_id(), workspace_id=workspace_id, created_at=now(), updated_at=now(), **body.model_dump())
    db.add(company)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=COMPANY_CREATED,
        entity_id=company.id,
        payload={"name": company.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return company


def _company_or_404(db: Session, workspace_id: str, company_id: str) -> Company:
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    return company


@app.patch(API + "/workspaces/{workspace_id}/companies/{company_id}", response_model=CompanyOut, tags=["crm"])
def update_company(
    workspace_id: str,
    company_id: str,
    body: CompanyUpdate,
    principal: Principal = Depends(require(COMPANY_WRITE)),
    db: Session = Depends(get_db),
) -> Company:
    """SB-013: partial metadata update, strictly inside the verified workspace."""
    verify_workspace(principal, workspace_id)
    company = _company_or_404(db, workspace_id, company_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="company name is required")
        duplicate = db.execute(
            select(Company.id).where(
                Company.workspace_id == workspace_id,
                Company.name == name,
                Company.id != company.id,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="company already exists")
        changes["name"] = name
    if "owner_id" in changes:
        _validate_owner(db, workspace_id, changes["owner_id"])
    for field, value in changes.items():
        setattr(company, field, value)
    company.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=COMPANY_UPDATED,
        entity_id=company.id,
        payload={"fields": sorted(changes)},
        actor_id=principal.user.id,
    )
    db.commit()
    return company


@app.post(API + "/workspaces/{workspace_id}/companies/{company_id}/archive", response_model=CompanyOut, tags=["crm"])
def archive_company(
    workspace_id: str,
    company_id: str,
    principal: Principal = Depends(require(COMPANY_WRITE)),
    db: Session = Depends(get_db),
) -> Company:
    """SB-013: reversible archive; never a hard delete."""
    verify_workspace(principal, workspace_id)
    company = _company_or_404(db, workspace_id, company_id)
    company.archived = True
    company.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=COMPANY_ARCHIVED,
        entity_id=company.id,
        payload={"name": company.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return company


@app.post(API + "/workspaces/{workspace_id}/companies/{company_id}/restore", response_model=CompanyOut, tags=["crm"])
def restore_company(
    workspace_id: str,
    company_id: str,
    principal: Principal = Depends(require(COMPANY_WRITE)),
    db: Session = Depends(get_db),
) -> Company:
    """SB-013: restore an archived company to the active list."""
    verify_workspace(principal, workspace_id)
    company = _company_or_404(db, workspace_id, company_id)
    company.archived = False
    company.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=COMPANY_RESTORED,
        entity_id=company.id,
        payload={"name": company.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return company


def _list_options(
    sort: str,
    order: str,
    skip: int,
    limit: int,
    columns: dict,
):
    """Validate list options and return a safe ordering clause.

    Sort keys are resolved from an explicit allow-list, never from raw user
    input, so this cannot be used to reference arbitrary SQL expressions.
    """
    if sort not in columns:
        raise HTTPException(
            status_code=422,
            detail="sort must be one of: " + ", ".join(sorted(columns)),
        )
    if order.lower() not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order must be asc or desc")
    if skip < 0:
        raise HTTPException(status_code=422, detail="skip must be zero or greater")
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    column = columns[sort]
    ordering = column.asc() if order.lower() == "asc" else column.desc()
    return ordering, skip, limit


@app.get(API + "/workspaces/{workspace_id}/leads", response_model=list[LeadOut], tags=["crm"])
def list_leads(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Match lead status, source, priority or contact name/email"),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require(LEAD_READ)),
    db: Session = Depends(get_db),
) -> list[Lead]:
    verify_workspace(principal, workspace_id)
    ordering, offset, page_size = _list_options(
        sort, order, skip, limit,
        {"created_at": Lead.created_at, "status": Lead.status, "priority": Lead.priority,
         "score": Lead.score, "id": Lead.id},
    )
    query = select(Lead).where(Lead.workspace_id == workspace_id)
    if status_filter:
        query = query.where(Lead.status == status_filter)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.join(Contact, Contact.id == Lead.contact_id).where(
            or_(
                Lead.status.ilike(pattern),
                Lead.priority.ilike(pattern),
                Lead.source.ilike(pattern),
                Contact.full_name.ilike(pattern),
                Contact.email.ilike(pattern),
            )
        )
    return db.execute(
        query.order_by(ordering, Lead.id).offset(offset).limit(page_size)
    ).scalars().all()


@app.post(API + "/workspaces/{workspace_id}/leads", response_model=LeadOut, status_code=201, tags=["crm"])
def create_lead(
    workspace_id: str,
    body: LeadCreate,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> Lead:
    verify_workspace(principal, workspace_id)
    _validate_owner(db, workspace_id, body.owner_id)
    contact = _contact_or_404(db, workspace_id, body.contact_id)
    exists = db.execute(
        select(Lead).where(Lead.workspace_id == workspace_id, Lead.contact_id == contact.id)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="a lead already exists for this contact")
    lead = Lead(id=new_id(), workspace_id=workspace_id, created_at=now(), **body.model_dump())
    db.add(lead)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=LEAD_CREATED,
        entity_id=lead.id,
        payload={"contact_id": contact.id},
        actor_id=principal.user.id,
    )
    db.commit()
    return lead


@app.patch(API + "/workspaces/{workspace_id}/leads/{lead_id}", response_model=LeadOut, tags=["crm"])
def update_lead(
    workspace_id: str,
    lead_id: str,
    body: LeadUpdate,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> Lead:
    verify_workspace(principal, workspace_id)
    _validate_owner(db, workspace_id, body.owner_id)
    lead = db.execute(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)).scalar_one_or_none()
    lead = _require_row(lead, "lead")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.commit()
    return lead


@app.post(API + "/workspaces/{workspace_id}/leads/{lead_id}/qualify", response_model=LeadOut, tags=["crm"])
def qualify_lead(
    workspace_id: str,
    lead_id: str,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> Lead:
    verify_workspace(principal, workspace_id)
    lead = db.execute(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)).scalar_one_or_none()
    lead = _require_row(lead, "lead")
    lead.status = "qualified"
    lead.qualified_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=LEAD_QUALIFIED, entity_id=lead.id,
        payload={"contact_id": lead.contact_id}, actor_id=principal.user.id,
    )
    db.commit()
    return lead


@app.post(API + "/workspaces/{workspace_id}/leads/{lead_id}/convert", response_model=LeadOut, tags=["crm"])
def convert_lead(
    workspace_id: str,
    lead_id: str,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> Lead:
    verify_workspace(principal, workspace_id)
    lead = db.execute(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)).scalar_one_or_none()
    lead = _require_row(lead, "lead")
    if lead.status != "qualified":
        raise HTTPException(status_code=409, detail="qualify the lead before converting it")
    lead.status = "converted"
    lead.converted_at = now()
    contact = _contact_or_404(db, workspace_id, lead.contact_id)
    contact.lifecycle_stage = "customer"
    contact.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=LEAD_CONVERTED, entity_id=lead.id,
        payload={"contact_id": lead.contact_id}, actor_id=principal.user.id,
    )
    db.commit()
    return lead


@app.get(API + "/workspaces/{workspace_id}/contacts/{contact_id}/notes", response_model=list[NoteOut], tags=["crm"])
def list_notes(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Note]:
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    return db.execute(
        select(Note).where(Note.workspace_id == workspace_id, Note.contact_id == contact_id).order_by(Note.created_at)
    ).scalars().all()


@app.post(API + "/workspaces/{workspace_id}/contacts/{contact_id}/notes", response_model=NoteOut, status_code=201, tags=["crm"])
def create_note(
    workspace_id: str,
    contact_id: str,
    body: NoteCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Note:
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    note = Note(
        id=new_id(), workspace_id=workspace_id, contact_id=contact_id,
        author_id=principal.user.id, body=body.body, created_at=now(),
    )
    db.add(note)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=NOTE_CREATED, entity_id=note.id,
        payload={"contact_id": contact_id}, actor_id=principal.user.id,
    )
    db.commit()
    return note


@app.get(API + "/workspaces/{workspace_id}/tasks", response_model=list[TaskOut], tags=["tasks"])
def list_tasks(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Match title, description, status or priority"),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require(TASK_READ)),
    db: Session = Depends(get_db),
) -> list[Task]:
    verify_workspace(principal, workspace_id)
    ordering, offset, page_size = _list_options(
        sort, order, skip, limit,
        {"created_at": Task.created_at, "due_at": Task.due_at, "status": Task.status,
         "priority": Task.priority, "title": Task.title, "id": Task.id},
    )
    query = select(Task).where(Task.workspace_id == workspace_id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
                Task.status.ilike(pattern),
                Task.priority.ilike(pattern),
            )
        )
    return db.execute(
        query.order_by(ordering, Task.id).offset(offset).limit(page_size)
    ).scalars().all()


@app.post(API + "/workspaces/{workspace_id}/tasks", response_model=TaskOut, status_code=201, tags=["tasks"])
def create_task(
    workspace_id: str,
    body: TaskCreate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Task:
    verify_workspace(principal, workspace_id)
    _validate_owner(db, workspace_id, body.owner_id)
    if body.contact_id:
        _contact_or_404(db, workspace_id, body.contact_id)
    task = Task(id=new_id(), workspace_id=workspace_id, created_at=now(), **body.model_dump())
    db.add(task)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TASK_CREATED, entity_id=task.id,
        payload={"contact_id": task.contact_id, "title": task.title}, actor_id=principal.user.id,
    )
    db.commit()
    return task


@app.patch(API + "/workspaces/{workspace_id}/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def update_task(
    workspace_id: str,
    task_id: str,
    body: TaskUpdate,
    principal: Principal = Depends(require(TASK_WRITE)),
    db: Session = Depends(get_db),
) -> Task:
    verify_workspace(principal, workspace_id)
    _validate_owner(db, workspace_id, body.owner_id)
    task = db.execute(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)).scalar_one_or_none()
    task = _require_row(task, "task")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(task, key, value)
    if updates.get("status") == "done" and task.completed_at is None:
        task.completed_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=TASK_UPDATED, entity_id=task.id,
        payload={"fields": sorted(updates.keys())}, actor_id=principal.user.id,
    )
    db.commit()
    return task


# --------------------------------------------------------------------------
# Notifications, audit log, unified timeline
# --------------------------------------------------------------------------


def _notification_scope(workspace_id: str, user_id: str) -> list:
    """Rows visible to one identity: its own messages plus workspace broadcasts."""
    return [
        Notification.workspace_id == workspace_id,
        or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
    ]


def _notification_counts(db: Session, workspace_id: str, user_id: str) -> dict:
    """Plain dict so the same function backs both the REST response and the feed
    stream. Counts are real aggregates over the caller's visible rows."""
    scope = _notification_scope(workspace_id, user_id)
    total = db.execute(select(func.count(Notification.id)).where(*scope)).scalar_one()
    unread = db.execute(
        select(func.count(Notification.id)).where(*scope, Notification.read.is_(False))
    ).scalar_one()
    unseen = db.execute(
        select(func.count(Notification.id)).where(*scope, Notification.seen.is_(False))
    ).scalar_one()
    groups = db.execute(
        select(Notification.category, func.count(Notification.id)).where(*scope)
        .group_by(Notification.category)
    ).all()
    return {
        "total": total,
        "unread": unread,
        "unseen": unseen,
        "by_category": {str(category): count for category, count in groups},
    }


def _scoped_notification(
    db: Session, workspace_id: str, user_id: str, notification_id: str
) -> Notification:
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            *_notification_scope(workspace_id, user_id),
        )
    ).scalar_one_or_none()
    return _require_row(notification, "notification")


@app.get(API + "/workspaces/{workspace_id}/notifications", response_model=list[NotificationOut], tags=["activity"])
def list_notifications(
    workspace_id: str,
    category: str | None = Query(None, max_length=50),
    unread_only: bool = Query(False),
    unseen_only: bool = Query(False),
    since: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> list[Notification]:
    verify_workspace(principal, workspace_id)
    query = select(Notification).where(*_notification_scope(workspace_id, principal.user.id))
    if category:
        query = query.where(Notification.category == category)
    if unread_only:
        query = query.where(Notification.read.is_(False))
    if unseen_only:
        query = query.where(Notification.seen.is_(False))
    if since:
        query = query.where(Notification.created_at >= since)
    return db.execute(
        query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()


@app.get(API + "/workspaces/{workspace_id}/notifications/counts", response_model=NotificationCountsOut, tags=["activity"])
def notification_counts(
    workspace_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return _notification_counts(db, workspace_id, principal.user.id)


@app.get(API + "/workspaces/{workspace_id}/notifications/stream", tags=["activity"])
def notification_stream(
    workspace_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
):
    """Server-sent real-time feed of the caller's notification counts.

    Auth stays in the Authorization header (native EventSource cannot send one),
    so the browser consumes this with a streaming fetch. Each poll uses a fresh
    short-lived session; no row is mutated and nothing leaves localhost.
    """
    verify_workspace(principal, workspace_id)
    user_id = principal.user.id
    bind = db.get_bind()

    async def event_stream():
        last = None
        for tick in range(720):  # one hour at five-second polls, then reconnect
            try:
                with Session(bind) as poll_db:
                    snapshot = _notification_counts(poll_db, workspace_id, user_id)
            except Exception:
                snapshot = None
            if snapshot is not None and snapshot != last:
                yield "data: " + json.dumps(snapshot) + "\n\n"
                last = snapshot
            elif tick % 12 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(API + "/workspaces/{workspace_id}/notifications/{notification_id}/seen", response_model=NotificationOut, tags=["activity"])
def mark_notification_seen(
    workspace_id: str,
    notification_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> Notification:
    verify_workspace(principal, workspace_id)
    notification = _scoped_notification(db, workspace_id, principal.user.id, notification_id)
    if not notification.seen:
        notification.seen = True
        notification.seen_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=NOTIF_SEEN_EVENT,
            entity_id=notification.id, actor_id=principal.user.id,
            payload={"category": notification.category},
        )
        db.commit()
    return notification


@app.post(API + "/workspaces/{workspace_id}/notifications/seen-all", response_model=NotificationCountsOut, tags=["activity"])
def mark_all_notifications_seen(
    workspace_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(Notification).where(
            *_notification_scope(workspace_id, principal.user.id),
            Notification.seen.is_(False),
        )
    ).scalars().all()
    for row in rows:
        row.seen = True
        row.seen_at = now()
    if rows:
        publish_event(
            db, workspace_id=workspace_id, event_type=NOTIF_SEEN_EVENT,
            entity_id=None, actor_id=principal.user.id,
            payload={"bulk": True, "count": len(rows)},
            idempotency_key=f"notif-seen-all:{principal.user.id}:{len(rows)}:{rows[-1].id}",
        )
        db.commit()
    return _notification_counts(db, workspace_id, principal.user.id)


@app.post(API + "/workspaces/{workspace_id}/notifications/{notification_id}/read", response_model=NotificationOut, tags=["activity"])
def mark_notification_read(
    workspace_id: str,
    notification_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> Notification:
    verify_workspace(principal, workspace_id)
    notification = _scoped_notification(db, workspace_id, principal.user.id, notification_id)
    if not notification.read:
        notification.read = True
        notification.read_at = now()
        notification.seen = True
        notification.seen_at = notification.seen_at or notification.read_at
        publish_event(
            db, workspace_id=workspace_id, event_type=NOTIF_READ_EVENT,
            entity_id=notification.id, actor_id=principal.user.id,
            payload={"category": notification.category},
        )
        db.commit()
    return notification


@app.post(API + "/workspaces/{workspace_id}/notifications/read-all", response_model=NotificationCountsOut, tags=["activity"])
def mark_all_notifications_read(
    workspace_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    stamp = now()
    rows = db.execute(
        select(Notification).where(
            *_notification_scope(workspace_id, principal.user.id),
            Notification.read.is_(False),
        )
    ).scalars().all()
    for row in rows:
        row.read = True
        row.read_at = stamp
        row.seen = True
        row.seen_at = row.seen_at or stamp
    if rows:
        publish_event(
            db, workspace_id=workspace_id, event_type=NOTIF_READ_ALL_EVENT,
            entity_id=None, actor_id=principal.user.id,
            payload={"count": len(rows)},
            idempotency_key=f"notif-read-all:{principal.user.id}:{len(rows)}:{rows[-1].id}",
        )
        db.commit()
    return _notification_counts(db, workspace_id, principal.user.id)


def _workspace_notification_settings(db: Session, workspace_id: str) -> WorkspaceNotificationSettings:
    settings = db.execute(
        select(WorkspaceNotificationSettings).where(
            WorkspaceNotificationSettings.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if settings is None:
        settings = WorkspaceNotificationSettings(workspace_id=workspace_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@app.get(API + "/workspaces/{workspace_id}/notification-settings", response_model=NotificationSettingsOut, tags=["activity"])
def get_notification_settings(
    workspace_id: str,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> WorkspaceNotificationSettings:
    verify_workspace(principal, workspace_id)
    return _workspace_notification_settings(db, workspace_id)


@app.put(API + "/workspaces/{workspace_id}/notification-settings", response_model=NotificationSettingsOut, tags=["activity"])
def update_notification_settings(
    workspace_id: str,
    payload: NotificationSettingsUpdate,
    principal: Principal = Depends(require(NOTIFICATION_READ)),
    db: Session = Depends(get_db),
) -> WorkspaceNotificationSettings:
    verify_workspace(principal, workspace_id)
    settings = _workspace_notification_settings(db, workspace_id)
    changed = sorted(payload.model_fields_set)
    for field in changed:
        setattr(settings, field, getattr(payload, field))
    settings.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=NOTIF_SETTINGS_EVENT,
        entity_id=settings.id, actor_id=principal.user.id, payload={"fields": changed},
    )
    db.commit()
    return settings


@app.get(API + "/workspaces/{workspace_id}/events", response_model=list[EventOut], tags=["activity"])
def list_events(
    workspace_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[Event]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Event).where(Event.workspace_id == workspace_id).order_by(Event.seq).offset(skip).limit(limit)
    ).scalars().all()


@app.get(API + "/workspaces/{workspace_id}/contacts/{contact_id}/timeline", response_model=list[EventOut], tags=["activity"])
def contact_timeline(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Event]:
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    correlation_ids = db.execute(
        select(Event.correlation_id).where(
            Event.workspace_id == workspace_id, Event.entity_id == contact_id
        )
    ).scalars().all()
    if not correlation_ids:
        return []
    return db.execute(
        select(Event).where(
            Event.workspace_id == workspace_id,
            Event.correlation_id.in_(correlation_ids),
        ).order_by(Event.seq)
    ).scalars().all()


# --------------------------------------------------------------------------
# One application: attach every capability module, then serve the web client.
# Core and module routes are registered before the catch-all, so they win.
# --------------------------------------------------------------------------

include_all(app)
# Local outreach safety gates (policy, opt-outs, suppression, pre-send decision).
app.include_router(outreach_safety_router)

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


@app.get("/{full_path:path}", include_in_schema=False)
def web_client(full_path: str):
    """Serve the NOVARA single-page client from the same origin as the API."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="not found")
    candidate = (WEB_ROOT / full_path).resolve()
    if candidate.is_file() and WEB_ROOT.resolve() in candidate.parents:
        return FileResponse(candidate)
    if not (WEB_ROOT / "index.html").is_file():
        raise HTTPException(status_code=404, detail="web client is not installed")
    return FileResponse(WEB_ROOT / "index.html")
