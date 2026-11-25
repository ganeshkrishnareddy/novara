"""Feedback Intelligence and Unify Feedback (Formbricks P2 clean-room cluster).

Clean-room implementation of FB-024, FB-025, FB-029, FB-085, FB-096, FB-097,
FB-098, FB-099, FB-100 and FB-101 over NOVARA's shared workspace identity.

Everything is local: a reusable field library, reserved response context,
respondent metadata, contact-based audience segments, feedback datasets/sources/
records, unified ingestion and real analytics computed from persisted rows. No
Formbricks source is copied, no Cube.js service is contacted and no external
feedback provider is called. Every mutation is published to the shared audit
bus.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .feedback import _survey_or_404

FIELD_CREATED = "feedback.field_created"
FIELD_UPDATED = "feedback.field_updated"
FIELD_BOUND = "feedback.field_bound"
FIELD_UNBOUND = "feedback.field_unbound"
DATASET_CREATED = "feedback.dataset_created"
SOURCE_CREATED = "feedback.source_created"
RECORD_INGESTED = "feedback.record_ingested"
SENTIMENT_SET = "feedback.sentiment_set"
SEGMENT_CREATED = "feedback.segment_created"
SEGMENT_EVALUATED = "feedback.segment_evaluated"
DASHBOARD_CREATED = "feedback.dashboard_created"
register_event_types(
    FIELD_CREATED, FIELD_UPDATED, FIELD_BOUND, FIELD_UNBOUND, DATASET_CREATED,
    SOURCE_CREATED, RECORD_INGESTED, SENTIMENT_SET, SEGMENT_CREATED,
    SEGMENT_EVALUATED, DASHBOARD_CREATED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/feedback-intelligence",
    tags=["feedback-intelligence"],
)

# FB-024: reusable field library types (a documented local subset).
FIELD_TYPES = frozenset({
    "short_text", "long_text", "single_choice", "multi_choice", "rating",
    "nps", "csat", "number", "date", "email",
})
# FB-025: system fields captured on every feedback record.
RESERVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("page", "Page or route where the feedback was captured"),
    ("campaign", "Campaign or experiment identifier"),
    ("device", "Device class of the respondent"),
    ("timing", "Response timing metadata"),
    ("request_context", "Request context (locale, referrer, user agent)"),
)
RESERVED_NAMES = frozenset(name for name, _ in RESERVED_FIELDS)
# FB-099: accepted source types for feedback ingestion.
SOURCE_TYPES = frozenset({"survey", "email", "web", "chat", "api", "import", "support", "interview"})
# FB-100: sentiment classification values.
SENTIMENTS = frozenset({"positive", "neutral", "negative", "mixed", "unclassified"})
# FB-085: segment rule operators.
SEGMENT_OPERATORS = frozenset({"eq", "neq", "contains", "gt", "gte", "lt", "lte", "in"})

POSITIVE_WORDS = frozenset({
    "great", "love", "loved", "excellent", "awesome", "amazing", "happy",
    "thanks", "thank", "good", "best", "perfect", "easy", "fast", "helpful", "delight",
})
NEGATIVE_WORDS = frozenset({
    "bad", "terrible", "awful", "hate", "broken", "slow", "bug", "bugs",
    "frustrating", "worst", "hard", "difficult", "disappointed", "poor", "crash",
})
KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


# ---------------------------------------------------------------------------
# Clean-room helpers
# ---------------------------------------------------------------------------


def clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def clean_label(value: str) -> str:
    label = (value or "").strip()
    if not label or len(label) > 200:
        raise ValueError("a label of 1-200 characters is required")
    return label


def _text_values(value, depth: int = 0):
    """Yield scalar strings from a bounded JSON payload for sentiment analysis."""
    if depth > 6:
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _text_values(item, depth + 1)
    elif isinstance(value, list):
        for item in value[:50]:
            yield from _text_values(item, depth + 1)
    elif isinstance(value, str):
        yield value


def classify_sentiment(payload: dict) -> str:
    """A deterministic, local keyword classifier — no model or external call."""
    text = " ".join(_text_values(payload)).lower()
    if not text:
        return "unclassified"
    words = set(re.findall(r"[a-z]+", text))
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)
    if positive and negative and positive == negative:
        return "mixed"
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "unclassified"


def _matches_rule(attributes: dict, rule: dict) -> bool:
    field_name = str(rule.get("field", ""))
    op = str(rule.get("op", ""))
    expected = rule.get("value")
    actual = attributes.get(field_name)
    try:
        if op == "eq":
            return actual == expected
        if op == "neq":
            return actual != expected
        if op == "contains":
            return str(expected).lower() in str(actual or "").lower()
        if op == "in":
            return actual in (expected or [])
        left, right = float(actual), float(expected)
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
    except (TypeError, ValueError):
        return False
    return False


def _contact_attributes(contact: Contact) -> dict:
    attributes = {
        "email": contact.email,
        "full_name": contact.full_name,
        "company_name": contact.company_name,
        "source": contact.source,
        "lifecycle_stage": contact.lifecycle_stage,
    }
    attributes.update(contact.custom_fields or {})
    return attributes


# ---------------------------------------------------------------------------
# Tables (all additive and workspace-scoped)
# ---------------------------------------------------------------------------


class FeedbackLibraryField(Base):
    """FB-024: a reusable field declared once for the whole workspace."""

    __tablename__ = "feedback_library_fields"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_feedback_field_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackSurveyField(Base):
    """FB-024: binding of a library field into a concrete survey."""

    __tablename__ = "feedback_survey_fields"
    __table_args__ = (
        UniqueConstraint("workspace_id", "survey_id", "field_id", name="uq_feedback_survey_field"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("feedback_library_fields.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class FeedbackDataset(Base):
    """FB-098: organisation-level container grouping feedback records/sources."""

    __tablename__ = "feedback_datasets"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_feedback_dataset_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackSource(Base):
    """FB-099: a named source that brings feedback into a dataset."""

    __tablename__ = "feedback_sources"
    __table_args__ = (
        UniqueConstraint("workspace_id", "dataset_id", "key", name="uq_feedback_source_dataset_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feedback_datasets.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackRecord(Base):
    """FB-100: the normalised unit of feedback inside a dataset."""

    __tablename__ = "feedback_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("feedback_datasets.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("feedback_sources.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    reserved: Mapped[dict] = mapped_column(JSON, default=dict)
    # Mapped to the "metadata" DB column under a safe Python attribute name:
    # SQLAlchemy reserves ``metadata`` on declarative classes for the MetaData.
    context_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    respondent_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sentiment: Mapped[str] = mapped_column(String(20), default="unclassified", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackSegment(Base):
    """FB-085: a reusable audience definition over contact attributes."""

    __tablename__ = "feedback_segments"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_feedback_segment_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackDashboard(Base):
    """FB-096: a saved set of analytics widgets computed from stored records."""

    __tablename__ = "feedback_dashboards"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_feedback_dashboard_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    widgets: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FieldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str = "short_text"
    config: dict = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return clean_key(value)

    @field_validator("label")
    @classmethod
    def _label(cls, value):
        return clean_label(value)

    @field_validator("type")
    @classmethod
    def _type(cls, value):
        if value not in FIELD_TYPES:
            raise ValueError("unsupported field type")
        return value


class FieldPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    type: str | None = None
    config: dict | None = None

    @field_validator("label")
    @classmethod
    def _label(cls, value):
        return clean_label(value) if value is not None else value

    @field_validator("type")
    @classmethod
    def _type(cls, value):
        if value is not None and value not in FIELD_TYPES:
            raise ValueError("unsupported field type")
        return value


class FieldBind(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    position: int = 0

    @field_validator("position")
    @classmethod
    def _position(cls, value):
        if not 0 <= value <= 1000:
            raise ValueError("position must be between 0 and 1000")
        return value


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    description: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return clean_label(value)


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    source_type: str = "api"

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return clean_label(value)

    @field_validator("source_type")
    @classmethod
    def _source_type(cls, value):
        if value not in SOURCE_TYPES:
            raise ValueError("unsupported source type")
        return value


class RecordIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict = Field(default_factory=dict)
    reserved: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    external_id: str | None = None
    sentiment: str | None = None

    @field_validator("sentiment")
    @classmethod
    def _sentiment(cls, value):
        if value is not None and value not in SENTIMENTS:
            raise ValueError("unsupported sentiment")
        return value


class SentimentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment: str

    @field_validator("sentiment")
    @classmethod
    def _sentiment(cls, value):
        if value not in SENTIMENTS:
            raise ValueError("unsupported sentiment")
        return value


class SegmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    rules: list[dict] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return clean_label(value)

    @field_validator("rules")
    @classmethod
    def _rules(cls, value):
        for rule in value:
            if not isinstance(rule, dict) or not str(rule.get("field", "")).strip():
                raise ValueError("each rule needs a field")
            if rule.get("op") not in SEGMENT_OPERATORS:
                raise ValueError("unsupported segment operator")
        return value[:50]


class DashboardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    widgets: list[dict] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return clean_label(value)

    @field_validator("widgets")
    @classmethod
    def _widgets(cls, value):
        valid = {"count_by_source", "sentiment", "volume", "field"}
        for widget in value:
            if not isinstance(widget, dict) or widget.get("type") not in valid:
                raise ValueError("unsupported widget type")
            if not str(widget.get("id", "")).strip():
                raise ValueError("each widget needs an id")
        return value[:30]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _field_or_404(db: Session, workspace_id: str, field_id: str) -> FeedbackLibraryField:
    row = db.execute(
        select(FeedbackLibraryField).where(
            FeedbackLibraryField.id == field_id,
            FeedbackLibraryField.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="library field not found")
    return row


def _dataset_or_404(db: Session, workspace_id: str, dataset_id: str) -> FeedbackDataset:
    row = db.execute(
        select(FeedbackDataset).where(
            FeedbackDataset.id == dataset_id,
            FeedbackDataset.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="feedback dataset not found")
    return row


def _source_or_404(db: Session, workspace_id: str, source_id: str) -> FeedbackSource:
    row = db.execute(
        select(FeedbackSource).where(
            FeedbackSource.id == source_id,
            FeedbackSource.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="feedback source not found")
    return row


def _record_or_404(db: Session, workspace_id: str, record_id: str) -> FeedbackRecord:
    row = db.execute(
        select(FeedbackRecord).where(
            FeedbackRecord.id == record_id,
            FeedbackRecord.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="feedback record not found")
    return row


def _segment_or_404(db: Session, workspace_id: str, segment_id: str) -> FeedbackSegment:
    row = db.execute(
        select(FeedbackSegment).where(
            FeedbackSegment.id == segment_id,
            FeedbackSegment.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="segment not found")
    return row


def _dashboard_or_404(db: Session, workspace_id: str, dashboard_id: str) -> FeedbackDashboard:
    row = db.execute(
        select(FeedbackDashboard).where(
            FeedbackDashboard.id == dashboard_id,
            FeedbackDashboard.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    return row


# ---------------------------------------------------------------------------
# Output serialisers
# ---------------------------------------------------------------------------


def field_out(row: FeedbackLibraryField) -> dict:
    return {
        "id": row.id, "key": row.key, "label": row.label, "type": row.type,
        "config": row.config, "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def dataset_out(row: FeedbackDataset) -> dict:
    return {
        "id": row.id, "key": row.key, "name": row.name,
        "description": row.description,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def source_out(row: FeedbackSource) -> dict:
    return {
        "id": row.id, "dataset_id": row.dataset_id, "key": row.key,
        "name": row.name, "source_type": row.source_type,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def record_out(row: FeedbackRecord) -> dict:
    return {
        "id": row.id, "dataset_id": row.dataset_id, "source_id": row.source_id,
        "external_id": row.external_id, "payload": row.payload, "reserved": row.reserved,
        "metadata": row.context_metadata, "respondent_hash": row.respondent_hash,
        "sentiment": row.sentiment,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def segment_out(row: FeedbackSegment) -> dict:
    return {
        "id": row.id, "key": row.key, "name": row.name, "rules": row.rules,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def dashboard_out(row: FeedbackDashboard) -> dict:
    return {
        "id": row.id, "key": row.key, "name": row.name, "widgets": row.widgets,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# FB-101: one documented, stable API group
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="feedbackIntelligenceContract")
def api_contract():
    """FB-101: document the stable unify-feedback resource group; claim no legacy."""
    return {
        "version": "1",
        "legacy_versions": [],
        "router_prefix": "/api/v1/workspaces/{workspace_id}/feedback-intelligence",
        "resources": ["fields", "datasets", "sources", "feedbackRecords", "segments", "dashboards", "insights"],
        "delivery": "local-only",
    }


# ---------------------------------------------------------------------------
# FB-024: reusable field library
# ---------------------------------------------------------------------------


@router.get("/reserved-fields", operation_id="listFeedbackReservedFields")
def reserved_fields(principal: Principal = Depends(require(CONTACT_READ))):
    """FB-025: the system fields captured on every feedback record."""
    return [{"name": name, "description": description} for name, description in RESERVED_FIELDS]


@router.get("/fields", operation_id="listFeedbackLibraryFields")
def list_fields(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(FeedbackLibraryField).where(FeedbackLibraryField.workspace_id == workspace_id)
        .order_by(FeedbackLibraryField.key)
    ).scalars().all()
    return [field_out(row) for row in rows]


@router.post("/fields", status_code=status.HTTP_201_CREATED, operation_id="createFeedbackLibraryField")
def create_field(
    workspace_id: str,
    body: FieldCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(FeedbackLibraryField.id).where(
            FeedbackLibraryField.workspace_id == workspace_id,
            FeedbackLibraryField.key == body.key,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="library field key already exists")
    row = FeedbackLibraryField(
        id=new_id(), workspace_id=workspace_id, key=body.key, label=body.label,
        type=body.type, config=body.config, created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=FIELD_CREATED,
                  entity_id=row.id, payload={"key": row.key, "type": row.type},
                  actor_id=principal.user.id)
    db.commit()
    return field_out(row)


@router.patch("/fields/{field_id}", operation_id="updateFeedbackLibraryField")
def update_field(
    workspace_id: str,
    field_id: str,
    body: FieldPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _field_or_404(db, workspace_id, field_id)
    if body.label is not None:
        row.label = body.label
    if body.type is not None:
        row.type = body.type
    if body.config is not None:
        row.config = body.config
    row.updated_at = now()
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=FIELD_UPDATED,
                  entity_id=row.id, payload={"key": row.key, "label": row.label},
                  actor_id=principal.user.id)
    db.commit()
    return field_out(row)


@router.post("/surveys/{survey_id}/fields", status_code=status.HTTP_201_CREATED,
             operation_id="bindFeedbackSurveyField")
def bind_field(
    workspace_id: str,
    survey_id: str,
    body: FieldBind,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    field = _field_or_404(db, workspace_id, body.field_id)
    exists = db.execute(
        select(FeedbackSurveyField.id).where(
            FeedbackSurveyField.workspace_id == workspace_id,
            FeedbackSurveyField.survey_id == survey_id,
            FeedbackSurveyField.field_id == field.id,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="field already bound to this survey")
    row = FeedbackSurveyField(
        id=new_id(), workspace_id=workspace_id, survey_id=survey_id,
        field_id=field.id, position=body.position,
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=FIELD_BOUND,
                  entity_id=row.id, payload={"survey_id": survey_id, "field_key": field.key},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": row.id, "survey_id": survey_id, "field_id": field.id, "position": row.position}


@router.get("/surveys/{survey_id}/fields", operation_id="listFeedbackSurveyFields")
def survey_fields(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Effective fields: values are resolved live from the library, so one edit
    updates every survey that reuses the field (FB-024)."""
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    rows = db.execute(
        select(FeedbackSurveyField, FeedbackLibraryField).join(
            FeedbackLibraryField, FeedbackSurveyField.field_id == FeedbackLibraryField.id
        ).where(
            FeedbackSurveyField.workspace_id == workspace_id,
            FeedbackSurveyField.survey_id == survey_id,
        ).order_by(FeedbackSurveyField.position, FeedbackLibraryField.key)
    ).all()
    return [
        {
            "binding_id": binding.id, "field_id": field.id, "key": field.key,
            "label": field.label, "type": field.type, "config": field.config,
            "position": binding.position, "updated_at": field.updated_at.isoformat() if field.updated_at else None,
        }
        for binding, field in rows
    ]


@router.delete("/surveys/{survey_id}/fields/{field_id}", operation_id="unbindFeedbackSurveyField")
def unbind_field(
    workspace_id: str,
    survey_id: str,
    field_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(FeedbackSurveyField).where(
            FeedbackSurveyField.workspace_id == workspace_id,
            FeedbackSurveyField.survey_id == survey_id,
            FeedbackSurveyField.field_id == field_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="field binding not found")
    db.delete(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=FIELD_UNBOUND,
                  entity_id=field_id, payload={"survey_id": survey_id},
                  actor_id=principal.user.id)
    db.commit()
    return {"removed": True, "survey_id": survey_id, "field_id": field_id}


# ---------------------------------------------------------------------------
# FB-098 / FB-099: datasets and sources
# ---------------------------------------------------------------------------


@router.get("/datasets", operation_id="listFeedbackDatasets")
def list_datasets(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(FeedbackDataset).where(FeedbackDataset.workspace_id == workspace_id)
        .order_by(FeedbackDataset.key)
    ).scalars().all()
    return [dataset_out(row) for row in rows]


@router.post("/datasets", status_code=status.HTTP_201_CREATED, operation_id="createFeedbackDataset")
def create_dataset(
    workspace_id: str,
    body: DatasetCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(FeedbackDataset.id).where(
            FeedbackDataset.workspace_id == workspace_id, FeedbackDataset.key == body.key
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="feedback dataset key already exists")
    row = FeedbackDataset(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        description=body.description, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DATASET_CREATED,
                  entity_id=row.id, payload={"key": row.key}, actor_id=principal.user.id)
    db.commit()
    return dataset_out(row)


@router.get("/datasets/{dataset_id}/sources", operation_id="listFeedbackSources")
def list_sources(
    workspace_id: str,
    dataset_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _dataset_or_404(db, workspace_id, dataset_id)
    rows = db.execute(
        select(FeedbackSource).where(
            FeedbackSource.workspace_id == workspace_id, FeedbackSource.dataset_id == dataset_id
        ).order_by(FeedbackSource.key)
    ).scalars().all()
    return [source_out(row) for row in rows]


@router.post("/datasets/{dataset_id}/sources", status_code=status.HTTP_201_CREATED,
             operation_id="createFeedbackSource")
def create_source(
    workspace_id: str,
    dataset_id: str,
    body: SourceCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    _dataset_or_404(db, workspace_id, dataset_id)
    exists = db.execute(
        select(FeedbackSource.id).where(
            FeedbackSource.workspace_id == workspace_id,
            FeedbackSource.dataset_id == dataset_id,
            FeedbackSource.key == body.key,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="feedback source key already exists")
    row = FeedbackSource(
        id=new_id(), workspace_id=workspace_id, dataset_id=dataset_id, key=body.key,
        name=body.name, source_type=body.source_type, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=SOURCE_CREATED,
                  entity_id=row.id, payload={"key": row.key, "source_type": row.source_type},
                  actor_id=principal.user.id)
    db.commit()
    return source_out(row)


# ---------------------------------------------------------------------------
# FB-025 / FB-029 / FB-097 / FB-100: ingestion, reserved context, metadata
# ---------------------------------------------------------------------------


def _normalise_reserved(workspace_id: str, raw: dict) -> dict:
    captured = now().isoformat()
    reserved = {name: raw.get(name) for name, _ in RESERVED_FIELDS}
    # Timing is server-owned: a caller cannot back-date or spoof a response.
    reserved["timing"] = captured
    reserved["captured_at"] = captured
    # A client may add extra keys, but never override reserved names.
    for key, value in raw.items():
        if key not in RESERVED_NAMES and key not in ("captured_at", "timing"):
            reserved[key] = value
    return reserved


def _normalise_metadata(raw: dict) -> dict:
    return {
        "respondent_id": raw.get("respondent_id"),
        "locale": raw.get("locale"),
        "device": raw.get("device"),
        "referrer": raw.get("referrer"),
        "user_agent": raw.get("user_agent"),
        "captured_at": now().isoformat(),
    }


def _respondent_hash(workspace_id: str, metadata: dict, external_id: str | None) -> str:
    subject = metadata.get("respondent_id") or external_id or "anonymous"
    return hashlib.sha256(f"{workspace_id}:{subject}".encode("utf-8")).hexdigest()


@router.post("/datasets/{dataset_id}/records", status_code=status.HTTP_201_CREATED,
             operation_id="ingestFeedbackRecord")
def ingest_record(
    workspace_id: str,
    dataset_id: str,
    body: RecordIngest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """FB-097 ingest + FB-100 record creation in one local, audited operation."""
    verify_workspace(principal, workspace_id)
    _dataset_or_404(db, workspace_id, dataset_id)
    source = None
    source_id = (body.reserved or {}).get("source_id")
    if source_id:
        source = _source_or_404(db, workspace_id, source_id)
        if source.dataset_id != dataset_id:
            raise HTTPException(status_code=422, detail="source does not belong to this dataset")
    if source is None:
        source = db.execute(
            select(FeedbackSource).where(
                FeedbackSource.workspace_id == workspace_id,
                FeedbackSource.dataset_id == dataset_id,
            ).order_by(FeedbackSource.created_at, FeedbackSource.id)
        ).scalars().first()
        if source is None:
            raise HTTPException(status_code=422, detail="dataset has no feedback source; create one first")

    reserved = _normalise_reserved(workspace_id, body.reserved)
    metadata = _normalise_metadata(body.metadata)
    sentiment = body.sentiment or classify_sentiment(body.payload)
    row = FeedbackRecord(
        id=new_id(), workspace_id=workspace_id, dataset_id=dataset_id, source_id=source.id,
        external_id=body.external_id, payload=body.payload, reserved=reserved, context_metadata=metadata,
        respondent_hash=_respondent_hash(workspace_id, metadata, body.external_id),
        sentiment=sentiment, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=RECORD_INGESTED,
                  entity_id=row.id, payload={
                      "dataset_id": dataset_id, "source_id": source.id, "sentiment": sentiment,
                      "reserved_capture_claimed": False,
                  }, actor_id=principal.user.id)
    db.commit()
    return record_out(row)


@router.get("/datasets/{dataset_id}/records", operation_id="listFeedbackRecords")
def list_records(
    workspace_id: str,
    dataset_id: str,
    source_id: str | None = None,
    sentiment: str | None = None,
    external_id: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _dataset_or_404(db, workspace_id, dataset_id)
    query = select(FeedbackRecord).where(
        FeedbackRecord.workspace_id == workspace_id, FeedbackRecord.dataset_id == dataset_id
    )
    if source_id:
        query = query.where(FeedbackRecord.source_id == source_id)
    if sentiment:
        if sentiment not in SENTIMENTS:
            raise HTTPException(status_code=422, detail="unsupported sentiment")
        query = query.where(FeedbackRecord.sentiment == sentiment)
    if external_id:
        query = query.where(FeedbackRecord.external_id == external_id)
    rows = db.execute(query.order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id)).scalars().all()
    return [record_out(row) for row in rows]


@router.get("/records/{record_id}", operation_id="getFeedbackRecord")
def get_record(
    workspace_id: str,
    record_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return record_out(_record_or_404(db, workspace_id, record_id))


@router.patch("/records/{record_id}/sentiment", operation_id="setFeedbackRecordSentiment")
def set_sentiment(
    workspace_id: str,
    record_id: str,
    body: SentimentPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = _record_or_404(db, workspace_id, record_id)
    previous = row.sentiment
    row.sentiment = body.sentiment
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=SENTIMENT_SET,
                  entity_id=row.id, payload={"from": previous, "to": row.sentiment},
                  actor_id=principal.user.id)
    db.commit()
    return record_out(row)


@router.get("/datasets/{dataset_id}/metadata", operation_id="feedbackRespondentMetadata")
def respondent_metadata(
    workspace_id: str,
    dataset_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """FB-029: respondent context captured automatically at ingestion time."""
    verify_workspace(principal, workspace_id)
    _dataset_or_404(db, workspace_id, dataset_id)
    rows = db.execute(
        select(FeedbackRecord).where(
            FeedbackRecord.workspace_id == workspace_id, FeedbackRecord.dataset_id == dataset_id
        )
    ).scalars().all()
    grouped: dict[str, dict] = {}
    for row in rows:
        item = grouped.setdefault(row.respondent_hash, {
            "respondent_hash": row.respondent_hash, "record_count": 0, "metadata": row.context_metadata,
        })
        item["record_count"] += 1
    return sorted(grouped.values(), key=lambda item: item["respondent_hash"])


# ---------------------------------------------------------------------------
# FB-085: audience segments over real contact attributes
# ---------------------------------------------------------------------------


@router.get("/segments", operation_id="listFeedbackSegments")
def list_segments(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(FeedbackSegment).where(FeedbackSegment.workspace_id == workspace_id)
        .order_by(FeedbackSegment.key)
    ).scalars().all()
    return [segment_out(row) for row in rows]


@router.post("/segments", status_code=status.HTTP_201_CREATED, operation_id="createFeedbackSegment")
def create_segment(
    workspace_id: str,
    body: SegmentCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(FeedbackSegment.id).where(
            FeedbackSegment.workspace_id == workspace_id, FeedbackSegment.key == body.key
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="segment key already exists")
    row = FeedbackSegment(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        rules=body.rules, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=SEGMENT_CREATED,
                  entity_id=row.id, payload={"key": row.key, "rules": len(row.rules)},
                  actor_id=principal.user.id)
    db.commit()
    return segment_out(row)


@router.post("/segments/{segment_id}/evaluate", operation_id="evaluateFeedbackSegment")
def evaluate_segment(
    workspace_id: str,
    segment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    segment = _segment_or_404(db, workspace_id, segment_id)
    contacts = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.archived.is_(False))
    ).scalars().all()
    matched = [
        {"id": contact.id, "email": contact.email}
        for contact in contacts
        if all(_matches_rule(_contact_attributes(contact), rule) for rule in segment.rules)
    ]
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=SEGMENT_EVALUATED,
                  entity_id=segment.id, payload={"matched": len(matched)},
                  actor_id=principal.user.id)
    db.commit()
    return {
        "segment_id": segment.id, "key": segment.key,
        "evaluated": len(contacts), "matched_count": len(matched), "contacts": matched,
    }


# ---------------------------------------------------------------------------
# FB-096: dashboards and charts computed from stored records
# ---------------------------------------------------------------------------


@router.get("/dashboards", operation_id="listFeedbackDashboards")
def list_dashboards(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(FeedbackDashboard).where(FeedbackDashboard.workspace_id == workspace_id)
        .order_by(FeedbackDashboard.key)
    ).scalars().all()
    return [dashboard_out(row) for row in rows]


@router.post("/dashboards", status_code=status.HTTP_201_CREATED, operation_id="createFeedbackDashboard")
def create_dashboard(
    workspace_id: str,
    body: DashboardCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(FeedbackDashboard.id).where(
            FeedbackDashboard.workspace_id == workspace_id, FeedbackDashboard.key == body.key
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="dashboard key already exists")
    row = FeedbackDashboard(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        widgets=body.widgets, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DASHBOARD_CREATED,
                  entity_id=row.id, payload={"key": row.key, "widgets": len(row.widgets)},
                  actor_id=principal.user.id)
    db.commit()
    return dashboard_out(row)


@router.get("/dashboards/{dashboard_id}/data", operation_id="feedbackDashboardData")
def dashboard_data(
    workspace_id: str,
    dashboard_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    dashboard = _dashboard_or_404(db, workspace_id, dashboard_id)
    verify_workspace(principal, workspace_id)
    records = db.execute(
        select(FeedbackRecord).where(FeedbackRecord.workspace_id == workspace_id)
    ).scalars().all()
    sources = {
        row.id: row.name
        for row in db.execute(
            select(FeedbackSource).where(FeedbackSource.workspace_id == workspace_id)
        ).scalars().all()
    }
    results = []
    for widget in dashboard.widgets:
        scoped = [r for r in records if not widget.get("dataset_id") or r.dataset_id == widget["dataset_id"]]
        widget_type = widget.get("type")
        if widget_type == "count_by_source":
            counts = Counter(sources.get(r.source_id, r.source_id) for r in scoped)
            data = {"total": len(scoped), "by_source": dict(counts)}
        elif widget_type == "sentiment":
            data = {"total": len(scoped), "by_sentiment": dict(Counter(r.sentiment for r in scoped))}
        elif widget_type == "volume":
            by_day = Counter(r.created_at.date().isoformat() for r in scoped if r.created_at)
            data = {"total": len(scoped), "by_day": dict(by_day)}
        else:  # field distribution
            field = str(widget.get("field", ""))
            values = [str(r.payload.get(field)) for r in scoped if field in (r.payload or {})]
            data = {"field": field, "answered": len(values), "distribution": dict(Counter(values))}
        results.append({
            "id": widget.get("id"), "title": widget.get("title", widget.get("id")),
            "type": widget_type, "data": data,
        })
    return {
        "dashboard_id": dashboard.id, "widgets": results,
        "generated_at": now().isoformat(), "source_record_count": len(records),
    }


# ---------------------------------------------------------------------------
# FB-097: unified feedback insights across every source and dataset
# ---------------------------------------------------------------------------


@router.get("/unify/insights", operation_id="feedbackUnifiedInsights")
def unified_insights(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    records = db.execute(
        select(FeedbackRecord).where(FeedbackRecord.workspace_id == workspace_id)
    ).scalars().all()
    datasets = db.execute(
        select(FeedbackDataset).where(FeedbackDataset.workspace_id == workspace_id)
    ).scalars().all()
    sources = db.execute(
        select(FeedbackSource).where(FeedbackSource.workspace_id == workspace_id)
    ).scalars().all()
    source_types = {row.id: row.source_type for row in sources}
    dataset_names = {row.id: row.name for row in datasets}

    coverage = {
        name: sum(1 for r in records if r.reserved.get(name) not in (None, ""))
        for name, _ in RESERVED_FIELDS
    }
    return {
        "total_records": len(records),
        "dataset_count": len(datasets),
        "source_count": len(sources),
        "by_sentiment": dict(Counter(r.sentiment for r in records)),
        "by_source_type": dict(Counter(source_types.get(r.source_id, "unknown") for r in records)),
        "by_dataset": dict(Counter(dataset_names.get(r.dataset_id, r.dataset_id) for r in records)),
        "reserved_field_coverage": coverage,
        "generated_at": now().isoformat(),
    }
