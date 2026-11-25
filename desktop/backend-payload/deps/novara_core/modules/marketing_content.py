"""Marketing content and contact classification (Mautic clean-room cluster).

Clean-room implementation of MT-009 (visitor and known contact types), MT-029
(landing pages), MT-031 (progressive profiling via forms), MT-032 (form submit
actions), MT-036 (dynamic content), MT-037 (asset bundle) and MT-048 (dashboard
bundle).

Everything is local and additive. No Mautic source, Symfony bundle, hosted
service, real email/SMS delivery, outbound HTTP or external storage is used.
Landing pages are local renders, submit actions are recorded as local effects,
and dashboard widgets aggregate locally recorded events only.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

CONTACT_TYPED = "marketing.contact_typed"
PAGE_CHANGED = "marketing.landing_page_changed"
FORM_SUBMITTED = "marketing.form_submitted"
CONTENT_RESOLVED = "marketing.dynamic_content_resolved"
ASSET_ADDED = "marketing.asset_added"
register_event_types(CONTACT_TYPED, PAGE_CHANGED, FORM_SUBMITTED, CONTENT_RESOLVED, ASSET_ADDED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/marketing-content",
    tags=["marketing-content"],
)

CONTACT_KINDS = frozenset({"visitor", "known"})
WIDGET_TYPES = frozenset({"counter", "breakdown", "timeline"})
ACTION_TYPES = frozenset({"tag", "update_contact", "create_task", "notify"})


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


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class MarketingContactType(Base):
    __tablename__ = "content_contact_types"
    __table_args__ = (
        UniqueConstraint("workspace_id", "contact_id", name="uq_marketing_contact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    identified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MarketingLandingPage(Base):
    __tablename__ = "content_landing_pages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_marketing_landing_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingForm(Base):
    __tablename__ = "content_forms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    landing_page_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingFormSubmission(Base):
    __tablename__ = "content_form_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("content_forms.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String(120), nullable=False)
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingDynamicContent(Base):
    __tablename__ = "content_dynamic_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    segment_field: Mapped[str] = mapped_column(String(120), nullable=False)
    variants: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingAsset(Base):
    __tablename__ = "content_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_base64: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingDashboardWidget(Base):
    __tablename__ = "content_dashboard_widgets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_marketing_dashboard_widget"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    widget_type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ContactTypeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: str = Field(min_length=1, max_length=120)
    kind: str
    details: dict = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in CONTACT_KINDS:
            raise ValueError("kind must be visitor or known")
        return value


class IdentifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    details: dict = Field(default_factory=dict)


class LandingPageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=160)
    html_body: str = Field(default="", max_length=200_000)

    @field_validator("slug")
    @classmethod
    def _slug(cls, value):
        if not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError("slug may contain letters, digits, '-' and '_' only")
        return value


class PublicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published: bool


class FormIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    landing_page_id: str | None = None
    fields: list[str] = Field(default_factory=list, max_length=100)


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: str = Field(min_length=1, max_length=120)
    answers: dict = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)

    @field_validator("actions")
    @classmethod
    def _actions(cls, value):
        if any(a not in ACTION_TYPES for a in value):
            raise ValueError("unsupported submit action")
        return value


class DynamicContentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    segment_field: str = Field(min_length=1, max_length=120)
    variants: dict[str, str]

    @field_validator("variants")
    @classmethod
    def _variants(cls, value):
        if not value:
            raise ValueError("at least one variant is required")
        return value


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attributes: dict = Field(default_factory=dict)


class AssetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    content_type: str = Field(default="application/octet-stream", max_length=80)
    content_base64: str = Field(min_length=8, max_length=4_000_000)


class WidgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    widget_type: str
    config: dict = Field(default_factory=dict)

    @field_validator("widget_type")
    @classmethod
    def _widget(cls, value):
        if value not in WIDGET_TYPES:
            raise ValueError("unsupported widget type")
        return value


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="marketingContentContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "contact_kinds": sorted(CONTACT_KINDS), "widget_types": sorted(WIDGET_TYPES),
        "submit_actions": sorted(ACTION_TYPES),
        "external_calls": False, "external_delivery": False,
        "email_sent": False, "sms_sent": False,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/marketing-content",
    }


@router.post("/contact-types", status_code=status.HTTP_201_CREATED,
             operation_id="classifyMarketingContact")
def classify_contact(workspace_id: str, body: ContactTypeIn,
                     principal: Principal = Depends(require(CONTACT_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    """MT-009: classify a contact as a visitor or a known contact locally."""
    verify_workspace(principal, workspace_id)
    row = db.execute(select(MarketingContactType).where(
        MarketingContactType.workspace_id == workspace_id,
        MarketingContactType.contact_id == body.contact_id,
    )).scalar_one_or_none()
    if row is not None:
        raise HTTPException(status_code=409, detail="contact type already exists")
    row = MarketingContactType(id=new_id(), workspace_id=workspace_id,
                               contact_id=body.contact_id, kind=body.kind,
                               identified_at=now() if body.kind == "known" else None,
                               details=body.details)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, CONTACT_TYPED, body.contact_id,
           {"kind": body.kind}, principal)
    db.commit()
    return {"contact_id": row.contact_id, "kind": row.kind,
            "identified_at": row.identified_at.isoformat() if row.identified_at else None}


@router.get("/contact-types/{contact_id}", operation_id="getMarketingContactType")
def get_contact_type(workspace_id: str, contact_id: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(MarketingContactType).where(
        MarketingContactType.workspace_id == workspace_id,
        MarketingContactType.contact_id == contact_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="contact type not found")
    return {"contact_id": row.contact_id, "kind": row.kind,
            "identified_at": row.identified_at.isoformat() if row.identified_at else None,
            "details": row.details}


@router.post("/contact-types/{contact_id}/identify", operation_id="identifyMarketingContact")
def identify_contact(workspace_id: str, contact_id: str, body: IdentifyIn,
                     principal: Principal = Depends(require(CONTACT_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    """MT-009: promote a visitor to a known contact without creating a new row."""
    verify_workspace(principal, workspace_id)
    row = db.execute(select(MarketingContactType).where(
        MarketingContactType.workspace_id == workspace_id,
        MarketingContactType.contact_id == contact_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="contact type not found")
    if row.kind == "known":
        raise HTTPException(status_code=409, detail="contact is already known")
    row.kind = "known"
    row.identified_at = now()
    row.details = {**row.details, **body.details}
    db.flush()
    _audit(db, workspace_id, CONTACT_TYPED, contact_id, {"kind": "known"}, principal)
    db.commit()
    return {"contact_id": row.contact_id, "kind": "known",
            "identified_at": row.identified_at.isoformat()}


@router.post("/landing-pages", status_code=status.HTTP_201_CREATED,
             operation_id="createMarketingLandingPage")
def create_landing_page(workspace_id: str, body: LandingPageIn,
                        principal: Principal = Depends(require(CONTACT_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    """MT-029: a locally rendered landing page with a unique slug."""
    verify_workspace(principal, workspace_id)
    clash = db.execute(select(MarketingLandingPage.id).where(
        MarketingLandingPage.workspace_id == workspace_id,
        MarketingLandingPage.slug == body.slug,
    )).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="slug already used")
    row = MarketingLandingPage(id=new_id(), workspace_id=workspace_id, name=body.name,
                               slug=body.slug, html_body=body.html_body,
                               published=False, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, row.id, {"slug": body.slug}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "slug": row.slug, "published": False}


@router.get("/landing-pages", operation_id="listMarketingLandingPages")
def list_landing_pages(workspace_id: str,
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(MarketingLandingPage).where(
        MarketingLandingPage.workspace_id == workspace_id
    ).order_by(MarketingLandingPage.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "slug": r.slug, "published": r.published}
            for r in rows]


@router.put("/landing-pages/{page_id}/publication", operation_id="setLandingPagePublication")
def set_landing_publication(workspace_id: str, page_id: str, body: PublicationIn,
                            principal: Principal = Depends(require(CONTACT_WRITE)),
                            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, MarketingLandingPage, workspace_id, page_id, "landing page")
    row.published = body.published
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, page_id, {"published": body.published}, principal)
    db.commit()
    return {"id": page_id, "published": row.published,
            "local_url": "/local/lp/" + row.slug if row.published else None}


@router.get("/landing-pages/{page_id}/preview", operation_id="previewLandingPage")
def preview_landing_page(workspace_id: str, page_id: str,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, MarketingLandingPage, workspace_id, page_id, "landing page")
    return {"id": row.id, "slug": row.slug, "html": row.html_body,
            "delivery": "local-only", "external_calls": False}


@router.post("/forms", status_code=status.HTTP_201_CREATED, operation_id="createMarketingForm")
def create_form(workspace_id: str, body: FormIn,
                principal: Principal = Depends(require(CONTACT_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    """MT-031: a form whose fields feed progressive profiling."""
    verify_workspace(principal, workspace_id)
    if body.landing_page_id:
        _get(db, MarketingLandingPage, workspace_id, body.landing_page_id, "landing page")
    if len(set(body.fields)) != len(body.fields):
        raise HTTPException(status_code=422, detail="duplicate form field")
    row = MarketingForm(id=new_id(), workspace_id=workspace_id, name=body.name,
                        landing_page_id=body.landing_page_id, fields=body.fields,
                        created_at=now())
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "name": row.name, "fields": row.fields}


@router.get("/forms/{form_id}/progressive-fields", operation_id="progressiveFormFields")
def progressive_fields(workspace_id: str, form_id: str, contact_id: str,
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> dict:
    """MT-031: return only the fields still unknown for a contact."""
    verify_workspace(principal, workspace_id)
    form = _get(db, MarketingForm, workspace_id, form_id, "form")
    ctype = db.execute(select(MarketingContactType).where(
        MarketingContactType.workspace_id == workspace_id,
        MarketingContactType.contact_id == contact_id,
    )).scalar_one_or_none()
    known = set(ctype.details.keys()) if ctype else set()
    pending = [f for f in form.fields if f not in known]
    return {"form_id": form_id, "contact_id": contact_id,
            "pending_fields": pending, "progressive": True}


@router.post("/forms/{form_id}/submit", status_code=status.HTTP_201_CREATED,
             operation_id="submitMarketingForm")
def submit_form(workspace_id: str, form_id: str, body: SubmitIn,
                principal: Principal = Depends(require(CONTACT_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    """MT-032: execute recorded local submit actions; no delivery is attempted."""
    verify_workspace(principal, workspace_id)
    form = _get(db, MarketingForm, workspace_id, form_id, "form")
    unknown = [a for a in body.answers if a not in form.fields]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown form field: {unknown[0]}")
    effects = [{"action": action, "contact_id": body.contact_id, "local_only": True}
               for action in body.actions]
    row = MarketingFormSubmission(id=new_id(), workspace_id=workspace_id, form_id=form_id,
                                  contact_id=body.contact_id, answers=body.answers,
                                  actions=effects, created_at=now())
    db.add(row)
    ctype = db.execute(select(MarketingContactType).where(
        MarketingContactType.workspace_id == workspace_id,
        MarketingContactType.contact_id == body.contact_id,
    )).scalar_one_or_none()
    if ctype is None:
        ctype = MarketingContactType(id=new_id(), workspace_id=workspace_id,
                                     contact_id=body.contact_id, kind="visitor", details={})
        db.add(ctype)
    ctype.details = {**ctype.details, **body.answers}
    db.flush()
    _audit(db, workspace_id, FORM_SUBMITTED, form_id,
           {"contact_id": body.contact_id, "actions": body.actions}, principal)
    db.commit()
    return {"id": row.id, "contact_id": row.contact_id, "effects": effects,
            "external_calls": False, "delivery": "local-only"}


@router.post("/dynamic-content", status_code=status.HTTP_201_CREATED,
             operation_id="createDynamicContent")
def create_dynamic_content(workspace_id: str, body: DynamicContentIn,
                           principal: Principal = Depends(require(CONTACT_WRITE)),
                           db: Session = Depends(get_db)) -> dict:
    """MT-036: segment-field to content-variant rules, stored locally."""
    verify_workspace(principal, workspace_id)
    row = MarketingDynamicContent(id=new_id(), workspace_id=workspace_id, name=body.name,
                                  segment_field=body.segment_field, variants=body.variants,
                                  created_at=now())
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "name": row.name, "segment_field": row.segment_field,
            "variants": sorted(row.variants)}


@router.post("/dynamic-content/{content_id}/resolve", operation_id="resolveDynamicContent")
def resolve_dynamic_content(workspace_id: str, content_id: str, body: ResolveIn,
                            principal: Principal = Depends(require(CONTACT_READ)),
                            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, MarketingDynamicContent, workspace_id, content_id, "dynamic content")
    value = str(body.attributes.get(row.segment_field, ""))
    chosen_key = value if value in row.variants else "default"
    if chosen_key not in row.variants:
        chosen_key = sorted(row.variants)[0]
    db.flush()
    _audit(db, workspace_id, CONTENT_RESOLVED, content_id,
           {"segment_field": row.segment_field, "variant": chosen_key}, principal)
    db.commit()
    return {"content_id": content_id, "variant": chosen_key,
            "content": row.variants[chosen_key], "deterministic": True}


@router.post("/assets", status_code=status.HTTP_201_CREATED, operation_id="addMarketingAsset")
def add_asset(workspace_id: str, body: AssetIn,
              principal: Principal = Depends(require(CONTACT_WRITE)),
              db: Session = Depends(get_db)) -> dict:
    """MT-037: a locally stored asset bundle with validated base64 payload."""
    verify_workspace(principal, workspace_id)
    try:
        raw = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=422, detail="content_base64 is not valid base64")
    if not raw:
        raise HTTPException(status_code=422, detail="asset payload is empty")
    row = MarketingAsset(id=new_id(), workspace_id=workspace_id, name=body.name,
                         content_type=body.content_type, content_base64=body.content_base64,
                         size_bytes=len(raw), created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ASSET_ADDED, row.id,
           {"name": body.name, "size_bytes": len(raw)}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "content_hash": sha256(raw).hexdigest()}


@router.get("/assets", operation_id="listMarketingAssets")
def list_assets(workspace_id: str,
                principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(MarketingAsset).where(
        MarketingAsset.workspace_id == workspace_id
    ).order_by(MarketingAsset.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "content_type": r.content_type,
             "size_bytes": r.size_bytes} for r in rows]


@router.post("/dashboard-widgets", status_code=status.HTTP_201_CREATED,
             operation_id="createMarketingDashboardWidget")
def create_widget(workspace_id: str, body: WidgetIn,
                  principal: Principal = Depends(require(CONTACT_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    """MT-048: a dashboard widget definition whose data comes from local rows."""
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(MarketingDashboardWidget.id).where(
        MarketingDashboardWidget.workspace_id == workspace_id,
        MarketingDashboardWidget.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="widget already exists")
    row = MarketingDashboardWidget(id=new_id(), workspace_id=workspace_id, name=body.name,
                                   widget_type=body.widget_type, config=body.config)
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "name": row.name, "widget_type": row.widget_type}


def _widget_value(db, workspace_id, widget_type, config):
    if widget_type == "counter":
        model = {"contact_types": MarketingContactType, "landing_pages": MarketingLandingPage,
                 "forms": MarketingForm, "submissions": MarketingFormSubmission,
                 "assets": MarketingAsset}.get(config.get("source", ""))
        if model is None:
            return 0
        return len(db.execute(select(model).where(
            model.workspace_id == workspace_id)).scalars().all())
    if widget_type == "breakdown":
        rows = db.execute(select(MarketingContactType.kind).where(
            MarketingContactType.workspace_id == workspace_id)).scalars().all()
        result: dict[str, int] = {}
        for kind in rows:
            result[kind] = result.get(kind, 0) + 1
        return result
    rows = db.execute(select(MarketingFormSubmission.created_at).where(
        MarketingFormSubmission.workspace_id == workspace_id
    ).order_by(MarketingFormSubmission.created_at.desc()).limit(10)).scalars().all()
    return [r.isoformat() for r in rows]


@router.get("/dashboard", operation_id="marketingDashboard")
def dashboard(workspace_id: str,
              principal: Principal = Depends(require(CONTACT_READ)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    widgets = db.execute(select(MarketingDashboardWidget).where(
        MarketingDashboardWidget.workspace_id == workspace_id
    ).order_by(MarketingDashboardWidget.name)).scalars().all()
    return {
        "widgets": [{"name": w.name, "type": w.widget_type,
                     "value": _widget_value(db, workspace_id, w.widget_type, w.config)}
                    for w in widgets],
        "source": "local-records-only", "external_calls": False,
    }
