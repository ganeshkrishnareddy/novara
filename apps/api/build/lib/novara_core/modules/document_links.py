"""Document sharing links, visitor capture and engagement analytics.

Clean-room implementation of the Papermark-style shareable-link capabilities
(PM-028, PM-029, PM-030, PM-032, PM-033, PM-039, PM-042, PM-072, PM-073,
PM-074, PM-080, PM-088) over the shared NOVARA document metadata. No AGPL
code is copied; only the shared contracts (workspace, contact identity, events,
permissions) are reused.

No file bytes are served by this module. ``storage_path`` stays an opaque
reference; links point at documents by id and carry policy only.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, bearer_token, get_principal, require, verify_workspace
from ..events import NOTIFICATION_CREATED, publish_event, register_event_types
from ..models import (
    Contact,
    Event,
    Notification,
    ViewerIdentity,
    WorkspaceMember,
    new_id,
    now,
)
from .documents import (
    DOCUMENT_DOWNLOADED,
    DOCUMENT_VIEWED,
    DataRoom,
    Document,
    DocumentPage,
    DocumentPreference,
    DocumentRoomMembership,
    DocumentVersion,
    _preference_or_create,
    primary_version,
)
from ..permissions import DOCUMENT_ADMIN, DOCUMENT_READ, DOCUMENT_WRITE, has_permission
from ..security import hash_password, verify_password, hash_token

DOCUMENT_LINK_CREATED = "document.link_created"
DOCUMENT_LINK_UPDATED = "document.link_updated"
DOCUMENT_LINK_REVOKED = "document.link_revoked"
DOCUMENT_LINK_ACCESSED = "document.link_accessed"
DOCUMENT_LINK_SESSION_STARTED = "document.link_session_started"
DOCUMENT_LINK_SESSION_REVOKED = "document.link_session_revoked"
DOCUMENT_VIEWER_IDENTITY_CREATED = "document.viewer_identity_created"
DOCUMENT_VIEWER_CONSENT_UPDATED = "document.viewer_consent_updated"
DOCUMENT_VISITOR_IDENTIFIED = "document.visitor_identified"
DOCUMENT_VISIT_RECORDED = "document.visit_recorded"
DOCUMENT_PAGE_VIEWED = "document.page_viewed"
# P1 sharing/analytics surface: agreements, verification, ACLs and timed views.
DOCUMENT_AGREEMENT_CREATED = "document.agreement_created"
DOCUMENT_AGREEMENT_ACCEPTED = "document.agreement_accepted"
DOCUMENT_EMAIL_VERIFICATION_ISSUED = "document.email_verification_issued"
DOCUMENT_EMAIL_VERIFIED = "document.email_verified"
DOCUMENT_ACCESS_RULE_CREATED = "document.access_rule_created"
DOCUMENT_PERMISSION_GROUP_CREATED = "document.permission_group_created"
DOCUMENT_PERMISSION_GROUP_MEMBER_ADDED = "document.permission_group_member_added"
DOCUMENT_PAGE_TIMED = "document.page_timed"

register_event_types(
    DOCUMENT_LINK_CREATED,
    DOCUMENT_LINK_UPDATED,
    DOCUMENT_LINK_REVOKED,
    DOCUMENT_LINK_ACCESSED,
    DOCUMENT_LINK_SESSION_STARTED,
    DOCUMENT_LINK_SESSION_REVOKED,
    DOCUMENT_VIEWER_IDENTITY_CREATED,
    DOCUMENT_VIEWER_CONSENT_UPDATED,
    DOCUMENT_VISITOR_IDENTIFIED,
    DOCUMENT_VISIT_RECORDED,
    DOCUMENT_PAGE_VIEWED,
    DOCUMENT_AGREEMENT_CREATED,
    DOCUMENT_AGREEMENT_ACCEPTED,
    DOCUMENT_EMAIL_VERIFICATION_ISSUED,
    DOCUMENT_EMAIL_VERIFIED,
    DOCUMENT_ACCESS_RULE_CREATED,
    DOCUMENT_PERMISSION_GROUP_CREATED,
    DOCUMENT_PERMISSION_GROUP_MEMBER_ADDED,
    DOCUMENT_PAGE_TIMED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/documents",
    tags=["document-links"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class DocumentLink(Base):
    __tablename__ = "document_links"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_document_link_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    max_views: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_only: Mapped[bool] = mapped_column(default=True, nullable=False)
    download_allowed: Mapped[bool] = mapped_column(default=False, nullable=False)
    revoked: Mapped[bool] = mapped_column(default=False, nullable=False)
    # PM-031/PM-047/PM-063: viewer gates enforced before any view is created.
    require_email_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_nda: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("permission_groups.id"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class LinkSession(Base):
    """PM-030/039/042: a restricted viewer session scoped to exactly one link.

    The raw token is returned once; only its hash is persisted. Sessions die
    with their link (expiry or revocation) and can never authorise a workspace
    API call, because they are not workspace login sessions.
    """

    __tablename__ = "document_link_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_link_session_token"),
        Index("ix_link_session_link", "workspace_id", "link_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    viewer_email: Mapped[str | None] = mapped_column(String(320))
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class LinkVisit(Base):
    __tablename__ = "document_link_visits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    # PM-073: the visit is attached to the single CRM contact identity when the
    # visitor is known, so the shared view event can appear on that timeline.
    contact_id: Mapped[str | None] = mapped_column(String(36), index=True)
    visitor_name: Mapped[str | None] = mapped_column(String(200))
    visitor_email: Mapped[str | None] = mapped_column(String(320))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    pages_viewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # PM-082: the real download boundary stamps the visit, so analytics can
    # surface download status without inventing events.
    downloaded_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)


class PageView(Base):
    __tablename__ = "document_page_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("document_link_visits.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # PM-011: page views point at the immutable page record when it exists.
    page_id: Mapped[str | None] = mapped_column(ForeignKey("document_pages.id"), index=True)
    viewed_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    # PM-075: enter/leave timestamps are the source of time-on-page.
    entered_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)


class Agreement(Base):
    """PM-026/PM-047: an immutable-after-acceptance NDA record."""

    __tablename__ = "document_agreements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    visitor_contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"), index=True)
    visitor_email: Mapped[str | None] = mapped_column(String(320))
    signature_reference: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class LinkVerification(Base):
    """PM-031: one-time viewer email verification, no outbound message sent."""

    __tablename__ = "document_link_verifications"
    __table_args__ = (
        UniqueConstraint("workspace_id", "link_id", "email",
                         name="uq_link_verification_email"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class LinkAccessRule(Base):
    """PM-034: normalised email/domain allow and block rules for one link."""

    __tablename__ = "document_link_access_rules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "link_id", "effect", "kind", "value",
                         name="uq_link_access_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(10), nullable=False)  # allow | block
    kind: Mapped[str] = mapped_column(String(20), nullable=False)    # email | domain
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    include_subdomains: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class PermissionGroup(Base):
    """PM-063: workspace-scoped per-object ACL group."""

    __tablename__ = "permission_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class PermissionGroupMember(Base):
    __tablename__ = "permission_group_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "group_id", "user_id",
                         name="uq_permission_group_user"),
        UniqueConstraint("workspace_id", "group_id", "email",
                         name="uq_permission_group_email"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("permission_groups.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LinkCreate(BaseModel):
    password: str | None = None
    expires_in_hours: int | None = Field(default=None, ge=1, le=8760)
    max_views: int | None = Field(default=None, ge=1)
    view_only: bool = True
    download_allowed: bool = False
    require_email_verification: bool = False
    require_nda: bool = False
    required_group_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class LinkOut(BaseModel):
    id: str
    document_id: str
    has_password: bool
    expires_at: object
    max_views: int | None
    view_count: int
    view_only: bool
    download_allowed: bool
    revoked: bool
    require_email_verification: bool = False
    require_nda: bool = False
    required_group_id: str | None = None
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class LinkUpdate(BaseModel):
    """PM-029/PM-032: explicit management changes, including expiry extension."""

    password: str | None = None
    clear_password: bool = False
    # Setting these fields to null explicitly clears the corresponding control;
    # omitting a field leaves it unchanged.
    expires_in_hours: int | None = Field(default=None, ge=1, le=8760)
    max_views: int | None = Field(default=None, ge=1)
    view_only: bool | None = None
    download_allowed: bool | None = None
    require_email_verification: bool | None = None
    require_nda: bool | None = None
    required_group_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class LinkSessionOut(BaseModel):
    id: str
    link_id: str
    expires_at: object
    revoked_at: object
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ViewerIdentityCreate(BaseModel):
    email: str
    display_name: str | None = None
    consent: bool
    source_link_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str) -> str:
        result = value.strip().lower()
        if "@" not in result or result.startswith("@") or result.endswith("@"):
            raise ValueError("a valid email is required")
        return result


class ViewerConsentUpdate(BaseModel):
    granted: bool
    email: str | None = None
    display_name: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class ViewerIdentityOut(BaseModel):
    id: str
    workspace_id: str
    identified: bool
    email: str | None
    display_name: str | None
    contact_id: str | None
    verified_at: object
    consent_at: object
    consent_revoked_at: object
    created_at: object


class PageEventIn(BaseModel):
    page_number: int = Field(ge=1)
    page_id: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    leave: bool = True

    model_config = ConfigDict(extra="forbid")


class PageEventBatch(BaseModel):
    visit_id: str
    events: list[PageEventIn] = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")


class DocumentPageAnalyticsOut(BaseModel):
    page_number: int
    page_id: str | None
    label: str | None
    views: int
    unique_viewers: int
    total_duration_seconds: int
    average_duration_seconds: int
    page_events: int


class LinkResolveOut(BaseModel):
    link_id: str
    document_id: str
    title: str
    doc_type: str
    size_bytes: int
    # PM-009/PM-041: resolution advertises the immutable primary revision.
    primary_version_id: str | None = None
    primary_version_number: int | None = None
    storage_path: str | None = None
    pages: list[dict] = Field(default_factory=list)
    view_only: bool
    download_allowed: bool
    password_required: bool
    expired: bool
    revoked: bool
    views_remaining: int | None


class UnlockRequest(BaseModel):
    password: str

    model_config = ConfigDict(extra="forbid")


class VisitorIdentifyRequest(BaseModel):
    visitor_name: str | None = None
    visitor_email: str | None = None

    model_config = ConfigDict(extra="forbid")


class VisitStartRequest(BaseModel):
    visitor_name: str | None = None
    visitor_email: str | None = None
    contact_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    model_config = ConfigDict(extra="forbid")


class DownloadRequest(BaseModel):
    """Recording a download of metadata only; no file bytes are served."""

    page_number: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


class VisitOut(BaseModel):
    id: str
    link_id: str
    contact_id: str | None
    visitor_name: str | None
    visitor_email: str | None
    ip_address: str | None
    started_at: object
    ended_at: object
    duration_seconds: int | None
    pages_viewed: int

    model_config = ConfigDict(from_attributes=True)


class PageViewRequest(BaseModel):
    page_number: int = Field(ge=1)
    page_id: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class PageAnalyticsOut(BaseModel):
    page_number: int
    views: int
    total_duration_seconds: int


class AgreementCreate(BaseModel):
    title: str
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


class AgreementAccept(BaseModel):
    visitor_email: str | None = None
    visitor_name: str | None = None
    contact_id: str | None = None
    signature_reference: str | None = None

    model_config = ConfigDict(extra="forbid")


class AgreementPatch(BaseModel):
    title: str | None = None
    body: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "body")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be empty")
        return value


class VerificationRequest(BaseModel):
    email: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str) -> str:
        result = value.strip().lower()
        if "@" not in result or result.startswith("@") or result.endswith("@"):
            raise ValueError("a valid email is required")
        return result


class VerificationConfirm(VerificationRequest):
    code: str

    model_config = ConfigDict(extra="forbid")


class AccessRuleCreate(BaseModel):
    effect: str
    kind: str
    value: str
    include_subdomains: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("effect")
    @classmethod
    def valid_effect(cls, value: str) -> str:
        if value not in ("allow", "block"):
            raise ValueError("effect must be allow or block")
        return value

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        if value not in ("email", "domain"):
            raise ValueError("kind must be email or domain")
        return value

    @field_validator("value")
    @classmethod
    def normalise(cls, value: str) -> str:
        result = value.strip().lower()
        if not result:
            raise ValueError("value must not be empty")
        return result


class PermissionGroupCreate(BaseModel):
    name: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()


class PermissionGroupMemberCreate(BaseModel):
    user_id: str | None = None
    email: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _link_or_404(db: Session, workspace_id: str, link_id: str) -> DocumentLink:
    link = db.execute(
        select(DocumentLink).where(
            DocumentLink.id == link_id, DocumentLink.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="document link not found")
    return link


def _link_by_token(db: Session, token: str) -> DocumentLink | None:
    return db.execute(
        select(DocumentLink).where(DocumentLink.token_hash == hash_token(token))
    ).scalar_one_or_none()


def _document_or_404_link(db: Session, workspace_id: str, document_id: str):
    doc = db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


def _is_expired(link: DocumentLink) -> bool:
    if link.expires_at is None:
        return False
    naive = link.expires_at.replace(tzinfo=None) if getattr(link.expires_at, "tzinfo", None) else link.expires_at
    return naive <= now().replace(tzinfo=None)


def _views_remaining(link: DocumentLink) -> int | None:
    if link.max_views is None:
        return None
    return max(0, link.max_views - link.view_count)


def _link_out(link: DocumentLink) -> LinkOut:
    return LinkOut(
        id=link.id,
        document_id=link.document_id,
        has_password=link.password_hash is not None,
        expires_at=link.expires_at,
        max_views=link.max_views,
        view_count=link.view_count,
        view_only=link.view_only,
        download_allowed=link.download_allowed,
        revoked=link.revoked,
        require_email_verification=link.require_email_verification,
        require_nda=link.require_nda,
        required_group_id=link.required_group_id,
        created_by=link.created_by,
        created_at=link.created_at,
    )


# ---------------------------------------------------------------------------
# Restricted link sessions (PM-030/039/042)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkViewer:
    """Either a full workspace principal or a single-link restricted session."""

    workspace_id: str
    principal: Principal | None
    session: LinkSession | None

    @property
    def actor_id(self) -> str:
        if self.principal is not None:
            return self.principal.user.id
        return "link-session:" + (self.session.id if self.session else "unknown")

    @property
    def is_restricted(self) -> bool:
        return self.session is not None


def optional_principal(
    db: Session = Depends(get_db),
    token: str | None = Depends(bearer_token),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal | None:
    """Resolve a normal bearer/API-key principal, but allow link-only viewers."""
    if token is None and x_api_key is None:
        return None
    return get_principal(db, token, x_api_key)


def link_viewer(
    workspace_id: str,
    x_link_session: str | None = Header(default=None, alias="X-Link-Session"),
    db: Session = Depends(get_db),
    principal: Principal | None = Depends(optional_principal),
) -> LinkViewer:
    """Authorise a viewer-facing route by workspace session or link session."""
    if x_link_session:
        if principal is not None:
            raise HTTPException(status_code=401, detail="mixed viewer credentials")
        session = db.execute(
            select(LinkSession).where(
                LinkSession.token_hash == hash_token(x_link_session),
                LinkSession.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if (session is None or session.revoked_at is not None or _is_expired(session)):
            raise HTTPException(
                status_code=401, detail="invalid or expired link session",
                headers={"WWW-Authenticate": "Bearer"},
            )
        link = db.get(DocumentLink, session.link_id)
        if link is None or link.workspace_id != workspace_id:
            raise HTTPException(status_code=401, detail="invalid link session")
        if link.revoked or _is_expired(link):
            raise HTTPException(status_code=410, detail="link is no longer available")
        return LinkViewer(workspace_id=workspace_id, principal=None, session=session)

    if principal is None:
        raise HTTPException(
            status_code=401, detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if principal.api_key_id is not None and DOCUMENT_READ not in (principal.api_key_scopes or ()):
        raise HTTPException(status_code=403, detail=f"permission required: {DOCUMENT_READ}")
    if not has_permission(principal.role, DOCUMENT_READ):
        raise HTTPException(status_code=403, detail=f"permission required: {DOCUMENT_READ}")
    return LinkViewer(workspace_id=workspace_id, principal=principal, session=None)


def verify_viewer_workspace(viewer: LinkViewer, workspace_id: str) -> None:
    if viewer.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="cross-workspace access is denied")
    if viewer.session is not None:
        if viewer.session.revoked_at is not None or _is_expired(viewer.session):
            raise HTTPException(status_code=401, detail="link session is no longer valid")
    elif viewer.principal is not None:
        verify_workspace(viewer.principal, workspace_id)


def require_link_scope(viewer: LinkViewer, link: DocumentLink) -> None:
    if viewer.session is None:
        return
    if viewer.session.link_id != link.id:
        raise HTTPException(status_code=403, detail="link session is scoped to another link")
    if link.revoked or _is_expired(link):
        raise HTTPException(status_code=410, detail="link is no longer available")


def _start_link_session(
    db: Session, workspace_id: str, link: DocumentLink, actor_id: str
) -> tuple[LinkSession, str]:
    raw = secrets.token_urlsafe(32)
    session = LinkSession(
        id=new_id(), workspace_id=workspace_id, link_id=link.id,
        token_hash=hash_token(raw), expires_at=link.expires_at or (now() + timedelta(hours=24)),
        revoked_at=None, created_at=now(),
    )
    db.add(session)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=DOCUMENT_LINK_SESSION_STARTED,
        entity_id=session.id,
        payload={"link_id": link.id, "document_id": link.document_id},
        actor_id=actor_id,
    )
    return session, raw


def _revoke_link_sessions(db: Session, workspace_id: str, link_id: str) -> int:
    sessions = db.execute(
        select(LinkSession).where(
            LinkSession.workspace_id == workspace_id,
            LinkSession.link_id == link_id,
            LinkSession.revoked_at.is_(None),
        )
    ).scalars().all()
    for session in sessions:
        session.revoked_at = now()
    if sessions:
        publish_event(
            db, workspace_id=workspace_id, event_type=DOCUMENT_LINK_SESSION_REVOKED,
            entity_id=link_id, payload={"sessions": len(sessions)},
        )
    return len(sessions)


# ---------------------------------------------------------------------------
# Viewer gates (PM-031, PM-034, PM-047, PM-063)
# ---------------------------------------------------------------------------


def _normal_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[1] if "@" in email else ""


def _rule_matches(rule: LinkAccessRule, email: str) -> bool:
    if not email:
        return False
    if rule.kind == "email":
        return _normal_email(rule.value) == email
    domain = _email_domain(email)
    if not domain:
        return False
    if domain == rule.value:
        return True
    return bool(rule.include_subdomains) and domain.endswith("." + rule.value)


def _enforce_access_rules(
    db: Session, link: DocumentLink, visitor_email: str | None
) -> None:
    rules = db.execute(
        select(LinkAccessRule).where(
            LinkAccessRule.workspace_id == link.workspace_id,
            LinkAccessRule.link_id == link.id,
        )
    ).scalars().all()
    if not rules:
        return
    email = _normal_email(visitor_email)
    for rule in rules:
        if rule.effect == "block" and _rule_matches(rule, email):
            raise HTTPException(status_code=403, detail="viewer is blocked by link policy")
    allow_rules = [rule for rule in rules if rule.effect == "allow"]
    if allow_rules and not any(_rule_matches(rule, email) for rule in allow_rules):
        raise HTTPException(status_code=403, detail="viewer is not allowlisted for this link")


def _enforce_email_verification(
    db: Session, link: DocumentLink, visitor_email: str | None
) -> None:
    if not link.require_email_verification:
        return
    email = _normal_email(visitor_email)
    if not email:
        raise HTTPException(status_code=403, detail="verified viewer email is required")
    record = db.execute(
        select(LinkVerification).where(
            LinkVerification.workspace_id == link.workspace_id,
            LinkVerification.link_id == link.id,
            LinkVerification.email == email,
            LinkVerification.verified_at.is_not(None),
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=403, detail="viewer email is not verified")


def _enforce_nda(
    db: Session, link: DocumentLink, visitor_email: str | None, contact_id: str | None
) -> None:
    if not link.require_nda:
        return
    email = _normal_email(visitor_email)
    query = select(Agreement.id).where(
        Agreement.workspace_id == link.workspace_id,
        Agreement.document_id == link.document_id,
        Agreement.accepted_at.is_not(None),
    )
    conditions = []
    if email:
        conditions.append(Agreement.visitor_email == email)
    if contact_id:
        conditions.append(Agreement.visitor_contact_id == contact_id)
    if not conditions:
        raise HTTPException(status_code=403, detail="NDA acceptance is required before access")
    query = query.where(or_(*conditions))
    if db.execute(query).scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="NDA acceptance is required before access")


def _enforce_permission_group(
    db: Session,
    link: DocumentLink,
    principal: Principal | None,
    visitor_email: str | None,
    contact: Contact | None,
) -> None:
    if not link.required_group_id:
        return
    group = db.execute(
        select(PermissionGroup).where(
            PermissionGroup.id == link.required_group_id,
            PermissionGroup.workspace_id == link.workspace_id,
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="permission group not found")
    members = db.execute(
        select(PermissionGroupMember).where(
            PermissionGroupMember.workspace_id == link.workspace_id,
            PermissionGroupMember.group_id == group.id,
        )
    ).scalars().all()
    identities = {_normal_email(visitor_email)}
    if contact is not None:
        identities.add(_normal_email(contact.email))
    if principal is not None:
        identities.add(principal.user.id)
        identities.add(_normal_email(principal.user.email))
    member_ids = {m.user_id for m in members if m.user_id}
    member_emails = {_normal_email(m.email) for m in members if m.email}
    if not (identities & (member_ids | member_emails)):
        raise HTTPException(status_code=403, detail="viewer is not in the link permission group")


def _enforce_link_gates(
    db: Session,
    link: DocumentLink,
    principal: Principal | None = None,
    visitor_email: str | None = None,
    contact_id: str | None = None,
    contact: Contact | None = None,
) -> None:
    """All viewer gates run before any content metadata or view is returned."""
    if contact is None and contact_id:
        contact = db.execute(
            select(Contact).where(
                Contact.id == contact_id, Contact.workspace_id == link.workspace_id
            )
        ).scalar_one_or_none()
    if contact is not None and not visitor_email:
        visitor_email = contact.email
    _enforce_access_rules(db, link, visitor_email)
    _enforce_email_verification(db, link, visitor_email)
    _enforce_nda(db, link, visitor_email, contact_id)
    _enforce_permission_group(db, link, principal, visitor_email, contact)


# ---------------------------------------------------------------------------
# Visitor identity and engagement fan-out (PM-073)
# ---------------------------------------------------------------------------


def _visitor_contact(
    db: Session,
    workspace_id: str,
    email: str | None,
    name: str | None,
    actor_id: str,
    owner_id: str | None = None,
) -> tuple[Contact | None, bool]:
    """Reuse the single CRM contact identity; never create a second one."""
    if not email:
        return None, False
    contact = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == email)
    ).scalar_one_or_none()
    if contact is not None:
        return contact, False
    contact = Contact(
        id=new_id(),
        workspace_id=workspace_id,
        email=email,
        full_name=name,
        source="document_view",
        # PM-081: the contact is assigned to the sharer, so real-time view
        # notifications reach the owner who owns the document relationship.
        owner_id=owner_id or actor_id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(contact)
    db.flush()
    return contact, True


def _contact_or_none(
    db: Session, workspace_id: str, contact_id: str | None
) -> Contact | None:
    if not contact_id:
        return None
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact


def _notify_engagement(
    db: Session,
    workspace_id: str,
    link: DocumentLink,
    document: Document,
    contact: Contact | None,
    correlation_id: str,
    actor_id: str,
    downloaded: bool = False,
) -> None:
    """Notify the assigned owner in-app. No external message is sent."""
    if contact is None:
        return
    assigned_owner = contact.owner_id or link.created_by
    notification = Notification(
        workspace_id=workspace_id,
        contact_id=contact.id,
        user_id=assigned_owner,
        title="Document " + ("downloaded" if downloaded else "viewed"),
        message=("Download" if downloaded else "View") + " of '" + document.title
                + "' by " + (contact.full_name or contact.email),
        category="document_download" if downloaded else "document_view",
        link="#/contacts/" + contact.id,
        read=False,
    )
    db.add(notification)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=NOTIFICATION_CREATED,
        entity_id=notification.id,
        correlation_id=correlation_id,
        payload={
            "contact_id": contact.id,
            "user_id": assigned_owner,
            "category": notification.category,
            "document_id": document.id,
        },
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Management endpoints (workspace-scoped, authenticated)
# ---------------------------------------------------------------------------


@router.post("/{document_id}/links", status_code=status.HTTP_201_CREATED)
def create_link(
    workspace_id: str,
    document_id: str,
    body: LinkCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    if body.required_group_id:
        group = db.execute(
            select(PermissionGroup.id).where(
                PermissionGroup.id == body.required_group_id,
                PermissionGroup.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail="permission group not found")

    raw_token = secrets.token_urlsafe(32)
    # PM-121: workspace preferences provide real defaults for new links, while
    # any value explicitly supplied in the request still wins.
    pref = _preference_or_create(db, workspace_id, principal.user.id)
    expires_in_hours = body.expires_in_hours
    if expires_in_hours is None and "expires_in_hours" not in body.model_fields_set:
        expires_in_hours = pref.default_link_expiry_hours
    view_only = body.view_only
    if "view_only" not in body.model_fields_set:
        view_only = pref.default_view_only
    expires_at = None
    if expires_in_hours is not None:
        expires_at = now() + timedelta(hours=expires_in_hours)

    password_hash = None
    if body.password:
        password_hash = hash_password(body.password)

    link = DocumentLink(
        id=new_id(),
        workspace_id=workspace_id,
        document_id=document_id,
        token_hash=hash_token(raw_token),
        password_hash=password_hash,
        expires_at=expires_at,
        max_views=body.max_views,
        view_count=0,
        view_only=view_only,
        download_allowed=body.download_allowed,
        revoked=False,
        require_email_verification=body.require_email_verification,
        require_nda=body.require_nda,
        required_group_id=body.required_group_id,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(link)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_LINK_CREATED,
        entity_id=link.id,
        payload={
            "document_id": document_id,
            "has_password": password_hash is not None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "max_views": body.max_views,
            "view_only": view_only,
            "download_allowed": body.download_allowed,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": link.id,
        "token": raw_token,
        "expires_at": expires_at,
        "view_only": view_only,
        "required_group_id": body.required_group_id,
    }


@router.get("/{document_id}/links", response_model=list[LinkOut])
def list_links(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[LinkOut]:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    rows = db.execute(
        select(DocumentLink)
        .where(
            DocumentLink.workspace_id == workspace_id,
            DocumentLink.document_id == document_id,
        )
        .order_by(DocumentLink.created_at.desc())
    ).scalars().all()
    return [_link_out(link) for link in rows]


@router.get("/links/{link_id}", response_model=LinkOut)
def get_link(
    workspace_id: str,
    link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> LinkOut:
    verify_workspace(principal, workspace_id)
    return _link_out(_link_or_404(db, workspace_id, link_id))


@router.patch("/links/{link_id}", response_model=LinkOut)
def update_link(
    workspace_id: str,
    link_id: str,
    body: LinkUpdate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> LinkOut:
    """PM-029/PM-032: rotate password, extend/clear expiry, change controls."""
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    fields = body.model_fields_set
    before = {
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "max_views": link.max_views,
        "view_only": link.view_only,
        "download_allowed": link.download_allowed,
        "has_password": link.password_hash is not None,
    }
    if "required_group_id" in fields and body.required_group_id:
        group = db.execute(
            select(PermissionGroup.id).where(
                PermissionGroup.id == body.required_group_id,
                PermissionGroup.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail="permission group not found")

    sessions_revoked = 0
    if "password" in fields and body.password:
        link.password_hash = hash_password(body.password)
        sessions_revoked += _revoke_link_sessions(db, workspace_id, link.id)
    if body.clear_password:
        link.password_hash = None
        sessions_revoked += _revoke_link_sessions(db, workspace_id, link.id)
    if "expires_in_hours" in fields:
        link.expires_at = (
            now() + timedelta(hours=body.expires_in_hours)
            if body.expires_in_hours is not None else None
        )
    if "max_views" in fields:
        link.max_views = body.max_views
    if "required_group_id" in fields:
        link.required_group_id = body.required_group_id
    for name in ("view_only", "download_allowed", "require_email_verification", "require_nda"):
        if name in fields and getattr(body, name) is not None:
            setattr(link, name, getattr(body, name))

    publish_event(
        db, workspace_id=workspace_id, event_type=DOCUMENT_LINK_UPDATED,
        entity_id=link.id,
        payload={
            "document_id": link.document_id,
            "fields": sorted(fields),
            "before": before,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "has_password": link.password_hash is not None,
            "sessions_revoked": sessions_revoked,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return _link_out(link)


@router.post("/links/{link_id}/revoke", response_model=LinkOut)
def revoke_link(
    workspace_id: str,
    link_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> LinkOut:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    if not link.revoked:
        link.revoked = True
        revoked_sessions = _revoke_link_sessions(db, workspace_id, link.id)
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=DOCUMENT_LINK_REVOKED,
            entity_id=link.id,
            payload={"document_id": link.document_id, "sessions": revoked_sessions},
            actor_id=principal.user.id,
        )
        db.commit()
    return _link_out(link)


@router.get("/links/{link_id}/visits", response_model=list[VisitOut])
def list_visits(
    workspace_id: str,
    link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[LinkVisit]:
    verify_workspace(principal, workspace_id)
    _link_or_404(db, workspace_id, link_id)
    return db.execute(
        select(LinkVisit)
        .where(LinkVisit.workspace_id == workspace_id, LinkVisit.link_id == link_id)
        .order_by(LinkVisit.started_at.desc())
    ).scalars().all()


@router.get("/{document_id}/analytics", response_model=list[PageAnalyticsOut])
def document_analytics(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[PageAnalyticsOut]:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    link_ids = db.execute(
        select(DocumentLink.id).where(
            DocumentLink.workspace_id == workspace_id,
            DocumentLink.document_id == document_id,
        )
    ).scalars().all()
    if not link_ids:
        return []
    visit_ids = db.execute(
        select(LinkVisit.id).where(
            LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id.in_(link_ids),
        )
    ).scalars().all()
    if not visit_ids:
        return []
    rows = db.execute(
        select(
            PageView.page_number,
            func.count(PageView.id),
            func.coalesce(func.sum(PageView.duration_seconds), 0),
        )
        .where(PageView.workspace_id == workspace_id, PageView.visit_id.in_(visit_ids))
        .group_by(PageView.page_number)
        .order_by(PageView.page_number)
    ).all()
    return [
        PageAnalyticsOut(page_number=r[0], views=r[1], total_duration_seconds=int(r[2] or 0))
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Token-based resolution endpoints (authenticated caller supplies token)
# ---------------------------------------------------------------------------


@router.get("/links/resolve/{token}", response_model=LinkResolveOut)
def resolve_link(
    workspace_id: str,
    token: str,
    visitor_email: str | None = Query(None),
    contact_id: str | None = Query(None),
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> LinkResolveOut:
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    # PM-032: an expired link is rejected at the resolver, not merely labelled.
    if _is_expired(link):
        raise HTTPException(status_code=410, detail="link has expired")
    doc = db.execute(
        select(Document).where(Document.id == link.document_id, Document.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    # PM-031/034/047/063: gates run before document metadata is returned, so
    # an NDA gate really withholds content until acceptance is recorded.
    _enforce_link_gates(
        db, link, principal=viewer.principal, visitor_email=visitor_email, contact_id=contact_id
    )
    version = primary_version(db, workspace_id, doc.id)
    pages: list[dict] = []
    if version is not None:
        page_rows = db.execute(
            select(DocumentPage)
            .where(
                DocumentPage.workspace_id == workspace_id,
                DocumentPage.version_id == version.id,
            )
            .order_by(DocumentPage.page_number)
        ).scalars().all()
        pages = [
            {"id": page.id, "page_number": page.page_number, "label": page.label}
            for page in page_rows
        ]
    expired = _is_expired(link)
    if not expired and not link.revoked:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=DOCUMENT_LINK_ACCESSED,
            entity_id=link.id,
            payload={"document_id": link.document_id},
            actor_id=viewer.actor_id,
        )
        db.commit()
    return LinkResolveOut(
        link_id=link.id,
        document_id=doc.id,
        title=doc.title,
        doc_type=doc.doc_type,
        size_bytes=version.size_bytes if version is not None else doc.size_bytes,
        primary_version_id=version.id if version is not None else None,
        primary_version_number=version.version_number if version is not None else None,
        storage_path=version.storage_path if version is not None else None,
        pages=pages,
        view_only=link.view_only,
        download_allowed=link.download_allowed,
        password_required=link.password_hash is not None,
        expired=expired,
        revoked=link.revoked,
        views_remaining=_views_remaining(link),
    )


@router.post("/links/resolve/{token}/unlock")
def unlock_link(
    workspace_id: str,
    token: str,
    body: UnlockRequest,
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> dict:
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    if link.revoked or _is_expired(link):
        raise HTTPException(status_code=410, detail="link is no longer available")
    if link.password_hash is not None and not verify_password(body.password, link.password_hash):
        raise HTTPException(status_code=403, detail="incorrect password")
    session, raw_token = _start_link_session(db, workspace_id, link, viewer.actor_id)
    db.commit()
    return {
        "unlocked": True,
        "session_token": raw_token,
        "session_expires_at": session.expires_at,
        "link_id": link.id,
    }


@router.post("/links/resolve/{token}/identify")
def identify_visitor(
    workspace_id: str,
    token: str,
    body: VisitorIdentifyRequest,
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> dict:
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    if link.revoked or _is_expired(link):
        raise HTTPException(status_code=410, detail="link is no longer available")
    _enforce_link_gates(db, link, principal=viewer.principal, visitor_email=body.visitor_email)
    contact, created = _visitor_contact(
        db, workspace_id, body.visitor_email, body.visitor_name, viewer.actor_id,
        owner_id=link.created_by,
    )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_VISITOR_IDENTIFIED,
        entity_id=contact.id if contact else link.id,
        payload={
            "document_id": link.document_id,
            "visitor_name": body.visitor_name,
            "visitor_email": body.visitor_email,
            "contact_id": contact.id if contact else None,
        },
        actor_id=viewer.actor_id,
    )
    db.commit()
    return {
        "identified": True,
        "contact_id": contact.id if contact else None,
        "created": created,
    }


@router.post("/links/resolve/{token}/visits", response_model=VisitOut, status_code=status.HTTP_201_CREATED)
def start_visit(
    workspace_id: str,
    token: str,
    body: VisitStartRequest,
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> LinkVisit:
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    if link.revoked:
        raise HTTPException(status_code=410, detail="link has been revoked")
    if _is_expired(link):
        raise HTTPException(status_code=410, detail="link has expired")
    if link.max_views is not None and link.view_count >= link.max_views:
        raise HTTPException(status_code=429, detail="view limit reached")

    document = db.execute(
        select(Document).where(
            Document.id == link.document_id, Document.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")

    contact = _contact_or_none(db, workspace_id, body.contact_id)
    if contact is None and body.contact_id is None:
        contact, _ = _visitor_contact(
            db, workspace_id, body.visitor_email, body.visitor_name, viewer.actor_id,
            owner_id=link.created_by,
        )
    # Gates are enforced before the view row is created or the counter moves.
    _enforce_link_gates(
        db, link, principal=viewer.principal, visitor_email=body.visitor_email,
        contact_id=body.contact_id, contact=contact,
    )

    visit = LinkVisit(
        id=new_id(),
        workspace_id=workspace_id,
        link_id=link.id,
        contact_id=contact.id if contact else None,
        visitor_name=body.visitor_name,
        visitor_email=body.visitor_email,
        ip_address=body.ip_address,
        user_agent=body.user_agent,
        started_at=now(),
        pages_viewed=0,
    )
    db.add(visit)
    link.view_count += 1
    db.flush()

    correlation_id = new_id()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_VISIT_RECORDED,
        entity_id=visit.id,
        correlation_id=correlation_id,
        payload={"link_id": link.id, "document_id": document.id},
        actor_id=viewer.actor_id,
    )
    # PM-073: one shared event per view. When the visitor is a known CRM
    # contact the event's entity_id is that contact, so contact_timeline()
    # returns it; the same correlation id carries the audit and notification
    # events with it.
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_VIEWED,
        entity_id=contact.id if contact else document.id,
        correlation_id=correlation_id,
        payload={
            "document_id": document.id,
            "title": document.title,
            "link_id": link.id,
            "visit_id": visit.id,
            "contact_id": contact.id if contact else None,
        },
        actor_id=viewer.actor_id,
    )
    _notify_engagement(
        db, workspace_id, link, document, contact, correlation_id, viewer.actor_id
    )
    db.commit()
    return visit


@router.post("/links/resolve/{token}/visits/{visit_id}/page-views", status_code=status.HTTP_201_CREATED)
def record_page_view(
    workspace_id: str,
    token: str,
    visit_id: str,
    body: PageViewRequest,
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> dict:
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    visit = db.execute(
        select(LinkVisit).where(
            LinkVisit.id == visit_id,
            LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id == link.id,
        )
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=404, detail="visit not found")
    if body.page_id:
        version = primary_version(db, workspace_id, link.document_id)
        page = None
        if version is not None:
            page = db.execute(
                select(DocumentPage).where(
                    DocumentPage.id == body.page_id,
                    DocumentPage.workspace_id == workspace_id,
                    DocumentPage.version_id == version.id,
                )
            ).scalar_one_or_none()
        if page is None:
            raise HTTPException(status_code=404, detail="page not found in primary version")
        if page.page_number != body.page_number:
            raise HTTPException(status_code=422, detail="page id and page number disagree")
    pv = PageView(
        id=new_id(),
        workspace_id=workspace_id,
        visit_id=visit.id,
        page_number=body.page_number,
        page_id=body.page_id,
        viewed_at=now(),
        entered_at=now(),
        duration_seconds=body.duration_seconds,
    )
    db.add(pv)
    visit.pages_viewed = max(visit.pages_viewed, body.page_number)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PAGE_VIEWED,
        entity_id=pv.id,
        payload={"visit_id": visit.id, "page_number": body.page_number, "page_id": body.page_id},
        actor_id=viewer.actor_id,
    )
    db.commit()
    return {"recorded": True, "page_view_id": pv.id}


def _validate_link_page(
    db: Session, workspace_id: str, link: DocumentLink,
    page_number: int, page_id: str | None,
) -> None:
    if not page_id:
        return
    version = primary_version(db, workspace_id, link.document_id)
    page = None
    if version is not None:
        page = db.execute(
            select(DocumentPage).where(
                DocumentPage.id == page_id,
                DocumentPage.workspace_id == workspace_id,
                DocumentPage.version_id == version.id,
            )
        ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="page not found in primary version")
    if page.page_number != page_number:
        raise HTTPException(status_code=422, detail="page id and page number disagree")


@router.post("/links/resolve/{token}/page-views/batch", status_code=status.HTTP_201_CREATED)
def ingest_page_events(
    workspace_id: str,
    token: str,
    body: PageEventBatch,
    viewer: LinkViewer = Depends(link_viewer),
    db: Session = Depends(get_db),
) -> dict:
    """PM-074: ingest real per-page view/timing events for one scoped visit."""
    verify_viewer_workspace(viewer, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    require_link_scope(viewer, link)
    visit = db.execute(
        select(LinkVisit).where(
            LinkVisit.id == body.visit_id, LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id == link.id,
        )
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=404, detail="visit not found")

    created: list[str] = []
    for event in body.events:
        _validate_link_page(db, workspace_id, link, event.page_number, event.page_id)
        duration = event.duration_seconds
        entered = now() - timedelta(seconds=duration) if duration is not None else now()
        left = now() if (duration is not None and event.leave) else None
        pv = PageView(
            id=new_id(), workspace_id=workspace_id, visit_id=visit.id,
            page_number=event.page_number, page_id=event.page_id,
            viewed_at=entered, entered_at=entered, left_at=left,
            duration_seconds=duration,
        )
        db.add(pv)
        db.flush()
        created.append(pv.id)
        visit.pages_viewed = max(visit.pages_viewed, event.page_number)
        publish_event(
            db, workspace_id=workspace_id, event_type=DOCUMENT_PAGE_VIEWED,
            entity_id=pv.id,
            payload={"visit_id": visit.id, "document_id": link.document_id,
                     "page_number": event.page_number, "page_id": event.page_id},
            actor_id=viewer.actor_id,
        )
        if duration is not None and event.leave:
            publish_event(
                db, workspace_id=workspace_id, event_type=DOCUMENT_PAGE_TIMED,
                entity_id=pv.id,
                payload={"document_id": link.document_id, "page_number": event.page_number,
                         "page_view_id": pv.id, "duration_seconds": duration},
                actor_id=viewer.actor_id,
            )
    db.commit()
    return {"ingested": len(created), "page_view_ids": created, "visit_id": visit.id}


@router.post("/links/resolve/{token}/visits/{visit_id}/end")
def end_visit(
    workspace_id: str,
    token: str,
    visit_id: str,
    duration_seconds: int | None = Query(default=None, ge=0),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    visit = db.execute(
        select(LinkVisit).where(
            LinkVisit.id == visit_id,
            LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id == link.id,
        )
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=404, detail="visit not found")
    # PM-079: duration always comes from real timestamps. The legacy query
    # parameter is accepted for compatibility but never used as the source.
    visit.ended_at = now()
    # SQLite does not preserve tzinfo on DateTime columns, so a stored
    # started_at may be naive while now() is tz-aware. Normalise via the shared
    # helper instead of subtracting mixed datetimes directly (PM-079).
    elapsed = _duration_between(visit.started_at, visit.ended_at)
    visit.duration_seconds = elapsed
    db.commit()
    return {"ended": True, "visit_id": visit.id, "duration_seconds": elapsed}


@router.post("/links/resolve/{token}/visits/{visit_id}/download", status_code=status.HTTP_201_CREATED)
def record_download(
    workspace_id: str,
    token: str,
    visit_id: str,
    body: DownloadRequest,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Record an authorised download.

    NOVARA stores document metadata only, so this records the fact of the
    download through the shared event bus; it never serves file bytes. The
    share link's ``download_allowed`` policy is enforced here as well as being
    advertised by link resolution.
    """
    verify_workspace(principal, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    if link.revoked or _is_expired(link):
        raise HTTPException(status_code=410, detail="link is no longer available")
    if not link.download_allowed:
        raise HTTPException(status_code=403, detail="downloads are not allowed for this link")
    visit = db.execute(
        select(LinkVisit).where(
            LinkVisit.id == visit_id,
            LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id == link.id,
        )
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=404, detail="visit not found")
    document = db.execute(
        select(Document).where(
            Document.id == link.document_id, Document.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    contact = _contact_or_none(db, workspace_id, visit.contact_id)
    correlation_id = new_id()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_DOWNLOADED,
        entity_id=contact.id if contact else document.id,
        correlation_id=correlation_id,
        payload={
            "document_id": document.id,
            "title": document.title,
            "link_id": link.id,
            "visit_id": visit.id,
            "page_number": body.page_number,
            "contact_id": contact.id if contact else None,
        },
        actor_id=principal.user.id,
    )
    _notify_engagement(
        db, workspace_id, link, document, contact, correlation_id, principal.user.id,
        downloaded=True,
    )
    # PM-082: the real serving boundary stamps the visit, so download status
    # is durable and can be rolled up in analytics.
    visit.downloaded_at = now()
    db.commit()
    return {"downloaded": True, "visit_id": visit.id, "document_id": document.id}


@router.post("/links/{link_id}/instant-revoke")
def instant_revoke(
    workspace_id: str,
    link_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    link.revoked = True
    revoked_sessions = _revoke_link_sessions(db, workspace_id, link.id)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_LINK_REVOKED,
        entity_id=link.id,
        payload={"document_id": link.document_id, "instant": True,
                 "sessions": revoked_sessions},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"revoked": True, "link_id": link.id}


# ---------------------------------------------------------------------------
# PM-026/PM-047 — agreements and the NDA content gate
# ---------------------------------------------------------------------------


@router.post("/{document_id}/agreements", status_code=status.HTTP_201_CREATED)
def create_agreement(
    workspace_id: str,
    document_id: str,
    body: AgreementCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    agreement = Agreement(
        id=new_id(),
        workspace_id=workspace_id,
        document_id=document_id,
        title=body.title,
        body=body.body,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(agreement)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_AGREEMENT_CREATED,
        entity_id=agreement.id,
        payload={"document_id": document_id, "title": agreement.title},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": agreement.id, "document_id": document_id, "title": agreement.title,
        "body": agreement.body, "accepted_at": None, "visitor_email": None,
        "visitor_contact_id": None, "signature_reference": None,
    }


@router.get("/{document_id}/agreements")
def list_agreements(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    rows = db.execute(
        select(Agreement).where(
            Agreement.workspace_id == workspace_id,
            Agreement.document_id == document_id,
        ).order_by(Agreement.created_at.desc())
    ).scalars().all()
    return [{
        "id": row.id, "document_id": row.document_id, "title": row.title,
        "body": row.body, "accepted_at": row.accepted_at,
        "visitor_email": row.visitor_email,
        "visitor_contact_id": row.visitor_contact_id,
        "signature_reference": row.signature_reference,
    } for row in rows]


@router.post("/agreements/{agreement_id}/accept")
def accept_agreement(
    workspace_id: str,
    agreement_id: str,
    body: AgreementAccept,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    agreement = db.execute(
        select(Agreement).where(
            Agreement.id == agreement_id, Agreement.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="agreement not found")
    if agreement.accepted_at is not None:
        raise HTTPException(status_code=409, detail="agreement is already accepted and immutable")
    contact = _contact_or_none(db, workspace_id, body.contact_id)
    email = _normal_email(body.visitor_email or (contact.email if contact else None))
    if contact is None and email:
        contact, _ = _visitor_contact(
            db, workspace_id, email, body.visitor_name, principal.user.id,
            owner_id=agreement.created_by,
        )
    agreement.accepted_at = now()
    agreement.visitor_email = email or None
    agreement.visitor_contact_id = contact.id if contact else None
    agreement.signature_reference = body.signature_reference
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_AGREEMENT_ACCEPTED,
        entity_id=agreement.id,
        payload={
            "document_id": agreement.document_id,
            "visitor_email": agreement.visitor_email,
            "contact_id": agreement.visitor_contact_id,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": agreement.id, "accepted_at": agreement.accepted_at,
        "visitor_email": agreement.visitor_email,
        "visitor_contact_id": agreement.visitor_contact_id,
    }


@router.patch("/agreements/{agreement_id}")
def patch_agreement(
    workspace_id: str,
    agreement_id: str,
    body: AgreementPatch,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    agreement = db.execute(
        select(Agreement).where(
            Agreement.id == agreement_id, Agreement.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="agreement not found")
    if agreement.accepted_at is not None:
        raise HTTPException(status_code=409, detail="accepted agreements are immutable")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(agreement, key, value)
    db.commit()
    return {"id": agreement.id, "title": agreement.title, "body": agreement.body}


# ---------------------------------------------------------------------------
# PM-031 — viewer email verification (local one-time code, no outbound mail)
# ---------------------------------------------------------------------------


@router.post("/links/resolve/{token}/request-verification")
def request_verification(
    workspace_id: str,
    token: str,
    body: VerificationRequest,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    if not link.require_email_verification:
        raise HTTPException(status_code=409, detail="link does not require verification")
    raw = secrets.token_urlsafe(12)
    expires_at = now() + timedelta(hours=1)
    record = db.execute(
        select(LinkVerification).where(
            LinkVerification.workspace_id == workspace_id,
            LinkVerification.link_id == link.id,
            LinkVerification.email == body.email,
        )
    ).scalar_one_or_none()
    if record is None:
        record = LinkVerification(
            id=new_id(), workspace_id=workspace_id, link_id=link.id, email=body.email,
            code_hash=hash_token(raw), expires_at=expires_at,
            verified_at=None, created_at=now(),
        )
        db.add(record)
    else:
        record.code_hash = hash_token(raw)
        record.expires_at = expires_at
        record.verified_at = None
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_EMAIL_VERIFICATION_ISSUED,
        entity_id=link.id,
        payload={"email": body.email, "delivery": "api_only_no_outbound_message"},
        actor_id=principal.user.id,
    )
    db.commit()
    # No email/SMS/webhook is sent; the local code is returned to the caller.
    return {"email": body.email, "code": raw, "expires_at": expires_at}


@router.post("/links/resolve/{token}/confirm-verification")
def confirm_verification(
    workspace_id: str,
    token: str,
    body: VerificationConfirm,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    record = db.execute(
        select(LinkVerification).where(
            LinkVerification.workspace_id == workspace_id,
            LinkVerification.link_id == link.id,
            LinkVerification.email == body.email,
        )
    ).scalar_one_or_none()
    if record is None or _is_expired(record):
        raise HTTPException(status_code=404, detail="verification request not found")
    if hash_token(body.code) != record.code_hash:
        raise HTTPException(status_code=403, detail="incorrect verification code")
    record.verified_at = record.verified_at or now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_EMAIL_VERIFIED,
        entity_id=link.id,
        payload={"email": body.email},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"verified": True, "email": body.email}


# ---------------------------------------------------------------------------
# PM-034 — email allow/block rules
# ---------------------------------------------------------------------------


@router.post("/links/{link_id}/access-rules", status_code=status.HTTP_201_CREATED)
def create_access_rule(
    workspace_id: str,
    link_id: str,
    body: AccessRuleCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    value = body.value
    if body.kind == "email":
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise HTTPException(status_code=422, detail="invalid email rule")
    elif not value or "." not in value:
        raise HTTPException(status_code=422, detail="invalid domain rule")
    exists = db.execute(
        select(LinkAccessRule.id).where(
            LinkAccessRule.workspace_id == workspace_id,
            LinkAccessRule.link_id == link.id,
            LinkAccessRule.effect == body.effect,
            LinkAccessRule.kind == body.kind,
            LinkAccessRule.value == value,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="access rule already exists")
    rule = LinkAccessRule(
        id=new_id(), workspace_id=workspace_id, link_id=link.id,
        effect=body.effect, kind=body.kind, value=value,
        include_subdomains=body.include_subdomains if body.kind == "domain" else False,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(rule)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_ACCESS_RULE_CREATED,
        entity_id=link.id,
        payload={"effect": rule.effect, "kind": rule.kind, "value": rule.value},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": rule.id, "effect": rule.effect, "kind": rule.kind, "value": rule.value,
        "include_subdomains": rule.include_subdomains,
    }


@router.get("/links/{link_id}/access-rules")
def list_access_rules(
    workspace_id: str,
    link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    rows = db.execute(
        select(LinkAccessRule).where(
            LinkAccessRule.workspace_id == workspace_id, LinkAccessRule.link_id == link.id
        )
    ).scalars().all()
    return [{
        "id": r.id, "effect": r.effect, "kind": r.kind, "value": r.value,
        "include_subdomains": r.include_subdomains,
    } for r in rows]


# ---------------------------------------------------------------------------
# PM-063 — per-object permission groups
# ---------------------------------------------------------------------------


@router.post("/permission-groups", status_code=status.HTTP_201_CREATED)
def create_permission_group(
    workspace_id: str,
    body: PermissionGroupCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    group = PermissionGroup(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(group)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PERMISSION_GROUP_CREATED,
        entity_id=group.id,
        payload={"name": group.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": group.id, "name": group.name, "workspace_id": workspace_id}


@router.get("/permission-groups")
def list_permission_groups(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(PermissionGroup).where(
            PermissionGroup.workspace_id == workspace_id
        ).order_by(PermissionGroup.created_at.desc())
    ).scalars().all()
    return [{"id": g.id, "name": g.name, "workspace_id": g.workspace_id} for g in rows]


@router.post("/permission-groups/{group_id}/members", status_code=status.HTTP_201_CREATED)
def add_permission_group_member(
    workspace_id: str,
    group_id: str,
    body: PermissionGroupMemberCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    group = db.execute(
        select(PermissionGroup).where(
            PermissionGroup.id == group_id, PermissionGroup.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="permission group not found")
    if bool(body.user_id) == bool(body.email):
        raise HTTPException(status_code=422, detail="exactly one of user_id or email is required")
    if body.user_id:
        _active_member_or_none = db.execute(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == body.user_id,
                WorkspaceMember.status == "active",
            )
        ).scalar_one_or_none()
        if _active_member_or_none is None:
            raise HTTPException(status_code=404, detail="workspace member not found")
    member = PermissionGroupMember(
        id=new_id(), workspace_id=workspace_id, group_id=group.id,
        user_id=body.user_id, email=body.email, created_at=now(),
    )
    db.add(member)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PERMISSION_GROUP_MEMBER_ADDED,
        entity_id=group.id,
        payload={"user_id": body.user_id, "email": body.email},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"group_id": group.id, "user_id": body.user_id, "email": body.email}


@router.get("/permission-groups/{group_id}/members")
def list_permission_group_members(
    workspace_id: str,
    group_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    group = db.execute(
        select(PermissionGroup).where(
            PermissionGroup.id == group_id, PermissionGroup.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="permission group not found")
    rows = db.execute(
        select(PermissionGroupMember).where(
            PermissionGroupMember.workspace_id == workspace_id,
            PermissionGroupMember.group_id == group.id,
        )
    ).scalars().all()
    return [{"user_id": r.user_id, "email": r.email} for r in rows]


# ---------------------------------------------------------------------------
# PM-075/PM-078/PM-079/PM-082/PM-089/PM-090 — local engagement analytics
# ---------------------------------------------------------------------------


def _duration_between(start, end) -> int:
    if start is None or end is None:
        return 0
    start_naive = start.replace(tzinfo=None) if getattr(start, "tzinfo", None) else start
    end_naive = end.replace(tzinfo=None) if getattr(end, "tzinfo", None) else end
    return max(0, int((end_naive - start_naive).total_seconds()))


def _link_document_ids(db: Session, workspace_id: str, document_id: str) -> list[str]:
    return list(db.execute(
        select(DocumentLink.id).where(
            DocumentLink.workspace_id == workspace_id,
            DocumentLink.document_id == document_id,
        )
    ).scalars().all())


@router.post("/links/resolve/{token}/visits/{visit_id}/page-views/{page_view_id}/leave")
def leave_page(
    workspace_id: str,
    token: str,
    visit_id: str,
    page_view_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_by_token(db, token)
    if link is None or link.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="link not found")
    visit = db.execute(
        select(LinkVisit).where(
            LinkVisit.id == visit_id, LinkVisit.workspace_id == workspace_id,
            LinkVisit.link_id == link.id,
        )
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=404, detail="visit not found")
    page_view = db.execute(
        select(PageView).where(
            PageView.id == page_view_id, PageView.workspace_id == workspace_id,
            PageView.visit_id == visit.id,
        )
    ).scalar_one_or_none()
    if page_view is None:
        raise HTTPException(status_code=404, detail="page view not found")
    entered = page_view.entered_at or page_view.viewed_at
    page_view.left_at = now()
    # An idle cap prevents a forgotten tab from inflating read time.
    page_view.duration_seconds = min(_duration_between(entered, page_view.left_at), 1800)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PAGE_TIMED,
        entity_id=page_view.id,
        payload={"document_id": link.document_id, "page_number": page_view.page_number,
                 "duration_seconds": page_view.duration_seconds},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"left": True, "page_view_id": page_view.id,
            "duration_seconds": page_view.duration_seconds}


@router.get("/{document_id}/analytics/summary")
def analytics_summary(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    link_ids = _link_document_ids(db, workspace_id, document_id)
    if not link_ids:
        return {"total_views": 0, "unique_visitors": 0, "total_downloads": 0,
                "total_read_seconds": 0, "average_view_seconds": 0}
    visits = db.execute(
        select(LinkVisit).where(
            LinkVisit.workspace_id == workspace_id, LinkVisit.link_id.in_(link_ids)
        )
    ).scalars().all()
    identities = set()
    for visit in visits:
        if visit.contact_id:
            identities.add("contact:" + visit.contact_id)
        elif visit.visitor_email:
            identities.add("email:" + _normal_email(visit.visitor_email))
        else:
            identities.add("anonymous:" + visit.id)
    durations = [
        _duration_between(visit.started_at, visit.ended_at)
        if visit.ended_at else (visit.duration_seconds or 0)
        for visit in visits
    ]
    total = sum(durations)
    return {
        "total_views": len(visits),
        "unique_visitors": len(identities),
        "total_downloads": sum(1 for v in visits if v.downloaded_at is not None),
        "total_read_seconds": total,
        "average_view_seconds": int(total / len(visits)) if visits else 0,
    }


@router.get("/{document_id}/analytics/timing")
def analytics_timing(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    link_ids = _link_document_ids(db, workspace_id, document_id)
    if not link_ids:
        return []
    visits = db.execute(
        select(LinkVisit).where(
            LinkVisit.workspace_id == workspace_id, LinkVisit.link_id.in_(link_ids)
        ).order_by(LinkVisit.started_at)
    ).scalars().all()
    return [{
        "visit_id": v.id, "contact_id": v.contact_id,
        "visitor_email": v.visitor_email,
        "started_at": v.started_at, "ended_at": v.ended_at,
        "duration_seconds": _duration_between(v.started_at, v.ended_at),
    } for v in visits]


@router.get("/{document_id}/analytics/time-on-page")
def analytics_time_on_page(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    link_ids = _link_document_ids(db, workspace_id, document_id)
    if not link_ids:
        return []
    visit_ids = list(db.execute(
        select(LinkVisit.id).where(
            LinkVisit.workspace_id == workspace_id, LinkVisit.link_id.in_(link_ids)
        )
    ).scalars().all())
    page_views = db.execute(
        select(PageView).where(
            PageView.workspace_id == workspace_id, PageView.visit_id.in_(visit_ids)
        )
    ).scalars().all()
    grouped: dict[str | int, dict] = {}
    for pv in page_views:
        key = pv.page_id or pv.page_number
        row = grouped.setdefault(key, {
            "page_id": pv.page_id, "page_number": pv.page_number,
            "views": 0, "total_duration_seconds": 0,
        })
        row["views"] += 1
        row["total_duration_seconds"] += (
            _duration_between(pv.entered_at, pv.left_at)
            if pv.entered_at and pv.left_at else (pv.duration_seconds or 0)
        )
    return sorted(grouped.values(), key=lambda row: row["page_number"])


@router.get("/analytics/events")
def analytics_from_events(
    workspace_id: str,
    document_id: str | None = Query(None),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """PM-090: counts reproducible from the append-only event log alone."""
    verify_workspace(principal, workspace_id)
    query = select(Event.event_type, func.count(Event.id)).where(
        Event.workspace_id == workspace_id,
        Event.event_type.in_((DOCUMENT_VIEWED, DOCUMENT_DOWNLOADED, DOCUMENT_PAGE_VIEWED)),
    ).group_by(Event.event_type).order_by(Event.event_type)
    if document_id:
        _document_or_404_link(db, workspace_id, document_id)
    rows = db.execute(query).all()
    if document_id:
        events = db.execute(
            select(Event).where(
                Event.workspace_id == workspace_id,
                Event.event_type.in_((DOCUMENT_VIEWED, DOCUMENT_DOWNLOADED, DOCUMENT_PAGE_VIEWED)),
            )
        ).scalars().all()
        counts: dict[str, int] = {}
        for event in events:
            if (event.payload or {}).get("document_id") == document_id:
                counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return [{"event_type": key, "count": counts[key]} for key in sorted(counts)]
    return [{"event_type": row[0], "count": row[1]} for row in rows]


@router.get("/links/{link_id}/views", response_model=list[VisitOut])
def link_view_history(
    workspace_id: str,
    link_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[LinkVisit]:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    return db.execute(
        select(LinkVisit)
        .where(LinkVisit.workspace_id == workspace_id, LinkVisit.link_id == link.id)
        .order_by(LinkVisit.started_at.desc())
        .offset(skip).limit(limit)
    ).scalars().all()


@router.get("/visitors/{visitor_id}/views", response_model=list[VisitOut])
def visitor_view_history(
    workspace_id: str,
    visitor_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[LinkVisit]:
    verify_workspace(principal, workspace_id)
    contact = db.execute(
        select(Contact).where(Contact.id == visitor_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="visitor not found")
    return db.execute(
        select(LinkVisit)
        .where(LinkVisit.workspace_id == workspace_id, LinkVisit.contact_id == contact.id)
        .order_by(LinkVisit.started_at.desc())
        .offset(skip).limit(limit)
    ).scalars().all()


@router.get("/rooms/{room_id}/analytics")
def room_analytics(
    workspace_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """PM-089: room rollup over the same real view rows, never mock figures."""
    verify_workspace(principal, workspace_id)
    room = db.execute(
        select(DataRoom).where(DataRoom.id == room_id, DataRoom.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="data room not found")
    document_ids = set(db.execute(
        select(Document.id).where(
            Document.workspace_id == workspace_id, Document.room_id == room.id
        )
    ).scalars().all())
    document_ids.update(db.execute(
        select(DocumentRoomMembership.document_id).where(
            DocumentRoomMembership.workspace_id == workspace_id,
            DocumentRoomMembership.room_id == room.id,
        )
    ).scalars().all())
    if not document_ids:
        return {"total_views": 0, "unique_viewers": 0, "total_read_seconds": 0,
                "documents": []}
    link_ids = list(db.execute(
        select(DocumentLink.id).where(
            DocumentLink.workspace_id == workspace_id,
            DocumentLink.document_id.in_(document_ids),
        )
    ).scalars().all())
    visits = db.execute(
        select(LinkVisit).where(
            LinkVisit.workspace_id == workspace_id, LinkVisit.link_id.in_(link_ids)
        )
    ).scalars().all() if link_ids else []
    identities = {
        ("contact:" + v.contact_id) if v.contact_id
        else (("email:" + _normal_email(v.visitor_email)) if v.visitor_email
              else ("anonymous:" + v.id))
        for v in visits
    }
    read_seconds = sum(
        _duration_between(v.started_at, v.ended_at) if v.ended_at else (v.duration_seconds or 0)
        for v in visits
    )
    per_document = []
    for doc_id in sorted(document_ids):
        doc_links = [link for link in db.execute(
            select(DocumentLink).where(
                DocumentLink.workspace_id == workspace_id,
                DocumentLink.document_id == doc_id,
            )
        ).scalars().all() if link.id in link_ids]
        doc_visits = [v for v in visits if v.link_id in {link.id for link in doc_links}]
        per_document.append({
            "document_id": doc_id,
            "views": len(doc_visits),
            "unique_viewers": len({
                ("contact:" + v.contact_id) if v.contact_id
                else (("email:" + _normal_email(v.visitor_email)) if v.visitor_email
                      else ("anonymous:" + v.id))
                for v in doc_visits
            }),
        })
    return {
        "total_views": len(visits),
        "unique_viewers": len(identities),
        "total_read_seconds": read_seconds,
        "documents": per_document,
    }


# ---------------------------------------------------------------------------
# PM-074: page-by-page analytics aggregation over real persisted view rows
# ---------------------------------------------------------------------------


@router.get("/{document_id}/analytics/pages", response_model=list[DocumentPageAnalyticsOut])
def analytics_pages(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DocumentPageAnalyticsOut]:
    """Real per-page view counts, unique viewers and durations for a document.

    Every figure is derived from ``PageView`` rows written by the link view
    ingest routes; no figures are fabricated or mocked.
    """
    verify_workspace(principal, workspace_id)
    _document_or_404_link(db, workspace_id, document_id)
    link_ids = _link_document_ids(db, workspace_id, document_id)
    if not link_ids:
        return []
    visit_rows = db.execute(
        select(LinkVisit).where(
            LinkVisit.workspace_id == workspace_id, LinkVisit.link_id.in_(link_ids)
        )
    ).scalars().all()
    visit_by_id = {v.id: v for v in visit_rows}
    if not visit_by_id:
        return []
    page_views = db.execute(
        select(PageView).where(
            PageView.workspace_id == workspace_id,
            PageView.visit_id.in_(list(visit_by_id)),
        )
    ).scalars().all()

    grouped: dict[str | int, dict] = {}
    for pv in page_views:
        key = pv.page_id or pv.page_number
        row = grouped.setdefault(key, {
            "page_number": pv.page_number,
            "page_id": pv.page_id,
            "views": 0,
            "viewers": set(),
            "total_duration_seconds": 0,
            "page_events": 0,
        })
        visit = visit_by_id.get(pv.visit_id)
        if visit is not None:
            if visit.contact_id:
                row["viewers"].add("contact:" + visit.contact_id)
            elif visit.visitor_email:
                row["viewers"].add("email:" + _normal_email(visit.visitor_email))
            else:
                row["viewers"].add("anonymous:" + visit.id)
        row["views"] += 1
        row["page_events"] += 1
        row["total_duration_seconds"] += (
            _duration_between(pv.entered_at, pv.left_at)
            if pv.entered_at and pv.left_at else (pv.duration_seconds or 0)
        )

    # Resolve real page labels from the primary version where available.
    labels: dict[str | int, str | None] = {}
    version = primary_version(db, workspace_id, document_id)
    if version is not None:
        for page in db.execute(
            select(DocumentPage).where(
                DocumentPage.workspace_id == workspace_id,
                DocumentPage.version_id == version.id,
            )
        ).scalars().all():
            labels[page.id] = page.label
            labels[page.page_number] = page.label

    result = []
    for row in sorted(grouped.values(), key=lambda value: value["page_number"]):
        key = row["page_id"] or row["page_number"]
        views = row["views"]
        result.append(DocumentPageAnalyticsOut(
            page_number=row["page_number"],
            page_id=row["page_id"],
            label=labels.get(key),
            views=views,
            unique_viewers=len(row["viewers"]),
            total_duration_seconds=row["total_duration_seconds"],
            average_duration_seconds=(
                int(row["total_duration_seconds"] / views) if views else 0
            ),
            page_events=row["page_events"],
        ))
    return result


# ---------------------------------------------------------------------------
# PM-080: verified visitor identity with consent-controlled identification
# ---------------------------------------------------------------------------


def _viewer_out(viewer: ViewerIdentity) -> ViewerIdentityOut:
    """Only disclose readable identity fields while consent is active."""
    identified = (
        viewer.verified_at is not None
        and viewer.consent_at is not None
        and viewer.consent_revoked_at is None
        and viewer.email is not None
    )
    return ViewerIdentityOut(
        id=viewer.id,
        workspace_id=viewer.workspace_id,
        identified=identified,
        email=viewer.email if identified else None,
        display_name=viewer.display_name if identified else None,
        contact_id=viewer.contact_id if identified else None,
        verified_at=viewer.verified_at,
        consent_at=viewer.consent_at,
        consent_revoked_at=viewer.consent_revoked_at,
        created_at=viewer.created_at,
    )


@router.post("/viewers", response_model=ViewerIdentityOut, status_code=status.HTTP_201_CREATED)
def create_viewer_identity(
    workspace_id: str,
    body: ViewerIdentityCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> ViewerIdentityOut:
    """Verify a document viewer and record identification consent separately.

    A hashed identity row always exists for de-duplication. Readable email and
    CRM linkage are persisted only when ``consent`` is granted.
    """
    verify_workspace(principal, workspace_id)
    email_hash = hash_token(body.email)
    viewer = db.execute(
        select(ViewerIdentity).where(
            ViewerIdentity.workspace_id == workspace_id,
            ViewerIdentity.email_hash == email_hash,
        )
    ).scalar_one_or_none()
    if viewer is None:
        viewer = ViewerIdentity(
            id=new_id(), workspace_id=workspace_id, email_hash=email_hash,
        )
        db.add(viewer)
    verified_at = now()
    viewer.verified_at = verified_at
    viewer.source_link_id = body.source_link_id
    if body.consent:
        viewer.email = body.email
        viewer.display_name = body.display_name
        viewer.consent_at = now()
        viewer.consent_revoked_at = None
        # Link to the single CRM contact identity only when consent allows.
        contact, _ = _visitor_contact(
            db, workspace_id, body.email, body.display_name, principal.user.id
        )
        viewer.contact_id = contact.id if contact else None
    else:
        viewer.email = None
        viewer.display_name = None
        viewer.contact_id = None
        viewer.consent_at = None
    viewer.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=DOCUMENT_VIEWER_IDENTITY_CREATED,
        entity_id=viewer.id,
        payload={
            "verified": True,
            "consented": body.consent,
            "source_link_id": body.source_link_id,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return _viewer_out(viewer)


@router.get("/viewers", response_model=list[ViewerIdentityOut])
def list_viewer_identities(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[ViewerIdentityOut]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(ViewerIdentity).where(ViewerIdentity.workspace_id == workspace_id)
        .order_by(ViewerIdentity.created_at)
    ).scalars().all()
    return [_viewer_out(row) for row in rows]


@router.get("/viewers/{viewer_id}", response_model=ViewerIdentityOut)
def get_viewer_identity(
    workspace_id: str,
    viewer_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> ViewerIdentityOut:
    verify_workspace(principal, workspace_id)
    viewer = db.execute(
        select(ViewerIdentity).where(
            ViewerIdentity.id == viewer_id, ViewerIdentity.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if viewer is None:
        raise HTTPException(status_code=404, detail="viewer identity not found")
    return _viewer_out(viewer)


@router.patch("/viewers/{viewer_id}/consent", response_model=ViewerIdentityOut)
def update_viewer_consent(
    workspace_id: str,
    viewer_id: str,
    body: ViewerConsentUpdate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> ViewerIdentityOut:
    """Grant or revoke identification consent, scrubbing PII on revoke."""
    verify_workspace(principal, workspace_id)
    viewer = db.execute(
        select(ViewerIdentity).where(
            ViewerIdentity.id == viewer_id, ViewerIdentity.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if viewer is None:
        raise HTTPException(status_code=404, detail="viewer identity not found")
    if body.granted:
        email = body.email or viewer.email
        if not email:
            raise HTTPException(status_code=422, detail="email is required to grant consent")
        # If readable email was scrubbed, restore it from the body.
        viewer.email = email
        viewer.display_name = body.display_name or viewer.display_name
        contact, _ = _visitor_contact(
            db, workspace_id, email, viewer.display_name, principal.user.id
        )
        viewer.contact_id = contact.id if contact else None
        viewer.consent_at = now()
        viewer.consent_revoked_at = None
    else:
        # Revoke: clear all readable PII while keeping the hashed row and audit.
        viewer.email = None
        viewer.display_name = None
        viewer.contact_id = None
        viewer.consent_revoked_at = now()
    viewer.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=DOCUMENT_VIEWER_CONSENT_UPDATED,
        entity_id=viewer.id,
        payload={"granted": body.granted, "identified": _viewer_out(viewer).identified},
        actor_id=principal.user.id,
    )
    db.commit()
    return _viewer_out(viewer)