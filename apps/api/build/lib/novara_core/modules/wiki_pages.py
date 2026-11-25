"""Wiki page collaboration for projects (Plane P2 cluster).

Clean-room implementation of PL-096 (page version history), PL-097 (page
analytics), PL-098 (publish and export), PL-099 (page labels), PL-100 (nested
pages), PL-101 (page collections), PL-102 (editor blocks) and PL-103 (local
co-editing with inline comments).

Everything extends NOVARA's existing ``ProjectPage`` model additively. There is
no Django/Channels websocket transport, no React editor package, no hosted
service and no outbound traffic: editing presence uses expiring local leases,
exports are deterministic local renders, and analytics count locally recorded
views only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import TASK_READ, TASK_WRITE
from .projects import ProjectPage

PAGE_CHANGED = "wiki.page_changed"
PAGE_VIEWED = "wiki.page_viewed"
PAGE_PUBLISHED = "wiki.page_published"
PAGE_EXPORTED = "wiki.page_exported"
PAGE_COMMENTED = "wiki.page_commented"
register_event_types(PAGE_CHANGED, PAGE_VIEWED, PAGE_PUBLISHED, PAGE_EXPORTED, PAGE_COMMENTED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/wiki-pages",
    tags=["wiki-pages"],
)

BLOCK_TYPES = frozenset({"paragraph", "heading", "checklist", "code", "quote", "divider", "image"})
EXPORT_FORMATS = frozenset({"md", "html", "txt"})
MAX_EDIT_TTL = 300


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _page(db, workspace_id, page_id) -> ProjectPage:
    row = db.execute(select(ProjectPage).where(
        ProjectPage.id == page_id, ProjectPage.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return row


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


class WikiPageRevision(Base):
    __tablename__ = "wiki_page_revisions"
    __table_args__ = (
        UniqueConstraint("page_id", "version", name="uq_wiki_page_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    restored_from: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPageView(Base):
    __tablename__ = "wiki_page_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    visitor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(60), default="local", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPagePublication(Base):
    __tablename__ = "wiki_page_publications"
    __table_args__ = (
        UniqueConstraint("workspace_id", "page_id", name="uq_wiki_page_publication"),
        UniqueConstraint("workspace_id", "slug", name="uq_wiki_page_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WikiPageExport(Base):
    __tablename__ = "wiki_page_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPageLabel(Base):
    __tablename__ = "wiki_page_labels"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_wiki_page_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPageLabelLink(Base):
    __tablename__ = "wiki_page_label_links"
    __table_args__ = (
        UniqueConstraint("workspace_id", "page_id", "label_id", name="uq_wiki_page_label_link"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(ForeignKey("wiki_page_labels.id"), nullable=False, index=True)


class WikiPageNode(Base):
    __tablename__ = "wiki_page_nodes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "page_id", name="uq_wiki_page_node"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WikiPageCollection(Base):
    __tablename__ = "wiki_page_collections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_wiki_page_collection"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPageCollectionItem(Base):
    __tablename__ = "wiki_page_collection_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "collection_id", "page_id", name="uq_wiki_collection_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    collection_id: Mapped[str] = mapped_column(ForeignKey("wiki_page_collections.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WikiPageBlock(Base):
    __tablename__ = "wiki_page_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    block_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiPageComment(Base):
    __tablename__ = "wiki_page_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    block_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WikiEditSession(Base):
    __tablename__ = "wiki_edit_sessions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "page_id", "user_id", name="uq_wiki_edit_session"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=100_000)
    reason: str = Field(default="", max_length=300)


class ViewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_id: str = Field(min_length=1, max_length=120)
    source: str = Field(default="local", max_length=60)


class PublicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published: bool
    slug: str = Field(min_length=1, max_length=160)

    @field_validator("slug")
    @classmethod
    def _slug(cls, value):
        if not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError("slug may contain letters, digits, '-' and '_' only")
        return value


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: str

    @field_validator("format")
    @classmethod
    def _format(cls, value):
        if value not in EXPORT_FORMATS:
            raise ValueError("format must be md, html or txt")
        return value


class LabelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)


class PageLabelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)


class ParentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str | None = None
    position: int = Field(default=0, ge=0, le=10000)


class CollectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class CollectionItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_id: str = Field(min_length=1, max_length=36)
    position: int = Field(default=0, ge=0, le=10000)


class BlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_type: str
    content: dict = Field(default_factory=dict)
    position: int = Field(default=0, ge=0, le=10000)

    @field_validator("block_type")
    @classmethod
    def _type(cls, value):
        if value not in BLOCK_TYPES:
            raise ValueError("unsupported block type")
        return value


class BlocksIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocks: list[BlockIn] = Field(default_factory=list, max_length=500)


class EditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttl_seconds: int = Field(default=60, ge=5, le=MAX_EDIT_TTL)


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)
    block_id: str | None = Field(default=None, max_length=36)


# ---------------------------------------------------------------------------
# Routes - contract and history (PL-096)
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="wikiPagesContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "block_types": sorted(BLOCK_TYPES), "export_formats": sorted(EXPORT_FORMATS),
        "max_edit_ttl_seconds": MAX_EDIT_TTL,
        "external_calls": False, "external_delivery": False,
        "realtime_transport": "polling-only (no Channels/WebSocket)",
        "router_prefix": "/api/v1/workspaces/{workspace_id}/wiki-pages",
    }


@router.post("/pages/{page_id}/revisions", status_code=status.HTTP_201_CREATED,
             operation_id="createPageRevision")
def create_revision(workspace_id: str, page_id: str, body: RevisionIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    page = _page(db, workspace_id, page_id)
    last = db.execute(select(func.max(WikiPageRevision.version)).where(
        WikiPageRevision.workspace_id == workspace_id,
        WikiPageRevision.page_id == page_id,
    )).scalar_one()
    version = (last or 0) + 1
    row = WikiPageRevision(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                           version=version, title=body.title, body=body.body,
                           reason=body.reason, author_id=principal.user.id, created_at=now())
    db.add(row)
    page.title = body.title
    page.body = body.body
    page.updated_at = now()
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, page_id,
           {"version": version, "reason": body.reason}, principal)
    db.commit()
    return {"id": row.id, "version": version, "title": row.title,
            "body": row.body, "created_at": row.created_at.isoformat()}


@router.get("/pages/{page_id}/revisions", operation_id="listPageRevisions")
def list_revisions(workspace_id: str, page_id: str,
                   principal: Principal = Depends(require(TASK_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageRevision).where(
        WikiPageRevision.workspace_id == workspace_id,
        WikiPageRevision.page_id == page_id,
    ).order_by(WikiPageRevision.version.desc())).scalars().all()
    return [{"id": r.id, "version": r.version, "title": r.title, "body": r.body,
             "reason": r.reason, "author_id": r.author_id,
             "restored_from": r.restored_from,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/revisions/{revision_id}/restore", status_code=status.HTTP_201_CREATED,
             operation_id="restorePageRevision")
def restore_revision(workspace_id: str, revision_id: str,
                     principal: Principal = Depends(require(TASK_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    target = _get(db, WikiPageRevision, workspace_id, revision_id, "revision")
    page = _page(db, workspace_id, target.page_id)
    last = db.execute(select(func.max(WikiPageRevision.version)).where(
        WikiPageRevision.workspace_id == workspace_id,
        WikiPageRevision.page_id == page.id,
    )).scalar_one() or 0
    row = WikiPageRevision(id=new_id(), workspace_id=workspace_id, page_id=page.id,
                           version=last + 1, title=target.title, body=target.body,
                           reason=f"restored from v{target.version}",
                           author_id=principal.user.id, restored_from=target.id,
                           created_at=now())
    db.add(row)
    page.title = target.title
    page.body = target.body
    page.updated_at = now()
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, page.id,
           {"restored_from": target.id, "version": row.version}, principal)
    db.commit()
    return {"id": row.id, "version": row.version, "restored_from": target.id}


# ---------------------------------------------------------------------------
# Analytics and publication (PL-097, PL-098)
# ---------------------------------------------------------------------------


@router.post("/pages/{page_id}/views", status_code=status.HTTP_201_CREATED,
             operation_id="recordPageView")
def record_view(workspace_id: str, page_id: str, body: ViewIn,
                principal: Principal = Depends(require(TASK_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    row = WikiPageView(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                       visitor_id=body.visitor_id, source=body.source, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PAGE_VIEWED, page_id,
           {"visitor_id": body.visitor_id, "source": body.source}, principal)
    db.commit()
    return {"id": row.id, "visitor_id": row.visitor_id, "source": row.source}


@router.get("/pages/{page_id}/analytics", operation_id="pageAnalytics")
def page_analytics(workspace_id: str, page_id: str,
                   principal: Principal = Depends(require(TASK_READ)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageView).where(
        WikiPageView.workspace_id == workspace_id, WikiPageView.page_id == page_id
    ).order_by(WikiPageView.created_at.desc())).scalars().all()
    sources: dict[str, int] = {}
    for row in rows:
        sources[row.source] = sources.get(row.source, 0) + 1
    return {"page_id": page_id, "views": len(rows),
            "unique_visitors": len({r.visitor_id for r in rows}),
            "by_source": sources, "recent": [r.visitor_id for r in rows[:10]],
            "external_calls": False}


@router.put("/pages/{page_id}/publication", operation_id="setPagePublication")
def set_publication(workspace_id: str, page_id: str, body: PublicationIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    clash = db.execute(select(WikiPagePublication.id).where(
        WikiPagePublication.workspace_id == workspace_id,
        WikiPagePublication.slug == body.slug,
        WikiPagePublication.page_id != page_id,
    )).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="slug already used by another page")
    row = db.execute(select(WikiPagePublication).where(
        WikiPagePublication.workspace_id == workspace_id,
        WikiPagePublication.page_id == page_id,
    )).scalar_one_or_none()
    if row is None:
        row = WikiPagePublication(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                                  published=body.published, slug=body.slug,
                                  published_at=now() if body.published else None)
        db.add(row)
    else:
        row.slug = body.slug
        row.published = body.published
        if body.published and row.published_at is None:
            row.published_at = now()
    db.flush()
    _audit(db, workspace_id, PAGE_PUBLISHED, page_id,
           {"published": row.published, "slug": row.slug}, principal)
    db.commit()
    return {"page_id": page_id, "published": row.published, "slug": row.slug,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "public_url": "/local/p/" + row.slug if row.published else None}


@router.get("/pages/{page_id}/publication", operation_id="getPagePublication")
def get_publication(workspace_id: str, page_id: str,
                    principal: Principal = Depends(require(TASK_READ)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    row = db.execute(select(WikiPagePublication).where(
        WikiPagePublication.workspace_id == workspace_id,
        WikiPagePublication.page_id == page_id,
    )).scalar_one_or_none()
    if row is None:
        return {"page_id": page_id, "published": False, "slug": "", "public_url": None}
    return {"page_id": page_id, "published": row.published, "slug": row.slug,
            "public_url": "/local/p/" + row.slug if row.published else None}


def _render(page: ProjectPage, fmt: str) -> str:
    if fmt == "md":
        return f"# {page.title}\n\n{page.body}\n"
    if fmt == "html":
        escaped = (page.title.replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;"))
        body = page.body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<h1>{escaped}</h1>\n<p>{body}</p>\n"
    return f"{page.title}\n\n{page.body}\n"


@router.post("/pages/{page_id}/exports", status_code=status.HTTP_201_CREATED,
             operation_id="exportWikiPage")
def export_page(workspace_id: str, page_id: str, body: ExportIn,
                principal: Principal = Depends(require(TASK_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    page = _page(db, workspace_id, page_id)
    content = _render(page, body.format)
    row = WikiPageExport(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                         format=body.format, content=content,
                         content_hash=sha256(content.encode("utf-8")).hexdigest(),
                         created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PAGE_EXPORTED, page_id,
           {"format": body.format, "content_hash": row.content_hash}, principal)
    db.commit()
    return {"id": row.id, "format": row.format, "content": row.content,
            "content_hash": row.content_hash, "delivery": "local-only"}


@router.get("/pages/{page_id}/exports", operation_id="listWikiPageExports")
def list_exports(workspace_id: str, page_id: str,
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageExport).where(
        WikiPageExport.workspace_id == workspace_id, WikiPageExport.page_id == page_id
    ).order_by(WikiPageExport.created_at.desc()).limit(50)).scalars().all()
    return [{"id": r.id, "format": r.format, "content_hash": r.content_hash,
             "created_at": r.created_at.isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# Labels, hierarchy and collections (PL-099, PL-100, PL-101)
# ---------------------------------------------------------------------------


@router.post("/labels", status_code=status.HTTP_201_CREATED, operation_id="createWikiLabel")
def create_label(workspace_id: str, body: LabelIn,
                 principal: Principal = Depends(require(TASK_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(WikiPageLabel.id).where(
        WikiPageLabel.workspace_id == workspace_id, WikiPageLabel.name == body.name
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="label already exists")
    row = WikiPageLabel(id=new_id(), workspace_id=workspace_id, name=body.name,
                        created_at=now())
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "name": row.name}


@router.post("/pages/{page_id}/labels", status_code=status.HTTP_201_CREATED,
             operation_id="attachWikiLabel")
def attach_label(workspace_id: str, page_id: str, body: PageLabelIn,
                 principal: Principal = Depends(require(TASK_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    label = db.execute(select(WikiPageLabel).where(
        WikiPageLabel.workspace_id == workspace_id, WikiPageLabel.name == body.name
    )).scalar_one_or_none()
    if label is None:
        raise HTTPException(status_code=422, detail="label does not exist; create it first")
    exists = db.execute(select(WikiPageLabelLink.id).where(
        WikiPageLabelLink.workspace_id == workspace_id,
        WikiPageLabelLink.page_id == page_id, WikiPageLabelLink.label_id == label.id,
    )).scalar_one_or_none()
    if exists is None:
        db.add(WikiPageLabelLink(id=new_id(), workspace_id=workspace_id,
                                 page_id=page_id, label_id=label.id))
        db.flush()
    db.commit()
    return {"page_id": page_id, "label": label.name, "attached": True}


@router.get("/pages/{page_id}/labels", operation_id="listWikiPageLabels")
def list_labels(workspace_id: str, page_id: str,
                principal: Principal = Depends(require(TASK_READ)),
                db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageLabel.name).join(
        WikiPageLabelLink, WikiPageLabelLink.label_id == WikiPageLabel.id
    ).where(WikiPageLabelLink.workspace_id == workspace_id,
            WikiPageLabelLink.page_id == page_id)).scalars().all()
    return [{"name": name} for name in rows]


@router.delete("/pages/{page_id}/labels/{label_id}", operation_id="removeWikiPageLabel")
def remove_label(workspace_id: str, page_id: str, label_id: str,
                 principal: Principal = Depends(require(TASK_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    link = db.execute(select(WikiPageLabelLink).where(
        WikiPageLabelLink.workspace_id == workspace_id,
        WikiPageLabelLink.page_id == page_id, WikiPageLabelLink.label_id == label_id,
    )).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="label link not found")
    db.delete(link)
    db.flush()
    db.commit()
    return {"page_id": page_id, "label_id": label_id, "removed": True}


def _node(db, workspace_id, page_id) -> WikiPageNode:
    row = db.execute(select(WikiPageNode).where(
        WikiPageNode.workspace_id == workspace_id, WikiPageNode.page_id == page_id
    )).scalar_one_or_none()
    if row is None:
        row = WikiPageNode(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                           parent_id=None, position=0)
        db.add(row)
        db.flush()
    return row


@router.put("/pages/{page_id}/parent", operation_id="setWikiPageParent")
def set_parent(workspace_id: str, page_id: str, body: ParentIn,
               principal: Principal = Depends(require(TASK_WRITE)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    if body.parent_id == page_id:
        raise HTTPException(status_code=422, detail="a page cannot be its own parent")
    if body.parent_id:
        _page(db, workspace_id, body.parent_id)
        cursor = body.parent_id
        seen = set()
        while cursor:
            if cursor == page_id:
                raise HTTPException(status_code=422, detail="nested page cycle detected")
            if cursor in seen:
                raise HTTPException(status_code=422, detail="existing cycle detected")
            seen.add(cursor)
            parent = db.execute(select(WikiPageNode.parent_id).where(
                WikiPageNode.workspace_id == workspace_id, WikiPageNode.page_id == cursor
            )).scalar_one_or_none()
            cursor = parent
    node = _node(db, workspace_id, page_id)
    node.parent_id = body.parent_id
    node.position = body.position
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, page_id,
           {"parent_id": body.parent_id, "position": body.position}, principal)
    db.commit()
    return {"page_id": page_id, "parent_id": node.parent_id, "position": node.position}


@router.get("/pages/{page_id}/children", operation_id="listWikiPageChildren")
def list_children(workspace_id: str, page_id: str,
                  principal: Principal = Depends(require(TASK_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageNode).where(
        WikiPageNode.workspace_id == workspace_id, WikiPageNode.parent_id == page_id
    ).order_by(WikiPageNode.position)).scalars().all()
    return [{"page_id": r.page_id, "position": r.position} for r in rows]


@router.get("/trees", operation_id="wikiPageTrees")
def wiki_trees(workspace_id: str, project_id: str | None = Query(default=None),
               principal: Principal = Depends(require(TASK_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    stmt = select(WikiPageNode).where(WikiPageNode.workspace_id == workspace_id)
    if project_id:
        stmt = stmt.join(ProjectPage, ProjectPage.id == WikiPageNode.page_id).where(
            ProjectPage.project_id == project_id)
    rows = db.execute(stmt.order_by(WikiPageNode.position)).scalars().all()
    return [{"page_id": r.page_id, "parent_id": r.parent_id, "position": r.position}
            for r in rows]


@router.post("/collections", status_code=status.HTTP_201_CREATED,
             operation_id="createWikiCollection")
def create_collection(workspace_id: str, body: CollectionIn,
                      principal: Principal = Depends(require(TASK_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(WikiPageCollection.id).where(
        WikiPageCollection.workspace_id == workspace_id, WikiPageCollection.name == body.name
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="collection already exists")
    row = WikiPageCollection(id=new_id(), workspace_id=workspace_id, name=body.name,
                             description=body.description,
                             created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, row.id, {"collection": body.name}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "description": row.description}


@router.get("/collections", operation_id="listWikiCollections")
def list_collections(workspace_id: str,
                     principal: Principal = Depends(require(TASK_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(WikiPageCollection).where(
        WikiPageCollection.workspace_id == workspace_id
    ).order_by(WikiPageCollection.name)).scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.post("/collections/{collection_id}/items", status_code=status.HTTP_201_CREATED,
             operation_id="addWikiCollectionItem")
def add_collection_item(workspace_id: str, collection_id: str, body: CollectionItemIn,
                        principal: Principal = Depends(require(TASK_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _get(db, WikiPageCollection, workspace_id, collection_id, "collection")
    _page(db, workspace_id, body.page_id)
    exists = db.execute(select(WikiPageCollectionItem.id).where(
        WikiPageCollectionItem.workspace_id == workspace_id,
        WikiPageCollectionItem.collection_id == collection_id,
        WikiPageCollectionItem.page_id == body.page_id,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="page already in collection")
    row = WikiPageCollectionItem(id=new_id(), workspace_id=workspace_id,
                                 collection_id=collection_id, page_id=body.page_id,
                                 position=body.position)
    db.add(row)
    db.flush()
    db.commit()
    return {"collection_id": collection_id, "page_id": body.page_id,
            "position": body.position}


@router.get("/collections/{collection_id}/items", operation_id="listWikiCollectionItems")
def list_collection_items(workspace_id: str, collection_id: str,
                          principal: Principal = Depends(require(TASK_READ)),
                          db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _get(db, WikiPageCollection, workspace_id, collection_id, "collection")
    rows = db.execute(select(WikiPageCollectionItem).where(
        WikiPageCollectionItem.workspace_id == workspace_id,
        WikiPageCollectionItem.collection_id == collection_id,
    ).order_by(WikiPageCollectionItem.position)).scalars().all()
    return [{"page_id": r.page_id, "position": r.position} for r in rows]


# ---------------------------------------------------------------------------
# Editor blocks and local co-editing (PL-102, PL-103)
# ---------------------------------------------------------------------------


@router.put("/pages/{page_id}/blocks", operation_id="replaceWikiPageBlocks")
def replace_blocks(workspace_id: str, page_id: str, body: BlocksIn,
                   principal: Principal = Depends(require(TASK_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageBlock).where(
        WikiPageBlock.workspace_id == workspace_id, WikiPageBlock.page_id == page_id
    )).scalars().all()
    for row in rows:
        db.delete(row)
    db.flush()
    for item in body.blocks:
        db.add(WikiPageBlock(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                             block_type=item.block_type, content=item.content,
                             position=item.position, updated_at=now()))
    db.flush()
    _audit(db, workspace_id, PAGE_CHANGED, page_id, {"blocks": len(body.blocks)}, principal)
    db.commit()
    return {"page_id": page_id, "blocks": len(body.blocks)}


@router.get("/pages/{page_id}/blocks", operation_id="listWikiPageBlocks")
def list_blocks(workspace_id: str, page_id: str,
                principal: Principal = Depends(require(TASK_READ)),
                db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageBlock).where(
        WikiPageBlock.workspace_id == workspace_id, WikiPageBlock.page_id == page_id
    ).order_by(WikiPageBlock.position)).scalars().all()
    return [{"id": r.id, "block_type": r.block_type, "content": r.content,
             "position": r.position} for r in rows]


@router.post("/pages/{page_id}/editing", operation_id="startWikiEditSession")
def start_editing(workspace_id: str, page_id: str, body: EditIn,
                  principal: Principal = Depends(require(TASK_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    expires = now() + timedelta(seconds=body.ttl_seconds)
    row = db.execute(select(WikiEditSession).where(
        WikiEditSession.workspace_id == workspace_id,
        WikiEditSession.page_id == page_id, WikiEditSession.user_id == principal.user.id,
    )).scalar_one_or_none()
    if row is None:
        row = WikiEditSession(id=new_id(), workspace_id=workspace_id, page_id=page_id,
                              user_id=principal.user.id, expires_at=expires)
        db.add(row)
    else:
        row.expires_at = expires
    db.flush()
    db.commit()
    return {"page_id": page_id, "expires_at": expires.isoformat(),
            "realtime_transport": "polling-only"}


@router.get("/pages/{page_id}/editing", operation_id="listWikiEditSessions")
def list_editing(workspace_id: str, page_id: str,
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiEditSession).where(
        WikiEditSession.workspace_id == workspace_id,
        WikiEditSession.page_id == page_id,
        WikiEditSession.user_id != principal.user.id,
        WikiEditSession.expires_at > now(),
    )).scalars().all()
    return [{"user_id": r.user_id, "expires_at": r.expires_at.isoformat()} for r in rows]


@router.post("/blocks/{block_id}/comments", status_code=status.HTTP_201_CREATED,
             operation_id="createInlineComment")
def create_comment(workspace_id: str, block_id: str, body: CommentIn,
                   principal: Principal = Depends(require(TASK_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    block = db.execute(select(WikiPageBlock).where(
        WikiPageBlock.id == block_id, WikiPageBlock.workspace_id == workspace_id
    )).scalar_one_or_none()
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")
    row = WikiPageComment(id=new_id(), workspace_id=workspace_id, page_id=block.page_id,
                          block_id=block_id, author_id=principal.user.id,
                          body=body.body, resolved=False, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PAGE_COMMENTED, row.id,
           {"page_id": block.page_id, "block_id": block_id}, principal)
    db.commit()
    return {"id": row.id, "block_id": block_id, "body": row.body, "resolved": False}


@router.get("/pages/{page_id}/comments", operation_id="listInlineComments")
def list_comments(workspace_id: str, page_id: str,
                  principal: Principal = Depends(require(TASK_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _page(db, workspace_id, page_id)
    rows = db.execute(select(WikiPageComment).where(
        WikiPageComment.workspace_id == workspace_id, WikiPageComment.page_id == page_id
    ).order_by(WikiPageComment.created_at)).scalars().all()
    return [{"id": r.id, "block_id": r.block_id, "author_id": r.author_id,
             "body": r.body, "resolved": r.resolved,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/comments/{comment_id}/resolve", operation_id="resolveInlineComment")
def resolve_comment(workspace_id: str, comment_id: str,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, WikiPageComment, workspace_id, comment_id, "comment")
    row.resolved = True
    db.flush()
    _audit(db, workspace_id, PAGE_COMMENTED, row.id, {"resolved": True}, principal)
    db.commit()
    return {"id": row.id, "resolved": True}
