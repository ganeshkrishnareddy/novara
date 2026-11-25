"""Workspace-scoped document store (GB-087, clean-room compatible slice).

MongoDB's *primary-store semantics* — named collections, schema-free JSON
documents with a stable ``_id``, declarative indexes, operator-based queries,
upsert-style updates and optimistic concurrency — are provided here as NOVARA's
own small document-store abstraction on top of the existing relational store.

This deliberately does **not** vendor MongoDB code, install a MongoDB server or
open a network connection. It is an intentionally compatible implementation of
the behaviours the source feature describes, with the same workspace,
permission and event contracts as every other NOVARA capability. All documents
are real persisted rows and every write publishes a named event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

DOC_INSERTED = "docstore.document.inserted"
DOC_UPDATED = "docstore.document.updated"
DOC_DELETED = "docstore.document.deleted"
INDEX_CREATED = "docstore.index.created"
COLLECTION_CREATED = "docstore.collection.created"
register_event_types(DOC_INSERTED, DOC_UPDATED, DOC_DELETED, INDEX_CREATED, COLLECTION_CREATED)

INDEX_OPERATORS = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$exists"}
UPDATE_OPERATORS = {"$set", "$unset"}

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/docstore",
    tags=["document-store"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class DocCollection(Base):
    __tablename__ = "docstore_collections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_docstore_collection_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocIndex(Base):
    __tablename__ = "docstore_indexes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "collection", "field", name="uq_docstore_index_field"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    collection: Mapped[str] = mapped_column(String(120), nullable=False)
    field: Mapped[str] = mapped_column(String(200), nullable=False)
    unique: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocDocument(Base):
    __tablename__ = "docstore_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "collection", "doc_id", name="uq_docstore_doc_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    collection: Mapped[str] = mapped_column(String(120), nullable=False)
    doc_id: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Query engine — evaluated over real persisted rows
# ---------------------------------------------------------------------------


def _field_value(doc: dict, path: str) -> Any:
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


_MISSING = object()


def _matches(doc: dict, field: str, condition: Any) -> bool:
    """Evaluate one filter clause. Bare values mean equality."""
    actual = _field_value(doc, field)
    if not isinstance(condition, dict):
        return actual is not _MISSING and actual == condition
    for operator, expected in condition.items():
        if operator not in INDEX_OPERATORS:
            raise HTTPException(status_code=422, detail=f"unsupported query operator: {operator}")
        if operator == "$eq":
            ok = actual is not _MISSING and actual == expected
        elif operator == "$ne":
            ok = actual is _MISSING or actual != expected
        elif operator == "$exists":
            ok = (actual is not _MISSING) == bool(expected)
        elif operator == "$in":
            # MongoDB-style: a scalar matches when it is a member of the
            # expected list; an array field matches when any element is.
            if actual is _MISSING:
                ok = False
            elif isinstance(actual, (list, tuple, set)):
                ok = any(item in expected for item in actual)
            else:
                ok = actual in expected
        elif operator == "$nin":
            if actual is _MISSING:
                ok = True
            elif isinstance(actual, (list, tuple, set)):
                ok = not any(item in expected for item in actual)
            else:
                ok = actual not in expected
        else:
            if actual is _MISSING or actual is None:
                ok = False
            elif operator == "$gt":
                ok = actual > expected
            elif operator == "$gte":
                ok = actual >= expected
            elif operator == "$lt":
                ok = actual < expected
            else:
                ok = actual <= expected
        if not ok:
            return False
    return True


def _select_documents(
    db: Session, workspace_id: str, collection: str, filter_: dict[str, Any]
) -> list[DocDocument]:
    rows = db.execute(
        select(DocDocument).where(
            DocDocument.workspace_id == workspace_id,
            DocDocument.collection == collection,
        )
    ).scalars().all()
    matched: list[DocDocument] = []
    for row in rows:
        if all(_matches(row.body, field, condition) for field, condition in filter_.items()):
            matched.append(row)
    return sorted(matched, key=lambda r: r.doc_id)


# ---------------------------------------------------------------------------
# Service class — the reusable store seam
# ---------------------------------------------------------------------------


class DocumentStore:
    """Workspace-bound document store used by both the API and local callers."""

    def __init__(self, db: Session, workspace_id: str, actor_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.actor_id = actor_id

    def create_collection(self, name: str) -> DocCollection:
        row = self.db.execute(
            select(DocCollection).where(
                DocCollection.workspace_id == self.workspace_id,
                DocCollection.name == name,
            )
        ).scalar_one_or_none()
        if row is not None:
            raise HTTPException(status_code=409, detail="collection already exists")
        row = DocCollection(id=new_id(), workspace_id=self.workspace_id,
                            name=name, created_at=now())
        self.db.add(row)
        self.db.flush()
        publish_event(self.db, workspace_id=self.workspace_id,
                      event_type=COLLECTION_CREATED, entity_id=row.id,
                      payload={"collection": name}, actor_id=self.actor_id)
        return row

    def create_index(self, collection: str, field: str, unique: bool = False) -> DocIndex:
        self._require_collection(collection)
        row = self.db.execute(
            select(DocIndex).where(
                DocIndex.workspace_id == self.workspace_id,
                DocIndex.collection == collection,
                DocIndex.field == field,
            )
        ).scalar_one_or_none()
        if row is not None:
            raise HTTPException(status_code=409, detail="index already exists")
        row = DocIndex(id=new_id(), workspace_id=self.workspace_id, collection=collection,
                       field=field, unique=int(unique), created_at=now())
        self.db.add(row)
        self.db.flush()
        publish_event(self.db, workspace_id=self.workspace_id, event_type=INDEX_CREATED,
                      entity_id=row.id,
                      payload={"collection": collection, "field": field, "unique": unique},
                      actor_id=self.actor_id)
        return row

    def _require_collection(self, collection: str) -> None:
        row = self.db.execute(
            select(DocCollection.id).where(
                DocCollection.workspace_id == self.workspace_id,
                DocCollection.name == collection,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="collection not found")

    def _enforce_unique_indexes(self, collection: str, body: dict, exclude_id: str | None = None) -> None:
        """A declared unique index is enforced on insert and update, not merely stored."""
        indexes = self.db.execute(
            select(DocIndex).where(
                DocIndex.workspace_id == self.workspace_id,
                DocIndex.collection == collection,
                DocIndex.unique == 1,
            )
        ).scalars().all()
        if not indexes:
            return
        existing = self.db.execute(
            select(DocDocument).where(
                DocDocument.workspace_id == self.workspace_id,
                DocDocument.collection == collection,
            )
        ).scalars().all()
        for index in indexes:
            candidate = _field_value(body, index.field)
            if candidate is _MISSING:
                continue
            for row in existing:
                if exclude_id is not None and row.doc_id == exclude_id:
                    continue
                if _field_value(row.body, index.field) == candidate:
                    raise HTTPException(
                        status_code=409,
                        detail=f"unique index violation on {index.field}",
                    )

    def insert(self, collection: str, doc_id: str, body: dict) -> DocDocument:
        self._require_collection(collection)
        self._enforce_unique_indexes(collection, body)
        exists = self.db.execute(
            select(DocDocument.id).where(
                DocDocument.workspace_id == self.workspace_id,
                DocDocument.collection == collection,
                DocDocument.doc_id == doc_id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            raise HTTPException(status_code=409, detail="document _id already exists")
        row = DocDocument(id=new_id(), workspace_id=self.workspace_id, collection=collection,
                          doc_id=doc_id, body=body, version=1,
                          created_at=now(), updated_at=now())
        self.db.add(row)
        self.db.flush()
        publish_event(self.db, workspace_id=self.workspace_id, event_type=DOC_INSERTED,
                      entity_id=row.id,
                      payload={"collection": collection, "doc_id": doc_id},
                      actor_id=self.actor_id,
                      idempotency_key=f"docstore:insert:{self.workspace_id}:{collection}:{doc_id}")
        return row

    def find_one(self, collection: str, doc_id: str) -> DocDocument:
        self._require_collection(collection)
        row = self.db.execute(
            select(DocDocument).where(
                DocDocument.workspace_id == self.workspace_id,
                DocDocument.collection == collection,
                DocDocument.doc_id == doc_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="document not found")
        return row

    def query(self, collection: str, filter_: dict, skip: int, limit: int) -> list[DocDocument]:
        self._require_collection(collection)
        return _select_documents(self.db, self.workspace_id, collection, filter_)[skip:skip + limit]

    def update(self, collection: str, doc_id: str, updates: dict, expected_version: int) -> DocDocument:
        row = self.find_one(collection, doc_id)
        if expected_version != row.version:
            raise HTTPException(status_code=409, detail="stale document version")
        for operator, changes in updates.items():
            if operator not in UPDATE_OPERATORS:
                raise HTTPException(status_code=422, detail=f"unsupported update operator: {operator}")
            if not isinstance(changes, dict):
                raise HTTPException(status_code=422, detail="update changes must be an object")
            if operator == "$set":
                row.body.update(changes)
            else:
                for field in changes:
                    row.body.pop(field, None)
        self._enforce_unique_indexes(collection, row.body, exclude_id=row.doc_id)
        row.version += 1
        row.updated_at = now()
        publish_event(self.db, workspace_id=self.workspace_id, event_type=DOC_UPDATED,
                      entity_id=row.id,
                      payload={"collection": collection, "doc_id": doc_id, "version": row.version},
                      actor_id=self.actor_id)
        return row

    def delete(self, collection: str, doc_id: str) -> dict:
        row = self.find_one(collection, doc_id)
        result = {"deleted": True, "doc_id": doc_id, "collection": collection}
        publish_event(self.db, workspace_id=self.workspace_id, event_type=DOC_DELETED,
                      entity_id=row.id,
                      payload={"collection": collection, "doc_id": doc_id},
                      actor_id=self.actor_id)
        self.db.delete(row)
        return result


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_allowed(cls, value: str) -> str:
        value = value.strip()
        if not value.replace("_", "").isalnum():
            raise ValueError("collection name may contain letters, numbers and underscores")
        return value


class IndexCreate(BaseModel):
    field: str = Field(min_length=1, max_length=200)
    unique: bool = False

    model_config = ConfigDict(extra="forbid")


class DocumentInsert(BaseModel):
    # The document's stable identifier, the document-store equivalent of _id.
    id: str = Field(min_length=1, max_length=200)
    body: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class DocumentQuery(BaseModel):
    filter: dict[str, Any] = Field(default_factory=dict)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)

    model_config = ConfigDict(extra="forbid")


class DocumentUpdate(BaseModel):
    updates: dict[str, dict]

    model_config = ConfigDict(extra="forbid")

    @field_validator("updates")
    @classmethod
    def operators_allowed(cls, value: dict[str, dict]) -> dict[str, dict]:
        bad = set(value) - UPDATE_OPERATORS
        if bad:
            raise ValueError(f"unsupported update operator: {sorted(bad)[0]}")
        return value


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    collection: str
    doc_id: str
    body: dict
    version: int
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class CollectionOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class IndexOut(BaseModel):
    id: str
    workspace_id: str
    collection: str
    field: str
    unique: int
    created_at: object

    model_config = ConfigDict(from_attributes=True)


def _store(principal: Principal, workspace_id: str, db: Session) -> DocumentStore:
    verify_workspace(principal, workspace_id)
    return DocumentStore(db, workspace_id, principal.user.id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/collections", response_model=CollectionOut,
             status_code=status.HTTP_201_CREATED)
def create_collection(
    workspace_id: str,
    body: CollectionCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DocCollection:
    store = _store(principal, workspace_id, db)
    row = store.create_collection(body.name)
    db.commit()
    return row


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[DocCollection]:
    _store(principal, workspace_id, db)
    return db.execute(
        select(DocCollection).where(DocCollection.workspace_id == workspace_id)
        .order_by(DocCollection.name)
    ).scalars().all()


@router.post("/collections/{collection}/indexes", response_model=IndexOut,
             status_code=status.HTTP_201_CREATED)
def create_index(
    workspace_id: str,
    collection: str,
    body: IndexCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DocIndex:
    store = _store(principal, workspace_id, db)
    row = store.create_index(collection, body.field, body.unique)
    db.commit()
    return row


@router.get("/collections/{collection}/indexes", response_model=list[IndexOut])
def list_indexes(
    workspace_id: str,
    collection: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[DocIndex]:
    store = _store(principal, workspace_id, db)
    store._require_collection(collection)
    return db.execute(
        select(DocIndex).where(
            DocIndex.workspace_id == workspace_id, DocIndex.collection == collection
        ).order_by(DocIndex.field)
    ).scalars().all()


@router.post("/collections/{collection}/documents", response_model=DocumentOut,
             status_code=status.HTTP_201_CREATED)
def insert_document(
    workspace_id: str,
    collection: str,
    body: DocumentInsert,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DocDocument:
    store = _store(principal, workspace_id, db)
    row = store.insert(collection, body.id, body.body)
    db.commit()
    return row


@router.get("/collections/{collection}/documents/{doc_id}", response_model=DocumentOut)
def get_document(
    workspace_id: str,
    collection: str,
    doc_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> DocDocument:
    store = _store(principal, workspace_id, db)
    return store.find_one(collection, doc_id)


@router.post("/collections/{collection}/query", response_model=list[DocumentOut])
def query_documents(
    workspace_id: str,
    collection: str,
    body: DocumentQuery,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[DocDocument]:
    store = _store(principal, workspace_id, db)
    return store.query(collection, body.filter, body.skip, body.limit)


@router.patch("/collections/{collection}/documents/{doc_id}", response_model=DocumentOut)
def update_document(
    workspace_id: str,
    collection: str,
    doc_id: str,
    body: DocumentUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DocDocument:
    store = _store(principal, workspace_id, db)
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match header is required")
    try:
        expected = int(if_match.strip().strip('"'))
    except ValueError:
        raise HTTPException(status_code=400, detail="If-Match must be a version number")
    row = store.update(collection, doc_id, body.updates, expected)
    db.commit()
    return row


@router.delete("/collections/{collection}/documents/{doc_id}", response_model=dict)
def delete_document(
    workspace_id: str,
    collection: str,
    doc_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    store = _store(principal, workspace_id, db)
    result = store.delete(collection, doc_id)
    db.commit()
    return result
