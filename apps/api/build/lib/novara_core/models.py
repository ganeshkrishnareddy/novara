"""Core tables for NOVARA.

Design rules:
- A User is a global identity. A workspace relationship is a WorkspaceMember,
  so one person can belong to several workspaces with different roles.
- Every tenant-owned row carries workspace_id and every query filters on it.
- The single customer identity is Contact. Leads, tasks, notes and drafts point
  to it; none of them owns a separate customer record.
- Events are append-only and carry a correlation id shared by one workflow run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

ROLES = (
    "owner",
    "admin",
    "sales_manager",
    "sales_rep",
    "marketing",
    "support",
    "read_only",
)


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


def in_hours(hours: int) -> datetime:
    return now() + timedelta(hours=hours)


class User(Base):
    """Global login identity. It carries no workspace and no role."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_member_workspace_user"),
        Index("ix_member_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    invited_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkspaceInvitation(Base):
    __tablename__ = "workspace_invitations"
    __table_args__ = (Index("ix_invitation_workspace_email", "workspace_id", "email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    invited_by: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Base):
    """Server-side sessions make logout and revocation real, not cosmetic."""

    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("access_token_hash", name="uq_session_access"),
        UniqueConstraint("refresh_token_hash", name="uq_session_refresh"),
        Index("ix_session_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_company_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Contact(Base):
    """The single customer identity for a workspace."""

    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_contact_workspace_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    company_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(100), default="website_form")
    # MT-113: provenance of an external identity. NOVARA's id stays
    # authoritative; these fields only record what a named system called it.
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    external_source: Mapped[str | None] = mapped_column(String(100))
    # MT-019: workspace-wide do-not-contact flag, set by the signed DNC link.
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lifecycle_stage: Mapped[str] = mapped_column(String(50), default="lead")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ViewerIdentity(Base):
    """PM-080: a verified document viewer, distinct from login users.

    A visitor is deduplicated by a one-way email hash. The readable email and
    CRM contact link exist only while consent is active; revoking consent clears
    them while the hashed row and its audit events remain for accountability.
    """

    __tablename__ = "viewer_identities"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email_hash", name="uq_viewer_workspace_email"),
        Index("ix_viewer_workspace_contact", "workspace_id", "contact_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Present only while consent allows identification.
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    source_link_id: Mapped[str | None] = mapped_column(String(36), index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @property
    def identified(self) -> bool:
        return (
            self.verified_at is not None
            and self.consent_at is not None
            and self.consent_revoked_at is None
            and self.email is not None
        )


class Lead(Base):
    """A qualification record that points at a Contact. It never duplicates one."""

    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("workspace_id", "contact_id", name="uq_lead_workspace_contact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), default="website_form")
    status: Mapped[str] = mapped_column(String(50), default="new")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    score: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Event(Base):
    """Append-only event log. seq gives a stable order even when timestamps tie."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_event_workspace_idem"),
        Index("ix_event_workspace_type", "workspace_id", "event_type"),
        Index("ix_event_correlation", "workspace_id", "correlation_id"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=new_id)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    schema_version: Mapped[int] = mapped_column(default=1)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Notification(Base):
    """An in-app message addressed to one workspace identity (NV-023/030/035).

    Recipients are NOVARA users via ``user_id``; there is no separate subscriber
    login. A null ``user_id`` means a workspace-wide broadcast. ``seen`` records
    that the feed was displayed and ``read`` records an explicit user action;
    they are deliberately independent states.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_workspace_user", "workspace_id", "user_id"),
        Index("ix_notif_workspace_category", "workspace_id", "category"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    # Deep link into the SPA, e.g. "#/contacts/<id>". Purely local navigation.
    link: Mapped[str | None] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkspaceNotificationSettings(Base):
    """Workspace-scoped notification configuration (NV-068).

    One row per workspace. Delivery windows are local wall-clock times
    interpreted in ``timezone``; nothing here sends external messages, it is a
    contract that local delivery adapters and the UI consult.
    """

    __tablename__ = "workspace_notification_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivery_window_start: Mapped[str | None] = mapped_column(String(5))
    delivery_window_end: Mapped[str | None] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OutreachDraft(Base):
    """External messages always stop here. Nothing sends from this service."""

    __tablename__ = "outreach_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(36))


class WorkspaceOutreachPolicy(Base):
    """Workspace-owned outreach policy. The legal wording is an owner decision;
    NOVARA only stores and enforces the configured footer on drafts."""

    __tablename__ = "workspace_outreach_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    compliance_footer: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SuppressionEntry(Base):
    """Workspace-scoped do-not-contact record with a reason and optional expiry.

    Revocation is a timestamp rather than a delete so the decision remains
    auditable. ``scope`` is either an exact email address or a domain."""

    __tablename__ = "outreach_suppressions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "recipient", "scope", "reason",
            name="uq_suppression_workspace_recipient_scope_reason",
        ),
        Index("ix_suppression_workspace_recipient", "workspace_id", "recipient"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_by: Mapped[str | None] = mapped_column(String(36))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
