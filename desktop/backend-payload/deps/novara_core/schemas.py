"""Request and response contracts shared by the API and internal modules."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from .models import ROLES

FORBID = ConfigDict(extra="forbid")


def _clean_email(value: str) -> str:
    value = value.strip().lower()
    if any(char.isspace() for char in value) or value.count("@") != 1:
        raise ValueError("a valid email address is required")
    local, domain = value.split("@")
    if (
        not local
        or not domain
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or ".." in domain
    ):
        raise ValueError("a valid email address is required")
    return value


def _clean_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    return value


class WorkspaceCreate(BaseModel):
    name: str

    model_config = FORBID

    @field_validator("name")
    @classmethod
    def required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("workspace name is required")
        return value


class UserRegister(BaseModel):
    email: str
    password: str
    display_name: str

    model_config = FORBID

    _email = field_validator("email")(_clean_email)
    _password = field_validator("password")(_clean_password)


class EmailCheckRequest(BaseModel):
    """PL-056: lightweight, read-only sign-up email validation."""

    email: str

    model_config = FORBID

    _email = field_validator("email")(_clean_email)


class LoginRequest(BaseModel):
    email: str
    password: str
    workspace_id: str | None = None

    model_config = FORBID

    _email = field_validator("email")(_clean_email)


class BootstrapRequest(BaseModel):
    """First-run setup: creates the owner identity and first workspace."""

    workspace_name: str
    email: str
    password: str
    display_name: str

    model_config = FORBID

    _email = field_validator("email")(_clean_email)
    _password = field_validator("password")(_clean_password)

    @field_validator("workspace_name")
    @classmethod
    def required_workspace_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("workspace name is required")
        return value


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    workspace_id: str


class RefreshRequest(BaseModel):
    refresh_token: str

    model_config = FORBID


class InviteRequest(BaseModel):
    email: str
    role: str

    model_config = FORBID

    _email = field_validator("email")(_clean_email)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in ROLES or value == "owner":
            raise ValueError("role must be a non-owner workspace role")
        return value


class AcceptInviteRequest(BaseModel):
    token: str

    model_config = FORBID


class PasswordResetRequest(BaseModel):
    email: str

    model_config = FORBID

    _email = field_validator("email")(_clean_email)


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    model_config = FORBID

    _password = field_validator("new_password")(_clean_password)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    model_config = FORBID

    _password = field_validator("new_password")(_clean_password)


class EmailVerifyRequest(BaseModel):
    token: str

    model_config = FORBID


class WebsiteSubmission(BaseModel):
    submission_id: str | None = None
    email: str
    full_name: str | None = None
    company: str | None = None
    message: str | None = None
    source: str = "website_form"

    model_config = FORBID

    _email = field_validator("email")(_clean_email)


class IntakeResult(BaseModel):
    workspace_id: str
    contact_id: str
    lead_id: str
    task_id: str
    notification_id: str
    draft_id: str
    created_contact: bool
    correlation_id: str


class ContactCreate(BaseModel):
    email: str
    full_name: str | None = None
    company_name: str | None = None
    company_id: str | None = None
    phone: str | None = None
    source: str = "manual"
    tags: list[str] = []
    custom_fields: dict = {}

    model_config = FORBID

    _email = field_validator("email")(_clean_email)


class ContactUpdate(BaseModel):
    full_name: str | None = None
    external_id: str | None = None
    external_source: str | None = None
    company_name: str | None = None
    company_id: str | None = None
    phone: str | None = None
    lifecycle_stage: str | None = None
    owner_id: str | None = None
    tags: list[str] | None = None
    custom_fields: dict | None = None

    model_config = FORBID


class ContactOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    external_id: str | None
    external_source: str | None
    do_not_contact: bool
    company_name: str | None
    phone: str | None
    source: str
    lifecycle_stage: str
    owner_id: str | None
    tags: list
    custom_fields: dict
    archived: bool
    created_at: datetime
    updated_at: datetime


class CompanyCreate(BaseModel):
    name: str
    industry: str | None = None
    website: str | None = None
    location: str | None = None
    owner_id: str | None = None

    model_config = FORBID


class CompanyUpdate(BaseModel):
    """SB-013: partial, workspace-scoped company metadata update."""

    name: str | None = None
    industry: str | None = None
    website: str | None = None
    location: str | None = None
    owner_id: str | None = None

    model_config = FORBID


class CompanyOut(BaseModel):
    id: str
    name: str
    industry: str | None
    website: str | None
    location: str | None
    owner_id: str | None
    archived: bool = False
    created_at: datetime


class LeadCreate(BaseModel):
    contact_id: str
    source: str = "manual"
    status: str = "new"
    priority: str = "normal"
    score: int = 0
    owner_id: str | None = None

    model_config = FORBID


class LeadUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    score: int | None = None
    owner_id: str | None = None

    model_config = FORBID


class LeadOut(BaseModel):
    id: str
    contact_id: str
    source: str
    status: str
    priority: str
    score: int
    owner_id: str | None
    qualified_at: datetime | None
    converted_at: datetime | None
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    contact_id: str | None = None
    description: str | None = None
    priority: str = "normal"
    owner_id: str | None = None
    due_at: datetime | None = None

    model_config = FORBID


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None

    model_config = FORBID


class TaskOut(BaseModel):
    id: str
    contact_id: str | None
    title: str
    description: str | None
    status: str
    priority: str
    owner_id: str | None
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class NoteCreate(BaseModel):
    contact_id: str
    body: str

    model_config = FORBID


class NoteOut(BaseModel):
    id: str
    contact_id: str
    author_id: str
    body: str
    created_at: datetime


class NotificationOut(BaseModel):
    id: str
    workspace_id: str
    contact_id: str | None
    user_id: str | None
    title: str | None
    message: str
    category: str
    link: str | None
    read: bool
    read_at: datetime | None
    seen: bool
    seen_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationCountsOut(BaseModel):
    total: int
    unread: int
    unseen: int
    by_category: dict[str, int]


class NotificationSettingsOut(BaseModel):
    workspace_id: str
    in_app_enabled: bool
    digest_enabled: bool
    quiet_hours_enabled: bool
    delivery_window_start: str | None
    delivery_window_end: str | None
    timezone: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsUpdate(BaseModel):
    """Partial update. Only fields actually present in the body are applied;

    ``model_fields_set`` lets a caller clear a delivery window with null.
    """

    in_app_enabled: bool | None = None
    digest_enabled: bool | None = None
    quiet_hours_enabled: bool | None = None
    delivery_window_start: str | None = None
    delivery_window_end: str | None = None
    timezone: str | None = None

    model_config = FORBID

    @field_validator("delivery_window_start", "delivery_window_end")
    @classmethod
    def valid_clock(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            hours, minutes = value.split(":")
            if len(hours) != 2 or len(minutes) != 2:
                raise ValueError
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError("delivery times must use HH:MM")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or len(value) > 64 or any(ch.isspace() for ch in value):
            raise ValueError("invalid timezone")
        if not all(ch.isalnum() or ch in "_+-/" for ch in value):
            raise ValueError("invalid timezone")
        return value


class DraftOut(BaseModel):
    id: str
    contact_id: str
    subject: str
    body: str
    status: str
    approved_at: datetime | None
    approved_by: str | None


class EventOut(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    workspace_id: str
    entity_id: str | None
    correlation_id: str
    schema_version: int
    payload: dict


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    display_name: str
    role: str
    status: str


class MemberUpdateRequest(BaseModel):
    """Workspace membership lifecycle change (CW-129).

    Both fields are optional so suspending, reactivating or changing a role is
    a single audited operation. Owners cannot be created or assigned here.
    """

    role: str | None = None
    status: str | None = None

    model_config = FORBID

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str | None) -> str | None:
        if value is not None and (value not in ROLES or value == "owner"):
            raise ValueError("role must be a non-owner workspace role")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in ("active", "suspended"):
            raise ValueError("status must be active or suspended")
        return value


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    email_verified: bool


class MeOut(BaseModel):
    user: UserOut
    workspace_id: str
    workspace_name: str
    role: str
    permissions: list[str]
