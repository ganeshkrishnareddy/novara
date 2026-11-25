"""Work-item collaboration and API governance (Plane P2 cluster).

Clean-room implementation of PL-031 attachments, PL-032 mentions, PL-039 team
collaboration, PL-048 cursor pagination, PL-050 field projection/expansion,
PL-051 local OpenAPI documentation, PL-130 work-item restrictions and PL-132
provider-neutral CSV import.

Every row is workspace-scoped and extends NOVARA's existing ProjectItem,
ProjectComment, ProjectMember and StoredFile records. There is no Plane source,
Django/Channels transport, React package, hosted endpoint, outbound HTTP or
external import provider. Cursor cursors are opaque server-side page records;
CSV import is explicitly provider-neutral.
"""

from __future__ import annotations

import csv
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import User, WorkspaceMember, new_id, now
from ..permissions import TASK_READ, TASK_WRITE
from ..security import hash_token
from .projects import Project, ProjectComment, ProjectItem, ProjectMember, ItemCreate, create_item
from .storage import StoredFile
from .work_item_planning import PlanningSubscriber

COLLAB_PREFIX = "/api/v1/workspaces/{workspace_id}/work-collab"

ATTACHMENT_ADDED = "collab.attachment_added"
MENTION_CREATED = "collab.mention_created"
TEAM_NOTE_CREATED = "collab.team_note_created"
RESTRICTION_CHANGED = "collab.restriction_changed"
CSV_IMPORTED = "collab.csv_imported"
register_event_types(ATTACHMENT_ADDED, MENTION_CREATED, TEAM_NOTE_CREATED,
                     RESTRICTION_CHANGED, CSV_IMPORTED)

router = APIRouter(prefix=COLLAB_PREFIX, tags=["work-collab"])

ALLOWED_FIELDS = frozenset({
    "id", "project_id", "title", "status", "priority", "description",
    "assignee_id", "created_at", "updated_at",
})
ALLOWED_EXPANSIONS = frozenset({"project", "assignee", "comments", "attachments"})
MENTION_SOURCES = frozenset({"comment", "description"})
ITEM_STATUSES = frozenset({"todo", "in_progress", "done"})
ITEM_PRIORITIES = frozenset({"low", "medium", "high", "urgent"})


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _audit(db: Session, workspace_id: str, event_type: str, entity_id: str,
           payload: dict, principal: Principal) -> None:
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _project(db: Session, workspace_id: str, project_id: str) -> Project:
    row = db.execute(select(Project).where(
        Project.id == project_id, Project.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return row


def _project_access(db: Session, workspace_id: str, project: Project,
                    principal: Principal) -> None:
    if not project.restricted or project.owner_id == principal.user.id:
        return
    member = db.execute(select(ProjectMember.id).where(
        ProjectMember.workspace_id == workspace_id,
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == principal.user.id,
    )).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="project not found")


def _item(db: Session, workspace_id: str, item_id: str) -> ProjectItem:
    row = db.execute(select(ProjectItem).where(
        ProjectItem.id == item_id, ProjectItem.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="work item not found")
    return row


def _active_member(db: Session, workspace_id: str, user_id: str) -> str | None:
    return db.execute(select(User.id).join(
        WorkspaceMember, WorkspaceMember.user_id == User.id
    ).where(User.id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active")).scalar_one_or_none()


def _restriction(db: Session, workspace_id: str, item_id: str) -> CollabItemRestriction | None:
    return db.execute(select(CollabItemRestriction).where(
        CollabItemRestriction.workspace_id == workspace_id,
        CollabItemRestriction.item_id == item_id,
    )).scalar_one_or_none()


def _ensure_allowed(db: Session, workspace_id: str, item: ProjectItem,
                    principal: Principal) -> None:
    restriction = _restriction(db, workspace_id, item.id)
    if restriction is None:
        return
    if principal.user.id not in (restriction.allowed_user_ids or []):
        raise HTTPException(status_code=404, detail="work item not found")


def _activity(db: Session, workspace_id: str, project_id: str, actor_id: str,
              kind: str, detail: dict, item_id: str | None = None) -> CollabActivity:
    row = CollabActivity(id=new_id(), workspace_id=workspace_id,
                         project_id=project_id, item_id=item_id,
                         actor_id=actor_id, kind=kind, detail=detail,
                         created_at=now())
    db.add(row)
    return row


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class CollabAttachment(Base):
    __tablename__ = "collab_attachments"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "file_id", name="uq_collab_attachment",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("stored_files.id"), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CollabMention(Base):
    __tablename__ = "collab_mentions"
    __table_args__ = (UniqueConstraint(
        "workspace_id", "item_id", "user_id", "source", name="uq_collab_mention",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    comment_id: Mapped[str | None] = mapped_column(ForeignKey("project_comments.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), default="comment", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CollabActivity(Base):
    __tablename__ = "collab_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("project_items.id"), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CollabCursorPage(Base):
    __tablename__ = "collab_cursor_pages"
    __table_args__ = (UniqueConstraint("workspace_id", "token_hash", name="uq_collab_cursor"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    per_page: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_value: Mapped[int] = mapped_column(Integer, nullable=False)
    filter_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CollabItemRestriction(Base):
    __tablename__ = "collab_item_restrictions"
    __table_args__ = (UniqueConstraint("workspace_id", "item_id", name="uq_collab_restriction"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), nullable=False, index=True)
    allowed_user_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AttachmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    label: str | None = Field(default=None, max_length=160)


class MentionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[str] = Field(min_length=1, max_length=50)
    body: str = Field(min_length=1, max_length=5000)
    comment_id: str | None = None
    source: str = "comment"

    @field_validator("user_ids")
    @classmethod
    def unique_users(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate mentioned user")
        return value

    @field_validator("source")
    @classmethod
    def valid_source(cls, value: str) -> str:
        if value not in MENTION_SOURCES:
            raise ValueError("unsupported mention source")
        return value


class TeamNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=10000)
    item_id: str | None = None


class RestrictionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_user_ids: list[str] = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=500)

    @field_validator("allowed_user_ids")
    @classmethod
    def unique_users(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate allowed user")
        return value


class CsvImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(min_length=1, max_length=200_000)


# ---------------------------------------------------------------------------
# PL-031 — work-item attachments referencing real stored bytes
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/attachments", status_code=status.HTTP_201_CREATED,
             operation_id="attachStoredFileToWorkItem")
def add_attachment(workspace_id: str, item_id: str, body: AttachmentIn,
                   principal: Principal = Depends(require(TASK_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    file_row = db.execute(select(StoredFile).where(
        StoredFile.id == body.file_id, StoredFile.workspace_id == workspace_id,
        StoredFile.deleted_at.is_(None),
    )).scalar_one_or_none()
    if file_row is None:
        raise HTTPException(status_code=404, detail="stored file not found")
    duplicate = db.execute(select(CollabAttachment.id).where(
        CollabAttachment.workspace_id == workspace_id,
        CollabAttachment.item_id == item.id,
        CollabAttachment.file_id == file_row.id,
    )).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="file already attached")
    row = CollabAttachment(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                           file_id=file_row.id, label=body.label,
                           created_by=principal.user.id, created_at=now())
    db.add(row)
    _activity(db, workspace_id, item.project_id, principal.user.id,
              "attachment_added", {"file_id": file_row.id, "label": body.label}, item.id)
    _audit(db, workspace_id, ATTACHMENT_ADDED, item.id,
           {"attachment_id": row.id, "file_id": file_row.id,
            "bytes": file_row.size_bytes}, principal)
    db.commit()
    return {"id": row.id, "item_id": item.id, "file_id": file_row.id,
            "file_name": file_row.original_name, "label": row.label,
            "size_bytes": file_row.size_bytes, "external_calls": False}


@router.get("/items/{item_id}/attachments", operation_id="listWorkItemAttachments")
def list_attachments(workspace_id: str, item_id: str,
                     principal: Principal = Depends(require(TASK_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    rows = db.execute(select(CollabAttachment, StoredFile).join(
        StoredFile, StoredFile.id == CollabAttachment.file_id
    ).where(CollabAttachment.workspace_id == workspace_id,
            CollabAttachment.item_id == item.id).order_by(CollabAttachment.created_at)).all()
    return {"item_id": item.id, "external_calls": False, "attachments": [
        {"id": attachment.id, "file_id": file_row.id,
         "file_name": file_row.original_name, "mime_type": file_row.mime_type,
         "size_bytes": file_row.size_bytes, "checksum_sha256": file_row.checksum_sha256,
         "label": attachment.label}
        for attachment, file_row in rows
    ]}


# ---------------------------------------------------------------------------
# PL-032 — mentions notify and subscribe workspace members locally
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/mentions", status_code=status.HTTP_201_CREATED,
             operation_id="createWorkItemMentions")
def create_mentions(workspace_id: str, item_id: str, body: MentionIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    if body.comment_id is not None:
        comment = db.execute(select(ProjectComment).where(
            ProjectComment.id == body.comment_id,
            ProjectComment.workspace_id == workspace_id,
            ProjectComment.item_id == item.id,
        )).scalar_one_or_none()
        if comment is None:
            raise HTTPException(status_code=404, detail="comment not found")
    recipients: list[str] = []
    mentions: list[dict] = []
    for user_id in body.user_ids:
        valid = _active_member(db, workspace_id, user_id)
        if valid is None:
            raise HTTPException(status_code=404, detail="workspace member not found")
        duplicate = db.execute(select(CollabMention.id).where(
            CollabMention.workspace_id == workspace_id,
            CollabMention.item_id == item.id,
            CollabMention.user_id == valid,
            CollabMention.source == body.source,
        )).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="mention already recorded")
        subscribed = db.execute(select(PlanningSubscriber.id).where(
            PlanningSubscriber.workspace_id == workspace_id,
            PlanningSubscriber.item_id == item.id,
            PlanningSubscriber.user_id == valid,
        )).scalar_one_or_none()
        if subscribed is None:
            db.add(PlanningSubscriber(id=new_id(), workspace_id=workspace_id,
                                      item_id=item.id, user_id=valid, created_at=now()))
            recipients.append(valid)
        row = CollabMention(id=new_id(), workspace_id=workspace_id, item_id=item.id,
                            comment_id=body.comment_id, user_id=valid,
                            source=body.source, body=body.body,
                            created_by=principal.user.id, created_at=now())
        db.add(row)
        mentions.append({"id": row.id, "user_id": valid, "source": row.source})
    _activity(db, workspace_id, item.project_id, principal.user.id,
              "mention_created", {"user_ids": body.user_ids, "comment_id": body.comment_id}, item.id)
    _audit(db, workspace_id, MENTION_CREATED, item.id,
           {"mentions": mentions, "new_subscribers": recipients,
            "notification_delivery": "local-event-only", "external_delivery": False}, principal)
    db.commit()
    return {"item_id": item.id, "mentions": mentions, "subscribed": recipients,
            "notified": True, "notification_delivery": "local-event-only",
            "external_delivery": False}


@router.get("/items/{item_id}/mentions", operation_id="listWorkItemMentions")
def list_mentions(workspace_id: str, item_id: str,
                  principal: Principal = Depends(require(TASK_READ)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    rows = db.execute(select(CollabMention).where(
        CollabMention.workspace_id == workspace_id,
        CollabMention.item_id == item.id,
    ).order_by(CollabMention.created_at)).scalars().all()
    return {"item_id": item.id, "mentions": [
        {"id": row.id, "user_id": row.user_id, "source": row.source,
         "comment_id": row.comment_id} for row in rows
    ]}


# ---------------------------------------------------------------------------
# PL-039 — team discussion and permission-aware activity
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/team-notes", status_code=status.HTTP_201_CREATED,
             operation_id="createTeamNote")
def create_team_note(workspace_id: str, project_id: str, body: TeamNoteIn,
                     principal: Principal = Depends(require(TASK_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project(db, workspace_id, project_id)
    _project_access(db, workspace_id, project, principal)
    item_id = None
    if body.item_id is not None:
        item = _item(db, workspace_id, body.item_id)
        if item.project_id != project.id:
            raise HTTPException(status_code=422, detail="item belongs to another project")
        item_id = item.id
    row = _activity(db, workspace_id, project.id, principal.user.id,
                    "team_note", {"body": body.body}, item_id)
    _audit(db, workspace_id, TEAM_NOTE_CREATED, project.id,
           {"activity_id": row.id, "item_id": item_id}, principal)
    db.commit()
    return {"id": row.id, "project_id": project.id, "item_id": item_id,
            "kind": row.kind, "body": body.body}


@router.get("/projects/{project_id}/collaboration", operation_id="getProjectCollaboration")
def project_collaboration(workspace_id: str, project_id: str,
                          principal: Principal = Depends(require(TASK_READ)),
                          db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project(db, workspace_id, project_id)
    _project_access(db, workspace_id, project, principal)
    comments = db.execute(select(ProjectComment).where(
        ProjectComment.workspace_id == workspace_id,
        ProjectComment.project_id == project.id,
    ).order_by(ProjectComment.created_at)).scalars().all()
    activities = db.execute(select(CollabActivity).where(
        CollabActivity.workspace_id == workspace_id,
        CollabActivity.project_id == project.id,
    ).order_by(CollabActivity.created_at)).scalars().all()
    members = db.execute(select(ProjectMember).where(
        ProjectMember.workspace_id == workspace_id,
        ProjectMember.project_id == project.id,
    ).order_by(ProjectMember.created_at)).scalars().all()
    return {
        "project_id": project.id,
        "comments": [{"id": c.id, "item_id": c.item_id, "author_id": c.author_id,
                      "body": c.body, "created_at": _iso(c.created_at)} for c in comments],
        "activity": [{"id": a.id, "item_id": a.item_id, "actor_id": a.actor_id,
                      "kind": a.kind, "detail": a.detail,
                      "created_at": _iso(a.created_at)} for a in activities],
        "members": [{"user_id": m.user_id, "role": m.role} for m in members],
        "source": "local-records-only", "external_calls": False,
    }


# ---------------------------------------------------------------------------
# PL-048 — opaque cursor pages over a stable workspace ordering
# ---------------------------------------------------------------------------


def _new_cursor(db: Session, workspace_id: str, project_id: str, per_page: int,
                offset: int, principal: Principal) -> str:
    raw = secrets.token_urlsafe(24)
    row = CollabCursorPage(id=new_id(), workspace_id=workspace_id,
                           token_hash=hash_token(raw), project_id=project_id,
                           per_page=per_page, offset_value=offset,
                           filter_json={"order": "created_at,id"},
                           created_by=principal.user.id, created_at=now())
    db.add(row)
    return raw


@router.get("/projects/{project_id}/items/cursor", operation_id="listWorkItemsByCursor")
def cursor_items(workspace_id: str, project_id: str,
                 per_page: int = Query(2, ge=1, le=100),
                 cursor: str | None = Query(None),
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project(db, workspace_id, project_id)
    _project_access(db, workspace_id, project, principal)
    if cursor is None:
        offset = 0
    else:
        page = db.execute(select(CollabCursorPage).where(
            CollabCursorPage.workspace_id == workspace_id,
            CollabCursorPage.token_hash == hash_token(cursor),
        )).scalar_one_or_none()
        if page is None or page.project_id != project.id or page.per_page != per_page:
            raise HTTPException(status_code=400, detail="invalid cursor")
        offset = page.offset_value
    rows = db.execute(select(ProjectItem).where(
        ProjectItem.workspace_id == workspace_id,
        ProjectItem.project_id == project.id,
    ).order_by(ProjectItem.created_at, ProjectItem.id).offset(offset).limit(per_page + 1)).scalars().all()
    has_more = len(rows) > per_page
    page_rows = rows[:per_page]
    next_cursor = (_new_cursor(db, workspace_id, project.id, per_page,
                               offset + per_page, principal) if has_more else None)
    prev_cursor = (_new_cursor(db, workspace_id, project.id, per_page,
                               max(0, offset - per_page), principal) if offset > 0 else None)
    db.commit()
    return {"project_id": project.id, "per_page": per_page, "offset": offset,
            "count": len(page_rows), "has_more": has_more,
            "next_cursor": next_cursor, "prev_cursor": prev_cursor,
            "rows": [{"id": row.id, "title": row.title, "status": row.status,
                      "project_id": row.project_id} for row in page_rows],
            "external_calls": False}


# ---------------------------------------------------------------------------
# PL-050 — allow-listed projection and expansion
# ---------------------------------------------------------------------------


@router.get("/items/{item_id}/shaped", operation_id="getShapedWorkItem")
def shaped_item(workspace_id: str, item_id: str,
                fields: str | None = Query(None),
                expand: str | None = Query(None),
                principal: Principal = Depends(require(TASK_READ)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    requested = [part.strip() for part in (fields or "").split(",") if part.strip()]
    if not requested:
        requested = sorted(ALLOWED_FIELDS)
    invalid_fields = sorted(set(requested) - ALLOWED_FIELDS)
    if invalid_fields:
        raise HTTPException(status_code=422, detail=f"unsupported fields: {invalid_fields}")
    expansions = [part.strip() for part in (expand or "").split(",") if part.strip()]
    invalid_expansions = sorted(set(expansions) - ALLOWED_EXPANSIONS)
    if invalid_expansions:
        raise HTTPException(status_code=422, detail=f"unsupported expansions: {invalid_expansions}")
    result: dict[str, Any] = {}
    for name in requested:
        value = getattr(item, name)
        result[name] = _iso(value) if isinstance(value, datetime) else value
    if "project" in expansions:
        project = _project(db, workspace_id, item.project_id)
        result["project"] = {"id": project.id, "name": project.name, "status": project.status}
    if "assignee" in expansions:
        assignee = (db.execute(select(User).where(
            User.id == item.assignee_id, User.id != ""
        )).scalar_one_or_none() if item.assignee_id else None)
        result["assignee"] = ({"id": assignee.id, "email": assignee.email}
                              if assignee is not None else None)
    if "comments" in expansions:
        comments = db.execute(select(ProjectComment).where(
            ProjectComment.workspace_id == workspace_id,
            ProjectComment.item_id == item.id,
        ).order_by(ProjectComment.created_at)).scalars().all()
        result["comments"] = [{"id": c.id, "body": c.body, "author_id": c.author_id}
                              for c in comments]
    if "attachments" in expansions:
        attachments = db.execute(select(CollabAttachment).where(
            CollabAttachment.workspace_id == workspace_id,
            CollabAttachment.item_id == item.id,
        )).scalars().all()
        result["attachments"] = [{"id": a.id, "file_id": a.file_id, "label": a.label}
                                 for a in attachments]
    return {"item": result, "fields": requested, "expansions": expansions,
            "external_calls": False}


# ---------------------------------------------------------------------------
# PL-130 — least-privilege item restriction
# ---------------------------------------------------------------------------


@router.put("/items/{item_id}/restriction", operation_id="setWorkItemRestriction")
def set_restriction(workspace_id: str, item_id: str, body: RestrictionIn,
                    principal: Principal = Depends(require(TASK_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    allowed: list[str] = []
    for user_id in body.allowed_user_ids:
        valid = _active_member(db, workspace_id, user_id)
        if valid is None:
            raise HTTPException(status_code=404, detail="workspace member not found")
        allowed.append(valid)
    row = _restriction(db, workspace_id, item.id)
    if row is None:
        row = CollabItemRestriction(id=new_id(), workspace_id=workspace_id,
                                    item_id=item.id, created_by=principal.user.id)
        db.add(row)
    row.allowed_user_ids = allowed
    row.reason = body.reason
    row.updated_at = now()
    _activity(db, workspace_id, item.project_id, principal.user.id,
              "restriction_changed", {"allowed_user_ids": allowed}, item.id)
    _audit(db, workspace_id, RESTRICTION_CHANGED, item.id,
           {"allowed_user_ids": allowed, "reason": body.reason}, principal)
    db.commit()
    return {"item_id": item.id, "allowed_user_ids": allowed,
            "reason": row.reason, "external_calls": False}


@router.get("/items/{item_id}/restriction", operation_id="getWorkItemRestriction")
def get_restriction(workspace_id: str, item_id: str,
                    principal: Principal = Depends(require(TASK_READ)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    row = _restriction(db, workspace_id, item.id)
    return {"item_id": item.id,
            "allowed_user_ids": list(row.allowed_user_ids) if row else [],
            "reason": row.reason if row else "", "restricted": row is not None}


@router.get("/items/{item_id}/guarded", operation_id="getGuardedWorkItem")
def guarded_item(workspace_id: str, item_id: str,
                 principal: Principal = Depends(require(TASK_READ)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    item = _item(db, workspace_id, item_id)
    _ensure_allowed(db, workspace_id, item, principal)
    return {"id": item.id, "project_id": item.project_id, "title": item.title,
            "status": item.status, "priority": item.priority,
            "guarded": True, "external_calls": False}


# ---------------------------------------------------------------------------
# PL-132 — provider-neutral CSV import
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/csv-import", status_code=status.HTTP_201_CREATED,
             operation_id="importWorkItemsFromCsv")
def import_csv(workspace_id: str, project_id: str, body: CsvImportIn,
               principal: Principal = Depends(require(TASK_WRITE)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    project = _project(db, workspace_id, project_id)
    _project_access(db, workspace_id, project, principal)
    reader = csv.DictReader(io.StringIO(body.csv_text))
    if reader.fieldnames is None or "title" not in reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV must contain a title column")
    prepared: list[ItemCreate] = []
    for index, raw in enumerate(reader, start=2):
        title = (raw.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail=f"row {index}: title is required")
        priority = (raw.get("priority") or "medium").strip()
        item_status = (raw.get("status") or "todo").strip()
        if priority not in ITEM_PRIORITIES:
            raise HTTPException(status_code=422, detail=f"row {index}: invalid priority")
        if item_status not in ITEM_STATUSES:
            raise HTTPException(status_code=422, detail=f"row {index}: invalid status")
        prepared.append(ItemCreate(
            title=title, priority=priority, status=item_status,
            description=(raw.get("description") or "").strip() or None,
            tags=[tag.strip() for tag in (raw.get("tags") or "").split("|") if tag.strip()],
        ))
    if not prepared:
        raise HTTPException(status_code=422, detail="CSV contains no data rows")
    created: list[dict[str, str]] = []
    for payload in prepared:
        item = create_item(workspace_id, project_id, payload, principal, db)
        created.append({"id": item.id, "title": item.title})
    _activity(db, workspace_id, project.id, principal.user.id,
              "csv_imported", {"count": len(created), "provider": "provider-neutral"})
    _audit(db, workspace_id, CSV_IMPORTED, project.id,
           {"count": len(created), "provider": "provider-neutral",
            "external_calls": False}, principal)
    db.commit()
    return {"project_id": project.id, "source": "provider-neutral-csv",
            "count": len(created), "created": created, "external_calls": False}


# ---------------------------------------------------------------------------
# PL-051 — generated local contract and documentation inventory
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="workCollabApiContract")
def api_contract(request: Request) -> dict:
    schema = request.app.openapi()
    routes: list[dict[str, Any]] = []
    for path, operations in sorted(schema.get("paths", {}).items()):
        if not path.startswith(COLLAB_PREFIX):
            continue
        methods = sorted(method.upper() for method in operations
                         if method.lower() in ("get", "post", "put", "patch", "delete"))
        routes.append({
            "path": path,
            "methods": methods,
            "operation_ids": [operations[m.lower()].get("operationId")
                              for m in methods if operations.get(m.lower())],
        })
    return {
        "openapi": schema.get("openapi", "3.1.0"),
        "generated_from": "live FastAPI application",
        "work_collab_routes": routes,
        "route_count": len(routes),
        "documentation_routes": ["/openapi.json", "/docs", "/redoc"],
        "delivery": "local-only",
        "external_calls": False,
        "external_delivery": False,
    }
