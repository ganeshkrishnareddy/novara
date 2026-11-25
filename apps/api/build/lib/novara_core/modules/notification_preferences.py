"""Subscriber notification preferences (workflow, channel and global levels).

Clean-room implementation of Novu-style preference capabilities (NV-032, NV-039)
over the shared NOVARA workspace/user identity. No external delivery is
performed; preferences are stored and consulted by callers.
"""

from __future__ import annotations

import html
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

PREFERENCE_UPDATED = "notification.preference_updated"
register_event_types(PREFERENCE_UPDATED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/notification-preferences",
    tags=["notification-preferences"],
)

CHANNELS = ("in_app", "email", "sms", "push", "chat")
LEVELS = ("global", "workflow", "channel")

# NV-099: a deliberately small, sandboxed template language. There is no code
# execution, no attribute traversal outside plain dicts and no filter beyond
# the three listed below.
MAX_TEMPLATE_LENGTH = 5000
MAX_PLACEHOLDERS = 50
PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([A-Za-z0-9_\.]+)(?:\s*\|\s*(upper|lower|escape))?\s*\}\}"
)
FORBIDDEN_MARKERS = (
    "<script", "javascript:", "onerror=", "onload=", "onclick=", "<iframe", "<object",
)
SENSITIVE_PARTS = frozenset(
    {
        "secret", "secrets", "token", "tokens", "password", "passwords",
        "credential", "credentials", "apikey", "api_key", "privatekey",
        "authorization", "__class__", "__dict__", "__globals__",
    }
)


def render_personalized(template: str, values: dict) -> str:
    """Render `{{ path | filter }}` placeholders from an allow-listed value map.

    Every resolved value is HTML-escaped by default and credential-looking
    paths are rejected, so a stored template cannot leak secrets or inject a
    script into the notification panel.
    """
    if not isinstance(template, str) or not isinstance(values, dict):
        raise ValueError("template and values must be strings/objects")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise ValueError("template is too long")
    lowered = template.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            raise ValueError(f"template contains a forbidden marker: {marker}")
    matches = list(PLACEHOLDER_RE.finditer(template))
    if len(matches) > MAX_PLACEHOLDERS:
        raise ValueError("too many placeholders")
    # Any curly-brace content that is not a recognised placeholder is rejected.
    if PLACEHOLDER_RE.sub("", template).find("{{") >= 0:
        raise ValueError("unsupported placeholder syntax")

    def substitute(match: re.Match) -> str:
        path = match.group(1)
        parts = path.split(".")
        for part in parts:
            if part.lower() in SENSITIVE_PARTS:
                raise ValueError(f"credential-like placeholder is not allowed: {path}")
        current = values
        found = True
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        text = "" if not found else ("" if current is None else str(current))
        lowered_value = text.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker in lowered_value:
                raise ValueError(f"resolved value contains a forbidden marker: {marker}")
        filter_name = match.group(2)
        if filter_name == "upper":
            text = text.upper()
        elif filter_name == "lower":
            text = text.lower()
        # Escape last: upper-casing an already escaped entity would produce an
        # invalid HTML entity such as &AMP; instead of the safe &amp;.
        return html.escape(text, quote=True)

    return PLACEHOLDER_RE.sub(substitute, template)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", "level", "target", "channel", name="uq_notif_pref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False, default="*")
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class PreferenceCreate(BaseModel):
    level: str = "global"
    target: str = "*"
    channel: str
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        if value not in LEVELS:
            raise ValueError("invalid preference level")
        return value

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value not in CHANNELS:
            raise ValueError("invalid channel")
        return value


class PreferencePatch(BaseModel):
    enabled: bool

    model_config = ConfigDict(extra="forbid")


class ResolutionRequest(BaseModel):
    """NV-032: resolve the effective setting for one workflow and channel."""

    channel: str
    workflow: str = "*"

    model_config = ConfigDict(extra="forbid")

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value not in CHANNELS:
            raise ValueError("invalid channel")
        return value

    @field_validator("workflow")
    @classmethod
    def valid_workflow(cls, value: str) -> str:
        result = value.strip() or "*"
        return result


class ResolutionOut(BaseModel):
    channel: str
    workflow: str
    enabled: bool
    source: str
    layers: list[dict]


class PreferenceOut(BaseModel):
    id: str
    user_id: str
    level: str
    target: str
    channel: str
    enabled: bool
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


def _pref_or_404(db, workspace_id, pref_id):
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if pref is None:
        raise HTTPException(status_code=404, detail="preference not found")
    return pref


@router.get("", response_model=list[PreferenceOut])
def list_preferences(
    workspace_id: str,
    level: str | None = None,
    channel: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[NotificationPreference]:
    verify_workspace(principal, workspace_id)
    query = select(NotificationPreference).where(
        NotificationPreference.workspace_id == workspace_id,
        NotificationPreference.user_id == principal.user.id,
    )
    if level:
        query = query.where(NotificationPreference.level == level)
    if channel:
        query = query.where(NotificationPreference.channel == channel)
    return db.execute(query.order_by(NotificationPreference.created_at)).scalars().all()


@router.post("/resolve", response_model=ResolutionOut)
def resolve_preference(
    workspace_id: str,
    body: ResolutionRequest,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> ResolutionOut:
    """Return the effective enabled state from the layered preference rows.

    Precedence, most specific first: a channel-level override for this
    workflow, a channel-level wildcard, a workflow-level rule, a global rule,
    then the default (enabled). Every candidate actually found is returned in
    ``layers`` so the decision is inspectable rather than opaque.
    """
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.workspace_id == workspace_id,
            NotificationPreference.user_id == principal.user.id,
            NotificationPreference.channel == body.channel,
        )
    ).scalars().all()
    lookup = {(row.level, row.target): row.enabled for row in rows}
    candidates = (
        ("channel", body.workflow),
        ("channel", "*"),
        ("workflow", body.workflow),
        ("global", "*"),
    )
    layers = [
        {"level": level, "target": target, "enabled": lookup[(level, target)]}
        for level, target in candidates
        if (level, target) in lookup
    ]
    if layers:
        effective, source_level, source_target = (
            layers[0]["enabled"], layers[0]["level"], layers[0]["target"]
        )
    else:
        effective, source_level, source_target = True, "default", "*"
    return ResolutionOut(
        channel=body.channel,
        workflow=body.workflow,
        enabled=effective,
        source=f"{source_level}:{source_target}",
        layers=layers,
    )


@router.post("", response_model=PreferenceOut, status_code=status.HTTP_201_CREATED)
def upsert_preference(
    workspace_id: str,
    body: PreferenceCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    verify_workspace(principal, workspace_id)
    existing = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.workspace_id == workspace_id,
            NotificationPreference.user_id == principal.user.id,
            NotificationPreference.level == body.level,
            NotificationPreference.target == body.target,
            NotificationPreference.channel == body.channel,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.enabled = body.enabled
        existing.updated_at = now()
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=PREFERENCE_UPDATED,
            entity_id=existing.id,
            payload={"level": body.level, "target": body.target, "channel": body.channel, "enabled": body.enabled},
            actor_id=principal.user.id,
        )
        db.commit()
        return existing
    pref = NotificationPreference(
        id=new_id(),
        workspace_id=workspace_id,
        user_id=principal.user.id,
        level=body.level,
        target=body.target,
        channel=body.channel,
        enabled=body.enabled,
        created_at=now(),
        updated_at=now(),
    )
    db.add(pref)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PREFERENCE_UPDATED,
        entity_id=pref.id,
        payload={"level": body.level, "target": body.target, "channel": body.channel, "enabled": body.enabled},
        actor_id=principal.user.id,
    )
    db.commit()
    return pref


@router.patch("/{preference_id}", response_model=PreferenceOut)
def patch_preference(
    workspace_id: str,
    preference_id: str,
    body: PreferencePatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    verify_workspace(principal, workspace_id)
    pref = _pref_or_404(db, workspace_id, preference_id)
    if pref.user_id != principal.user.id:
        raise HTTPException(status_code=403, detail="cannot modify another user's preference")
    pref.enabled = body.enabled
    pref.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=PREFERENCE_UPDATED,
        entity_id=pref.id,
        payload={"enabled": body.enabled},
        actor_id=principal.user.id,
    )
    db.commit()
    return pref


@router.delete("/{preference_id}", status_code=status.HTTP_200_OK)
def delete_preference(
    workspace_id: str,
    preference_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    pref = _pref_or_404(db, workspace_id, preference_id)
    if pref.user_id != principal.user.id:
        raise HTTPException(status_code=403, detail="cannot delete another user's preference")
    db.delete(pref)
    db.commit()
    return {"deleted": True, "preference_id": preference_id}


# --------------------------------------------------------------------------
# NV-099: local preview of a sandboxed personalized template
# --------------------------------------------------------------------------


class TemplatePreviewRequest(BaseModel):
    template: str
    values: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class TemplatePreviewOut(BaseModel):
    rendered: str
    notes: str = "Sandboxed local renderer; no external service is called."


@router.post("/preview", response_model=TemplatePreviewOut)
def preview_template(
    workspace_id: str,
    body: TemplatePreviewRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> TemplatePreviewOut:
    verify_workspace(principal, workspace_id)
    try:
        rendered = render_personalized(body.template, body.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TemplatePreviewOut(rendered=rendered)