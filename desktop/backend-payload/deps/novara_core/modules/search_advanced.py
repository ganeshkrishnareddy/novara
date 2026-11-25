"""Advanced local search: hybrid/vector/federated ranking and index operations.

Clean-room implementation of Meilisearch MIT-core rows MS-001, MS-022, MS-036,
MS-038, MS-042, MS-048, MS-053, MS-074, MS-075, MS-076, MS-077, MS-078,
MS-095 and MS-103.

All computation runs inside NOVARA's own database with deterministic local
embeddings. No Meilisearch server, embedding model, external SDK, hosted demo,
LMDB/OpenLDAP connector or BUSL/enterprise source is used or copied.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .search_engine import SearchDocument, SearchIndex

EMBEDDER_CHANGED = "search.embedder_changed"
VECTOR_CHANGED = "search.vector_changed"
LOCALE_CHANGED = "search.locale_changed"
SUGGESTION_CHANGED = "search.suggestion_changed"
FEDERATION_CHANGED = "search.federation_changed"
INDEX_SWAPPED = "search.index_swapped"
DOCUMENT_FUNCTION_EDIT = "search.document_function_edit"
COMPACTION_RECORDED = "search.compaction_recorded"
TEMPLATE_CHANGED = "search.template_changed"
PREVIEW_CHANGED = "search.preview_changed"
register_event_types(
    EMBEDDER_CHANGED, VECTOR_CHANGED, LOCALE_CHANGED, SUGGESTION_CHANGED,
    FEDERATION_CHANGED, INDEX_SWAPPED, DOCUMENT_FUNCTION_EDIT,
    COMPACTION_RECORDED, TEMPLATE_CHANGED, PREVIEW_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/search-advanced",
    tags=["search-advanced"],
)

EMBEDDER_KINDS = frozenset({"local_text", "local_image", "user_provided", "composite"})
EDIT_OPS = frozenset({"set", "upper", "lower", "suffix", "prefix", "increment"})
KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _index(db, workspace_id, name):
    row = db.execute(select(SearchIndex).where(
        SearchIndex.workspace_id == workspace_id, SearchIndex.name == name
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="search index not found")
    return row


def _documents(db, workspace_id, index_id):
    return db.execute(select(SearchDocument).where(
        SearchDocument.workspace_id == workspace_id,
        SearchDocument.index_id == index_id,
    )).scalars().all()


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def _local_embedding(text: str, dimensions: int) -> list[float]:
    """Deterministic bag-of-token-hashes embedding; no external model."""
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_l = math.sqrt(sum(a * a for a in left)) or 1.0
    norm_r = math.sqrt(sum(b * b for b in right)) or 1.0
    # Similarity is exposed as a 0..1 score to callers, never a negative rank.
    return max(0.0, min(1.0, dot / (norm_l * norm_r)))


def _hamming(left: list[int], right: list[int]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    matches = sum(1 for a, b in zip(left, right) if a == b)
    return matches / len(left)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class SearchEmbedder(Base):
    __tablename__ = "search_embedders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=32)
    binary_quantized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SearchVector(Base):
    __tablename__ = "search_vectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    embedder_name: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[str] = mapped_column(String(160), nullable=False)
    vector: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    binary: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class SearchLocale(Base):
    __tablename__ = "search_locales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    attribute_pattern: Mapped[str] = mapped_column(String(160), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), nullable=False)
    query_locale: Mapped[str | None] = mapped_column(String(20), nullable=True)


class SearchSuggestion(Base):
    __tablename__ = "search_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    attribute: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SearchFederation(Base):
    __tablename__ = "search_federations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    members: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SearchSwap(Base):
    __tablename__ = "search_index_swaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    left_index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False)
    right_index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SearchCompaction(Base):
    __tablename__ = "search_compactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SearchTemplate(Base):
    __tablename__ = "search_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class SearchPreview(Base):
    __tablename__ = "search_previews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EmbedderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: str
    config: dict = Field(default_factory=dict)
    dimensions: int = 32
    binary_quantized: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return _clean_key(value)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in EMBEDDER_KINDS:
            raise ValueError("unsupported embedder kind")
        return value

    @field_validator("dimensions")
    @classmethod
    def _dims(cls, value):
        if value < 4 or value > 512:
            raise ValueError("dimensions must be between 4 and 512")
        return value

    @field_validator("config")
    @classmethod
    def _config(cls, value):
        if value.get("source") and value["source"] not in {"local", "document", "query"}:
            raise ValueError("embedder source must be local, document or query")
        return value


class VectorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embedder_name: str
    document_id: str = Field(min_length=1, max_length=160)
    vector: list[float] = Field(default_factory=list)


class HybridSearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1, max_length=200)
    embedder_name: str
    semantic_weight: float = 0.5
    limit: int = 10

    @field_validator("semantic_weight")
    @classmethod
    def _weight(cls, value):
        if not 0.0 <= value <= 1.0:
            raise ValueError("semantic_weight must be between 0 and 1")
        return value

    @field_validator("limit")
    @classmethod
    def _limit(cls, value):
        if value < 1 or value > 100:
            raise ValueError("limit must be between 1 and 100")
        return value


class SimilarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    embedder_name: str
    limit: int = 5


class LocaleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_pattern: str = Field(min_length=1, max_length=160)
    locale: str = Field(min_length=2, max_length=20)
    query_locale: str | None = None


class SuggestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    attribute: str = Field(min_length=1, max_length=120)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class SuggestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1, max_length=120)
    limit: int = 10


class FederationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    members: list[dict] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("members")
    @classmethod
    def _members(cls, value):
        if not value:
            raise ValueError("at least one federation member is required")
        for member in value:
            if not member.get("index") or not isinstance(member.get("weight", 1), (int, float)):
                raise ValueError("members need an index and numeric weight")
        return value


class FederatedSearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1, max_length=200)
    limit: int = 10


class SwapIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    right_index: str = Field(min_length=1, max_length=120)


class EditFunctionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(min_length=1, max_length=120)
    op: str
    value: str | int | None = None
    document_ids: list[str] = Field(default_factory=list)

    @field_validator("op")
    @classmethod
    def _op(cls, value):
        if value not in EDIT_OPS:
            raise ValueError("unsupported edit function")
        return value


class CompactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in {"index", "task_queue"}:
            raise ValueError("compaction kind must be index or task_queue")
        return value


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    kind: str
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value):
        if value not in {"embedder", "chat", "fragment"}:
            raise ValueError("unsupported template kind")
        return value


class RenderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: dict = Field(default_factory=dict)
    query: str = ""


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    query: str = ""
    config: dict = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


# ---------------------------------------------------------------------------
# Routes - contract, embedders and vectors
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="searchAdvancedContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["embedders", "vectors", "locales", "suggestions", "federations",
                      "swaps", "compactions", "templates", "previews"],
        "embedder_kinds": sorted(EMBEDDER_KINDS), "edit_ops": sorted(EDIT_OPS),
        "external_model_calls": False, "external_sdk": False,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/search-advanced",
    }


@router.post("/indexes/{name}/embedders", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchEmbedder")
def create_embedder(workspace_id: str, name: str, body: EmbedderIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    exists = db.execute(select(SearchEmbedder.id).where(
        SearchEmbedder.workspace_id == workspace_id,
        SearchEmbedder.index_id == index.id, SearchEmbedder.name == body.name,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="embedder name already exists")
    row = SearchEmbedder(
        id=new_id(), workspace_id=workspace_id, index_id=index.id, name=body.name,
        kind=body.kind, config=body.config, dimensions=body.dimensions,
        binary_quantized=body.binary_quantized,
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, EMBEDDER_CHANGED, row.id,
           {"name": body.name, "kind": body.kind}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "kind": row.kind,
            "binary_quantized": row.binary_quantized}


@router.get("/indexes/{name}/embedders", operation_id="listSearchEmbedders")
def list_embedders(workspace_id: str, name: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    rows = db.execute(select(SearchEmbedder).where(
        SearchEmbedder.workspace_id == workspace_id, SearchEmbedder.index_id == index.id
    ).order_by(SearchEmbedder.name)).scalars().all()
    return [{"id": r.id, "name": r.name, "kind": r.kind,
             "dimensions": r.dimensions, "binary_quantized": r.binary_quantized}
            for r in rows]


@router.post("/indexes/{name}/vectors", status_code=status.HTTP_201_CREATED,
             operation_id="storeUserProvidedVector")
def store_vector(workspace_id: str, name: str, body: VectorIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    embedder = db.execute(select(SearchEmbedder).where(
        SearchEmbedder.workspace_id == workspace_id,
        SearchEmbedder.index_id == index.id,
        SearchEmbedder.name == body.embedder_name,
    )).scalar_one_or_none()
    if embedder is None:
        raise HTTPException(status_code=404, detail="embedder not found")
    if embedder.kind != "user_provided":
        raise HTTPException(status_code=422, detail="vector upload requires a user_provided embedder")
    if not body.vector or len(body.vector) != embedder.dimensions:
        raise HTTPException(status_code=422, detail="vector dimension mismatch")
    binary = [1 if value >= 0 else 0 for value in body.vector]
    row = db.execute(select(SearchVector).where(
        SearchVector.workspace_id == workspace_id, SearchVector.index_id == index.id,
        SearchVector.embedder_name == embedder.name,
        SearchVector.document_id == body.document_id,
    )).scalar_one_or_none()
    if row is None:
        row = SearchVector(id=new_id(), workspace_id=workspace_id, index_id=index.id,
                           embedder_name=embedder.name, document_id=body.document_id,
                           vector=body.vector, binary=binary)
        db.add(row)
    else:
        row.vector = body.vector
        row.binary = binary
    db.flush()
    _audit(db, workspace_id, VECTOR_CHANGED, row.id,
           {"document_id": body.document_id}, principal)
    db.commit()
    return {"id": row.id, "document_id": row.document_id,
            "dimensions": len(row.vector), "stored_local": True}


def _embedder(db, workspace_id, index_id, name) -> SearchEmbedder:
    row = db.execute(select(SearchEmbedder).where(
        SearchEmbedder.workspace_id == workspace_id,
        SearchEmbedder.index_id == index_id, SearchEmbedder.name == name,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="embedder not found")
    return row


def _vector_for(db, workspace_id, index_id, embedder, document, query: str) -> list[float]:
    if embedder.kind == "user_provided":
        stored = db.execute(select(SearchVector).where(
            SearchVector.workspace_id == workspace_id, SearchVector.index_id == index_id,
            SearchVector.embedder_name == embedder.name,
            SearchVector.document_id == document.document_id,
        )).scalar_one_or_none()
        return stored.vector if stored else []
    return _local_embedding(str(document.data), embedder.dimensions)


@router.post("/indexes/{name}/search/hybrid", operation_id="hybridSearch")
def hybrid_search(workspace_id: str, name: str, body: HybridSearchIn,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    embedder = _embedder(db, workspace_id, index.id, body.embedder_name)
    query_vector = _local_embedding(body.q, embedder.dimensions)
    query_terms = set(_tokens(body.q))
    scored: list[dict] = []
    for doc in _documents(db, workspace_id, index.id):
        doc_vector = _vector_for(db, workspace_id, index.id, embedder, doc, body.q)
        if not doc_vector:
            continue
        semantic = (_hamming(
            [1 if v >= 0 else 0 for v in doc_vector],
            [1 if v >= 0 else 0 for v in query_vector],
        ) if embedder.binary_quantized else _cosine(doc_vector, query_vector))
        doc_terms = set(_tokens(str(doc.data)))
        lexical = len(query_terms & doc_terms) / (len(query_terms) or 1)
        score = body.semantic_weight * semantic + (1 - body.semantic_weight) * lexical
        scored.append({"document_id": doc.document_id, "score": round(score, 6),
                       "semantic": round(semantic, 6), "lexical": round(lexical, 6),
                       "data": doc.data})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {"index": name, "embedder": embedder.name, "hybrid": True,
            "binary_quantized": embedder.binary_quantized,
            "results": scored[:body.limit]}


@router.post("/indexes/{name}/similar", operation_id="similarDocuments")
def similar_documents(workspace_id: str, name: str, body: SimilarIn,
                      principal: Principal = Depends(require(CONTACT_READ)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    embedder = _embedder(db, workspace_id, index.id, body.embedder_name)
    docs = _documents(db, workspace_id, index.id)
    reference = next((d for d in docs if d.document_id == body.document_id), None)
    if reference is None:
        raise HTTPException(status_code=404, detail="reference document not found")
    ref_vector = _vector_for(db, workspace_id, index.id, embedder, reference, "")
    results = []
    for doc in docs:
        if doc.document_id == body.document_id:
            continue
        vector = _vector_for(db, workspace_id, index.id, embedder, doc, "")
        if not vector or not ref_vector:
            continue
        results.append({"document_id": doc.document_id,
                        "similarity": round(_cosine(ref_vector, vector), 6)})
    results.sort(key=lambda item: item["similarity"], reverse=True)
    return {"index": name, "reference": body.document_id, "results": results[:body.limit]}


# ---------------------------------------------------------------------------
# Routes - locales, suggestions and federation
# ---------------------------------------------------------------------------


@router.post("/indexes/{name}/locales", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchLocale")
def create_locale(workspace_id: str, name: str, body: LocaleIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    row = SearchLocale(id=new_id(), workspace_id=workspace_id, index_id=index.id,
                       attribute_pattern=body.attribute_pattern, locale=body.locale,
                       query_locale=body.query_locale)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, LOCALE_CHANGED, row.id, {"locale": body.locale}, principal)
    db.commit()
    return {"id": row.id, "locale": row.locale, "query_locale": row.query_locale}


@router.get("/indexes/{name}/locales", operation_id="listSearchLocales")
def list_locales(workspace_id: str, name: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    rows = db.execute(select(SearchLocale).where(
        SearchLocale.workspace_id == workspace_id, SearchLocale.index_id == index.id
    )).scalars().all()
    return [{"id": r.id, "attribute_pattern": r.attribute_pattern,
             "locale": r.locale, "query_locale": r.query_locale} for r in rows]


@router.post("/indexes/{name}/suggestions", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchSuggestion")
def create_suggestion(workspace_id: str, name: str, body: SuggestionIn,
                      principal: Principal = Depends(require(NOTE_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    exists = db.execute(select(SearchSuggestion.id).where(
        SearchSuggestion.workspace_id == workspace_id, SearchSuggestion.index_id == index.id,
        SearchSuggestion.key == body.key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="suggestion key already exists")
    row = SearchSuggestion(id=new_id(), workspace_id=workspace_id, index_id=index.id,
                           key=body.key, attribute=body.attribute, enabled=True)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, SUGGESTION_CHANGED, row.id, {"key": body.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "attribute": row.attribute}


@router.post("/indexes/{name}/suggest", operation_id="suggestSearchTerms")
def suggest(workspace_id: str, name: str, body: SuggestIn,
            principal: Principal = Depends(require(CONTACT_READ)),
            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    configs = db.execute(select(SearchSuggestion).where(
        SearchSuggestion.workspace_id == workspace_id, SearchSuggestion.index_id == index.id,
        SearchSuggestion.enabled.is_(True),
    )).scalars().all()
    terms: set[str] = set()
    for config in configs:
        for doc in _documents(db, workspace_id, index.id):
            value = doc.data.get(config.attribute)
            if isinstance(value, str) and value.lower().startswith(body.q.lower()):
                terms.add(value)
    ordered = sorted(terms)[:body.limit]
    return {"index": name, "suggestions": ordered, "connectors": len(configs)}


@router.post("/federations", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchFederation")
def create_federation(workspace_id: str, body: FederationIn,
                      principal: Principal = Depends(require(NOTE_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    for member in body.members:
        _index(db, workspace_id, member["index"])
    row = SearchFederation(id=new_id(), workspace_id=workspace_id, key=body.key,
                           members=body.members, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, FEDERATION_CHANGED, row.id,
           {"key": body.key, "members": len(body.members)}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "member_count": len(row.members)}


@router.get("/federations", operation_id="listSearchFederations")
def list_federations(workspace_id: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(SearchFederation).where(
        SearchFederation.workspace_id == workspace_id
    ).order_by(SearchFederation.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "members": r.members} for r in rows]


@router.post("/federations/{federation_id}/search", operation_id="federatedSearch")
def federated_search(workspace_id: str, federation_id: str, body: FederatedSearchIn,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    federation = _get(db, SearchFederation, workspace_id, federation_id, "federation")
    query_terms = set(_tokens(body.q))
    merged: list[dict] = []
    for member in federation.members:
        index = _index(db, workspace_id, member["index"])
        weight = float(member.get("weight", 1))
        for doc in _documents(db, workspace_id, index.id):
            doc_terms = set(_tokens(str(doc.data)))
            lexical = len(query_terms & doc_terms) / (len(query_terms) or 1)
            if lexical <= 0:
                continue
            merged.append({"index": index.name, "document_id": doc.document_id,
                           "score": round(lexical * weight, 6),
                           "weight": weight, "data": doc.data})
    merged.sort(key=lambda item: item["score"], reverse=True)
    return {"federation": federation.key, "results": merged[:body.limit]}


# ---------------------------------------------------------------------------
# Routes - index operations, templates and previews
# ---------------------------------------------------------------------------


@router.post("/indexes/{name}/swap", operation_id="swapSearchIndexes")
def swap_indexes(workspace_id: str, name: str, body: SwapIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    left = _index(db, workspace_id, name)
    right = _index(db, workspace_id, body.right_index)
    if left.id == right.id:
        raise HTTPException(status_code=422, detail="cannot swap an index with itself")
    left_docs = _documents(db, workspace_id, left.id)
    right_docs = _documents(db, workspace_id, right.id)
    for doc in left_docs:
        doc.index_id = right.id
    for doc in right_docs:
        doc.index_id = left.id
    left.settings, right.settings = right.settings, left.settings
    swap = SearchSwap(id=new_id(), workspace_id=workspace_id,
                      left_index_id=left.id, right_index_id=right.id,
                      status="completed", created_at=now())
    db.add(swap)
    db.flush()
    _audit(db, workspace_id, INDEX_SWAPPED, swap.id,
           {"left": left.name, "right": right.name,
            "documents": len(left_docs) + len(right_docs)}, principal)
    db.commit()
    return {"id": swap.id, "status": swap.status,
            "documents_swapped": len(left_docs) + len(right_docs)}


@router.post("/indexes/{name}/documents/edit-function", operation_id="editDocumentsByFunction")
def edit_documents(workspace_id: str, name: str, body: EditFunctionIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    docs = _documents(db, workspace_id, index.id)
    if body.document_ids:
        docs = [d for d in docs if d.document_id in body.document_ids]
    changed = 0
    for doc in docs:
        data = dict(doc.data or {})
        current = data.get(body.attribute)
        if body.op == "set":
            data[body.attribute] = body.value
        elif body.op == "upper" and isinstance(current, str):
            data[body.attribute] = current.upper()
        elif body.op == "lower" and isinstance(current, str):
            data[body.attribute] = current.lower()
        elif body.op == "suffix" and isinstance(current, str):
            data[body.attribute] = current + str(body.value or "")
        elif body.op == "prefix" and isinstance(current, str):
            data[body.attribute] = str(body.value or "") + current
        elif body.op == "increment" and isinstance(current, (int, float)):
            data[body.attribute] = current + int(body.value or 1)
        else:
            continue
        # Reassign the whole JSON value so SQLAlchemy persists the mutation.
        doc.data = data
        changed += 1
    db.flush()
    _audit(db, workspace_id, DOCUMENT_FUNCTION_EDIT, index.id,
           {"op": body.op, "changed": changed}, principal)
    db.commit()
    return {"index": name, "op": body.op, "changed": changed}


@router.post("/indexes/{name}/compact", status_code=status.HTTP_201_CREATED,
             operation_id="recordSearchCompaction")
def compact(workspace_id: str, name: str, body: CompactionIn,
            principal: Principal = Depends(require(NOTE_WRITE)),
            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    row = SearchCompaction(
        id=new_id(), workspace_id=workspace_id, index_id=index.id, kind=body.kind,
        document_count=len(_documents(db, workspace_id, index.id)),
        status="completed", created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, COMPACTION_RECORDED, row.id,
           {"kind": body.kind, "documents": row.document_count}, principal)
    db.commit()
    return {"id": row.id, "kind": row.kind, "status": row.status,
            "external_service": False}


@router.get("/indexes/{name}/compactions", operation_id="listSearchCompactions")
def list_compactions(workspace_id: str, name: str,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    rows = db.execute(select(SearchCompaction).where(
        SearchCompaction.workspace_id == workspace_id, SearchCompaction.index_id == index.id
    )).scalars().all()
    return [{"id": r.id, "kind": r.kind, "document_count": r.document_count,
             "status": r.status} for r in rows]


@router.post("/indexes/{name}/templates", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchTemplate")
def create_template(workspace_id: str, name: str, body: TemplateIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    row = SearchTemplate(id=new_id(), workspace_id=workspace_id, index_id=index.id,
                         key=body.key, kind=body.kind, body=body.body)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TEMPLATE_CHANGED, row.id, {"key": body.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "kind": row.kind}


@router.get("/indexes/{name}/templates", operation_id="listSearchTemplates")
def list_templates(workspace_id: str, name: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    rows = db.execute(select(SearchTemplate).where(
        SearchTemplate.workspace_id == workspace_id, SearchTemplate.index_id == index.id
    )).scalars().all()
    return [{"id": r.id, "key": r.key, "kind": r.kind, "body": r.body} for r in rows]


@router.post("/indexes/{name}/templates/{template_id}/render", operation_id="renderSearchTemplate")
def render_template(workspace_id: str, name: str, template_id: str, body: RenderIn,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    template = _get(db, SearchTemplate, workspace_id, template_id, "template")
    if template.index_id != index.id:
        raise HTTPException(status_code=404, detail="template not found")
    values = dict(body.document)
    values["query"] = body.query

    def replace(match):
        return str(values.get(match.group(1), ""))

    rendered = re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, template.body)
    return {"template": template.key, "rendered": rendered, "external_service": False}


@router.post("/indexes/{name}/previews", status_code=status.HTTP_201_CREATED,
             operation_id="createSearchPreview")
def create_preview(workspace_id: str, name: str, body: PreviewIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    index = _index(db, workspace_id, name)
    row = SearchPreview(id=new_id(), workspace_id=workspace_id, index_id=index.id,
                        key=body.key, query=body.query, config=body.config)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PREVIEW_CHANGED, row.id, {"key": body.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "query": row.query}


@router.post("/previews/{preview_id}/run", operation_id="runSearchPreview")
def run_preview(workspace_id: str, preview_id: str,
                principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    preview = _get(db, SearchPreview, workspace_id, preview_id, "preview")
    index = db.execute(select(SearchIndex).where(
        SearchIndex.id == preview.index_id, SearchIndex.workspace_id == workspace_id
    )).scalar_one_or_none()
    if index is None:
        raise HTTPException(status_code=404, detail="search index not found")
    terms = set(_tokens(preview.query))
    results = []
    for doc in _documents(db, workspace_id, index.id):
        doc_terms = set(_tokens(str(doc.data)))
        score = len(terms & doc_terms) / (len(terms) or 1)
        if score > 0:
            results.append({"document_id": doc.document_id, "score": round(score, 6)})
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"preview": preview.key, "index": index.name, "results": results[:10],
            "local_only": True}
