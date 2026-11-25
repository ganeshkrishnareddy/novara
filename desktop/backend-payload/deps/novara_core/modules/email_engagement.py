"""Email content and engagement tracking (Mautic P2/P3 clean-room cluster).

Clean-room implementation of MT-014 (HTML and text formats), MT-015
(translations and A/B variants), MT-017 (open tracking pixel), MT-018 (link and
click tracking), MT-020 (bounce management), MT-021 (reply monitoring), MT-022
(mailer identity and user signatures), MT-023 (base64 inline images) and MT-024
(online version of an email).

Everything is local and additive. No Mautic source, Symfony bundle, hosted
service, real email delivery, outbound HTTP, tracking domain or mail provider is
used. Tracking tokens are opaque local identifiers; opens and clicks are only
recorded when a caller hits the local tracking endpoint, and no request ever
leaves the workspace.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

TRACKED = "email.engagement_tracked"
TEMPLATE_CHANGED = "email.template_changed"
BOUNCED = "email.bounced"
REPLIED = "email.replied"
register_event_types(TRACKED, TEMPLATE_CHANGED, BOUNCED, REPLIED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/email-engagement",
    tags=["email-engagement"],
)

KINDS = frozenset({"opened", "clicked", "bounced", "replied"})
TOKEN_KINDS = frozenset({"open", "click"})
# 1x1 transparent GIF, generated locally. Not fetched from any CDN.
PIXEL_GIF_BASE64 = "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="


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


class EmailTemplate(Base):
    __tablename__ = "email_engagement_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class EmailTranslation(Base):
    __tablename__ = "email_engagement_translations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "template_id", "locale", name="uq_email_translation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("email_engagement_templates.id"), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_body: Mapped[str] = mapped_column(Text, default="", nullable=False)


class EmailVariant(Base):
    __tablename__ = "email_engagement_variants"
    __table_args__ = (
        UniqueConstraint("workspace_id", "template_id", "name", name="uq_email_variant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("email_engagement_templates.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EmailTrackingToken(Base):
    __tablename__ = "email_engagement_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_email_tracking_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("email_engagement_templates.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(120), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class EmailEngagementEvent(Base):
    __tablename__ = "email_engagement_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    token_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class EmailSignature(Base):
    __tablename__ = "email_engagement_signatures"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_email_signature"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)


class EmailInlineImage(Base):
    __tablename__ = "email_engagement_images"
    __table_args__ = (
        UniqueConstraint("workspace_id", "template_id", "cid", name="uq_email_inline_image"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("email_engagement_templates.id"), nullable=False, index=True)
    cid: Mapped[str] = mapped_column(String(120), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_base64: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=300)
    html_body: str = Field(default="", max_length=200_000)
    text_body: str = Field(default="", max_length=200_000)

    @field_validator("html_body", "text_body")
    @classmethod
    def _body_present(cls, value, info):
        return value


class TranslationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: str = Field(min_length=2, max_length=20)
    subject: str = Field(min_length=1, max_length=300)
    html_body: str = Field(default="", max_length=200_000)
    text_body: str = Field(default="", max_length=200_000)


class VariantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    subject: str = Field(min_length=1, max_length=300)
    weight: int = Field(default=1, ge=1, le=100)


class TokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_id: str = Field(min_length=1, max_length=120)
    target_url: str = Field(default="", max_length=2000)


class EngagementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_id: str = Field(min_length=1, max_length=120)
    metadata: dict = Field(default_factory=dict)
    template_id: str | None = Field(default=None, max_length=36)


class SignatureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=160)
    body_html: str = Field(default="", max_length=20_000)
    is_default: bool = False


class ImageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cid: str = Field(min_length=1, max_length=120)
    content_type: str = Field(default="image/png", max_length=80)
    content_base64: str = Field(min_length=8, max_length=4_000_000)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="emailEngagementContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "tracking": "local-tokens-only",
        "pixel": "locally generated 1x1 GIF (no CDN)",
        "external_calls": False, "external_delivery": False,
        "email_sent": False, "vendor_sdk_used": False,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/email-engagement",
    }


@router.post("/templates", status_code=status.HTTP_201_CREATED, operation_id="createEmailTemplate")
def create_template(workspace_id: str, body: TemplateIn,
                    principal: Principal = Depends(require(CONTACT_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if not (body.html_body.strip() or body.text_body.strip()):
        raise HTTPException(status_code=422, detail="provide an HTML or text body")
    row = EmailTemplate(id=new_id(), workspace_id=workspace_id, name=body.name,
                        subject=body.subject, html_body=body.html_body,
                        text_body=body.text_body, created_by=principal.user.id,
                        created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, row.id,
           {"formats": [f for f, v in (("html", body.html_body), ("text", body.text_body)) if v.strip()]},
           principal)
    db.commit()
    return {"id": row.id, "name": row.name, "subject": row.subject,
            "formats": [f for f, v in (("html", row.html_body), ("text", row.text_body)) if v.strip()]}


@router.get("/templates", operation_id="listEmailTemplates")
def list_templates(workspace_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(EmailTemplate).where(
        EmailTemplate.workspace_id == workspace_id
    ).order_by(EmailTemplate.created_at.desc())).scalars().all()
    return [{"id": r.id, "name": r.name, "subject": r.subject,
             "has_html": bool(r.html_body.strip()), "has_text": bool(r.text_body.strip())}
            for r in rows]


@router.get("/templates/{template_id}/formats", operation_id="emailTemplateFormats")
def template_formats(workspace_id: str, template_id: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    """MT-014: both renderable formats of a template, without any delivery."""
    verify_workspace(principal, workspace_id)
    row = _get(db, EmailTemplate, workspace_id, template_id, "template")
    return {"id": row.id, "subject": row.subject, "html": row.html_body,
            "text": row.text_body, "external_calls": False}


@router.post("/templates/{template_id}/translations", status_code=status.HTTP_201_CREATED,
             operation_id="createEmailTranslation")
def create_translation(workspace_id: str, template_id: str, body: TranslationIn,
                       principal: Principal = Depends(require(CONTACT_WRITE)),
                       db: Session = Depends(get_db)) -> dict:
    """MT-015: store a locale-specific subject and body."""
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    exists = db.execute(select(EmailTranslation.id).where(
        EmailTranslation.workspace_id == workspace_id,
        EmailTranslation.template_id == template_id,
        EmailTranslation.locale == body.locale,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="translation already exists")
    row = EmailTranslation(id=new_id(), workspace_id=workspace_id, template_id=template_id,
                           locale=body.locale, subject=body.subject,
                           html_body=body.html_body, text_body=body.text_body)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, template_id,
           {"translation": body.locale}, principal)
    db.commit()
    return {"id": row.id, "locale": row.locale, "subject": row.subject}


@router.get("/templates/{template_id}/translations", operation_id="listEmailTranslations")
def list_translations(workspace_id: str, template_id: str,
                      principal: Principal = Depends(require(CONTACT_READ)),
                      db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    rows = db.execute(select(EmailTranslation).where(
        EmailTranslation.workspace_id == workspace_id,
        EmailTranslation.template_id == template_id,
    ).order_by(EmailTranslation.locale)).scalars().all()
    return [{"id": r.id, "locale": r.locale, "subject": r.subject} for r in rows]


@router.post("/templates/{template_id}/variants", status_code=status.HTTP_201_CREATED,
             operation_id="createEmailVariant")
def create_variant(workspace_id: str, template_id: str, body: VariantIn,
                   principal: Principal = Depends(require(CONTACT_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    """MT-015: weighted A/B variant with deterministic selection."""
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    exists = db.execute(select(EmailVariant.id).where(
        EmailVariant.workspace_id == workspace_id,
        EmailVariant.template_id == template_id,
        EmailVariant.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="variant already exists")
    row = EmailVariant(id=new_id(), workspace_id=workspace_id, template_id=template_id,
                       name=body.name, subject=body.subject, weight=body.weight)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, template_id,
           {"variant": body.name, "weight": body.weight}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "subject": row.subject, "weight": row.weight}


@router.get("/templates/{template_id}/variants/select", operation_id="selectEmailVariant")
def select_variant(workspace_id: str, template_id: str, bucket: int = Query(default=0, ge=0),
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    rows = db.execute(select(EmailVariant).where(
        EmailVariant.workspace_id == workspace_id,
        EmailVariant.template_id == template_id,
    ).order_by(EmailVariant.name)).scalars().all()
    if not rows:
        return {"selected": None, "bucket": bucket, "total_weight": 0}
    total = sum(r.weight for r in rows)
    point = (bucket % total) + 1
    cursor = 0
    chosen = rows[-1]
    for row in rows:
        cursor += row.weight
        if point <= cursor:
            chosen = row
            break
    return {"selected": chosen.name, "subject": chosen.subject,
            "bucket": bucket, "total_weight": total, "deterministic": True}


@router.post("/templates/{template_id}/tokens", status_code=status.HTTP_201_CREATED,
             operation_id="createEmailTrackingToken")
def create_token(workspace_id: str, template_id: str, body: TokenIn,
                 principal: Principal = Depends(require(CONTACT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    """MT-017/MT-018: mint an opaque local open or click token."""
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    kind = "click" if body.target_url else "open"
    token = sha256(f"{workspace_id}:{template_id}:{body.recipient_id}:{kind}:{new_id()}".encode()).hexdigest()
    row = EmailTrackingToken(id=new_id(), workspace_id=workspace_id, template_id=template_id,
                             token=token, kind=kind, recipient_id=body.recipient_id,
                             target_url=body.target_url, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, template_id,
           {"token_kind": kind, "recipient_id": body.recipient_id}, principal)
    db.commit()
    path = "/track/click/" + token if kind == "click" else "/track/open/" + token
    return {"id": row.id, "token": token, "kind": kind,
            "local_path": "/api/v1/workspaces/" + workspace_id + "/email-engagement" + path,
            "external_calls": False}


@router.get("/track/open/{token}", operation_id="recordEmailOpen")
def track_open(workspace_id: str, token: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> dict:
    """MT-017: record a local open and return a locally generated 1x1 GIF."""
    return _record_token(workspace_id, token, "open", principal, db,
                         {"pixel_base64": PIXEL_GIF_BASE64})


@router.get("/track/click/{token}", operation_id="recordEmailClick")
def track_click(workspace_id: str, token: str,
                principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> dict:
    """MT-018: record a local click; never redirect to an external host."""
    result = _record_token(workspace_id, token, "click", principal, db,
                           {"local_only_redirect": True})
    result["target_url"] = result.pop("_target_url", "")
    return result


def _record_token(workspace_id, token, kind, principal, db, extra):
    verify_workspace(principal, workspace_id)
    row = db.execute(select(EmailTrackingToken).where(
        EmailTrackingToken.workspace_id == workspace_id,
        EmailTrackingToken.token == token,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="tracking token not found")
    if row.kind != kind:
        raise HTTPException(status_code=422, detail="token kind mismatch")
    event_kind = "opened" if kind == "open" else "clicked"
    event = EmailEngagementEvent(id=new_id(), workspace_id=workspace_id, token_id=row.id,
                                 template_id=row.template_id, kind=event_kind,
                                 recipient_id=row.recipient_id,
                                 details={"origin": "local-tracking-endpoint"}, created_at=now())
    db.add(event)
    db.flush()
    _audit(db, workspace_id, TRACKED, row.template_id,
           {"kind": kind, "recipient_id": row.recipient_id}, principal)
    db.commit()
    result = {"kind": event_kind, "recipient_id": row.recipient_id,
              "recorded": True, "external_calls": False}
    result.update(extra)
    if kind == "click":
        result["_target_url"] = row.target_url
    return result


@router.get("/templates/{template_id}/engagement", operation_id="emailEngagementStats")
def engagement_stats(workspace_id: str, template_id: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    rows = db.execute(select(EmailEngagementEvent).where(
        EmailEngagementEvent.workspace_id == workspace_id,
        EmailEngagementEvent.template_id == template_id,
    )).scalars().all()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.kind] = counts.get(row.kind, 0) + 1
    return {"template_id": template_id, "events": len(rows), "by_kind": counts,
            "unique_recipients": len({r.recipient_id for r in rows}), "external_calls": False}


@router.post("/engagement/bounces", status_code=status.HTTP_201_CREATED,
             operation_id="recordEmailBounce")
def record_bounce(workspace_id: str, body: EngagementIn,
                  principal: Principal = Depends(require(CONTACT_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    """MT-020: record a bounce event with a local reason and affected recipient."""
    verify_workspace(principal, workspace_id)
    return _record_event(workspace_id, "bounced", body, principal, db, BOUNCED)


@router.post("/engagement/replies", status_code=status.HTTP_201_CREATED,
             operation_id="recordEmailReply")
def record_reply(workspace_id: str, body: EngagementIn,
                 principal: Principal = Depends(require(CONTACT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    """MT-021: record a locally detected reply without polling any mailbox."""
    verify_workspace(principal, workspace_id)
    return _record_event(workspace_id, "replied", body, principal, db, REPLIED)


def _record_event(workspace_id, kind, body, principal, db, event_type):
    if body.template_id:
        _get(db, EmailTemplate, workspace_id, body.template_id, "template")
    row = EmailEngagementEvent(id=new_id(), workspace_id=workspace_id, token_id=None,
                               template_id=body.template_id, kind=kind,
                               recipient_id=body.recipient_id, details=body.metadata,
                               created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, event_type, body.recipient_id,
           {"kind": kind, "template_id": body.template_id}, principal)
    db.commit()
    return {"id": row.id, "kind": kind, "recipient_id": row.recipient_id,
            "metadata": row.details, "external_calls": False}


@router.get("/engagement", operation_id="listEmailEngagement")
def list_engagement(workspace_id: str, kind: str | None = Query(default=None),
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    stmt = select(EmailEngagementEvent).where(EmailEngagementEvent.workspace_id == workspace_id)
    if kind:
        if kind not in KINDS:
            raise HTTPException(status_code=422, detail="unsupported engagement kind")
        stmt = stmt.where(EmailEngagementEvent.kind == kind)
    rows = db.execute(stmt.order_by(EmailEngagementEvent.created_at.desc()).limit(200)).scalars().all()
    return [{"id": r.id, "kind": r.kind, "recipient_id": r.recipient_id,
             "template_id": r.template_id, "metadata": r.details,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/signatures", status_code=status.HTTP_201_CREATED,
             operation_id="upsertEmailSignature")
def upsert_signature(workspace_id: str, body: SignatureIn,
                     principal: Principal = Depends(require(CONTACT_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    """MT-022: one mailer identity/signature per user, scoped to the workspace."""
    verify_workspace(principal, workspace_id)
    row = db.execute(select(EmailSignature).where(
        EmailSignature.workspace_id == workspace_id,
        EmailSignature.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = EmailSignature(id=new_id(), workspace_id=workspace_id,
                             user_id=principal.user.id, display_name=body.display_name,
                             body_html=body.body_html, is_default=body.is_default)
        db.add(row)
    else:
        row.display_name = body.display_name
        row.body_html = body.body_html
        row.is_default = body.is_default
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, row.id,
           {"signature": body.display_name}, principal)
    db.commit()
    return {"id": row.id, "user_id": row.user_id, "display_name": row.display_name,
            "is_default": row.is_default}


@router.get("/signatures", operation_id="listEmailSignatures")
def list_signatures(workspace_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(EmailSignature).where(
        EmailSignature.workspace_id == workspace_id
    ).order_by(EmailSignature.display_name)).scalars().all()
    return [{"id": r.id, "user_id": r.user_id, "display_name": r.display_name,
             "is_default": r.is_default, "body_html": r.body_html} for r in rows]


@router.post("/templates/{template_id}/images", status_code=status.HTTP_201_CREATED,
             operation_id="addEmailInlineImage")
def add_image(workspace_id: str, template_id: str, body: ImageIn,
              principal: Principal = Depends(require(CONTACT_WRITE)),
              db: Session = Depends(get_db)) -> dict:
    """MT-023: store a validated base64 inline image keyed by Content-ID."""
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    try:
        raw = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=422, detail="content_base64 is not valid base64")
    if not raw:
        raise HTTPException(status_code=422, detail="image payload is empty")
    exists = db.execute(select(EmailInlineImage.id).where(
        EmailInlineImage.workspace_id == workspace_id,
        EmailInlineImage.template_id == template_id,
        EmailInlineImage.cid == body.cid,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="inline image cid already exists")
    row = EmailInlineImage(id=new_id(), workspace_id=workspace_id, template_id=template_id,
                           cid=body.cid, content_type=body.content_type,
                           content_base64=body.content_base64, size_bytes=len(raw))
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, template_id,
           {"inline_image": body.cid, "size_bytes": len(raw)}, principal)
    db.commit()
    return {"id": row.id, "cid": row.cid, "content_type": row.content_type,
            "size_bytes": row.size_bytes}


@router.get("/templates/{template_id}/images", operation_id="listEmailInlineImages")
def list_images(workspace_id: str, template_id: str,
                principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _get(db, EmailTemplate, workspace_id, template_id, "template")
    rows = db.execute(select(EmailInlineImage).where(
        EmailInlineImage.workspace_id == workspace_id,
        EmailInlineImage.template_id == template_id,
    ).order_by(EmailInlineImage.cid)).scalars().all()
    return [{"id": r.id, "cid": r.cid, "content_type": r.content_type,
             "content_base64": r.content_base64, "size_bytes": r.size_bytes} for r in rows]


@router.get("/templates/{template_id}/online", operation_id="emailOnlineVersion")
def online_version(workspace_id: str, template_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> dict:
    """MT-024: a local 'view in browser' render, assembled from stored content."""
    verify_workspace(principal, workspace_id)
    template = _get(db, EmailTemplate, workspace_id, template_id, "template")
    images = db.execute(select(EmailInlineImage).where(
        EmailInlineImage.workspace_id == workspace_id,
        EmailInlineImage.template_id == template_id,
    )).scalars().all()
    signature = db.execute(select(EmailSignature).where(
        EmailSignature.workspace_id == workspace_id,
        EmailSignature.user_id == principal.user.id,
    )).scalar_one_or_none()
    parts = [f"<h1>{_esc(template.subject)}</h1>", template.html_body or f"<p>{_esc(template.text_body)}</p>"]
    for image in images:
        parts.append(f'<img src="data:{image.content_type};base64,{image.content_base64}" alt="{_esc(image.cid)}"/>')
    if signature:
        parts.append(f"<footer>{signature.body_html}</footer>")
    html = "\n".join(parts)
    return {"template_id": template_id, "html": html,
            "content_hash": sha256(html.encode("utf-8")).hexdigest(),
            "delivery": "local-only", "external_calls": False}


def _esc(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
