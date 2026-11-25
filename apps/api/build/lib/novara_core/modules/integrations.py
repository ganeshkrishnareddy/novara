"""Integration catalog and non-sensitive integration settings.

Only non-sensitive configuration is accepted or stored. Secrets (API keys,
tokens, passwords, credentials) are rejected before they reach the database.
No outbound network call is made in this build: recording a configuration is
not the same as having a live adapter.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, WORKSPACE_MANAGE

INTEGRATION_CONFIGURED = "integration.configured"
INTEGRATION_DISABLED = "integration.disabled"
register_event_types(INTEGRATION_CONFIGURED, INTEGRATION_DISABLED)

INTEGRATION_NOTES = (
    "No outbound network call is made in this build. Only non-sensitive settings "
    "are stored; API keys, tokens, passwords and credentials are never accepted."
)
NOT_CONFIGURED = "adapter not configured"
NOT_CONFIGURED_NOTE = "adapter not configured; no outbound network call is made in this build"
RECORDED_NOTE = "configuration recorded; no outbound adapter is active in this build"

SUPPORTED_PROVIDERS = {
    "gmail": "Gmail",
    "outlook": "Outlook",
    "whatsapp": "WhatsApp",
    "sms": "SMS",
    "openai": "OpenAI",
    "local_llm": "Local LLM",
    "meilisearch": "Meilisearch",
    "growthbook": "GrowthBook",
    "chatwoot": "Chatwoot",
    "novu": "Novu",
    "plane": "Plane (compatible adapter, opt-in)",
}

SECRET_FIELD_NAMES = frozenset(
    {
        "apikey",
        "apikeys",
        "token",
        "tokens",
        "accesstoken",
        "refreshtoken",
        "secret",
        "secrets",
        "clientsecret",
        "password",
        "passwords",
        "credential",
        "credentials",
        "privatekey",
        "authorization",
    }
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/integrations",
    tags=["integrations"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_integration_workspace_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="configured")
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


def _normalise_key(key: object) -> str:
    return "".join(character for character in str(key).lower() if character.isalnum())


def _reject_secret_fields(value: object, path: str = "config") -> None:
    """Reject any secret-looking key, including nested ones, with a 422."""
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalise_key(key) in SECRET_FIELD_NAMES:
                raise ValueError(f"secret field is not accepted: {path}.{key}")
            _reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, f"{path}[{index}]")


class IntegrationUpsert(BaseModel):
    provider: str
    display_name: str | None = None
    status: Literal["disconnected", "configured", "disabled"] = "configured"
    config: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("provider")
    @classmethod
    def provider_allowed(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported integration provider")
        return provider

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be empty")
        return value

    @field_validator("config")
    @classmethod
    def no_secrets(cls, value: dict) -> dict:
        _reject_secret_fields(value)
        return value


class IntegrationOut(BaseModel):
    id: str
    workspace_id: str
    provider: str
    display_name: str
    status: str
    config: dict
    created_by: str
    created_at: object
    updated_at: object
    notes: str = INTEGRATION_NOTES

    model_config = ConfigDict(from_attributes=True)


class CapabilityEntry(BaseModel):
    provider: str
    display_name: str
    status: str
    configured: bool
    notes: str


class CapabilitiesOut(BaseModel):
    workspace_id: str
    providers: list[CapabilityEntry]
    notes: str = INTEGRATION_NOTES


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _integration_or_404(db: Session, workspace_id: str, provider: str) -> Integration:
    provider = provider.strip().lower()
    row = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == provider,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="integration not found")
    return row


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[IntegrationOut])
def list_integrations(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Integration]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Integration)
        .where(Integration.workspace_id == workspace_id)
        .order_by(Integration.provider)
    ).scalars().all()


@router.get("/capabilities", response_model=CapabilitiesOut)
def list_capabilities(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> CapabilitiesOut:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(Integration).where(Integration.workspace_id == workspace_id)
    ).scalars().all()
    by_provider = {row.provider: row for row in rows}
    entries = []
    for provider, display_name in SUPPORTED_PROVIDERS.items():
        row = by_provider.get(provider)
        entries.append(
            CapabilityEntry(
                provider=provider,
                display_name=display_name,
                status=row.status if row is not None else NOT_CONFIGURED,
                configured=row is not None,
                notes=RECORDED_NOTE if row is not None else NOT_CONFIGURED_NOTE,
            )
        )
    return CapabilitiesOut(workspace_id=workspace_id, providers=entries)


@router.put("", response_model=IntegrationOut)
def upsert_integration(
    workspace_id: str,
    body: IntegrationUpsert,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Integration:
    verify_workspace(principal, workspace_id)
    display_name = body.display_name or SUPPORTED_PROVIDERS[body.provider]
    row = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == body.provider,
        )
    ).scalar_one_or_none()
    if row is None:
        row = Integration(
            id=new_id(),
            workspace_id=workspace_id,
            provider=body.provider,
            display_name=display_name,
            status=body.status,
            config=body.config,
            created_by=principal.user.id,
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
    else:
        row.display_name = display_name
        row.status = body.status
        row.config = body.config
        row.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=INTEGRATION_CONFIGURED,
        entity_id=row.id,
        payload={"provider": row.provider, "status": row.status, "config_keys": sorted(row.config)},
        actor_id=principal.user.id,
    )
    db.commit()
    return row


@router.get("/{provider}", response_model=IntegrationOut)
def get_integration(
    workspace_id: str,
    provider: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Integration:
    verify_workspace(principal, workspace_id)
    return _integration_or_404(db, workspace_id, provider)


@router.post("/{provider}/disable", response_model=IntegrationOut)
def disable_integration(
    workspace_id: str,
    provider: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Integration:
    verify_workspace(principal, workspace_id)
    row = _integration_or_404(db, workspace_id, provider)
    previous_status = row.status
    row.status = "disabled"
    row.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=INTEGRATION_DISABLED,
        entity_id=row.id,
        payload={"provider": row.provider, "from": previous_status, "to": row.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return row
