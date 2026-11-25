"""Documents and data rooms module.

STORES METADATA ONLY. ``storage_path`` is an opaque reference supplied by the
caller; this module never opens, reads, writes or uploads a file, and never
pretends that a file exists. All queries are scoped to the verified workspace.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import DOCUMENT_ADMIN, DOCUMENT_READ, DOCUMENT_WRITE

DATAROOM_CREATED = "dataroom.created"
DATAROOM_UPDATED = "dataroom.updated"
DATAROOM_DELETED = "dataroom.deleted"
DOCUMENT_CREATED = "document.created"
DOCUMENT_DELETED = "document.deleted"
# PM-073: engagement events are shared through the same append-only bus, so a
# document view can notify a salesperson and appear on the customer timeline.
DOCUMENT_VIEWED = "document.viewed"
DOCUMENT_DOWNLOADED = "document.downloaded"
# P1 document-library surface: versions, pages, folders, collections, room
# membership and per-workspace preferences. All are local, audited records.
DOCUMENT_UPDATED = "document.updated"
DOCUMENT_VERSION_CREATED = "document.version_created"
DOCUMENT_PAGE_CREATED = "document.page_created"
DOCUMENT_FOLDER_CREATED = "document.folder_created"
DOCUMENT_FOLDER_UPDATED = "document.folder_updated"
DOCUMENT_FOLDER_DELETED = "document.folder_deleted"
DOCUMENT_COLLECTION_CREATED = "document.collection_created"
DOCUMENT_COLLECTION_MEMBER_ADDED = "document.collection_member_added"
DOCUMENT_COLLECTION_MEMBER_REMOVED = "document.collection_member_removed"
DOCUMENT_ROOM_ATTACHED = "document.room_attached"
DOCUMENT_ROOM_DETACHED = "document.room_detached"
DOCUMENT_PREFERENCES_UPDATED = "document.preferences_updated"
ROOM_MEMBER_SETTINGS_UPDATED = "document.room_member_settings_updated"
register_event_types(
    DATAROOM_CREATED,
    DATAROOM_UPDATED,
    DATAROOM_DELETED,
    DOCUMENT_CREATED,
    DOCUMENT_UPDATED,
    DOCUMENT_DELETED,
    DOCUMENT_VIEWED,
    DOCUMENT_DOWNLOADED,
    DOCUMENT_VERSION_CREATED,
    DOCUMENT_PAGE_CREATED,
    DOCUMENT_FOLDER_CREATED,
    DOCUMENT_FOLDER_UPDATED,
    DOCUMENT_FOLDER_DELETED,
    DOCUMENT_COLLECTION_CREATED,
    DOCUMENT_COLLECTION_MEMBER_ADDED,
    DOCUMENT_COLLECTION_MEMBER_REMOVED,
    DOCUMENT_ROOM_ATTACHED,
    DOCUMENT_ROOM_DETACHED,
    DOCUMENT_PREFERENCES_UPDATED,
    ROOM_MEMBER_SETTINGS_UPDATED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/documents",
    tags=["documents"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class DataRoom(Base):
    __tablename__ = "data_rooms"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_dataroom_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str | None] = mapped_column(
        ForeignKey("data_rooms.id"), index=True
    )
    # PM-019/PM-022: a document may sit in a library folder as well as being
    # attached to zero or more rooms through DocumentRoomMembership.
    folder_id: Mapped[str | None] = mapped_column(
        ForeignKey("library_folders.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), default="other", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentVersion(Base):
    """PM-009/PM-041: an immutable file reference for one document revision.

    Exactly one version is primary. A new version demotes the previous primary
    in the same transaction, and links resolve the primary version rather than
    remembering bytes, so replacing a file never invalidates an existing link.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "document_id", "version_number",
                         name="uq_document_version_number"),
        # SQLite enforces one primary per document; application code enforces
        # the same invariant on other backends by demoting before promoting.
        Index("uq_document_version_primary", "document_id", unique=True,
              sqlite_where=text("is_primary = 1")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentPage(Base):
    """PM-011: a rendered page has a stable id and belongs to one version."""

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version_id", "page_number",
                         name="uq_document_page_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    text_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LibraryFolder(Base):
    """PM-019: a team-library folder with a server-derived, unique path."""

    __tablename__ = "library_folders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "path_key", name="uq_library_folder_path"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("library_folders.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    path_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentRoomMembership(Base):
    """PM-055: attaching a library document to a room never copies the row."""

    __tablename__ = "document_room_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "document_id", "room_id",
                         name="uq_document_room_membership"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentCollection(Base):
    """PM-022: one clean-room grouping model for library and room contexts."""

    __tablename__ = "document_collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), nullable=False)
    # "library" (room_id null) or "room" (room_id required).
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("data_rooms.id"), index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CollectionDocument(Base):
    __tablename__ = "collection_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "collection_id", "document_id",
                         name="uq_collection_document"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("document_collections.id"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    added_by: Mapped[str] = mapped_column(String(36), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentPreference(Base):
    """PM-121: per-user document settings, always scoped to one workspace."""

    __tablename__ = "document_preferences"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_document_preference"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    default_view_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_link_expiry_hours: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoomMemberSetting(Base):
    """PM-121: per-room settings for a named workspace member."""

    __tablename__ = "room_member_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "room_id", "user_id",
                         name="uq_room_member_setting"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_download: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class RoomCreate(BaseModel):
    name: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("data room name must not be empty")
        return stripped


class RoomPatch(BaseModel):
    name: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("data room name must not be empty")
        return stripped


class DocumentCreate(BaseModel):
    title: str
    doc_type: str = "other"
    size_bytes: int = Field(default=0, ge=0)
    storage_path: str
    room_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "doc_type", "storage_path")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class RoomOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: str
    room_id: str | None
    folder_id: str | None = None
    title: str
    doc_type: str
    size_bytes: int
    storage_path: str
    uploaded_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class VersionCreate(BaseModel):
    storage_path: str
    size_bytes: int = Field(default=0, ge=0)
    checksum_sha256: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("storage_path")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("storage_path must not be empty")
        return value.strip()

    @field_validator("checksum_sha256")
    @classmethod
    def checksum_format(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value)):
            raise ValueError("checksum must be a 64-character hex digest")
        return value


class VersionOut(BaseModel):
    id: str
    document_id: str
    version_number: int
    storage_path: str
    size_bytes: int
    checksum_sha256: str | None
    is_primary: bool
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class PageCreate(BaseModel):
    page_number: int = Field(ge=1)
    label: str | None = None
    text_excerpt: str | None = None

    model_config = ConfigDict(extra="forbid")


class PageOut(BaseModel):
    id: str
    version_id: str
    page_number: int
    label: str | None
    text_excerpt: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or "/" in stripped or "\\" in stripped:
            raise ValueError("folder name must be non-empty and contain no separators")
        return stripped


class FolderPatch(BaseModel):
    name: str | None = None
    parent_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or "/" in stripped or "\\" in stripped:
            raise ValueError("folder name must be non-empty and contain no separators")
        return stripped


class FolderOut(BaseModel):
    id: str
    parent_id: str | None
    name: str
    path: str
    created_by: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class FolderPlacement(BaseModel):
    folder_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class CollectionCreate(BaseModel):
    name: str
    scope: str = "library"
    room_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("collection name must not be empty")
        return stripped

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str) -> str:
        if value not in ("library", "room"):
            raise ValueError("scope must be library or room")
        return value


class CollectionOut(BaseModel):
    id: str
    name: str
    scope: str
    room_id: str | None
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class CollectionMember(BaseModel):
    document_id: str

    model_config = ConfigDict(extra="forbid")


class PreferencePatch(BaseModel):
    default_view_only: bool | None = None
    default_link_expiry_hours: int | None = Field(default=None, ge=1, le=8760)

    model_config = ConfigDict(extra="forbid")


class PreferenceOut(BaseModel):
    workspace_id: str
    user_id: str
    default_view_only: bool
    default_link_expiry_hours: int | None
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class RoomMemberSettingPatch(BaseModel):
    can_manage: bool | None = None
    can_download: bool | None = None

    model_config = ConfigDict(extra="forbid")


class RoomMemberSettingOut(BaseModel):
    room_id: str
    user_id: str
    can_manage: bool
    can_download: bool
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _room_or_404(db: Session, workspace_id: str, room_id: str) -> DataRoom:
    room = db.execute(
        select(DataRoom).where(DataRoom.id == room_id, DataRoom.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="data room not found")
    return room


def _document_or_404(db: Session, workspace_id: str, document_id: str) -> Document:
    document = db.execute(
        select(Document).where(
            Document.id == document_id, Document.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def _room_name_taken(
    db: Session, workspace_id: str, name: str, exclude_room_id: str | None = None
) -> bool:
    query = select(DataRoom.id).where(
        DataRoom.workspace_id == workspace_id, DataRoom.name == name
    )
    if exclude_room_id is not None:
        query = query.where(DataRoom.id != exclude_room_id)
    return db.execute(query).scalar_one_or_none() is not None


def primary_version(
    db: Session, workspace_id: str, document_id: str
) -> DocumentVersion | None:
    """The single primary revision served by share links (PM-009/PM-041)."""
    return db.execute(
        select(DocumentVersion).where(
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_primary.is_(True),
        )
    ).scalar_one_or_none()


def _version_or_404(
    db: Session, workspace_id: str, document_id: str, version_id: str
) -> DocumentVersion:
    version = db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="document version not found")
    return version


def _folder_or_404(db: Session, workspace_id: str, folder_id: str) -> LibraryFolder:
    folder = db.execute(
        select(LibraryFolder).where(
            LibraryFolder.id == folder_id, LibraryFolder.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    return folder


def _folder_path(
    db: Session, workspace_id: str, parent_id: str | None, name: str
) -> tuple[str, str]:
    if parent_id:
        parent = _folder_or_404(db, workspace_id, parent_id)
        path = f"{parent.path}/{name}"
    else:
        path = f"/{name}"
    return path, path.casefold()


def _folder_path_taken(
    db: Session, workspace_id: str, path_key: str, exclude_id: str | None = None
) -> bool:
    query = select(LibraryFolder.id).where(
        LibraryFolder.workspace_id == workspace_id, LibraryFolder.path_key == path_key
    )
    if exclude_id:
        query = query.where(LibraryFolder.id != exclude_id)
    return db.execute(query).scalar_one_or_none() is not None


def _rename_folder_descendants(
    db: Session, workspace_id: str, folder: LibraryFolder, new_path: str
) -> None:
    """Keep derived paths consistent after a move or rename."""
    children = db.execute(
        select(LibraryFolder).where(
            LibraryFolder.workspace_id == workspace_id,
            LibraryFolder.parent_id == folder.id,
        )
    ).scalars().all()
    for child in children:
        child_path = f"{new_path}/{child.name}"
        child.path = child_path
        child.path_key = child_path.casefold()
        _rename_folder_descendants(db, workspace_id, child, child_path)


def _collection_or_404(
    db: Session, workspace_id: str, collection_id: str
) -> DocumentCollection:
    collection = db.execute(
        select(DocumentCollection).where(
            DocumentCollection.id == collection_id,
            DocumentCollection.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="collection not found")
    return collection


def _collection_name_taken(
    db: Session, workspace_id: str, name_key: str, scope: str, room_id: str | None
) -> bool:
    query = select(DocumentCollection.id).where(
        DocumentCollection.workspace_id == workspace_id,
        DocumentCollection.name_key == name_key,
        DocumentCollection.scope == scope,
    )
    if room_id:
        query = query.where(DocumentCollection.room_id == room_id)
    else:
        query = query.where(DocumentCollection.room_id.is_(None))
    return db.execute(query).scalar_one_or_none() is not None


def _preference_or_create(
    db: Session, workspace_id: str, user_id: str
) -> DocumentPreference:
    pref = db.execute(
        select(DocumentPreference).where(
            DocumentPreference.workspace_id == workspace_id,
            DocumentPreference.user_id == user_id,
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = DocumentPreference(
            id=new_id(),
            workspace_id=workspace_id,
            user_id=user_id,
            default_view_only=True,
            default_link_expiry_hours=None,
            updated_at=now(),
        )
        db.add(pref)
        db.flush()
    return pref


def _active_member_or_404(
    db: Session, workspace_id: str, user_id: str
) -> WorkspaceMember:
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="workspace member not found")
    return member


# --------------------------------------------------------------------------
# Data room endpoints
# --------------------------------------------------------------------------


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DataRoom]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(DataRoom)
        .where(DataRoom.workspace_id == workspace_id)
        .order_by(DataRoom.created_at.desc())
    ).scalars().all()


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    workspace_id: str,
    body: RoomCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DataRoom:
    verify_workspace(principal, workspace_id)
    name = body.name.strip()
    if _room_name_taken(db, workspace_id, name):
        raise HTTPException(status_code=409, detail="a data room with this name already exists")
    room = DataRoom(
        id=new_id(),
        workspace_id=workspace_id,
        name=name,
        description=body.description,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(room)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DATAROOM_CREATED,
        entity_id=room.id,
        payload={"name": room.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return room


@router.get("/rooms/{room_id}", response_model=RoomOut)
def get_room(
    workspace_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> DataRoom:
    verify_workspace(principal, workspace_id)
    return _room_or_404(db, workspace_id, room_id)


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def patch_room(
    workspace_id: str,
    room_id: str,
    body: RoomPatch,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DataRoom:
    verify_workspace(principal, workspace_id)
    room = _room_or_404(db, workspace_id, room_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        name = updates["name"]
        if name is None or not name.strip():
            raise HTTPException(status_code=422, detail="data room name must not be empty")
        name = name.strip()
        if _room_name_taken(db, workspace_id, name, exclude_room_id=room.id):
            raise HTTPException(status_code=409, detail="a data room with this name already exists")
        updates["name"] = name
    for key, value in updates.items():
        setattr(room, key, value)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DATAROOM_UPDATED,
        entity_id=room.id,
        payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_200_OK)
def delete_room(
    workspace_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    room = _room_or_404(db, workspace_id, room_id)
    dependent = db.execute(
        select(func.count()).select_from(Document).where(
            Document.workspace_id == workspace_id, Document.room_id == room.id
        )
    ).scalar()
    if dependent:
        raise HTTPException(
            status_code=409,
            detail="remove or move the room's documents before deleting it",
        )
    db.delete(room)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DATAROOM_DELETED,
        entity_id=room.id,
        payload={"name": room.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "room_id": room.id}


# --------------------------------------------------------------------------
# Document metadata endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[DocumentOut])
def list_documents(
    workspace_id: str,
    room_id: str | None = Query(None),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[Document]:
    verify_workspace(principal, workspace_id)
    query = select(Document).where(Document.workspace_id == workspace_id)
    if room_id:
        _room_or_404(db, workspace_id, room_id)
        query = query.where(Document.room_id == room_id)
    return db.execute(query.order_by(Document.created_at.desc())).scalars().all()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    workspace_id: str,
    body: DocumentCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> Document:
    verify_workspace(principal, workspace_id)
    if body.room_id:
        _room_or_404(db, workspace_id, body.room_id)
    document = Document(
        id=new_id(),
        workspace_id=workspace_id,
        room_id=body.room_id,
        title=body.title.strip(),
        doc_type=body.doc_type.strip(),
        size_bytes=body.size_bytes,
        storage_path=body.storage_path.strip(),
        uploaded_by=principal.user.id,
        created_at=now(),
    )
    db.add(document)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_CREATED,
        entity_id=document.id,
        payload={
            "room_id": document.room_id,
            "title": document.title,
            "doc_type": document.doc_type,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return document


# --------------------------------------------------------------------------
# PM-009/PM-041 — document versions and primary-version invariant
# --------------------------------------------------------------------------


@router.get("/{document_id}/versions", response_model=list[VersionOut])
def list_versions(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DocumentVersion]:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    return db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
        )
        .order_by(DocumentVersion.version_number)
    ).scalars().all()


@router.post("/{document_id}/versions", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
def create_version(
    workspace_id: str,
    document_id: str,
    body: VersionCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DocumentVersion:
    verify_workspace(principal, workspace_id)
    document = _document_or_404(db, workspace_id, document_id)
    previous = db.execute(
        select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
        )
    ).scalar()
    version = DocumentVersion(
        id=new_id(),
        workspace_id=workspace_id,
        document_id=document_id,
        version_number=int(previous) + 1,
        storage_path=body.storage_path,
        size_bytes=body.size_bytes,
        checksum_sha256=body.checksum_sha256,
        is_primary=True,
        created_by=principal.user.id,
        created_at=now(),
    )
    # Atomic demotion: the new primary is only visible once the previous one
    # has been demoted in the same transaction, so links never see two primaries.
    db.query(DocumentVersion).where(
        DocumentVersion.workspace_id == workspace_id,
        DocumentVersion.document_id == document_id,
        DocumentVersion.is_primary.is_(True),
    ).update({DocumentVersion.is_primary: False}, synchronize_session=False)
    db.add(version)
    db.flush()
    document.storage_path = version.storage_path
    document.size_bytes = version.size_bytes
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_VERSION_CREATED,
        entity_id=version.id,
        payload={
            "document_id": document_id,
            "version_number": version.version_number,
            "demoted_versions": int(previous or 0),
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return version


# --------------------------------------------------------------------------
# PM-011 — immutable document pages
# --------------------------------------------------------------------------


@router.get("/{document_id}/versions/{version_id}/pages", response_model=list[PageOut])
def list_pages(
    workspace_id: str,
    document_id: str,
    version_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DocumentPage]:
    verify_workspace(principal, workspace_id)
    version = _version_or_404(db, workspace_id, document_id, version_id)
    return db.execute(
        select(DocumentPage)
        .where(
            DocumentPage.workspace_id == workspace_id,
            DocumentPage.version_id == version.id,
        )
        .order_by(DocumentPage.page_number)
    ).scalars().all()


@router.post("/{document_id}/versions/{version_id}/pages", response_model=PageOut,
             status_code=status.HTTP_201_CREATED)
def create_page(
    workspace_id: str,
    document_id: str,
    version_id: str,
    body: PageCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DocumentPage:
    verify_workspace(principal, workspace_id)
    version = _version_or_404(db, workspace_id, document_id, version_id)
    exists = db.execute(
        select(DocumentPage.id).where(
            DocumentPage.workspace_id == workspace_id,
            DocumentPage.version_id == version.id,
            DocumentPage.page_number == body.page_number,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="page number already exists for this version")
    page = DocumentPage(
        id=new_id(),
        workspace_id=workspace_id,
        version_id=version.id,
        page_number=body.page_number,
        label=body.label,
        text_excerpt=body.text_excerpt,
        created_at=now(),
    )
    db.add(page)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PAGE_CREATED,
        entity_id=page.id,
        payload={
            "document_id": document_id,
            "version_id": version.id,
            "page_number": page.page_number,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return page


# --------------------------------------------------------------------------
# PM-019 — team library folders with server-derived paths
# --------------------------------------------------------------------------


@router.get("/folders", response_model=list[FolderOut])
def list_folders(
    workspace_id: str,
    parent_id: str | None = Query(None),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[LibraryFolder]:
    verify_workspace(principal, workspace_id)
    query = select(LibraryFolder).where(LibraryFolder.workspace_id == workspace_id)
    if parent_id:
        _folder_or_404(db, workspace_id, parent_id)
        query = query.where(LibraryFolder.parent_id == parent_id)
    return db.execute(query.order_by(LibraryFolder.path)).scalars().all()


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    workspace_id: str,
    body: FolderCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> LibraryFolder:
    verify_workspace(principal, workspace_id)
    path, path_key = _folder_path(db, workspace_id, body.parent_id, body.name)
    if _folder_path_taken(db, workspace_id, path_key):
        raise HTTPException(status_code=409, detail="a folder with this path already exists")
    folder = LibraryFolder(
        id=new_id(),
        workspace_id=workspace_id,
        parent_id=body.parent_id,
        name=body.name,
        path=path,
        path_key=path_key,
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(folder)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_FOLDER_CREATED,
        entity_id=folder.id,
        payload={"name": folder.name, "path": folder.path},
        actor_id=principal.user.id,
    )
    db.commit()
    return folder


@router.get("/folders/{folder_id}", response_model=FolderOut)
def get_folder(
    workspace_id: str,
    folder_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> LibraryFolder:
    verify_workspace(principal, workspace_id)
    return _folder_or_404(db, workspace_id, folder_id)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def patch_folder(
    workspace_id: str,
    folder_id: str,
    body: FolderPatch,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> LibraryFolder:
    verify_workspace(principal, workspace_id)
    folder = _folder_or_404(db, workspace_id, folder_id)
    name = body.name if body.name is not None else folder.name
    parent_id = folder.parent_id if body.parent_id is None else body.parent_id
    if body.parent_id is None and "parent_id" in body.model_fields_set:
        parent_id = None
    if parent_id == folder.id:
        raise HTTPException(status_code=422, detail="a folder cannot be its own parent")
    path, path_key = _folder_path(db, workspace_id, parent_id, name)
    if _folder_path_taken(db, workspace_id, path_key, exclude_id=folder.id):
        raise HTTPException(status_code=409, detail="a folder with this path already exists")
    folder.name = name
    folder.parent_id = parent_id
    folder.path = path
    folder.path_key = path_key
    folder.updated_at = now()
    _rename_folder_descendants(db, workspace_id, folder, path)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_FOLDER_UPDATED,
        entity_id=folder.id,
        payload={"fields": sorted(body.model_fields_set), "path": path},
        actor_id=principal.user.id,
    )
    db.commit()
    return folder


@router.delete("/folders/{folder_id}", status_code=status.HTTP_200_OK)
def delete_folder(
    workspace_id: str,
    folder_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    folder = _folder_or_404(db, workspace_id, folder_id)
    child = db.execute(
        select(LibraryFolder.id).where(
            LibraryFolder.workspace_id == workspace_id, LibraryFolder.parent_id == folder.id
        )
    ).scalar_one_or_none()
    documents_in_folder = db.execute(
        select(Document.id).where(
            Document.workspace_id == workspace_id, Document.folder_id == folder.id
        )
    ).scalar_one_or_none()
    if child is not None or documents_in_folder is not None:
        raise HTTPException(
            status_code=409,
            detail="move or remove child folders and documents before deleting",
        )
    path = folder.path
    db.delete(folder)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_FOLDER_DELETED,
        entity_id=folder.id,
        payload={"path": path},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "folder_id": folder.id}


@router.post("/{document_id}/folder", response_model=DocumentOut)
def place_document_in_folder(
    workspace_id: str,
    document_id: str,
    body: FolderPlacement,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> Document:
    verify_workspace(principal, workspace_id)
    document = _document_or_404(db, workspace_id, document_id)
    if body.folder_id:
        _folder_or_404(db, workspace_id, body.folder_id)
    document.folder_id = body.folder_id
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_UPDATED,
        entity_id=document.id,
        payload={"folder_id": document.folder_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return document


# --------------------------------------------------------------------------
# PM-022 — collections shared by library and rooms
# --------------------------------------------------------------------------


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(
    workspace_id: str,
    scope: str | None = Query(None),
    room_id: str | None = Query(None),
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DocumentCollection]:
    verify_workspace(principal, workspace_id)
    query = select(DocumentCollection).where(
        DocumentCollection.workspace_id == workspace_id
    )
    if scope:
        if scope not in ("library", "room"):
            raise HTTPException(status_code=422, detail="scope must be library or room")
        query = query.where(DocumentCollection.scope == scope)
    if room_id:
        _room_or_404(db, workspace_id, room_id)
        query = query.where(DocumentCollection.room_id == room_id)
    return db.execute(query.order_by(DocumentCollection.created_at.desc())).scalars().all()


@router.post("/collections", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    workspace_id: str,
    body: CollectionCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DocumentCollection:
    verify_workspace(principal, workspace_id)
    if body.scope == "room":
        if not body.room_id:
            raise HTTPException(status_code=422, detail="room_id is required for room collections")
        _room_or_404(db, workspace_id, body.room_id)
    elif body.room_id:
        raise HTTPException(status_code=422, detail="library collections cannot have a room_id")
    name = body.name.strip()
    if _collection_name_taken(db, workspace_id, name.casefold(), body.scope, body.room_id):
        raise HTTPException(status_code=409, detail="collection name already exists in this scope")
    collection = DocumentCollection(
        id=new_id(),
        workspace_id=workspace_id,
        name=name,
        name_key=name.casefold(),
        scope=body.scope,
        room_id=body.room_id,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(collection)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_COLLECTION_CREATED,
        entity_id=collection.id,
        payload={"name": collection.name, "scope": collection.scope, "room_id": collection.room_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return collection


@router.get("/collections/{collection_id}", response_model=CollectionOut)
def get_collection(
    workspace_id: str,
    collection_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> DocumentCollection:
    verify_workspace(principal, workspace_id)
    return _collection_or_404(db, workspace_id, collection_id)


@router.get("/collections/{collection_id}/documents", response_model=list[DocumentOut])
def list_collection_documents(
    workspace_id: str,
    collection_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[Document]:
    verify_workspace(principal, workspace_id)
    collection = _collection_or_404(db, workspace_id, collection_id)
    return db.execute(
        select(Document)
        .join(CollectionDocument, CollectionDocument.document_id == Document.id)
        .where(
            CollectionDocument.workspace_id == workspace_id,
            CollectionDocument.collection_id == collection.id,
            Document.workspace_id == workspace_id,
        )
        .order_by(Document.created_at.desc())
    ).scalars().all()


@router.post("/collections/{collection_id}/documents", status_code=status.HTTP_201_CREATED)
def add_collection_document(
    workspace_id: str,
    collection_id: str,
    body: CollectionMember,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    collection = _collection_or_404(db, workspace_id, collection_id)
    _document_or_404(db, workspace_id, body.document_id)
    member = db.execute(
        select(CollectionDocument).where(
            CollectionDocument.workspace_id == workspace_id,
            CollectionDocument.collection_id == collection.id,
            CollectionDocument.document_id == body.document_id,
        )
    ).scalar_one_or_none()
    if member is None:
        member = CollectionDocument(
            id=new_id(),
            workspace_id=workspace_id,
            collection_id=collection.id,
            document_id=body.document_id,
            added_by=principal.user.id,
            added_at=now(),
        )
        db.add(member)
        db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_COLLECTION_MEMBER_ADDED,
        entity_id=collection.id,
        payload={"document_id": body.document_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"collection_id": collection.id, "document_id": body.document_id}


@router.delete("/collections/{collection_id}/documents/{document_id}", status_code=status.HTTP_200_OK)
def remove_collection_document(
    workspace_id: str,
    collection_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    collection = _collection_or_404(db, workspace_id, collection_id)
    member = db.execute(
        select(CollectionDocument).where(
            CollectionDocument.workspace_id == workspace_id,
            CollectionDocument.collection_id == collection.id,
            CollectionDocument.document_id == document_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="document is not in this collection")
    db.delete(member)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_COLLECTION_MEMBER_REMOVED,
        entity_id=collection.id,
        payload={"document_id": document_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"removed": True, "collection_id": collection.id, "document_id": document_id}


# --------------------------------------------------------------------------
# PM-055 — attach/detach room documents without duplicating the library record
# --------------------------------------------------------------------------


@router.get("/{document_id}/rooms", response_model=list[str])
def list_document_rooms(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[str]:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    rows = db.execute(
        select(DocumentRoomMembership.room_id)
        .where(
            DocumentRoomMembership.workspace_id == workspace_id,
            DocumentRoomMembership.document_id == document_id,
        )
        .order_by(DocumentRoomMembership.created_at)
    ).scalars().all()
    return list(rows)


@router.post("/{document_id}/rooms/{room_id}", status_code=status.HTTP_201_CREATED)
def attach_document_to_room(
    workspace_id: str,
    document_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    _room_or_404(db, workspace_id, room_id)
    membership = db.execute(
        select(DocumentRoomMembership).where(
            DocumentRoomMembership.workspace_id == workspace_id,
            DocumentRoomMembership.document_id == document_id,
            DocumentRoomMembership.room_id == room_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(DocumentRoomMembership(
            id=new_id(), workspace_id=workspace_id, document_id=document_id,
            room_id=room_id, created_by=principal.user.id, created_at=now(),
        ))
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_ROOM_ATTACHED,
        entity_id=document_id,
        payload={"room_id": room_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"attached": True, "document_id": document_id, "room_id": room_id}


@router.delete("/{document_id}/rooms/{room_id}", status_code=status.HTTP_200_OK)
def detach_document_from_room(
    workspace_id: str,
    document_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    room = _room_or_404(db, workspace_id, room_id)
    membership = db.execute(
        select(DocumentRoomMembership).where(
            DocumentRoomMembership.workspace_id == workspace_id,
            DocumentRoomMembership.document_id == document_id,
            DocumentRoomMembership.room_id == room.id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="document is not attached to this room")
    db.delete(membership)
    document = _document_or_404(db, workspace_id, document_id)
    if document.room_id == room.id:
        document.room_id = None
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_ROOM_DETACHED,
        entity_id=document_id,
        payload={"room_id": room_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"detached": True, "document_id": document_id, "room_id": room_id}


# --------------------------------------------------------------------------
# PM-121 — document preferences and room member settings
# --------------------------------------------------------------------------


@router.get("/preferences", response_model=PreferenceOut)
def get_preferences(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> DocumentPreference:
    verify_workspace(principal, workspace_id)
    return _preference_or_create(db, workspace_id, principal.user.id)


@router.patch("/preferences", response_model=PreferenceOut)
def patch_preferences(
    workspace_id: str,
    body: PreferencePatch,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> DocumentPreference:
    verify_workspace(principal, workspace_id)
    pref = _preference_or_create(db, workspace_id, principal.user.id)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(pref, key, value)
    pref.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_PREFERENCES_UPDATED,
        entity_id=pref.id,
        payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return pref


@router.get("/rooms/{room_id}/members", response_model=list[RoomMemberSettingOut])
def list_room_member_settings(
    workspace_id: str,
    room_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[RoomMemberSetting]:
    verify_workspace(principal, workspace_id)
    _room_or_404(db, workspace_id, room_id)
    return db.execute(
        select(RoomMemberSetting).where(
            RoomMemberSetting.workspace_id == workspace_id,
            RoomMemberSetting.room_id == room_id,
        )
    ).scalars().all()


@router.put("/rooms/{room_id}/members/{user_id}/settings",
            response_model=RoomMemberSettingOut)
def set_room_member_settings(
    workspace_id: str,
    room_id: str,
    user_id: str,
    body: RoomMemberSettingPatch,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> RoomMemberSetting:
    verify_workspace(principal, workspace_id)
    _room_or_404(db, workspace_id, room_id)
    _active_member_or_404(db, workspace_id, user_id)
    setting = db.execute(
        select(RoomMemberSetting).where(
            RoomMemberSetting.workspace_id == workspace_id,
            RoomMemberSetting.room_id == room_id,
            RoomMemberSetting.user_id == user_id,
        )
    ).scalar_one_or_none()
    if setting is None:
        setting = RoomMemberSetting(
            id=new_id(), workspace_id=workspace_id, room_id=room_id,
            user_id=user_id, can_manage=False, can_download=False, updated_at=now(),
        )
        db.add(setting)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(setting, key, value)
    setting.updated_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=ROOM_MEMBER_SETTINGS_UPDATED,
        entity_id=setting.id,
        payload={"room_id": room_id, "user_id": user_id, "fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return setting


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> Document:
    verify_workspace(principal, workspace_id)
    return _document_or_404(db, workspace_id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    workspace_id: str,
    document_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document_or_404(db, workspace_id, document_id)
    db.delete(document)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_DELETED,
        entity_id=document.id,
        payload={"title": document.title, "room_id": document.room_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "document_id": document.id}
