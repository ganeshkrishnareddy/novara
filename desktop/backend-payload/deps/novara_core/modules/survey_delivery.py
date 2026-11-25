"""Survey delivery, flow, branding and local creatives (Formbricks P2 cluster).

Clean-room implementation of the Formbricks survey delivery and creative rows:
in-app/website/link/email/embed distribution (FB-002..006), the no-code editor
and multi-page flow with rules/fallbacks/endings (FB-010, FB-015), email
branding and answer/ending follow-ups (FB-036, FB-080), back-button and PIN
controls (FB-038, FB-074), custom head scripts and host CSS interaction
(FB-075, FB-079), accessibility support (FB-183), and the local creatives
package with feedback button and banner creatives and show conditions
(FB-184..187).

No Formbricks server source is copied. Every deliverable is a NOVARA-local,
workspace-scoped record; no survey email, tracking pixel, hosted widget or
external SDK is contacted.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from ..security import hash_token
from .feedback import Survey

CONFIG_CREATED = "survey.delivery_config_created"
CONFIG_UPDATED = "survey.delivery_config_updated"
FLOW_CHANGED = "survey.flow_changed"
BRANDING_CHANGED = "survey.email_branding_changed"
FOLLOWUP_CHANGED = "survey.followup_changed"
HEAD_SCRIPT_CHANGED = "survey.head_script_changed"
CREATIVE_CHANGED = "survey.creative_changed"
CREATIVE_EVALUATED = "survey.creative_evaluated"
register_event_types(
    CONFIG_CREATED, CONFIG_UPDATED, FLOW_CHANGED, BRANDING_CHANGED,
    FOLLOWUP_CHANGED, HEAD_SCRIPT_CHANGED, CREATIVE_CHANGED, CREATIVE_EVALUATED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/survey-delivery",
    tags=["survey-delivery"],
)

CHANNELS = frozenset({"in_app", "website", "link", "email", "embed"})
HOST_CSS_MODES = frozenset({"isolated", "scoped", "inherit"})
CREATIVE_TYPES = frozenset({"feedback_button", "banner"})
DEVICES = frozenset({"desktop", "tablet", "mobile"})
KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
PIN_RE = re.compile(r"^\d{4}$")


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _survey(db, workspace_id, survey_id) -> Survey:
    row = db.execute(select(Survey).where(
        Survey.id == survey_id, Survey.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="survey not found")
    return row


def _config(db, workspace_id, config_id):
    return _get(db, SurveyDeliveryConfig, workspace_id, config_id, "delivery config")


# ---------------------------------------------------------------------------
# Tables (additive, workspace-scoped)
# ---------------------------------------------------------------------------


class SurveyDeliveryConfig(Base):
    __tablename__ = "survey_delivery_configs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "survey_id", name="uq_survey_delivery_config"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    embed_mode: Mapped[str] = mapped_column(String(20), default="iframe", nullable=False)
    host_css_mode: Mapped[str] = mapped_column(String(20), default="isolated", nullable=False)
    style_scope: Mapped[str] = mapped_column(String(60), default="novara-survey", nullable=False)
    hide_back_button: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accessibility: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SurveyFlowPage(Base):
    __tablename__ = "survey_flow_pages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "config_id", "key", name="uq_survey_flow_page"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SurveyFlowRule(Base):
    __tablename__ = "survey_flow_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    from_page: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    condition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    target_page: Mapped[str] = mapped_column(String(64), nullable=False)


class SurveyEmailBranding(Base):
    __tablename__ = "survey_email_brandings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "config_id", name="uq_survey_email_branding"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    from_name: Mapped[str] = mapped_column(String(120), nullable=False)
    from_address: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_template: Mapped[str] = mapped_column(String(200), nullable=False)
    footer_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(200), nullable=True)


class SurveyEmailFollowup(Base):
    __tablename__ = "survey_email_followups"
    __table_args__ = (
        UniqueConstraint("workspace_id", "config_id", "key", name="uq_survey_followup"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_value: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class SurveyHeadScript(Base):
    __tablename__ = "survey_head_scripts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "config_id", "key", name="uq_survey_head_script"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SurveyCreative(Base):
    __tablename__ = "survey_creatives"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_survey_creative_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("survey_delivery_configs.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(60), default="message", nullable=False)
    colors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    size: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    position: Mapped[str] = mapped_column(String(20), default="bottom-right", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    button_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    targeting: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    survey_id: str
    channels: list[str] = Field(default_factory=list)
    embed_mode: str = "iframe"
    host_css_mode: str = "isolated"
    style_scope: str = "novara-survey"
    hide_back_button: bool = False
    pin: str | None = None
    accessibility: dict = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def _channels(cls, value):
        if not value or any(c not in CHANNELS for c in value):
            raise ValueError("at least one supported channel is required")
        return list(dict.fromkeys(value))

    @field_validator("embed_mode")
    @classmethod
    def _embed(cls, value):
        if value not in {"iframe", "email_snippet", "widget"}:
            raise ValueError("unsupported embed mode")
        return value

    @field_validator("host_css_mode")
    @classmethod
    def _css(cls, value):
        if value not in HOST_CSS_MODES:
            raise ValueError("unsupported host CSS mode")
        return value

    @field_validator("pin")
    @classmethod
    def _pin(cls, value):
        if value is not None and not PIN_RE.match(value):
            raise ValueError("PIN must be exactly four digits")
        return value


class ConfigUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channels: list[str] | None = None
    embed_mode: str | None = None
    host_css_mode: str | None = None
    style_scope: str | None = None
    hide_back_button: bool | None = None
    pin: str | None = None
    remove_pin: bool = False
    accessibility: dict | None = None
    status: str | None = None

    @field_validator("channels")
    @classmethod
    def _channels(cls, value):
        if value is not None and (not value or any(c not in CHANNELS for c in value)):
            raise ValueError("at least one supported channel is required")
        return value

    @field_validator("pin")
    @classmethod
    def _pin(cls, value):
        if value is not None and not PIN_RE.match(value):
            raise ValueError("PIN must be exactly four digits")
        return value

    @field_validator("status")
    @classmethod
    def _status(cls, value):
        if value is not None and value not in {"draft", "active", "paused"}:
            raise ValueError("unsupported config status")
        return value


class PinVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin: str = Field(min_length=4, max_length=4)


class PageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    title: str
    questions: list[dict] = Field(default_factory=list)
    position: int = 0
    ending: bool = False

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_page: str
    kind: str
    condition: dict = Field(default_factory=dict)
    target_page: str

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in {"post_block", "fallback", "ending"}:
            raise ValueError("unsupported flow rule kind")
        return value


class BrandingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_name: str = Field(min_length=1, max_length=120)
    from_address: str = Field(min_length=3, max_length=200)
    subject_template: str = Field(min_length=1, max_length=200)
    footer_text: str = ""
    reply_to: str | None = None


class FollowupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    trigger_type: str
    trigger_value: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("trigger_type")
    @classmethod
    def _trigger(cls, value):
        if value not in {"answer", "ending"}:
            raise ValueError("unsupported follow-up trigger")
        return value


class HeadScriptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str = Field(min_length=1, max_length=120)
    script: str = Field(min_length=1, max_length=8000)
    enabled: bool = True

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class CreativeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_id: str
    key: str
    type: str
    label: str = Field(min_length=1, max_length=120)
    icon: str = "message"
    colors: dict = Field(default_factory=dict)
    size: str = "medium"
    position: str = "bottom-right"
    message: str = ""
    button_label: str | None = None
    target_url: str | None = None
    schedule: dict = Field(default_factory=dict)
    targeting: dict = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("type")
    @classmethod
    def _type(cls, value):
        if value not in CREATIVE_TYPES:
            raise ValueError("unsupported creative type")
        return value


class CreativeUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    label: str | None = None
    schedule: dict | None = None
    targeting: dict | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, value):
        if value is not None and value not in {"draft", "active", "paused"}:
            raise ValueError("unsupported creative status")
        return value


class EvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: str = "/"
    views: int = 1
    device: str = "desktop"
    share: int = 100
    at: datetime | None = None

    @field_validator("device")
    @classmethod
    def _device(cls, value):
        if value not in DEVICES:
            raise ValueError("unsupported device")
        return value

    @field_validator("views", "share")
    @classmethod
    def _range(cls, value):
        if value < 0 or value > 100000:
            raise ValueError("value must be between 0 and 100000")
        return value


# ---------------------------------------------------------------------------
# Routes - contract and delivery config
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="surveyDeliveryContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["configs", "pages", "rules", "brandings", "followups",
                      "headScripts", "creatives"],
        "channels": sorted(CHANNELS), "creative_types": sorted(CREATIVE_TYPES),
        "router_prefix": "/api/v1/workspaces/{workspace_id}/survey-delivery",
        "external_calls": False,
    }


@router.get("/configs", operation_id="listSurveyDeliveryConfigs")
def list_configs(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(SurveyDeliveryConfig).where(
        SurveyDeliveryConfig.workspace_id == workspace_id
    ).order_by(SurveyDeliveryConfig.created_at)).scalars().all()
    return [{"id": r.id, "survey_id": r.survey_id, "channels": r.channels,
             "embed_mode": r.embed_mode, "status": r.status,
             "pin_protected": r.pin_hash is not None} for r in rows]


@router.post("/configs", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyDeliveryConfig")
def create_config(workspace_id: str, body: ConfigIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    survey = _survey(db, workspace_id, body.survey_id)
    existing = db.execute(select(SurveyDeliveryConfig).where(
        SurveyDeliveryConfig.workspace_id == workspace_id,
        SurveyDeliveryConfig.survey_id == survey.id,
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="delivery config already exists")
    row = SurveyDeliveryConfig(
        id=new_id(), workspace_id=workspace_id, survey_id=survey.id,
        channels=body.channels, embed_mode=body.embed_mode,
        host_css_mode=body.host_css_mode, style_scope=body.style_scope,
        hide_back_button=body.hide_back_button,
        pin_hash=hash_token(body.pin) if body.pin else None,
        accessibility=body.accessibility, status="draft", created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, CONFIG_CREATED, row.id,
           {"survey_id": survey.id, "channels": row.channels}, principal)
    db.commit()
    return {"id": row.id, "survey_id": row.survey_id, "channels": row.channels,
            "status": row.status}


@router.get("/configs/{config_id}", operation_id="getSurveyDeliveryConfig")
def get_config(workspace_id: str, config_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    return {
        "id": row.id, "survey_id": row.survey_id, "channels": row.channels,
        "embed_mode": row.embed_mode, "host_css_mode": row.host_css_mode,
        "style_scope": row.style_scope, "hide_back_button": row.hide_back_button,
        "pin_protected": row.pin_hash is not None, "accessibility": row.accessibility,
        "status": row.status,
    }


@router.patch("/configs/{config_id}", operation_id="updateSurveyDeliveryConfig")
def update_config(workspace_id: str, config_id: str, body: ConfigUpdateIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    data = body.model_dump(exclude_unset=True)
    if "pin" in data:
        row.pin_hash = hash_token(data.pop("pin"))
    if data.pop("remove_pin", False):
        row.pin_hash = None
    for field, value in data.items():
        setattr(row, field, value)
    db.flush()
    _audit(db, workspace_id, CONFIG_UPDATED, row.id, {"fields": sorted(data)}, principal)
    db.commit()
    return {"id": row.id, "status": row.status, "pin_protected": row.pin_hash is not None}


@router.post("/configs/{config_id}/verify-pin", operation_id="verifySurveyPin")
def verify_pin(workspace_id: str, config_id: str, body: PinVerifyIn,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    if row.pin_hash is None:
        return {"required": False, "valid": True, "stored_pin_exposed": False}
    return {"required": True, "valid": hash_token(body.pin) == row.pin_hash,
            "stored_pin_exposed": False}


@router.get("/configs/{config_id}/embed-snippets", operation_id="surveyEmbedSnippets")
def embed_snippets(workspace_id: str, config_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    scripts = db.execute(select(SurveyHeadScript).where(
        SurveyHeadScript.workspace_id == workspace_id,
        SurveyHeadScript.config_id == row.id, SurveyHeadScript.enabled.is_(True),
    )).scalars().all()
    head = "\n".join(s.script for s in scripts)
    iframe = (
        '<iframe src="/s/' + row.survey_id + '" title="Survey ' + row.survey_id +
        '" class="' + row.style_scope + '" loading="lazy"></iframe>'
    )
    email = (
        '<a href="/s/' + row.survey_id + '" class="' + row.style_scope +
        '">Open the survey</a>'
    )
    return {
        "config_id": row.id, "embed_mode": row.embed_mode,
        "iframe": iframe, "email_snippet": email,
        "head_scripts": head, "external_service": False,
        "host_css_mode": row.host_css_mode, "style_scope": row.style_scope,
    }


# ---------------------------------------------------------------------------
# Routes - no-code flow editor and multi-page rules
# ---------------------------------------------------------------------------


@router.get("/configs/{config_id}/pages", operation_id="listSurveyFlowPages")
def list_pages(workspace_id: str, config_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    pages = db.execute(select(SurveyFlowPage).where(
        SurveyFlowPage.workspace_id == workspace_id, SurveyFlowPage.config_id == row.id
    ).order_by(SurveyFlowPage.position, SurveyFlowPage.key)).scalars().all()
    return [{"id": p.id, "key": p.key, "title": p.title, "questions": p.questions,
             "position": p.position, "ending": p.ending} for p in pages]


@router.post("/configs/{config_id}/pages", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyFlowPage")
def create_page(workspace_id: str, config_id: str, body: PageIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    exists = db.execute(select(SurveyFlowPage.id).where(
        SurveyFlowPage.workspace_id == workspace_id,
        SurveyFlowPage.config_id == row.id, SurveyFlowPage.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="page key already exists")
    page = SurveyFlowPage(
        id=new_id(), workspace_id=workspace_id, config_id=row.id, key=body.key,
        title=body.title, questions=body.questions, position=body.position,
        ending=body.ending,
    )
    db.add(page)
    db.flush()
    _audit(db, workspace_id, FLOW_CHANGED, row.id, {"page": body.key}, principal)
    db.commit()
    return {"id": page.id, "key": page.key, "position": page.position}


@router.post("/configs/{config_id}/rules", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyFlowRule")
def create_rule(workspace_id: str, config_id: str, body: RuleIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    rule = SurveyFlowRule(
        id=new_id(), workspace_id=workspace_id, config_id=row.id,
        from_page=body.from_page, kind=body.kind, condition=body.condition,
        target_page=body.target_page,
    )
    db.add(rule)
    db.flush()
    _audit(db, workspace_id, FLOW_CHANGED, row.id,
           {"kind": body.kind, "from_page": body.from_page}, principal)
    db.commit()
    return {"id": rule.id, "kind": rule.kind, "target_page": rule.target_page}


@router.get("/configs/{config_id}/rules", operation_id="listSurveyFlowRules")
def list_rules(workspace_id: str, config_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    rules = db.execute(select(SurveyFlowRule).where(
        SurveyFlowRule.workspace_id == workspace_id, SurveyFlowRule.config_id == row.id
    ).order_by(SurveyFlowRule.from_page, SurveyFlowRule.kind)).scalars().all()
    return [{"id": r.id, "from_page": r.from_page, "kind": r.kind,
             "condition": r.condition, "target_page": r.target_page} for r in rules]


@router.get("/configs/{config_id}/flow", operation_id="getSurveyFlowOutline")
def flow_outline(workspace_id: str, config_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    pages = db.execute(select(SurveyFlowPage).where(
        SurveyFlowPage.workspace_id == workspace_id, SurveyFlowPage.config_id == row.id
    ).order_by(SurveyFlowPage.position)).scalars().all()
    rules = db.execute(select(SurveyFlowRule).where(
        SurveyFlowRule.workspace_id == workspace_id, SurveyFlowRule.config_id == row.id
    )).scalars().all()
    return {
        "config_id": row.id,
        "pages": [{"key": p.key, "title": p.title, "questions": len(p.questions),
                   "position": p.position, "ending": p.ending} for p in pages],
        "rules": [{"from_page": r.from_page, "kind": r.kind,
                   "target_page": r.target_page} for r in rules],
    }


# ---------------------------------------------------------------------------
# Routes - email branding, follow-ups and head scripts
# ---------------------------------------------------------------------------


@router.get("/configs/{config_id}/email-branding", operation_id="getSurveyEmailBranding")
def get_branding(workspace_id: str, config_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> dict | None:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    branding = db.execute(select(SurveyEmailBranding).where(
        SurveyEmailBranding.workspace_id == workspace_id,
        SurveyEmailBranding.config_id == row.id,
    )).scalar_one_or_none()
    if branding is None:
        return None
    return {"id": branding.id, "from_name": branding.from_name,
            "from_address": branding.from_address,
            "subject_template": branding.subject_template,
            "footer_text": branding.footer_text, "reply_to": branding.reply_to}


@router.put("/configs/{config_id}/email-branding", operation_id="setSurveyEmailBranding")
def set_branding(workspace_id: str, config_id: str, body: BrandingIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    branding = db.execute(select(SurveyEmailBranding).where(
        SurveyEmailBranding.workspace_id == workspace_id,
        SurveyEmailBranding.config_id == row.id,
    )).scalar_one_or_none()
    if branding is None:
        branding = SurveyEmailBranding(
            id=new_id(), workspace_id=workspace_id, config_id=row.id,
            from_name=body.from_name, from_address=body.from_address,
            subject_template=body.subject_template, footer_text=body.footer_text,
            reply_to=body.reply_to,
        )
        db.add(branding)
    else:
        branding.from_name = body.from_name
        branding.from_address = body.from_address
        branding.subject_template = body.subject_template
        branding.footer_text = body.footer_text
        branding.reply_to = body.reply_to
    db.flush()
    _audit(db, workspace_id, BRANDING_CHANGED, row.id,
           {"from_address": body.from_address}, principal)
    db.commit()
    return {"id": branding.id, "from_name": branding.from_name, "external_send": False}


@router.get("/configs/{config_id}/followups", operation_id="listSurveyFollowups")
def list_followups(workspace_id: str, config_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    rows = db.execute(select(SurveyEmailFollowup).where(
        SurveyEmailFollowup.workspace_id == workspace_id,
        SurveyEmailFollowup.config_id == row.id,
    ).order_by(SurveyEmailFollowup.key)).scalars().all()
    return [{"id": f.id, "key": f.key, "trigger_type": f.trigger_type,
             "trigger_value": f.trigger_value, "subject": f.subject,
             "status": f.status} for f in rows]


@router.post("/configs/{config_id}/followups", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyFollowup")
def create_followup(workspace_id: str, config_id: str, body: FollowupIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    exists = db.execute(select(SurveyEmailFollowup.id).where(
        SurveyEmailFollowup.workspace_id == workspace_id,
        SurveyEmailFollowup.config_id == row.id, SurveyEmailFollowup.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="follow-up key already exists")
    followup = SurveyEmailFollowup(
        id=new_id(), workspace_id=workspace_id, config_id=row.id, key=body.key,
        trigger_type=body.trigger_type, trigger_value=body.trigger_value,
        subject=body.subject, body=body.body, status="draft",
    )
    db.add(followup)
    db.flush()
    _audit(db, workspace_id, FOLLOWUP_CHANGED, row.id,
           {"key": body.key, "trigger_type": body.trigger_type}, principal)
    db.commit()
    return {"id": followup.id, "key": followup.key, "status": followup.status,
            "external_send": False}


@router.get("/configs/{config_id}/head-scripts", operation_id="listSurveyHeadScripts")
def list_head_scripts(workspace_id: str, config_id: str,
                      principal: Principal = Depends(require(CONTACT_READ)),
                      db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    rows = db.execute(select(SurveyHeadScript).where(
        SurveyHeadScript.workspace_id == workspace_id,
        SurveyHeadScript.config_id == row.id,
    ).order_by(SurveyHeadScript.key)).scalars().all()
    return [{"id": s.id, "key": s.key, "label": s.label,
             "enabled": s.enabled} for s in rows]


@router.post("/configs/{config_id}/head-scripts", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyHeadScript")
def create_head_script(workspace_id: str, config_id: str, body: HeadScriptIn,
                       principal: Principal = Depends(require(NOTE_WRITE)),
                       db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _config(db, workspace_id, config_id)
    exists = db.execute(select(SurveyHeadScript.id).where(
        SurveyHeadScript.workspace_id == workspace_id,
        SurveyHeadScript.config_id == row.id, SurveyHeadScript.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="head script key already exists")
    script = SurveyHeadScript(
        id=new_id(), workspace_id=workspace_id, config_id=row.id, key=body.key,
        label=body.label, script=body.script, enabled=body.enabled,
    )
    db.add(script)
    db.flush()
    _audit(db, workspace_id, HEAD_SCRIPT_CHANGED, row.id, {"key": body.key}, principal)
    db.commit()
    return {"id": script.id, "key": script.key, "enabled": script.enabled}


# ---------------------------------------------------------------------------
# Routes - local creatives
# ---------------------------------------------------------------------------


@router.get("/creatives", operation_id="listSurveyCreatives")
def list_creatives(workspace_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(SurveyCreative).where(
        SurveyCreative.workspace_id == workspace_id
    ).order_by(SurveyCreative.key)).scalars().all()
    return [{"id": c.id, "key": c.key, "type": c.type, "label": c.label,
             "status": c.status, "position": c.position} for c in rows]


@router.post("/creatives", status_code=status.HTTP_201_CREATED,
             operation_id="createSurveyCreative")
def create_creative(workspace_id: str, body: CreativeIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    config = _config(db, workspace_id, body.config_id)
    exists = db.execute(select(SurveyCreative.id).where(
        SurveyCreative.workspace_id == workspace_id, SurveyCreative.key == body.key
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="creative key already exists")
    creative = SurveyCreative(
        id=new_id(), workspace_id=workspace_id, config_id=config.id, key=body.key,
        type=body.type, label=body.label, icon=body.icon, colors=body.colors,
        size=body.size, position=body.position, message=body.message,
        button_label=body.button_label, target_url=body.target_url,
        schedule=body.schedule, targeting=body.targeting, status="draft",
        created_at=now(),
    )
    db.add(creative)
    db.flush()
    _audit(db, workspace_id, CREATIVE_CHANGED, creative.id,
           {"key": body.key, "type": body.type}, principal)
    db.commit()
    return {"id": creative.id, "key": creative.key, "type": creative.type,
            "status": creative.status}


@router.patch("/creatives/{creative_id}", operation_id="updateSurveyCreative")
def update_creative(workspace_id: str, creative_id: str, body: CreativeUpdateIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    creative = _get(db, SurveyCreative, workspace_id, creative_id, "creative")
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(creative, field, value)
    db.flush()
    _audit(db, workspace_id, CREATIVE_CHANGED, creative.id,
           {"fields": sorted(data)}, principal)
    db.commit()
    return {"id": creative.id, "status": creative.status}


@router.post("/creatives/{creative_id}/evaluate", operation_id="evaluateSurveyCreative")
def evaluate_creative(workspace_id: str, creative_id: str, body: EvaluateIn,
                      principal: Principal = Depends(require(CONTACT_READ)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    creative = _get(db, SurveyCreative, workspace_id, creative_id, "creative")
    reasons: list[str] = []
    show = creative.status == "active"
    if not show:
        reasons.append("creative_not_active")
    schedule = creative.schedule or {}
    moment = body.at or now()
    if "start" in schedule and moment.isoformat() < str(schedule["start"]):
        show = False
        reasons.append("before_start")
    if "end" in schedule and moment.isoformat() > str(schedule["end"]):
        show = False
        reasons.append("after_end")
    targeting = creative.targeting or {}
    pages = targeting.get("pages") or []
    if pages and body.page not in pages:
        show = False
        reasons.append("page_not_targeted")
    devices = targeting.get("devices") or []
    if devices and body.device not in devices:
        show = False
        reasons.append("device_not_targeted")
    min_views = targeting.get("min_views", 0) or 0
    if body.views < min_views:
        show = False
        reasons.append("below_min_views")
    share = targeting.get("share", 100)
    if body.share > share:
        show = False
        reasons.append("outside_share")
    db.flush()
    _audit(db, workspace_id, CREATIVE_EVALUATED, creative.id,
           {"show": show, "reasons": reasons}, principal)
    db.commit()
    return {"creative_id": creative.id, "show": show, "reasons": reasons,
            "type": creative.type, "local_evaluation": True}
