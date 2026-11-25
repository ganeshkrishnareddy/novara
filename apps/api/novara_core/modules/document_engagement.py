"""Document collaboration and engagement analytics (Papermark P2 cluster).

Clean-room implementation of the Papermark collaboration and analytics rows:
document metadata update and folder move (PM-007), version promotion and link
repoint (PM-010), case-insensitive name search (PM-018), reactions (PM-024),
feedback (PM-025), annotations (PM-027), scroll-depth/completion (PM-076),
video analytics (PM-077), visitor location (PM-083), device/OS/platform
analytics (PM-084), internal-visit exclusion (PM-085) and the click route
(PM-091).

No Papermark server source is copied. Every record is a NOVARA-local,
workspace-scoped row; no outbound email, hosted viewer, geolocation service or
external analytics provider is contacted. Location and client fields are
caller-supplied metadata, never resolved through an external lookup.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import DOCUMENT_READ, DOCUMENT_WRITE
from .documents import Document, DocumentVersion, LibraryFolder

METADATA_CHANGED = "document.metadata_changed"
VERSION_PROMOTED = "document.version_promoted"
REACTION_CHANGED = "document.reaction_changed"
FEEDBACK_CHANGED = "document.feedback_changed"
ANNOTATION_CHANGED = "document.annotation_changed"
ENGAGEMENT_RECORDED = "document.engagement_recorded"
INTERNAL_VISITOR_CHANGED = "document.internal_visitor_changed"
register_event_types(
    METADATA_CHANGED, VERSION_PROMOTED, REACTION_CHANGED, FEEDBACK_CHANGED,
    ANNOTATION_CHANGED, ENGAGEMENT_RECORDED, INTERNAL_VISITOR_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/document-engagement",
    tags=["document-engagement"],
)

EVENT_TYPES = frozenset({"view", "scroll", "video", "click"})
ANNOTATION_KINDS = frozenset({"highlight", "comment", "note"})
MATCH_TYPES = frozenset({"visitor", "email_domain"})
REACTION_KEYS = frozenset({"like", "love", "insightful", "question", "celebrate"})


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _document(db, workspace_id, document_id) -> Document:
    row = db.execute(select(Document).where(
        Document.id == document_id, Document.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return row


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


# ---------------------------------------------------------------------------
# Tables (additive, workspace-scoped)
# ---------------------------------------------------------------------------


class DocumentReaction(Base):
    __tablename__ = "document_reactions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "document_id", "page_number", "user_id", "key",
                         name="uq_document_reaction"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    key: Mapped[str] = mapped_column(String(24), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DocumentFeedback(Base):
    __tablename__ = "document_feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author: Mapped[str] = mapped_column(String(200), default="anonymous", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DocumentAnnotation(Base):
    __tablename__ = "document_annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DocumentVersionTarget(Base):
    __tablename__ = "document_version_targets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version_id", name="uq_document_version_target"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), nullable=False, index=True)
    external_url: Mapped[str] = mapped_column(String(500), nullable=False)


class DocumentEngagementEvent(Base):
    __tablename__ = "document_engagement_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    visitor: Mapped[str] = mapped_column(String(200), default="anonymous", nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scroll_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    video_position_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    video_duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    device: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    os: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="unknown", nullable=False)
    city: Mapped[str] = mapped_column(String(120), default="unknown", nullable=False)
    target: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DocumentInternalVisitor(Base):
    __tablename__ = "document_internal_visitors"
    __table_args__ = (
        UniqueConstraint("workspace_id", "match_type", "value", name="uq_document_internal_visitor"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MetadataIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=300)
    folder_id: str | None = None
    clear_folder: bool = False


class PromoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_url: str | None = Field(default=None, max_length=500)


class ReactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    page_number: int = 0

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        if value not in REACTION_KEYS:
            raise ValueError("unsupported reaction key")
        return value

    @field_validator("page_number")
    @classmethod
    def _page(cls, value):
        if value < 0:
            raise ValueError("page_number must be zero or greater")
        return value


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)
    rating: int | None = None
    author: str = Field(default="anonymous", max_length=200)

    @field_validator("rating")
    @classmethod
    def _rating(cls, value):
        if value is not None and not 1 <= value <= 5:
            raise ValueError("rating must be between 1 and 5")
        return value


class AnnotationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = 1
    kind: str
    content: str = Field(min_length=1, max_length=4000)
    position: dict = Field(default_factory=dict)
    version_id: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in ANNOTATION_KINDS:
            raise ValueError("unsupported annotation kind")
        return value

    @field_validator("page_number")
    @classmethod
    def _page(cls, value):
        if value < 1:
            raise ValueError("page_number must be at least 1")
        return value


class InternalVisitorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_type: str
    value: str = Field(min_length=1, max_length=200)

    @field_validator("match_type")
    @classmethod
    def _match(cls, value):
        if value not in MATCH_TYPES:
            raise ValueError("unsupported internal-visitor match type")
        return value


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str
    visitor: str = Field(default="anonymous", max_length=200)
    page_number: int | None = None
    scroll_depth: int = 0
    completed: bool = False
    video_position_s: float = 0.0
    video_duration_s: float = 0.0
    device: str = Field(default="unknown", max_length=40)
    os: str = Field(default="unknown", max_length=40)
    platform: str = Field(default="unknown", max_length=40)
    country: str = Field(default="unknown", max_length=80)
    city: str = Field(default="unknown", max_length=120)
    target: str = Field(default="", max_length=300)

    @field_validator("event_type")
    @classmethod
    def _type(cls, value):
        if value not in EVENT_TYPES:
            raise ValueError("unsupported engagement event type")
        return value

    @field_validator("scroll_depth")
    @classmethod
    def _depth(cls, value):
        if not 0 <= value <= 100:
            raise ValueError("scroll_depth must be between 0 and 100")
        return value


class ClickIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor: str = Field(default="anonymous", max_length=200)
    target: str = Field(min_length=1, max_length=300)
    device: str = Field(default="unknown", max_length=40)
    country: str = Field(default="unknown", max_length=80)
    city: str = Field(default="unknown", max_length=120)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_internal(db, workspace_id, visitor: str) -> bool:
    rows = db.execute(select(DocumentInternalVisitor).where(
        DocumentInternalVisitor.workspace_id == workspace_id
    )).scalars().all()
    domain = visitor.split("@", 1)[1].lower() if "@" in visitor else ""
    for row in rows:
        if row.match_type == "visitor" and row.value == visitor:
            return True
        if row.match_type == "email_domain" and domain and row.value.lower() == domain:
            return True
    return False


def _record_event(db, workspace_id, document, body: EventIn, principal) -> DocumentEngagementEvent:
    row = DocumentEngagementEvent(
        id=new_id(), workspace_id=workspace_id, document_id=document.id,
        event_type=body.event_type, visitor=body.visitor, page_number=body.page_number,
        scroll_depth=body.scroll_depth, completed=body.completed,
        video_position_s=body.video_position_s, video_duration_s=body.video_duration_s,
        device=body.device, os=body.os, platform=body.platform,
        country=body.country, city=body.city, target=body.target,
        is_internal=_is_internal(db, workspace_id, body.visitor), created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ENGAGEMENT_RECORDED, row.id,
           {"event_type": body.event_type, "is_internal": row.is_internal}, principal)
    return row


# ---------------------------------------------------------------------------
# Routes - contract, metadata, version promotion and name search
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="documentEngagementContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["metadata", "versions", "search", "reactions", "feedback",
                      "annotations", "events", "clicks", "analytics", "internalVisitors"],
        "event_types": sorted(EVENT_TYPES), "reaction_keys": sorted(REACTION_KEYS),
        "external_calls": False, "external_geolocation": False,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/document-engagement",
    }


@router.patch("/documents/{document_id}/metadata", operation_id="updateDocumentMetadata")
def update_metadata(workspace_id: str, document_id: str, body: MetadataIn,
                    principal: Principal = Depends(require(DOCUMENT_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    fields: list[str] = []
    if body.title is not None:
        document.title = body.title.strip()
        fields.append("title")
    if body.clear_folder:
        document.folder_id = None
        fields.append("folder_id")
    elif body.folder_id is not None:
        folder = db.execute(select(LibraryFolder).where(
            LibraryFolder.id == body.folder_id, LibraryFolder.workspace_id == workspace_id
        )).scalar_one_or_none()
        if folder is None:
            raise HTTPException(status_code=404, detail="folder not found")
        document.folder_id = folder.id
        fields.append("folder_id")
    if not fields:
        raise HTTPException(status_code=422, detail="no metadata change supplied")
    db.flush()
    _audit(db, workspace_id, METADATA_CHANGED, document.id, {"fields": fields}, principal)
    db.commit()
    return {"id": document.id, "title": document.title, "folder_id": document.folder_id}


@router.post("/documents/{document_id}/versions/{version_id}/promote",
             operation_id="promoteDocumentVersion")
def promote_version(workspace_id: str, document_id: str, version_id: str, body: PromoteIn,
                    principal: Principal = Depends(require(DOCUMENT_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    version = db.execute(select(DocumentVersion).where(
        DocumentVersion.id == version_id, DocumentVersion.workspace_id == workspace_id,
        DocumentVersion.document_id == document.id,
    )).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="version not found")
    # Atomic demotion first (same pattern as documents.py): a single flush that
    # both demotes and promotes can batch UPDATEs in an order that transiently
    # leaves two primaries, violating uq_document_version_primary on SQLite.
    db.query(DocumentVersion).where(
        DocumentVersion.workspace_id == workspace_id,
        DocumentVersion.document_id == document.id,
        DocumentVersion.is_primary.is_(True),
    ).update({DocumentVersion.is_primary: False}, synchronize_session="evaluate")
    version.is_primary = True
    external_url = None
    if body.external_url is not None:
        target = db.execute(select(DocumentVersionTarget).where(
            DocumentVersionTarget.workspace_id == workspace_id,
            DocumentVersionTarget.version_id == version.id,
        )).scalar_one_or_none()
        if target is None:
            target = DocumentVersionTarget(id=new_id(), workspace_id=workspace_id,
                                           version_id=version.id, external_url=body.external_url)
            db.add(target)
        else:
            target.external_url = body.external_url
        external_url = body.external_url
    db.flush()
    _audit(db, workspace_id, VERSION_PROMOTED, version.id,
           {"version_number": version.version_number, "repointed": external_url is not None},
           principal)
    db.commit()
    return {"version_id": version.id, "is_primary": True, "external_url": external_url}


@router.get("/documents/search", operation_id="searchDocumentNames")
def search_documents(workspace_id: str,
                     q: str = Query(min_length=1, max_length=200),
                     principal: Principal = Depends(require(DOCUMENT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(Document).where(
        Document.workspace_id == workspace_id,
        func.lower(Document.title).contains(q.strip().lower()),
    ).order_by(Document.title)).scalars().all()
    return [{"id": d.id, "title": d.title, "doc_type": d.doc_type} for d in rows]


# ---------------------------------------------------------------------------
# Routes - reactions, feedback and annotations
# ---------------------------------------------------------------------------


@router.get("/documents/{document_id}/reactions", operation_id="listDocumentReactions")
def list_reactions(workspace_id: str, document_id: str,
                   principal: Principal = Depends(require(DOCUMENT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document(db, workspace_id, document_id)
    rows = db.execute(select(DocumentReaction).where(
        DocumentReaction.workspace_id == workspace_id,
        DocumentReaction.document_id == document_id,
    ).order_by(DocumentReaction.created_at)).scalars().all()
    return [{"id": r.id, "key": r.key, "page_number": r.page_number,
             "user_id": r.user_id} for r in rows]


@router.post("/documents/{document_id}/reactions", status_code=status.HTTP_201_CREATED,
             operation_id="addDocumentReaction")
def add_reaction(workspace_id: str, document_id: str, body: ReactionIn,
                 principal: Principal = Depends(require(DOCUMENT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    exists = db.execute(select(DocumentReaction.id).where(
        DocumentReaction.workspace_id == workspace_id,
        DocumentReaction.document_id == document.id,
        DocumentReaction.page_number == body.page_number,
        DocumentReaction.user_id == principal.user.id, DocumentReaction.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="reaction already exists")
    row = DocumentReaction(id=new_id(), workspace_id=workspace_id, document_id=document.id,
                           page_number=body.page_number, key=body.key,
                           user_id=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, REACTION_CHANGED, row.id, {"key": body.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "page_number": row.page_number}


@router.delete("/documents/{document_id}/reactions/{reaction_id}",
               operation_id="removeDocumentReaction")
def remove_reaction(workspace_id: str, document_id: str, reaction_id: str,
                    principal: Principal = Depends(require(DOCUMENT_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(DocumentReaction).where(
        DocumentReaction.id == reaction_id, DocumentReaction.workspace_id == workspace_id,
        DocumentReaction.document_id == document_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="reaction not found")
    db.delete(row)
    db.flush()
    _audit(db, workspace_id, REACTION_CHANGED, reaction_id, {"removed": True}, principal)
    db.commit()
    return {"id": reaction_id, "removed": True}


@router.get("/documents/{document_id}/feedback", operation_id="listDocumentFeedback")
def list_feedback(workspace_id: str, document_id: str,
                  principal: Principal = Depends(require(DOCUMENT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document(db, workspace_id, document_id)
    rows = db.execute(select(DocumentFeedback).where(
        DocumentFeedback.workspace_id == workspace_id,
        DocumentFeedback.document_id == document_id,
    ).order_by(DocumentFeedback.created_at)).scalars().all()
    return [{"id": f.id, "body": f.body, "rating": f.rating, "author": f.author,
             "status": f.status} for f in rows]


@router.post("/documents/{document_id}/feedback", status_code=status.HTTP_201_CREATED,
             operation_id="addDocumentFeedback")
def add_feedback(workspace_id: str, document_id: str, body: FeedbackIn,
                 principal: Principal = Depends(require(DOCUMENT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    row = DocumentFeedback(id=new_id(), workspace_id=workspace_id, document_id=document.id,
                           body=body.body, rating=body.rating, author=body.author,
                           status="open", created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, FEEDBACK_CHANGED, row.id, {"rating": body.rating}, principal)
    db.commit()
    return {"id": row.id, "status": row.status, "rating": row.rating}


@router.get("/documents/{document_id}/annotations", operation_id="listDocumentAnnotations")
def list_annotations(workspace_id: str, document_id: str,
                     principal: Principal = Depends(require(DOCUMENT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _document(db, workspace_id, document_id)
    rows = db.execute(select(DocumentAnnotation).where(
        DocumentAnnotation.workspace_id == workspace_id,
        DocumentAnnotation.document_id == document_id,
    ).order_by(DocumentAnnotation.page_number)).scalars().all()
    return [{"id": a.id, "page_number": a.page_number, "kind": a.kind,
             "content": a.content, "position": a.position} for a in rows]


@router.post("/documents/{document_id}/annotations", status_code=status.HTTP_201_CREATED,
             operation_id="addDocumentAnnotation")
def add_annotation(workspace_id: str, document_id: str, body: AnnotationIn,
                   principal: Principal = Depends(require(DOCUMENT_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    if body.version_id is not None:
        version = db.execute(select(DocumentVersion).where(
            DocumentVersion.id == body.version_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document.id,
        )).scalar_one_or_none()
        if version is None:
            raise HTTPException(status_code=404, detail="version not found")
    row = DocumentAnnotation(id=new_id(), workspace_id=workspace_id, document_id=document.id,
                             version_id=body.version_id, page_number=body.page_number,
                             kind=body.kind, content=body.content, position=body.position,
                             created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ANNOTATION_CHANGED, row.id,
           {"kind": body.kind, "page": body.page_number}, principal)
    db.commit()
    return {"id": row.id, "kind": row.kind, "page_number": row.page_number}


# ---------------------------------------------------------------------------
# Routes - internal visitors, engagement events, clicks and analytics
# ---------------------------------------------------------------------------


@router.get("/internal-visitors", operation_id="listInternalVisitors")
def list_internal_visitors(workspace_id: str,
                           principal: Principal = Depends(require(DOCUMENT_READ)),
                           db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(DocumentInternalVisitor).where(
        DocumentInternalVisitor.workspace_id == workspace_id
    ).order_by(DocumentInternalVisitor.value)).scalars().all()
    return [{"id": r.id, "match_type": r.match_type, "value": r.value} for r in rows]


@router.post("/internal-visitors", status_code=status.HTTP_201_CREATED,
             operation_id="addInternalVisitor")
def add_internal_visitor(workspace_id: str, body: InternalVisitorIn,
                         principal: Principal = Depends(require(DOCUMENT_WRITE)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(DocumentInternalVisitor.id).where(
        DocumentInternalVisitor.workspace_id == workspace_id,
        DocumentInternalVisitor.match_type == body.match_type,
        DocumentInternalVisitor.value == body.value,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="internal visitor already exists")
    row = DocumentInternalVisitor(id=new_id(), workspace_id=workspace_id,
                                  match_type=body.match_type, value=body.value, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, INTERNAL_VISITOR_CHANGED, row.id,
           {"match_type": body.match_type}, principal)
    db.commit()
    return {"id": row.id, "match_type": row.match_type, "value": row.value}


@router.delete("/internal-visitors/{visitor_id}", operation_id="removeInternalVisitor")
def remove_internal_visitor(workspace_id: str, visitor_id: str,
                            principal: Principal = Depends(require(DOCUMENT_WRITE)),
                            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, DocumentInternalVisitor, workspace_id, visitor_id, "internal visitor")
    db.delete(row)
    db.flush()
    _audit(db, workspace_id, INTERNAL_VISITOR_CHANGED, visitor_id, {"removed": True}, principal)
    db.commit()
    return {"id": visitor_id, "removed": True}


@router.post("/documents/{document_id}/events", status_code=status.HTTP_201_CREATED,
             operation_id="recordDocumentEngagement")
def record_event(workspace_id: str, document_id: str, body: EventIn,
                 principal: Principal = Depends(require(DOCUMENT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    row = _record_event(db, workspace_id, document, body, principal)
    db.commit()
    return {"id": row.id, "event_type": row.event_type, "is_internal": row.is_internal}


@router.post("/documents/{document_id}/click", status_code=status.HTTP_201_CREATED,
             operation_id="recordDocumentClick")
def record_click(workspace_id: str, document_id: str, body: ClickIn,
                 principal: Principal = Depends(require(DOCUMENT_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document(db, workspace_id, document_id)
    event = EventIn(event_type="click", visitor=body.visitor, target=body.target,
                    device=body.device, country=body.country, city=body.city)
    row = _record_event(db, workspace_id, document, event, principal)
    db.commit()
    return {"id": row.id, "event_type": "click", "target": row.target,
            "is_internal": row.is_internal}


@router.get("/documents/{document_id}/analytics", operation_id="documentEngagementAnalytics")
def analytics(workspace_id: str, document_id: str,
              principal: Principal = Depends(require(DOCUMENT_READ)),
              db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _document(db, workspace_id, document_id)
    rows = db.execute(select(DocumentEngagementEvent).where(
        DocumentEngagementEvent.workspace_id == workspace_id,
        DocumentEngagementEvent.document_id == document_id,
    )).scalars().all()
    external = [r for r in rows if not r.is_internal]
    excluded = len(rows) - len(external)
    views = [r for r in external if r.event_type == "view"]
    scrolls = [r for r in external if r.event_type == "scroll"]
    videos = [r for r in external if r.event_type == "video"]
    clicks = [r for r in external if r.event_type == "click"]

    def _count(field):
        counts: dict[str, int] = {}
        for r in external:
            key = getattr(r, field) or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return [{"value": k, "count": v} for k, v in sorted(counts.items())]

    locations: dict[tuple, int] = {}
    for r in external:
        key = (r.country, r.city)
        locations[key] = locations.get(key, 0) + 1

    return {
        "document_id": document_id,
        "views": len(views),
        "avg_scroll_depth": round(sum(r.scroll_depth for r in scrolls) / len(scrolls), 2) if scrolls else 0.0,
        "completion_rate": round(sum(1 for r in scrolls if r.completed) / len(scrolls), 4) if scrolls else 0.0,
        "video": {
            "views": len(videos),
            "avg_position_s": round(sum(r.video_position_s for r in videos) / len(videos), 2) if videos else 0.0,
        },
        "locations": [{"country": c, "city": ci, "count": n}
                      for (c, ci), n in sorted(locations.items())],
        "devices": _count("device"),
        "platforms": _count("platform"),
        "clicks": len(clicks),
        "excluded_internal": excluded,
        "external_geolocation": False,
    }