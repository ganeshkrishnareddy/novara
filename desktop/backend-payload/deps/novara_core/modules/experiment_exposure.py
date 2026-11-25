"""Exposure-event tracker adapters for experiments (GrowthBook P3 cluster).

Clean-room implementation of GB-134..GB-147: documented exposure-event paths
for Amplitude, CleverTap, Custom, Firebase, Freshpaint, FullStory, Heap, Jitsu,
Keen IO, Langfuse, mParticle, Arize Phoenix, Segment and Snowplow.

Every provider is a *local adapter*: a documented payload shape is normalised
into one workspace-scoped exposure row and published to NOVARA's shared event
spine. No vendor SDK, hosted API, browser script or outbound traffic is used or
claimed. Workspace admins can override the documented field paths with their
own dotted-path mappings (the "Custom" provider exists for this purpose), and
invalid payloads are logged instead of being silently dropped.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

TRACKER_CHANGED = "experiment.tracker_changed"
EXPOSURE_RECORDED = "experiment.exposure_recorded"
EXPOSURE_REJECTED = "experiment.exposure_rejected"
EXPOSURE_BATCH_INGESTED = "experiment.exposure_batch_ingested"
register_event_types(TRACKER_CHANGED, EXPOSURE_RECORDED, EXPOSURE_REJECTED, EXPOSURE_BATCH_INGESTED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-exposure",
    tags=["experiment-exposure"],
)

MAX_BATCH = 200
MAX_PAYLOAD_BYTES = 64_000
MAPPING_TARGETS = frozenset({"subject", "experiment", "variation", "occurred_at"})


@dataclass(frozen=True)
class TrackerSpec:
    key: str
    label: str
    documentation: str
    event_field: str | None
    event_values: frozenset[str]
    subject_fields: tuple[str, ...]
    properties_field: str | None
    experiment_fields: tuple[str, ...]
    variation_fields: tuple[str, ...]


def _spec(key, label, doc, event_field, event_values, subjects, props, experiments, variations):
    return TrackerSpec(
        key=key, label=label, documentation=doc, event_field=event_field,
        event_values=frozenset(event_values), subject_fields=tuple(subjects),
        properties_field=props, experiment_fields=tuple(experiments),
        variation_fields=tuple(variations),
    )


# Each entry documents a real provider's exposure-event vocabulary. Values are
# field *names* only; there is no upstream source, SDK code or hosted endpoint.
TRACKERS: dict[str, TrackerSpec] = {
    "amplitude": _spec(
        "amplitude", "Amplitude", "https://amplitude.com/docs",
        "event_type", ("$exposure", "experiment_viewed", "Exposure"),
        ("user_id", "device_id"), "event_properties",
        ("experiment_id", "experiment", "experimentId"),
        ("variation_id", "variant", "variationId"),
    ),
    "clevertap": _spec(
        "clevertap", "CleverTap", "https://developer.clevertap.com/docs",
        "event", ("Experiment Viewed", "experiment_viewed"),
        ("identity", "profileId", "userId"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "custom": _spec(
        "custom", "Custom", "local caller-written adapter",
        None, (), ("subject", "user_id"), None,
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "firebase": _spec(
        "firebase", "Firebase", "https://firebase.google.com/docs/analytics",
        "event", ("experiment_viewed", "exposure", "Experiment Viewed"),
        ("app_instance_id", "user_id", "userId"), "params",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "freshpaint": _spec(
        "freshpaint", "Freshpaint", "https://docs.freshpaint.io",
        "event", ("Experiment Viewed", "experiment_viewed"),
        ("anonymous_id", "user_id"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "fullstory": _spec(
        "fullstory", "FullStory", "https://developer.fullstory.com",
        "event", ("Experiment Viewed", "exposure", "experiment_viewed"),
        ("user_id", "uid"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "heap": _spec(
        "heap", "Heap", "https://developers.heap.io",
        "event", ("experiment_viewed", "Experiment Viewed"),
        ("identity", "user_id"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "jitsu": _spec(
        "jitsu", "Jitsu", "https://jitsu.com/docs",
        "event", ("experiment_viewed", "Experiment Viewed"),
        ("user_id", "anonymous_id"), "props",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "keenio": _spec(
        "keenio", "Keen IO", "https://keen.io/docs",
        "event_name", ("experiment_viewed", "Experiment Viewed"),
        ("keen.id", "user_id"), "keen.properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "langfuse": _spec(
        "langfuse", "Langfuse", "https://langfuse.com/docs",
        "name", ("experiment_viewed", "exposure"),
        ("user_id", "session_id"), "metadata",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "mparticle": _spec(
        "mparticle", "mParticle", "https://docs.mparticle.com",
        "event", ("experiment_viewed", "Experiment Viewed"),
        ("user_id", "mpid"), "attributes",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "arizephoenix": _spec(
        "arizephoenix", "Arize Phoenix", "https://docs.arize.com/phoenix",
        "event", ("experiment_viewed", "exposure"),
        ("user_id", "session_id"), "attributes",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "segment": _spec(
        "segment", "Segment", "https://segment.com/docs",
        "event", ("Experiment Viewed", "experiment_viewed"),
        ("userId", "anonymousId"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
    "snowplow": _spec(
        "snowplow", "Snowplow", "https://docs.snowplow.io",
        "event", ("experiment_viewed", "Experiment Viewed", "exposure"),
        ("user_id", "domain_userid"), "properties",
        ("experiment_id", "experiment"), ("variation_id", "variant"),
    ),
}


def _get_path(data: dict, dotted: str):
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_path(data: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    current = data
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _first(data: dict, paths: tuple[str, ...]):
    for path in paths:
        value = _get_path(data, path)
        if value not in (None, "", [], {}):
            return value
    return None


def sample_payload(key: str) -> dict:
    """Return a documented, locally verifiable sample for one provider path."""
    spec = TRACKERS[key]
    payload: dict = {}
    if spec.event_field:
        payload[spec.event_field] = sorted(spec.event_values)[0]
    for path in spec.subject_fields:
        _set_path(payload, path, "subject-123")
        break
    props: dict = {}
    for path in spec.experiment_fields:
        _set_path(props, path, "exp-1")
        break
    for path in spec.variation_fields:
        _set_path(props, path, "var-a")
        break
    if spec.properties_field:
        _set_path(payload, spec.properties_field, props)
    else:
        payload.update(props)
    return payload


# ---------------------------------------------------------------------------
# Additive, workspace-scoped tables
# ---------------------------------------------------------------------------


class ExposureTracker(Base):
    __tablename__ = "exposure_trackers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider_key", name="uq_exposure_tracker"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExposureFieldMapping(Base):
    __tablename__ = "exposure_field_mappings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "tracker_id", "source_field", name="uq_exposure_mapping"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    tracker_id: Mapped[str] = mapped_column(ForeignKey("exposure_trackers.id"), nullable=False, index=True)
    source_field: Mapped[str] = mapped_column(String(160), nullable=False)
    target_field: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class NormalizedExposure(Base):
    __tablename__ = "normalized_exposures"
    __table_args__ = (
        UniqueConstraint("workspace_id", "event_id", name="uq_normalized_exposure"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    tracker_id: Mapped[str] = mapped_column(ForeignKey("exposure_trackers.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    experiment_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    variation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExposureRejection(Base):
    __tablename__ = "exposure_rejections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExposureBatch(Base):
    __tablename__ = "exposure_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    tracker_id: Mapped[str] = mapped_column(ForeignKey("exposure_trackers.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TrackerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_key: str = Field(min_length=1, max_length=40)
    enabled: bool = True
    note: str = Field(default="", max_length=300)

    @field_validator("provider_key")
    @classmethod
    def _known(cls, value):
        if value not in TRACKERS:
            raise ValueError("unknown exposure tracker provider")
        return value


class TrackerUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    note: str = Field(default="", max_length=300)


class MappingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_field: str = Field(min_length=1, max_length=160)
    target_field: str = Field(min_length=1, max_length=40)

    @field_validator("target_field")
    @classmethod
    def _target(cls, value):
        if value not in MAPPING_TARGETS:
            raise ValueError("target_field must be subject, experiment, variation or occurred_at")
        return value


class ExposureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict = Field(min_length=1)
    event_id: str | None = Field(default=None, max_length=160)

    @field_validator("payload")
    @classmethod
    def _size(cls, value):
        if len(json.dumps(value, default=str)) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload too large")
        return value


class BatchItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict = Field(min_length=1)
    event_id: str | None = Field(default=None, max_length=160)


class BatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BatchItemIn] = Field(min_length=1, max_length=MAX_BATCH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _tracker(db, workspace_id, tracker_id) -> ExposureTracker:
    row = db.execute(select(ExposureTracker).where(
        ExposureTracker.id == tracker_id,
        ExposureTracker.workspace_id == workspace_id,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="exposure tracker not found")
    return row


def _mapping_overrides(db, workspace_id, tracker_id) -> dict[str, str]:
    rows = db.execute(select(ExposureFieldMapping).where(
        ExposureFieldMapping.workspace_id == workspace_id,
        ExposureFieldMapping.tracker_id == tracker_id,
    )).scalars().all()
    return {r.target_field: r.source_field for r in rows}


def _reject(db, workspace_id, provider_key, reason, payload, principal):
    db.add(ExposureRejection(id=new_id(), workspace_id=workspace_id,
                             provider_key=provider_key, reason=reason,
                             payload=payload, created_at=now()))
    db.flush()
    _audit(db, workspace_id, EXPOSURE_REJECTED, None,
           {"provider_key": provider_key, "reason": reason}, principal)


def _normalize(spec: TrackerSpec, overrides: dict[str, str], payload: dict) -> dict:
    """Map one provider payload to the shared exposure envelope, locally."""
    props = _get_path(payload, spec.properties_field) if spec.properties_field else None
    props = props if isinstance(props, dict) else {}
    if spec.event_field and spec.event_values:
        marker = _get_path(payload, spec.event_field)
        if marker not in spec.event_values:
            return {"error": "payload is not an exposure event for this provider"}

    def field(target, defaults):
        source = overrides.get(target)
        if source:
            value = _get_path(payload, source)
            if value not in (None, "", [], {}):
                return value, source
        for path in defaults:
            for scope in (props, payload):
                value = _get_path(scope, path)
                if value not in (None, "", [], {}):
                    return value, path
        return None, None

    subject, subject_path = field("subject", spec.subject_fields)
    experiment, experiment_path = field("experiment", spec.experiment_fields)
    variation, variation_path = field("variation", spec.variation_fields)
    if subject is None or experiment is None or variation is None:
        missing = [n for n, v in (("subject", subject), ("experiment", experiment),
                                  ("variation", variation)) if v is None]
        return {"error": "missing required exposure fields: " + ", ".join(missing)}

    occurred_at = now()
    time_source = overrides.get("occurred_at")
    if time_source:
        raw_time = _get_path(payload, time_source)
        if isinstance(raw_time, str):
            try:
                parsed = datetime.fromisoformat(raw_time)
                if parsed.tzinfo is not None:
                    occurred_at = parsed
            except ValueError:
                pass

    return {
        "subject": str(subject)[:160], "experiment_id": str(experiment)[:160],
        "variation_id": str(variation)[:160], "occurred_at": occurred_at,
        "mapped_from": {"subject": subject_path, "experiment": experiment_path,
                        "variation": variation_path},
        "delivery": "local-only",
    }


def _event_id(payload: dict, given: str | None, normalized: dict) -> str:
    if given:
        return given
    explicit = _get_path(payload, "event_id") or _get_path(payload, "id")
    if explicit:
        return str(explicit)[:160]
    # The generated key must be stable across retries: ingestion time is
    # intentionally excluded so the same payload deduplicates on replay.
    basis = "|".join((normalized["subject"], normalized["experiment_id"],
                      normalized["variation_id"],
                      json.dumps(payload, sort_keys=True, default=str)))
    return "sha256:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def _store(db, workspace_id, tracker, payload, given_event_id, principal):
    spec = TRACKERS[tracker.provider_key]
    overrides = _mapping_overrides(db, workspace_id, tracker.id)
    normalized = _normalize(spec, overrides, payload)
    if "error" in normalized:
        _reject(db, workspace_id, tracker.provider_key, normalized["error"], payload, principal)
        return {"status": "rejected", "reason": normalized["error"]}
    event_id = _event_id(payload, given_event_id, normalized)
    existing = db.execute(select(NormalizedExposure).where(
        NormalizedExposure.workspace_id == workspace_id,
        NormalizedExposure.event_id == event_id,
    )).scalar_one_or_none()
    if existing is not None:
        return {"status": "duplicate", "event_id": event_id, "exposure_id": existing.id}
    row = NormalizedExposure(
        id=new_id(), workspace_id=workspace_id, tracker_id=tracker.id,
        provider_key=tracker.provider_key, event_id=event_id,
        subject=normalized["subject"], experiment_id=normalized["experiment_id"],
        variation_id=normalized["variation_id"], occurred_at=normalized["occurred_at"],
        payload=payload, created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, EXPOSURE_RECORDED, row.id,
           {"provider_key": tracker.provider_key, "experiment_id": row.experiment_id,
            "variation_id": row.variation_id, "mapped_from": normalized["mapped_from"]},
           principal)
    return {"status": "accepted", "event_id": event_id, "exposure_id": row.id,
            "subject": row.subject, "experiment_id": row.experiment_id,
            "variation_id": row.variation_id}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="exposureContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "providers": sorted(TRACKERS), "max_batch": MAX_BATCH,
        "max_payload_bytes": MAX_PAYLOAD_BYTES, "mapping_targets": sorted(MAPPING_TARGETS),
        "external_calls": False, "external_delivery": False,
        "vendor_sdk_used": False, "generated_by": "local-adapter",
        "event_spine": EXPOSURE_RECORDED,
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-exposure",
    }


@router.get("/providers", operation_id="listExposureProviders")
def list_providers(principal: Principal = Depends(require(CONTACT_READ))) -> list[dict]:
    return [{"key": s.key, "label": s.label, "documentation": s.documentation,
             "event_field": s.event_field, "event_values": sorted(s.event_values),
             "subject_fields": list(s.subject_fields),
             "properties_field": s.properties_field,
             "experiment_fields": list(s.experiment_fields),
             "variation_fields": list(s.variation_fields),
             "vendor_sdk_used": False, "external_calls": False} for s in TRACKERS.values()]


@router.get("/providers/{key}/sample", operation_id="exposureProviderSample")
def provider_sample(key: str,
                    principal: Principal = Depends(require(CONTACT_READ))) -> dict:
    if key not in TRACKERS:
        raise HTTPException(status_code=404, detail="unknown exposure tracker provider")
    return {"provider_key": key, "payload": sample_payload(key),
            "note": "locally verifiable sample; no outbound traffic"}


@router.get("/trackers", operation_id="listExposureTrackers")
def list_trackers(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExposureTracker).where(
        ExposureTracker.workspace_id == workspace_id
    ).order_by(ExposureTracker.provider_key)).scalars().all()
    return [{"id": r.id, "provider_key": r.provider_key, "enabled": r.enabled,
             "note": r.note, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/trackers", status_code=status.HTTP_201_CREATED,
             operation_id="createExposureTracker")
def create_tracker(workspace_id: str, body: TrackerIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(select(ExposureTracker.id).where(
        ExposureTracker.workspace_id == workspace_id,
        ExposureTracker.provider_key == body.provider_key,
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="tracker already configured for this provider")
    row = ExposureTracker(id=new_id(), workspace_id=workspace_id,
                          provider_key=body.provider_key, enabled=body.enabled,
                          note=body.note, created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, TRACKER_CHANGED, row.id,
           {"provider_key": row.provider_key, "enabled": row.enabled}, principal)
    db.commit()
    return {"id": row.id, "provider_key": row.provider_key, "enabled": row.enabled,
            "note": row.note}


@router.put("/trackers/{tracker_id}", operation_id="updateExposureTracker")
def update_tracker(workspace_id: str, tracker_id: str, body: TrackerUpdateIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _tracker(db, workspace_id, tracker_id)
    row.enabled = body.enabled
    row.note = body.note
    db.flush()
    _audit(db, workspace_id, TRACKER_CHANGED, row.id,
           {"provider_key": row.provider_key, "enabled": row.enabled}, principal)
    db.commit()
    return {"id": row.id, "provider_key": row.provider_key, "enabled": row.enabled}


@router.get("/trackers/{tracker_id}/mappings", operation_id="listExposureMappings")
def list_mappings(workspace_id: str, tracker_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _tracker(db, workspace_id, tracker_id)
    rows = db.execute(select(ExposureFieldMapping).where(
        ExposureFieldMapping.workspace_id == workspace_id,
        ExposureFieldMapping.tracker_id == tracker_id,
    ).order_by(ExposureFieldMapping.target_field)).scalars().all()
    return [{"id": r.id, "source_field": r.source_field,
             "target_field": r.target_field} for r in rows]


@router.put("/trackers/{tracker_id}/mappings", operation_id="setExposureMapping")
def set_mapping(workspace_id: str, tracker_id: str, body: MappingIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _tracker(db, workspace_id, tracker_id)
    row = db.execute(select(ExposureFieldMapping).where(
        ExposureFieldMapping.workspace_id == workspace_id,
        ExposureFieldMapping.tracker_id == tracker_id,
        ExposureFieldMapping.source_field == body.source_field,
    )).scalar_one_or_none()
    if row is None:
        row = ExposureFieldMapping(id=new_id(), workspace_id=workspace_id,
                                   tracker_id=tracker_id,
                                   source_field=body.source_field,
                                   target_field=body.target_field, created_at=now())
        db.add(row)
    else:
        row.target_field = body.target_field
    db.flush()
    _audit(db, workspace_id, TRACKER_CHANGED, tracker_id,
           {"source_field": body.source_field, "target_field": body.target_field}, principal)
    db.commit()
    return {"source_field": row.source_field, "target_field": row.target_field}


@router.post("/trackers/{tracker_id}/exposures", status_code=status.HTTP_201_CREATED,
             operation_id="ingestExposure")
def ingest_exposure(workspace_id: str, tracker_id: str, body: ExposureIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    tracker = _tracker(db, workspace_id, tracker_id)
    if not tracker.enabled:
        raise HTTPException(status_code=409, detail="exposure tracker is disabled")
    result = _store(db, workspace_id, tracker, body.payload, body.event_id, principal)
    db.commit()
    if result["status"] == "rejected":
        raise HTTPException(status_code=422, detail=result["reason"])
    return result


@router.post("/trackers/{tracker_id}/exposures/batch", status_code=status.HTTP_201_CREATED,
             operation_id="ingestExposureBatch")
def ingest_batch(workspace_id: str, tracker_id: str, body: BatchIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    tracker = _tracker(db, workspace_id, tracker_id)
    if not tracker.enabled:
        raise HTTPException(status_code=409, detail="exposure tracker is disabled")
    results = [_store(db, workspace_id, tracker, item.payload, item.event_id, principal)
               for item in body.items]
    counts = {state: sum(1 for r in results if r["status"] == state)
              for state in ("accepted", "duplicate", "rejected")}
    batch = ExposureBatch(id=new_id(), workspace_id=workspace_id, tracker_id=tracker_id,
                          provider_key=tracker.provider_key, total=len(results),
                          accepted=counts["accepted"], duplicates=counts["duplicate"],
                          rejected=counts["rejected"], created_by=principal.user.id,
                          created_at=now())
    db.add(batch)
    db.flush()
    _audit(db, workspace_id, EXPOSURE_BATCH_INGESTED, batch.id,
           {"provider_key": tracker.provider_key, **counts}, principal)
    db.commit()
    return {"batch_id": batch.id, "total": batch.total, "accepted": batch.accepted,
            "duplicates": batch.duplicates, "rejected": batch.rejected,
            "results": results}


@router.get("/exposures", operation_id="listNormalizedExposures")
def list_exposures(workspace_id: str,
                   provider_key: str | None = Query(default=None),
                   experiment_id: str | None = Query(default=None),
                   limit: int = Query(default=100, ge=1, le=500),
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    stmt = select(NormalizedExposure).where(NormalizedExposure.workspace_id == workspace_id)
    if provider_key:
        stmt = stmt.where(NormalizedExposure.provider_key == provider_key)
    if experiment_id:
        stmt = stmt.where(NormalizedExposure.experiment_id == experiment_id)
    rows = db.execute(stmt.order_by(NormalizedExposure.created_at.desc()).limit(limit)).scalars().all()
    return [{"id": r.id, "provider_key": r.provider_key, "event_id": r.event_id,
             "subject": r.subject, "experiment_id": r.experiment_id,
             "variation_id": r.variation_id, "occurred_at": r.occurred_at.isoformat(),
             "delivery": "local-only"} for r in rows]


@router.get("/exposures/stats", operation_id="exposureStats")
def exposure_stats(workspace_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    by_provider = db.execute(
        select(NormalizedExposure.provider_key, func.count(NormalizedExposure.id)).where(
            NormalizedExposure.workspace_id == workspace_id
        ).group_by(NormalizedExposure.provider_key)
    ).all()
    by_experiment = db.execute(
        select(NormalizedExposure.experiment_id, func.count(NormalizedExposure.id)).where(
            NormalizedExposure.workspace_id == workspace_id
        ).group_by(NormalizedExposure.experiment_id)
    ).all()
    return {"total": sum(c for _, c in by_provider),
            "by_provider": {k: c for k, c in by_provider},
            "by_experiment": {k: c for k, c in by_experiment},
            "external_calls": False}


@router.get("/experiments/{experiment_id}/exposures", operation_id="experimentExposures")
def experiment_exposures(workspace_id: str, experiment_id: str,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> list[dict]:
    return list_exposures(workspace_id, None, experiment_id, 500, principal, db)


@router.get("/rejections", operation_id="listExposureRejections")
def list_rejections(workspace_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExposureRejection).where(
        ExposureRejection.workspace_id == workspace_id
    ).order_by(ExposureRejection.created_at.desc()).limit(100)).scalars().all()
    return [{"id": r.id, "provider_key": r.provider_key, "reason": r.reason,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/batches", operation_id="listExposureBatches")
def list_batches(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExposureBatch).where(
        ExposureBatch.workspace_id == workspace_id
    ).order_by(ExposureBatch.created_at.desc()).limit(100)).scalars().all()
    return [{"id": r.id, "provider_key": r.provider_key, "total": r.total,
             "accepted": r.accepted, "duplicates": r.duplicates, "rejected": r.rejected,
             "created_at": r.created_at.isoformat()} for r in rows]
