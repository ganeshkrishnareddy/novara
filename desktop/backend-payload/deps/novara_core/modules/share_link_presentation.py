"""Clean-room P2 Papermark share-link presentation and hardening.

Documented/public behaviour implemented from scratch (no upstream source copied,
no external service contacted):

- PM-023: a multi-file share set resolves only documents marked visible.
- PM-035: a custom domain must be verified before it can serve a link slug, and
  releasing a revoked link frees that slug for reuse.
- PM-036: domain verification accepts only the exactly matching one-time token.
- PM-037: the Open Graph preview exposes only owner-approved, escaped metadata.
- PM-043: a custom password-screen message is rendered as text, never HTML.
- PM-044: detectable screenshot attempts are logged locally and the UI states
  honestly that absolute prevention (especially on mobile) is not possible.
- PM-046: watermark variables and style are configurable and rendered with all
  configured variables, escaping viewer-supplied text.
- PM-071: room/link branding resolves custom > pinned > default without copying
  any hosted plan configuration.

All new state lives in additive ``slp_*`` tables. Existing document, link and
data-room records are referenced by id only and are never altered.
"""

from __future__ import annotations

import html
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import User, new_id, now
from ..permissions import DOCUMENT_READ, DOCUMENT_WRITE
from ..security import hash_token
from .document_links import DocumentLink
from .documents import DataRoom, Document

SLP_EVENT = "share_link_presentation.changed"
register_event_types(SLP_EVENT)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/share-links",
    tags=["share-link-presentation"],
)

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,99}$")
_WATERMARK_VARIABLES = {"email", "name", "ip", "date", "time"}
_BRAND_FIELDS = ("brand_name", "accent", "logo_url", "banner_url", "preview_url")
_DEFAULT_BRAND = {
    "brand_name": "NOVARA",
    "accent": "#2563eb",
    "logo_url": "",
    "banner_url": "",
    "preview_url": "",
}


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class ShareSet(Base):
    __tablename__ = "slp_share_sets"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_slp_set_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ShareSetItem(Base):
    __tablename__ = "slp_share_set_items"
    __table_args__ = (UniqueConstraint("share_set_id", "document_id", name="uq_slp_set_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    share_set_id: Mapped[str] = mapped_column(ForeignKey("slp_share_sets.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomDomain(Base):
    __tablename__ = "slp_domains"
    __table_args__ = (UniqueConstraint("workspace_id", "domain", name="uq_slp_domain"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LinkSlug(Base):
    __tablename__ = "slp_link_slugs"
    __table_args__ = (
        UniqueConstraint("link_id", name="uq_slp_slug_link"),
        UniqueConstraint("domain_id", "slug", name="uq_slp_domain_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("slp_domains.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OgMetadata(Base):
    __tablename__ = "slp_og_metadata"
    __table_args__ = (UniqueConstraint("link_id", name="uq_slp_og_link"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PasswordScreen(Base):
    __tablename__ = "slp_password_screens"
    __table_args__ = (UniqueConstraint("link_id", name="uq_slp_password_screen"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScreenshotConfig(Base):
    __tablename__ = "slp_screenshot_configs"
    __table_args__ = (UniqueConstraint("link_id", name="uq_slp_screenshot_config"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    limitation: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScreenshotAttempt(Base):
    __tablename__ = "slp_screenshot_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WatermarkProfile(Base):
    __tablename__ = "slp_watermark_profiles"
    __table_args__ = (UniqueConstraint("link_id", name="uq_slp_watermark_profile"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("document_links.id"), nullable=False, index=True)
    variables: Mapped[list] = mapped_column(JSON, nullable=False)
    style: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BrandingConfig(Base):
    __tablename__ = "slp_branding_configs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "scope", "entity_type", "entity_id",
                         name="uq_slp_branding_config"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # pinned | custom
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # room | link
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SetCreate(BaseModel):
    name: str
    slug: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not _SLUG_RE.fullmatch(value):
            raise ValueError("slug must be lower case with dashes")
        return value


class SetItemIn(BaseModel):
    document_id: str
    visible: bool = True

    model_config = ConfigDict(extra="forbid")


class SetVisibilityIn(BaseModel):
    visible: bool

    model_config = ConfigDict(extra="forbid")


class DomainIn(BaseModel):
    domain: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, value: str) -> str:
        value = value.strip().lower()
        if not _DOMAIN_RE.fullmatch(value):
            raise ValueError("domain must be a valid lower-case hostname")
        return value


class DomainVerifyIn(BaseModel):
    domain: str
    token: str

    model_config = ConfigDict(extra="forbid")


class SlugIn(BaseModel):
    domain: str
    slug: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, value: str) -> str:
        value = value.strip().lower()
        if not _DOMAIN_RE.fullmatch(value):
            raise ValueError("domain must be a valid lower-case hostname")
        return value

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not _SLUG_RE.fullmatch(value):
            raise ValueError("slug must be lower case with dashes")
        return value


class OgIn(BaseModel):
    title: str
    description: str
    image_url: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "description")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("image_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        if not value.startswith("https://") or len(value) > 500:
            raise ValueError("image_url must be an https URL")
        return value


class PasswordScreenIn(BaseModel):
    message: str
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("message")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip() or len(value) > 500:
            raise ValueError("message must be 1-500 characters")
        return value.strip()


class ScreenshotConfigIn(BaseModel):
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")


class ScreenshotAttemptIn(BaseModel):
    channel: str
    detected: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9 _-]{2,100}", value.strip().lower()):
            raise ValueError("channel must be a simple label")
        return value.strip().lower()


class WatermarkProfileIn(BaseModel):
    variables: list[str]
    style: dict

    model_config = ConfigDict(extra="forbid")

    @field_validator("variables")
    @classmethod
    def valid_variables(cls, values: list[str]) -> list[str]:
        if not values or len(values) > 5 or len(set(values)) != len(values):
            raise ValueError("variables must be 1-5 unique entries")
        if any(v not in _WATERMARK_VARIABLES for v in values):
            raise ValueError("unsupported watermark variable")
        return values

    @field_validator("style")
    @classmethod
    def valid_style(cls, value: dict) -> dict:
        if value.get("tiling") not in (True, False):
            raise ValueError("tiling must be a boolean")
        if value.get("position") not in ("top-left", "top-right", "bottom-left", "bottom-right", "center"):
            raise ValueError("invalid position")
        if not isinstance(value.get("rotation"), int) or not -90 <= value["rotation"] <= 90:
            raise ValueError("rotation must be -90..90")
        if not isinstance(value.get("font_size"), int) or not 8 <= value["font_size"] <= 72:
            raise ValueError("font_size must be 8..72")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value.get("color", ""))):
            raise ValueError("color must be #RRGGBB")
        opacity = value.get("opacity")
        if not isinstance(opacity, (int, float)) or not 0.05 <= float(opacity) <= 1.0:
            raise ValueError("opacity must be 0.05..1.0")
        return value


class WatermarkRenderIn(BaseModel):
    email: str = ""
    name: str = ""
    ip: str = ""
    at: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("ip")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9a-fA-F:.]{5,45}", value):
            raise ValueError("ip must be an IP-shaped literal")
        return value


class BrandingIn(BaseModel):
    brand_name: str
    accent: str
    logo_url: str = ""
    banner_url: str = ""
    preview_url: str = ""

    model_config = ConfigDict(extra="forbid")

    @field_validator("brand_name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip() or len(value) > 200:
            raise ValueError("brand_name must be 1-200 characters")
        return value.strip()

    @field_validator("accent")
    @classmethod
    def valid_accent(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("accent must be #RRGGBB")
        return value

    @field_validator("logo_url", "banner_url", "preview_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("brand asset URLs must be https")
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_or_404(db: Session, model, workspace_id: str, row_id: str, label: str):
    row = db.execute(
        select(model).where(model.id == row_id, model.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return row


def _link_or_404(db: Session, workspace_id: str, link_id: str) -> DocumentLink:
    return _row_or_404(db, DocumentLink, workspace_id, link_id, "link")


def _doc_or_404(db: Session, workspace_id: str, document_id: str) -> Document:
    return _row_or_404(db, Document, workspace_id, document_id, "document")


def _domain_or_404(db: Session, workspace_id: str, domain: str) -> CustomDomain:
    row = db.execute(
        select(CustomDomain).where(
            CustomDomain.workspace_id == workspace_id, CustomDomain.domain == domain
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="domain not found")
    return row


def _emit(db: Session, workspace_id: str, entity_id: str, action: str, actor_id: str) -> None:
    publish_event(
        db, workspace_id=workspace_id, event_type=SLP_EVENT, entity_id=entity_id,
        payload={"action": action}, actor_id=actor_id,
    )


def _one_or_none(db: Session, model, **filters):
    return db.execute(select(model).where(*[getattr(model, k) == v for k, v in filters.items()])).scalar_one_or_none()


# ---------------------------------------------------------------------------
# PM-023 — multi-file share sets with per-item visibility
# ---------------------------------------------------------------------------


@router.post("/share-sets", status_code=status.HTTP_201_CREATED)
def create_share_set(
    workspace_id: str, body: SetCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if _one_or_none(db, ShareSet, workspace_id=workspace_id, slug=body.slug) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already used")
    row = ShareSet(
        id=new_id(), workspace_id=workspace_id, name=body.name, slug=body.slug,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, row.id, "share_set_created", principal.user.id)
    db.commit()
    return {"id": row.id, "name": row.name, "slug": row.slug}


@router.post("/share-sets/{set_id}/items", status_code=status.HTTP_201_CREATED)
def add_share_set_item(
    workspace_id: str, set_id: str, body: SetItemIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    share_set = _row_or_404(db, ShareSet, workspace_id, set_id, "share set")
    document = _doc_or_404(db, workspace_id, body.document_id)
    if _one_or_none(db, ShareSetItem, share_set_id=share_set.id, document_id=document.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="item already in set")
    row = ShareSetItem(
        id=new_id(), workspace_id=workspace_id, share_set_id=share_set.id,
        document_id=document.id, visible=body.visible, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, share_set.id, "share_set_item_added", principal.user.id)
    db.commit()
    return {"document_id": document.id, "visible": row.visible}


@router.patch("/share-sets/{set_id}/items/{document_id}")
def set_share_item_visibility(
    workspace_id: str, set_id: str, document_id: str, body: SetVisibilityIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    share_set = _row_or_404(db, ShareSet, workspace_id, set_id, "share set")
    item = _one_or_none(db, ShareSetItem, share_set_id=share_set.id, document_id=document_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    item.visible = body.visible
    _emit(db, workspace_id, share_set.id, "share_set_visibility", principal.user.id)
    db.commit()
    return {"document_id": document_id, "visible": item.visible}


@router.post("/share-sets/{set_id}/revoke")
def revoke_share_set(
    workspace_id: str, set_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    share_set = _row_or_404(db, ShareSet, workspace_id, set_id, "share set")
    share_set.revoked = True
    _emit(db, workspace_id, share_set.id, "share_set_revoked", principal.user.id)
    db.commit()
    return {"id": share_set.id, "revoked": True}


@router.get("/public/sets/{slug}")
def resolve_share_set(workspace_id: str, slug: str, db: Session = Depends(get_db)) -> dict:
    share_set = db.execute(
        select(ShareSet).where(ShareSet.workspace_id == workspace_id, ShareSet.slug == slug)
    ).scalar_one_or_none()
    if share_set is None or share_set.revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share set not found")
    rows = db.execute(
        select(Document).join(ShareSetItem, ShareSetItem.document_id == Document.id).where(
            ShareSetItem.workspace_id == workspace_id,
            ShareSetItem.share_set_id == share_set.id,
            ShareSetItem.visible.is_(True),
            Document.workspace_id == workspace_id,
        ).order_by(Document.title)
    ).scalars().all()
    return {
        "slug": share_set.slug,
        "documents": [{"id": d.id, "title": d.title, "doc_type": d.doc_type} for d in rows],
    }


# ---------------------------------------------------------------------------
# PM-035 / PM-036 — verified custom domains and reusable link slugs
# ---------------------------------------------------------------------------


@router.post("/domains", status_code=status.HTTP_201_CREATED)
def register_domain(
    workspace_id: str, body: DomainIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if _one_or_none(db, CustomDomain, workspace_id=workspace_id, domain=body.domain) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain already registered")
    raw_token = secrets.token_urlsafe(24)
    row = CustomDomain(
        id=new_id(), workspace_id=workspace_id, domain=body.domain,
        token_hash=hash_token(raw_token), verified=False,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, row.id, "domain_registered", principal.user.id)
    db.commit()
    return {"id": row.id, "domain": row.domain, "verification_token": raw_token, "verified": False}


@router.post("/domains/verify")
def verify_domain(
    workspace_id: str, body: DomainVerifyIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    domain = _domain_or_404(db, workspace_id, body.domain.strip().lower())
    if hash_token(body.token) != domain.token_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification token mismatch")
    domain.verified = True
    domain.verified_at = now()
    _emit(db, workspace_id, domain.id, "domain_verified", principal.user.id)
    db.commit()
    return {"domain": domain.domain, "verified": True}


@router.put("/links/{link_id}/slug")
def assign_link_slug(
    workspace_id: str, link_id: str, body: SlugIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    domain = _domain_or_404(db, workspace_id, body.domain)
    if not domain.verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="domain is not verified")
    if link.revoked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="link is revoked")
    # A revoked link frees its slug: reclaim any stale binding before checking
    # for a live conflict. No hosted state or background job is involved.
    stale = db.execute(
        select(LinkSlug).where(LinkSlug.domain_id == domain.id, LinkSlug.slug == body.slug)
    ).scalars().all()
    for candidate in stale:
        old_link = db.execute(
            select(DocumentLink.id).where(
                DocumentLink.id == candidate.link_id,
                DocumentLink.workspace_id == workspace_id,
                DocumentLink.revoked.is_(True),
            )
        ).scalar_one_or_none()
        if old_link is not None:
            db.delete(candidate)
    db.flush()
    conflict = db.execute(
        select(LinkSlug).where(LinkSlug.domain_id == domain.id, LinkSlug.slug == body.slug)
    ).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already in use")
    existing = _one_or_none(db, LinkSlug, link_id=link.id)
    if existing is not None:
        db.delete(existing)
    row = LinkSlug(
        id=new_id(), workspace_id=workspace_id, link_id=link.id,
        domain_id=domain.id, slug=body.slug, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, link.id, "slug_assigned", principal.user.id)
    db.commit()
    return {"link_id": link.id, "domain": domain.domain, "slug": row.slug}


@router.delete("/links/{link_id}/slug", status_code=status.HTTP_204_NO_CONTENT)
def release_link_slug(
    workspace_id: str, link_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> None:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    row = _one_or_none(db, LinkSlug, link_id=link.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="slug not found")
    db.delete(row)
    _emit(db, workspace_id, link.id, "slug_released", principal.user.id)
    db.commit()


@router.get("/public/domains/{domain}/links/{slug}")
def resolve_custom_domain_link(workspace_id: str, domain: str, slug: str, db: Session = Depends(get_db)) -> dict:
    domain_row = db.execute(
        select(CustomDomain).where(
            CustomDomain.workspace_id == workspace_id, CustomDomain.domain == domain.lower()
        )
    ).scalar_one_or_none()
    if domain_row is None or not domain_row.verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="domain not verified")
    slug_row = db.execute(
        select(LinkSlug).where(
            LinkSlug.workspace_id == workspace_id,
            LinkSlug.domain_id == domain_row.id, LinkSlug.slug == slug,
        )
    ).scalar_one_or_none()
    if slug_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    link = db.execute(
        select(DocumentLink).where(
            DocumentLink.id == slug_row.link_id, DocumentLink.workspace_id == workspace_id,
            DocumentLink.revoked.is_(False),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link is not active")
    return {"link_id": link.id, "domain": domain_row.domain, "slug": slug_row.slug}


# ---------------------------------------------------------------------------
# PM-037 — owner-approved Open Graph preview
# ---------------------------------------------------------------------------


@router.put("/links/{link_id}/og")
def put_og_metadata(
    workspace_id: str, link_id: str, body: OgIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    row = _one_or_none(db, OgMetadata, link_id=link.id)
    if row is None:
        row = OgMetadata(
            id=new_id(), workspace_id=workspace_id, link_id=link.id, title=body.title,
            description=body.description, image_url=body.image_url, approved=False,
            created_by=principal.user.id, updated_at=now(),
        )
        db.add(row)
    else:
        row.title, row.description, row.image_url, row.approved, row.updated_at = (
            body.title, body.description, body.image_url, False, now()
        )
    _emit(db, workspace_id, link.id, "og_saved", principal.user.id)
    db.commit()
    return {"link_id": link.id, "approved": False}


@router.post("/links/{link_id}/og/approve")
def approve_og_metadata(
    workspace_id: str, link_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    row = _one_or_none(db, OgMetadata, link_id=link.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="metadata not found")
    row.approved = True
    row.updated_at = now()
    _emit(db, workspace_id, link.id, "og_approved", principal.user.id)
    db.commit()
    return {"link_id": link.id, "approved": True}


@router.get("/public/links/{link_id}/og")
def public_og_preview(workspace_id: str, link_id: str, db: Session = Depends(get_db)) -> dict:
    link = db.execute(
        select(DocumentLink).where(
            DocumentLink.id == link_id, DocumentLink.workspace_id == workspace_id,
            DocumentLink.revoked.is_(False),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    row = _one_or_none(db, OgMetadata, link_id=link.id)
    if row is None or not row.approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="preview not approved")
    return {
        "og:title": html.escape(row.title, quote=True),
        "og:description": html.escape(row.description, quote=True),
        "og:image": html.escape(row.image_url, quote=True),
    }


# ---------------------------------------------------------------------------
# PM-043 — custom password screen without HTML injection
# ---------------------------------------------------------------------------


@router.put("/links/{link_id}/password-screen")
def put_password_screen(
    workspace_id: str, link_id: str, body: PasswordScreenIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    row = _one_or_none(db, PasswordScreen, link_id=link.id)
    if row is None:
        row = PasswordScreen(
            id=new_id(), workspace_id=workspace_id, link_id=link.id,
            message=body.message, enabled=body.enabled, updated_at=now(),
        )
        db.add(row)
    else:
        row.message, row.enabled, row.updated_at = body.message, body.enabled, now()
    _emit(db, workspace_id, link.id, "password_screen_saved", principal.user.id)
    db.commit()
    return {"link_id": link.id, "enabled": row.enabled}


@router.get("/public/links/{link_id}/password-screen")
def public_password_screen(workspace_id: str, link_id: str, db: Session = Depends(get_db)) -> dict:
    link = db.execute(
        select(DocumentLink).where(
            DocumentLink.id == link_id, DocumentLink.workspace_id == workspace_id,
            DocumentLink.revoked.is_(False),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    row = _one_or_none(db, PasswordScreen, link_id=link.id)
    if row is None or not row.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="password screen not configured")
    return {"enabled": True, "message": html.escape(row.message, quote=True)}


# ---------------------------------------------------------------------------
# PM-044 — screenshot protection with honest limitations
# ---------------------------------------------------------------------------


@router.put("/links/{link_id}/screenshot-config")
def put_screenshot_config(
    workspace_id: str, link_id: str, body: ScreenshotConfigIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    limitation = (
        "Deterrent only: detectable shortcut attempts are logged, but absolute prevention "
        "is impossible and mobile/OS-level capture cannot be reliably blocked."
    )
    row = _one_or_none(db, ScreenshotConfig, link_id=link.id)
    if row is None:
        row = ScreenshotConfig(
            id=new_id(), workspace_id=workspace_id, link_id=link.id,
            enabled=body.enabled, limitation=limitation, updated_at=now(),
        )
        db.add(row)
    else:
        row.enabled, row.updated_at = body.enabled, now()
    _emit(db, workspace_id, link.id, "screenshot_config_saved", principal.user.id)
    db.commit()
    return {"link_id": link.id, "enabled": row.enabled, "limitation": row.limitation}


@router.post("/public/links/{link_id}/screenshot-attempts", status_code=status.HTTP_201_CREATED)
def log_screenshot_attempt(
    workspace_id: str, link_id: str, body: ScreenshotAttemptIn, db: Session = Depends(get_db),
) -> dict:
    link = db.execute(
        select(DocumentLink).where(
            DocumentLink.id == link_id, DocumentLink.workspace_id == workspace_id,
            DocumentLink.revoked.is_(False),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    row = ScreenshotAttempt(
        id=new_id(), workspace_id=workspace_id, link_id=link.id,
        channel=body.channel, detected=body.detected, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, link.id, "screenshot_attempt", "visitor")
    db.commit()
    return {"link_id": link.id, "channel": row.channel, "detected": row.detected}


@router.get("/links/{link_id}/screenshot-attempts")
def screenshot_attempt_report(
    workspace_id: str, link_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    config = _one_or_none(db, ScreenshotConfig, link_id=link.id)
    rows = db.execute(
        select(ScreenshotAttempt.channel, func.count(ScreenshotAttempt.id)).where(
            ScreenshotAttempt.workspace_id == workspace_id,
            ScreenshotAttempt.link_id == link.id,
        ).group_by(ScreenshotAttempt.channel)
    ).all()
    return {
        "link_id": link.id,
        "enabled": config.enabled if config else False,
        "limits": config.limitation if config else "protection not configured",
        "attempts": {channel: count for channel, count in rows},
    }


# ---------------------------------------------------------------------------
# PM-046 — watermark variables and style
# ---------------------------------------------------------------------------


@router.put("/links/{link_id}/watermark-profile")
def put_watermark_profile(
    workspace_id: str, link_id: str, body: WatermarkProfileIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    row = _one_or_none(db, WatermarkProfile, link_id=link.id)
    if row is None:
        row = WatermarkProfile(
            id=new_id(), workspace_id=workspace_id, link_id=link.id,
            variables=list(body.variables), style=dict(body.style), updated_at=now(),
        )
        db.add(row)
    else:
        row.variables, row.style, row.updated_at = list(body.variables), dict(body.style), now()
    _emit(db, workspace_id, link.id, "watermark_profile_saved", principal.user.id)
    db.commit()
    return {"link_id": link.id, "variables": row.variables, "style": row.style}


@router.post("/links/{link_id}/watermark/render")
def render_watermark(
    workspace_id: str, link_id: str, body: WatermarkRenderIn,
    principal: Principal = Depends(require(DOCUMENT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    link = _link_or_404(db, workspace_id, link_id)
    profile = _one_or_none(db, WatermarkProfile, link_id=link.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watermark profile not found")
    moment = datetime.now(timezone.utc)
    if body.at:
        try:
            moment = datetime.fromisoformat(body.at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid at")
    values = {
        "email": body.email, "name": body.name, "ip": body.ip,
        "date": moment.strftime("%Y-%m-%d"), "time": moment.strftime("%H:%M"),
    }
    lines = [f"{name}: {html.escape(str(values[name]), quote=True)}" for name in profile.variables]
    return {"link_id": link.id, "lines": lines, "style": profile.style}


# ---------------------------------------------------------------------------
# PM-071 — room/link branding resolution
# ---------------------------------------------------------------------------


@router.put("/branding/pinned/{entity_type}")
def put_pinned_branding(
    workspace_id: str, entity_type: str, body: BrandingIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if entity_type not in ("room", "link"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid entity_type")
    row = _one_or_none(
        db, BrandingConfig, workspace_id=workspace_id, scope="pinned",
        entity_type=entity_type, entity_id="*",
    )
    values = body.model_dump()
    if row is None:
        row = BrandingConfig(
            id=new_id(), workspace_id=workspace_id, scope="pinned", entity_type=entity_type,
            entity_id="*", values=values, updated_at=now(),
        )
        db.add(row)
    else:
        row.values, row.updated_at = values, now()
    _emit(db, workspace_id, workspace_id, "pinned_branding_saved", principal.user.id)
    db.commit()
    return {"scope": "pinned", "entity_type": entity_type, "values": values}


@router.put("/branding/{entity_type}/{entity_id}")
def put_branding(
    workspace_id: str, entity_type: str, entity_id: str, body: BrandingIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if entity_type not in ("room", "link"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid entity_type")
    if entity_type == "room":
        _row_or_404(db, DataRoom, workspace_id, entity_id, "room")
    else:
        _link_or_404(db, workspace_id, entity_id)
    scope = "custom"
    row = _one_or_none(
        db, BrandingConfig, workspace_id=workspace_id, scope=scope,
        entity_type=entity_type, entity_id=entity_id,
    )
    values = body.model_dump()
    if row is None:
        row = BrandingConfig(
            id=new_id(), workspace_id=workspace_id, scope=scope, entity_type=entity_type,
            entity_id=entity_id, values=values, updated_at=now(),
        )
        db.add(row)
    else:
        row.values, row.updated_at = values, now()
    _emit(db, workspace_id, entity_id, "branding_saved", principal.user.id)
    db.commit()
    return {"scope": scope, "entity_type": entity_type, "entity_id": entity_id, "values": values}


@router.get("/branding/effective/{entity_type}/{entity_id}")
def effective_branding(
    workspace_id: str, entity_type: str, entity_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if entity_type not in ("room", "link"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid entity_type")
    if entity_type == "room":
        _row_or_404(db, DataRoom, workspace_id, entity_id, "room")
    else:
        _link_or_404(db, workspace_id, entity_id)
    custom = _one_or_none(
        db, BrandingConfig, workspace_id=workspace_id, scope="custom",
        entity_type=entity_type, entity_id=entity_id,
    )
    pinned = _one_or_none(
        db, BrandingConfig, workspace_id=workspace_id, scope="pinned",
        entity_type=entity_type, entity_id="*",
    )
    if custom is not None:
        values, source = custom.values, "custom"
    elif pinned is not None:
        values, source = pinned.values, "pinned"
    else:
        values, source = dict(_DEFAULT_BRAND), "default"
    return {
        "entity_type": entity_type, "entity_id": entity_id, "source": source,
        **{field: values.get(field, _DEFAULT_BRAND[field]) for field in _BRAND_FIELDS},
    }
