"""Clean-room P2 Chatwoot help-centre governance.

Documented/public behaviour implemented from scratch (no upstream source copied,
no external service contacted):

- CW-087: rich-text articles carry validated embeds and metadata, and every
  create/revise step writes an immutable, workspace-scoped revision.
- CW-088: two portals hold independent branding, categories and articles; no
  route can return another portal's content.
- CW-089: article views and visitor searches are recorded as real local events
  and reported only inside their own workspace.
- CW-090: a widget surface surfaces published public articles and opening one
  never creates a support ticket.
- CW-091: private pages are invisible through every unauthenticated surface.
- CW-092: the API article CRUD honours the same permission model as the UI.
- CW-066: content gaps are advisory and derived only from stored search events.
- CW-067: FAQ indexing accepts only workspace-authorized documents and retains
  a citation for every indexed item.

All new state lives in additive ``hcg_*`` tables; existing portal, article and
document records are reused by reference and are never copied or altered.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import User, new_id, now
from ..permissions import CONTACT_READ, DOCUMENT_WRITE, NOTE_WRITE
from .documents import Document
from .support import HelpArticle, HelpPortal

HCG_EVENT = "help_centre_governance.changed"
register_event_types(HCG_EVENT)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/help-centre",
    tags=["help-centre-governance"],
)

_ALLOWED_EMBED_HOSTS = {"youtube.com", "www.youtube.com", "vimeo.com", "www.vimeo.com"}


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class PortalBranding(Base):
    __tablename__ = "hcg_portal_branding"
    __table_args__ = (UniqueConstraint("workspace_id", "portal_id", name="uq_hcg_portal_brand"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(ForeignKey("support_help_portals.id"), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False)
    accent: Mapped[str] = mapped_column(String(20), default="#2563eb", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HelpCategory(Base):
    __tablename__ = "hcg_categories"
    __table_args__ = (UniqueConstraint("portal_id", "slug", name="uq_hcg_category_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(ForeignKey("support_help_portals.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ArticleMeta(Base):
    __tablename__ = "hcg_article_meta"
    __table_args__ = (UniqueConstraint("article_id", name="uq_hcg_article_meta"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_articles.id"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    embeds: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ArticleRevision(Base):
    __tablename__ = "hcg_article_revisions"
    __table_args__ = (UniqueConstraint("article_id", "version", name="uq_hcg_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_articles.id"), nullable=False, index=True
    )
    portal_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_portals.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ArticleView(Base):
    __tablename__ = "hcg_article_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_articles.id"), nullable=False, index=True
    )
    portal_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_portals.id"), nullable=False, index=True
    )
    visitor_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SearchEvent(Base):
    __tablename__ = "hcg_search_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_portals.id"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(String(300), nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False)
    visitor_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PageVisibility(Base):
    __tablename__ = "hcg_page_visibility"
    __table_args__ = (UniqueConstraint("article_id", name="uq_hcg_page_visibility"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_articles.id"), nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    allowed_group: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WidgetSurface(Base):
    __tablename__ = "hcg_widget_surfaces"
    __table_args__ = (UniqueConstraint("portal_id", name="uq_hcg_widget"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_portals.id"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="Help", nullable=False)
    intro: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContentGap(Base):
    __tablename__ = "hcg_content_gaps"
    __table_args__ = (UniqueConstraint("portal_id", "query", name="uq_hcg_gap"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(
        ForeignKey("support_help_portals.id"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(String(300), nullable=False)
    searches: Mapped[int] = mapped_column(Integer, nullable=False)
    zero_result_searches: Mapped[int] = mapped_column(Integer, nullable=False)
    advisory: Mapped[str] = mapped_column(String(500), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FaqIndexEntry(Base):
    __tablename__ = "hcg_faq_index"
    __table_args__ = (UniqueConstraint("workspace_id", "document_id", name="uq_hcg_faq_doc"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    article_id: Mapped[str | None] = mapped_column(
        ForeignKey("support_help_articles.id"), index=True
    )
    citation: Mapped[dict] = mapped_column(JSON, nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BrandingIn(BaseModel):
    brand_name: str
    accent: str = "#2563eb"

    model_config = ConfigDict(extra="forbid")

    @field_validator("brand_name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("brand_name must not be empty")
        return value.strip()

    @field_validator("accent")
    @classmethod
    def valid_accent(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("accent must be a #RRGGBB colour")
        return value


class CategoryIn(BaseModel):
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
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", value):
            raise ValueError("slug must be lower case with dashes")
        return value


class MetadataIn(BaseModel):
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    embeds: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, values: list[str]) -> list[str]:
        if len(values) > 20 or any(not re.fullmatch(r"[a-z0-9 -]{1,40}", v) for v in values):
            raise ValueError("tags must be at most 20 simple labels")
        return values

    @field_validator("embeds")
    @classmethod
    def valid_embeds(cls, values: list[dict]) -> list[dict]:
        if len(values) > 10:
            raise ValueError("at most 10 embeds are allowed")
        clean = []
        for embed in values:
            kind = embed.get("kind")
            url = embed.get("url")
            if kind not in ("video", "image") or not isinstance(url, str):
                raise ValueError("embed needs a kind and url")
            parsed = urlparse(url)
            if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_EMBED_HOSTS:
                raise ValueError("embed url must be an allowed https host")
            clean.append({"kind": kind, "url": url})
        return clean


class RevisionIn(BaseModel):
    note: str = ""

    model_config = ConfigDict(extra="forbid")


class ViewIn(BaseModel):
    visitor_key: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("visitor_key")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,100}", value):
            raise ValueError("visitor_key must be 4-100 url-safe characters")
        return value


class SearchIn(BaseModel):
    query: str
    results_count: int = 0
    visitor_key: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("query")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 300:
            raise ValueError("query must be 1-300 characters")
        return value

    @field_validator("results_count")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("results_count must not be negative")
        return value


class VisibilityIn(BaseModel):
    visibility: str
    allowed_group: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("visibility")
    @classmethod
    def valid_visibility(cls, value: str) -> str:
        if value not in ("public", "internal"):
            raise ValueError("visibility must be public or internal")
        return value


class WidgetIn(BaseModel):
    enabled: bool = True
    title: str = "Help"
    intro: str = ""

    model_config = ConfigDict(extra="forbid")


class ArticleIn(BaseModel):
    portal_id: str
    title: str
    slug: str
    body: str
    audience: str = "public"
    status: str = "draft"

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,119}", value):
            raise ValueError("slug must be lower case with dashes")
        return value

    @field_validator("audience")
    @classmethod
    def valid_audience(cls, value: str) -> str:
        if value not in ("public", "agents"):
            raise ValueError("audience must be public or agents")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in ("draft", "published"):
            raise ValueError("status must be draft or published")
        return value


class ArticlePatchIn(BaseModel):
    title: str | None = None
    body: str | None = None
    audience: str | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class FaqIndexIn(BaseModel):
    document_id: str
    article_id: str | None = None
    excerpt: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("excerpt")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip() or len(value) > 500:
            raise ValueError("excerpt must be 1-500 characters")
        return value.strip()


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


def _portal_or_404(db: Session, workspace_id: str, portal_id: str) -> HelpPortal:
    return _row_or_404(db, HelpPortal, workspace_id, portal_id, "portal")


def _article_or_404(db: Session, workspace_id: str, article_id: str) -> HelpArticle:
    return _row_or_404(db, HelpArticle, workspace_id, article_id, "article")


def _portal_by_slug(db: Session, workspace_id: str, slug: str) -> HelpPortal:
    portal = db.execute(
        select(HelpPortal).where(
            HelpPortal.workspace_id == workspace_id, HelpPortal.slug == slug
        )
    ).scalar_one_or_none()
    if portal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portal not found")
    return portal


def _internal_article_ids(db: Session, workspace_id: str):
    return select(PageVisibility.article_id).where(
        PageVisibility.workspace_id == workspace_id,
        PageVisibility.visibility == "internal",
    )


def _public_article_by_slug(
    db: Session, workspace_id: str, portal_slug: str, article_slug: str
) -> HelpArticle:
    portal = _portal_by_slug(db, workspace_id, portal_slug)
    article = db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id,
            HelpArticle.portal_id == portal.id,
            HelpArticle.slug == article_slug,
            HelpArticle.status == "published",
            HelpArticle.audience == "public",
            HelpArticle.id.notin_(_internal_article_ids(db, workspace_id)),
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    return article


def _meta_for(db: Session, workspace_id: str, article_id: str) -> ArticleMeta | None:
    return db.execute(
        select(ArticleMeta).where(
            ArticleMeta.workspace_id == workspace_id, ArticleMeta.article_id == article_id
        )
    ).scalar_one_or_none()


def _snapshot(
    db: Session, workspace_id: str, article: HelpArticle, actor_id: str, note: str = ""
) -> ArticleRevision:
    version = db.execute(
        select(func.coalesce(func.max(ArticleRevision.version), 0) + 1).where(
            ArticleRevision.workspace_id == workspace_id,
            ArticleRevision.article_id == article.id,
        )
    ).scalar_one()
    meta = _meta_for(db, workspace_id, article.id)
    revision = ArticleRevision(
        id=new_id(), workspace_id=workspace_id, article_id=article.id,
        portal_id=article.portal_id, version=version, title=article.title,
        body=article.body, audience=article.audience, status=article.status,
        summary=meta.summary if meta else "", tags=list(meta.tags) if meta else [],
        note=note, created_by=actor_id, created_at=now(),
    )
    db.add(revision)
    return revision


def _emit(db: Session, workspace_id: str, entity_id: str, action: str, actor_id: str) -> None:
    publish_event(
        db, workspace_id=workspace_id, event_type=HCG_EVENT, entity_id=entity_id,
        payload={"action": action}, actor_id=actor_id,
    )


def _article_out(article: HelpArticle, meta: ArticleMeta | None = None) -> dict:
    return {
        "id": article.id, "portal_id": article.portal_id, "title": article.title,
        "slug": article.slug, "body": article.body, "audience": article.audience,
        "status": article.status, "published_at": article.published_at,
        "summary": meta.summary if meta else "",
        "tags": list(meta.tags) if meta else [],
        "embeds": list(meta.embeds) if meta else [],
    }


# ---------------------------------------------------------------------------
# CW-088 — independent portals, branding and categories
# ---------------------------------------------------------------------------


@router.put("/portals/{portal_id}/branding")
def put_branding(
    workspace_id: str, portal_id: str, body: BrandingIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    row = db.execute(
        select(PortalBranding).where(
            PortalBranding.workspace_id == workspace_id, PortalBranding.portal_id == portal_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = PortalBranding(
            id=new_id(), workspace_id=workspace_id, portal_id=portal_id,
            brand_name=body.brand_name, accent=body.accent, updated_at=now(),
        )
        db.add(row)
    else:
        row.brand_name, row.accent, row.updated_at = body.brand_name, body.accent, now()
    _emit(db, workspace_id, portal_id, "branding", principal.user.id)
    db.commit()
    return {"portal_id": portal_id, "brand_name": row.brand_name, "accent": row.accent}


@router.get("/portals/{portal_id}/branding")
def get_branding(
    workspace_id: str, portal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    row = db.execute(
        select(PortalBranding).where(
            PortalBranding.workspace_id == workspace_id, PortalBranding.portal_id == portal_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="branding not found")
    return {"portal_id": portal_id, "brand_name": row.brand_name, "accent": row.accent}


@router.post("/portals/{portal_id}/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    workspace_id: str, portal_id: str, body: CategoryIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    exists = db.execute(
        select(HelpCategory.id).where(
            HelpCategory.workspace_id == workspace_id,
            HelpCategory.portal_id == portal_id, HelpCategory.slug == body.slug,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="category already exists")
    row = HelpCategory(
        id=new_id(), workspace_id=workspace_id, portal_id=portal_id,
        name=body.name, slug=body.slug, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, portal_id, "category", principal.user.id)
    db.commit()
    return {"id": row.id, "portal_id": portal_id, "name": row.name, "slug": row.slug}


@router.get("/portals/{portal_id}/categories")
def list_categories(
    workspace_id: str, portal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    rows = db.execute(
        select(HelpCategory).where(
            HelpCategory.workspace_id == workspace_id, HelpCategory.portal_id == portal_id
        ).order_by(HelpCategory.name)
    ).scalars().all()
    return [{"id": r.id, "name": r.name, "slug": r.slug} for r in rows]


@router.get("/portals/{portal_id}/articles")
def list_portal_articles_governed(
    workspace_id: str, portal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    rows = db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id, HelpArticle.portal_id == portal_id
        ).order_by(HelpArticle.title)
    ).scalars().all()
    return [_article_out(r, _meta_for(db, workspace_id, r.id)) for r in rows]


# ---------------------------------------------------------------------------
# CW-087 — metadata, validated embeds and immutable revisions
# ---------------------------------------------------------------------------


@router.put("/articles/{article_id}/metadata")
def put_metadata(
    workspace_id: str, article_id: str, body: MetadataIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    article = _article_or_404(db, workspace_id, article_id)
    meta = _meta_for(db, workspace_id, article_id)
    if meta is None:
        meta = ArticleMeta(
            id=new_id(), workspace_id=workspace_id, article_id=article_id,
            summary=body.summary, tags=list(body.tags), embeds=list(body.embeds),
            updated_at=now(),
        )
        db.add(meta)
    else:
        meta.summary, meta.tags, meta.embeds, meta.updated_at = (
            body.summary, list(body.tags), list(body.embeds), now()
        )
    revision = _snapshot(db, workspace_id, article, principal.user.id, "metadata")
    _emit(db, workspace_id, article_id, "metadata", principal.user.id)
    db.commit()
    return {
        "article_id": article_id, "summary": meta.summary, "tags": meta.tags,
        "embeds": meta.embeds, "revision": revision.version,
    }


@router.get("/articles/{article_id}/metadata")
def get_metadata(
    workspace_id: str, article_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _article_or_404(db, workspace_id, article_id)
    meta = _meta_for(db, workspace_id, article_id)
    return {
        "article_id": article_id, "summary": meta.summary if meta else "",
        "tags": list(meta.tags) if meta else [], "embeds": list(meta.embeds) if meta else [],
    }


@router.post("/articles/{article_id}/revisions", status_code=status.HTTP_201_CREATED)
def create_revision(
    workspace_id: str, article_id: str, body: RevisionIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    article = _article_or_404(db, workspace_id, article_id)
    revision = _snapshot(db, workspace_id, article, principal.user.id, body.note)
    _emit(db, workspace_id, article_id, "revision", principal.user.id)
    db.commit()
    return {"article_id": article_id, "version": revision.version, "title": revision.title,
            "body": revision.body, "note": revision.note}


@router.get("/articles/{article_id}/revisions")
def list_revisions(
    workspace_id: str, article_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _article_or_404(db, workspace_id, article_id)
    rows = db.execute(
        select(ArticleRevision).where(
            ArticleRevision.workspace_id == workspace_id,
            ArticleRevision.article_id == article_id,
        ).order_by(ArticleRevision.version)
    ).scalars().all()
    return [{"version": r.version, "title": r.title, "body": r.body, "status": r.status,
             "summary": r.summary, "tags": r.tags, "note": r.note,
             "created_by": r.created_by} for r in rows]


# ---------------------------------------------------------------------------
# CW-089 — real local view/search events
# ---------------------------------------------------------------------------


@router.post("/articles/{article_id}/views", status_code=status.HTTP_201_CREATED)
def record_view(
    workspace_id: str, article_id: str, body: ViewIn, db: Session = Depends(get_db),
) -> dict:
    article = db.execute(
        select(HelpArticle).where(
            HelpArticle.id == article_id, HelpArticle.workspace_id == workspace_id,
            HelpArticle.status == "published", HelpArticle.audience == "public",
            HelpArticle.id.notin_(_internal_article_ids(db, workspace_id)),
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    row = ArticleView(
        id=new_id(), workspace_id=workspace_id, article_id=article_id,
        portal_id=article.portal_id, visitor_key=body.visitor_key, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, article_id, "view", "visitor")
    db.commit()
    return {"article_id": article_id, "visitor_key": body.visitor_key, "recorded": True}


@router.get("/reports/article-views")
def article_view_report(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(ArticleView.article_id, func.count(ArticleView.id)).where(
            ArticleView.workspace_id == workspace_id
        ).group_by(ArticleView.article_id)
    ).all()
    return {"workspace_id": workspace_id, "views": {a: c for a, c in rows}}


@router.post("/public/{portal_slug}/searches", status_code=status.HTTP_201_CREATED)
def record_search(
    workspace_id: str, portal_slug: str, body: SearchIn, db: Session = Depends(get_db),
) -> dict:
    portal = _portal_by_slug(db, workspace_id, portal_slug)
    row = SearchEvent(
        id=new_id(), workspace_id=workspace_id, portal_id=portal.id, query=body.query,
        results_count=body.results_count, visitor_key=body.visitor_key, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, portal.id, "search", "visitor")
    db.commit()
    return {"portal_id": portal.id, "query": row.query, "results_count": row.results_count}


@router.get("/reports/searches")
def search_report(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SearchEvent.query, func.count(SearchEvent.id),
               func.sum(SearchEvent.results_count)).where(
            SearchEvent.workspace_id == workspace_id
        ).group_by(SearchEvent.query).order_by(SearchEvent.query)
    ).all()
    return {"workspace_id": workspace_id,
            "searches": [{"query": q, "count": c, "results": int(r or 0)} for q, c, r in rows]}


# ---------------------------------------------------------------------------
# CW-090 — widget surface (opening an article never creates a ticket)
# ---------------------------------------------------------------------------


@router.put("/portals/{portal_id}/widget")
def put_widget(
    workspace_id: str, portal_id: str, body: WidgetIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    row = db.execute(
        select(WidgetSurface).where(
            WidgetSurface.workspace_id == workspace_id, WidgetSurface.portal_id == portal_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = WidgetSurface(
            id=new_id(), workspace_id=workspace_id, portal_id=portal_id,
            enabled=body.enabled, title=body.title, intro=body.intro, updated_at=now(),
        )
        db.add(row)
    else:
        row.enabled, row.title, row.intro, row.updated_at = (
            body.enabled, body.title, body.intro, now()
        )
    _emit(db, workspace_id, portal_id, "widget", principal.user.id)
    db.commit()
    return {"portal_id": portal_id, "enabled": row.enabled, "title": row.title}


@router.get("/public/{portal_slug}/widget/articles")
def widget_articles(
    workspace_id: str, portal_slug: str, db: Session = Depends(get_db),
) -> dict:
    portal = _portal_by_slug(db, workspace_id, portal_slug)
    widget = db.execute(
        select(WidgetSurface).where(
            WidgetSurface.workspace_id == workspace_id, WidgetSurface.portal_id == portal.id
        )
    ).scalar_one_or_none()
    if widget is None or not widget.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="widget not available")
    rows = db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id, HelpArticle.portal_id == portal.id,
            HelpArticle.status == "published", HelpArticle.audience == "public",
            HelpArticle.id.notin_(_internal_article_ids(db, workspace_id)),
        ).order_by(HelpArticle.title)
    ).scalars().all()
    return {"portal_id": portal.id, "title": widget.title, "intro": widget.intro,
            "articles": [{"slug": r.slug, "title": r.title} for r in rows]}


@router.get("/public/{portal_slug}/widget/articles/{article_slug}")
def widget_article(
    workspace_id: str, portal_slug: str, article_slug: str, db: Session = Depends(get_db),
) -> dict:
    _portal_by_slug(db, workspace_id, portal_slug)
    article = _public_article_by_slug(db, workspace_id, portal_slug, article_slug)
    return _article_out(article, _meta_for(db, workspace_id, article.id))


# ---------------------------------------------------------------------------
# CW-091 — private pages stay invisible without authentication
# ---------------------------------------------------------------------------


@router.put("/articles/{article_id}/visibility")
def put_visibility(
    workspace_id: str, article_id: str, body: VisibilityIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _article_or_404(db, workspace_id, article_id)
    row = db.execute(
        select(PageVisibility).where(
            PageVisibility.workspace_id == workspace_id, PageVisibility.article_id == article_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = PageVisibility(
            id=new_id(), workspace_id=workspace_id, article_id=article_id,
            visibility=body.visibility, allowed_group=body.allowed_group, updated_at=now(),
        )
        db.add(row)
    else:
        row.visibility, row.allowed_group, row.updated_at = (
            body.visibility, body.allowed_group, now()
        )
    _emit(db, workspace_id, article_id, "visibility", principal.user.id)
    db.commit()
    return {"article_id": article_id, "visibility": row.visibility,
            "allowed_group": row.allowed_group}


@router.get("/articles/{article_id}/visibility")
def get_visibility(
    workspace_id: str, article_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _article_or_404(db, workspace_id, article_id)
    row = db.execute(
        select(PageVisibility).where(
            PageVisibility.workspace_id == workspace_id, PageVisibility.article_id == article_id
        )
    ).scalar_one_or_none()
    return {"article_id": article_id, "visibility": row.visibility if row else "public",
            "allowed_group": row.allowed_group if row else None}


# ---------------------------------------------------------------------------
# CW-092 — API article CRUD with UI-equivalent permissions
# ---------------------------------------------------------------------------


@router.post("/articles", status_code=status.HTTP_201_CREATED)
def create_article(
    workspace_id: str, body: ArticleIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, body.portal_id)
    exists = db.execute(
        select(HelpArticle.id).where(
            HelpArticle.workspace_id == workspace_id, HelpArticle.portal_id == body.portal_id,
            HelpArticle.slug == body.slug,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="article slug already exists")
    article = HelpArticle(
        id=new_id(), workspace_id=workspace_id, portal_id=body.portal_id, title=body.title,
        slug=body.slug, body=body.body, audience=body.audience, status=body.status,
        published_at=now() if body.status == "published" else None,
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(article)
    db.flush()
    _snapshot(db, workspace_id, article, principal.user.id, "created")
    _emit(db, workspace_id, article.id, "article_created", principal.user.id)
    db.commit()
    return _article_out(article)


@router.get("/articles")
def list_articles(
    workspace_id: str, portal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _portal_or_404(db, workspace_id, portal_id)
    rows = db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id, HelpArticle.portal_id == portal_id
        ).order_by(HelpArticle.title)
    ).scalars().all()
    return [_article_out(r, _meta_for(db, workspace_id, r.id)) for r in rows]


@router.get("/articles/{article_id}")
def get_article(
    workspace_id: str, article_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    article = _article_or_404(db, workspace_id, article_id)
    return _article_out(article, _meta_for(db, workspace_id, article_id))


@router.patch("/articles/{article_id}")
def patch_article(
    workspace_id: str, article_id: str, body: ArticlePatchIn,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    article = _article_or_404(db, workspace_id, article_id)
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in updates.items():
        if key in ("audience", "status") and value not in (
            ("public", "agents") if key == "audience" else ("draft", "published")
        ):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"invalid {key}")
        setattr(article, key, value)
    if updates.get("status") == "published" and article.published_at is None:
        article.published_at = now()
    if updates.get("status") == "draft":
        article.published_at = None
    article.updated_at = now()
    _snapshot(db, workspace_id, article, principal.user.id, "patched")
    _emit(db, workspace_id, article_id, "article_patched", principal.user.id)
    db.commit()
    return _article_out(article, _meta_for(db, workspace_id, article_id))


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(
    workspace_id: str, article_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> None:
    verify_workspace(principal, workspace_id)
    article = _article_or_404(db, workspace_id, article_id)
    db.delete(article)
    _emit(db, workspace_id, article_id, "article_deleted", principal.user.id)
    db.commit()


# ---------------------------------------------------------------------------
# CW-066 — advisory gaps derived only from stored local data
# ---------------------------------------------------------------------------


@router.post("/content-gaps/refresh")
def refresh_content_gaps(
    workspace_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SearchEvent.portal_id, SearchEvent.query, func.count(SearchEvent.id),
               func.sum(SearchEvent.results_count)).where(
            SearchEvent.workspace_id == workspace_id
        ).group_by(SearchEvent.portal_id, SearchEvent.query)
    ).all()
    made = 0
    for portal_id, query, count, results in rows:
        zero = int(results or 0) == 0
        existing = db.execute(
            select(ContentGap).where(
                ContentGap.workspace_id == workspace_id,
                ContentGap.portal_id == portal_id, ContentGap.query == query,
            )
        ).scalar_one_or_none()
        advisory = (
            f" advisorily review: no published article matched '{query}' in {count} local search(es)."
            if zero else f" advisory: '{query}' returned {int(results or 0)} local result(s)."
        ).strip()
        if existing is None:
            db.add(ContentGap(
                id=new_id(), workspace_id=workspace_id, portal_id=portal_id, query=query,
                searches=count, zero_result_searches=count if zero else 0,
                advisory=advisory, computed_at=now(),
            ))
            made += 1
        else:
            existing.searches, existing.zero_result_searches, existing.advisory = (
                count, count if zero else 0, advisory
            )
            existing.computed_at = now()
    _emit(db, workspace_id, workspace_id, "gaps_refreshed", principal.user.id)
    db.commit()
    return {"workspace_id": workspace_id, "advisory_rows": made, "source": "local_search_events"}


@router.get("/content-gaps")
def list_content_gaps(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(ContentGap).where(ContentGap.workspace_id == workspace_id)
        .order_by(ContentGap.query)
    ).scalars().all()
    return [{"portal_id": r.portal_id, "query": r.query, "searches": r.searches,
             "zero_result_searches": r.zero_result_searches, "advisory": r.advisory,
             "advisory_only": True} for r in rows]


# ---------------------------------------------------------------------------
# CW-067 — authorized-document FAQ index with retained citations
# ---------------------------------------------------------------------------


@router.post("/faq-index", status_code=status.HTTP_201_CREATED)
def index_document(
    workspace_id: str, body: FaqIndexIn,
    principal: Principal = Depends(require(DOCUMENT_WRITE)), db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    document = db.execute(
        select(Document).where(
            Document.id == body.document_id, Document.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    if body.article_id is not None:
        _article_or_404(db, workspace_id, body.article_id)
    exists = db.execute(
        select(FaqIndexEntry.id).where(
            FaqIndexEntry.workspace_id == workspace_id,
            FaqIndexEntry.document_id == body.document_id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="document already indexed")
    citation = {
        "document_id": document.id, "title": document.title,
        "doc_type": document.doc_type, "excerpt": body.excerpt,
        "article_id": body.article_id, "workspace_id": workspace_id,
    }
    row = FaqIndexEntry(
        id=new_id(), workspace_id=workspace_id, document_id=document.id,
        article_id=body.article_id, citation=citation, authorized=True,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(row)
    _emit(db, workspace_id, document.id, "faq_indexed", principal.user.id)
    db.commit()
    return {"id": row.id, "document_id": document.id, "citation": citation,
            "authorized": True}


@router.get("/faq-index")
def list_faq_index(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(FaqIndexEntry).where(FaqIndexEntry.workspace_id == workspace_id)
        .order_by(FaqIndexEntry.created_at)
    ).scalars().all()
    return [{"id": r.id, "document_id": r.document_id, "citation": r.citation,
             "authorized": r.authorized} for r in rows]
