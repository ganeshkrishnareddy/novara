"""Local experimentation delivery and refresh surface (GrowthBook P2 cluster).

Clean-room implementation of GB-071 (event webhooks), GB-072 (SDK webhooks),
GB-073 (global SDK webhooks), GB-074 (Slack-compatible notifier), GB-075 (CDN
cache purge), GB-076 (self-hosted proxy/cache), GB-081 (agenda-style local job
queue), GB-082 (experiment-result refresh) and GB-083 (metric refresh).

Every action is recorded in NOVARA's own workspace-scoped tables. No outbound
webhook, Slack call, CDN API, proxy fetch or external scheduler is contacted.
No GrowthBook source is copied.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .experiment_operations import TimeSeriesPoint
from .experiment_stats import ExperimentDefinition, ExperimentObservation

WEBHOOK_CREATED = "experiment.webhook_created"
WEBHOOK_EMITTED = "experiment.webhook_emitted"
NOTIFIER_CREATED = "experiment.notifier_created"
NOTIFIER_RECORDED = "experiment.notifier_recorded"
CACHE_STORED = "experiment.cache_stored"
CACHE_PURGED = "experiment.cache_purged"
PROXY_STORED = "experiment.proxy_stored"
PROXY_SERVED = "experiment.proxy_served"
REFRESH_SCHEDULED = "experiment.refresh_scheduled"
REFRESH_RUN = "experiment.refresh_run"
register_event_types(
    WEBHOOK_CREATED, WEBHOOK_EMITTED, NOTIFIER_CREATED, NOTIFIER_RECORDED,
    CACHE_STORED, CACHE_PURGED, PROXY_STORED, PROXY_SERVED,
    REFRESH_SCHEDULED, REFRESH_RUN,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-delivery",
    tags=["experiment-delivery"],
)

KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
WEBHOOK_SCOPES = frozenset({"event", "sdk", "global_sdk"})
REFRESH_TYPES = frozenset({"experiment_results", "metric"})


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _get(db, model, workspace_id, entity_id, label):
    row = db.execute(select(model).where(
        model.id == entity_id, model.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def _exists(db, model, workspace_id, key) -> bool:
    return db.execute(select(model.id).where(
        model.workspace_id == workspace_id, model.key == key
    )).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Tables (additive, workspace-scoped)
# ---------------------------------------------------------------------------


class ExperimentWebhook(Base):
    __tablename__ = "experiment_webhooks"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_webhook_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    target_label: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExperimentWebhookDelivery(Base):
    __tablename__ = "experiment_webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    webhook_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_webhooks.id"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="recorded_local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExperimentNotifierMessage(Base):
    __tablename__ = "experiment_notifier_messages"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_notifier_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExperimentCacheEntry(Base):
    __tablename__ = "experiment_cache_entries"
    __table_args__ = (UniqueConstraint("workspace_id", "cache_key", name="uq_experiment_cache_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentCachePurge(Base):
    __tablename__ = "experiment_cache_purges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    purged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExperimentProxySnapshot(Base):
    __tablename__ = "experiment_proxy_snapshots"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_proxy_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    stale_if_error: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExperimentRefreshJob(Base):
    __tablename__ = "experiment_refresh_jobs"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_refresh_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    last_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WebhookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    scope: str
    event_types: list[str] = Field(default_factory=list)
    target_label: str = Field(min_length=1, max_length=200)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("scope")
    @classmethod
    def _scope(cls, value):
        if value not in WEBHOOK_SCOPES:
            raise ValueError("unsupported webhook scope")
        return value


class WebhookEmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=1, max_length=80)
    payload: dict = Field(default_factory=dict)


class NotifierIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    channel: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    experiment_key: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class CacheIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cache_key: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)


class CachePurgeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefix: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=200)


class ProxyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    payload: dict = Field(default_factory=dict)
    stale_if_error: bool = True

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class ProxyServeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulate_error: bool = False


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    job_type: str
    target_key: str
    run_at: datetime | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("job_type")
    @classmethod
    def _type(cls, value):
        if value not in REFRESH_TYPES:
            raise ValueError("unsupported refresh job type")
        return value

    @field_validator("target_key")
    @classmethod
    def _target(cls, value):
        return _clean_key(value)


# ---------------------------------------------------------------------------
# Routes - contract, webhooks and notifier
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="experimentDeliveryContract")
def api_contract() -> dict:
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["webhooks", "webhookDeliveries", "notifierMessages", "cacheEntries",
                      "cachePurges", "proxySnapshots", "refreshJobs"],
        "webhook_scopes": sorted(WEBHOOK_SCOPES),
        "refresh_types": sorted(REFRESH_TYPES),
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-delivery",
        "external_calls": False,
    }


@router.get("/webhooks", operation_id="listExperimentWebhooks")
def list_webhooks(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentWebhook).where(
        ExperimentWebhook.workspace_id == workspace_id
    ).order_by(ExperimentWebhook.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "scope": r.scope,
             "event_types": r.event_types, "target_label": r.target_label,
             "enabled": r.enabled} for r in rows]


@router.post("/webhooks", status_code=status.HTTP_201_CREATED,
             operation_id="createExperimentWebhook")
def create_webhook(workspace_id: str, body: WebhookIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if _exists(db, ExperimentWebhook, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="webhook key already exists")
    row = ExperimentWebhook(id=new_id(), workspace_id=workspace_id, key=body.key,
                            name=body.name, scope=body.scope, event_types=body.event_types,
                            target_label=body.target_label, enabled=True, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, WEBHOOK_CREATED, row.id, {"scope": row.scope}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "scope": row.scope}


@router.post("/webhooks/{webhook_id}/emit", operation_id="emitExperimentWebhook")
def emit_webhook(workspace_id: str, webhook_id: str, body: WebhookEmitIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    hook = _get(db, ExperimentWebhook, workspace_id, webhook_id, "webhook")
    if not hook.enabled:
        raise HTTPException(status_code=422, detail="webhook is disabled")
    if hook.event_types and body.event_type not in hook.event_types:
        raise HTTPException(status_code=422, detail="event type is not subscribed")
    delivery = ExperimentWebhookDelivery(
        id=new_id(), workspace_id=workspace_id, webhook_id=hook.id, scope=hook.scope,
        event_type=body.event_type, payload=body.payload,
        status="recorded_local", created_at=now(),
    )
    db.add(delivery)
    db.flush()
    _audit(db, workspace_id, WEBHOOK_EMITTED, delivery.id,
           {"scope": hook.scope, "event_type": body.event_type}, principal)
    db.commit()
    return {"id": delivery.id, "scope": hook.scope, "event_type": body.event_type,
            "status": delivery.status}


@router.get("/webhooks/{webhook_id}/deliveries", operation_id="listExperimentWebhookDeliveries")
def list_deliveries(workspace_id: str, webhook_id: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    hook = _get(db, ExperimentWebhook, workspace_id, webhook_id, "webhook")
    rows = db.execute(select(ExperimentWebhookDelivery).where(
        ExperimentWebhookDelivery.workspace_id == workspace_id,
        ExperimentWebhookDelivery.webhook_id == hook.id,
    ).order_by(ExperimentWebhookDelivery.created_at)).scalars().all()
    return [{"id": r.id, "scope": r.scope, "event_type": r.event_type,
             "status": r.status} for r in rows]


@router.get("/notifier", operation_id="listExperimentNotifierMessages")
def list_messages(workspace_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentNotifierMessage).where(
        ExperimentNotifierMessage.workspace_id == workspace_id
    ).order_by(ExperimentNotifierMessage.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "channel": r.channel, "subject": r.subject,
             "experiment_key": r.experiment_key, "status": r.status} for r in rows]


@router.post("/notifier", status_code=status.HTTP_201_CREATED,
             operation_id="createExperimentNotifierMessage")
def create_message(workspace_id: str, body: NotifierIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if _exists(db, ExperimentNotifierMessage, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="notifier message key already exists")
    row = ExperimentNotifierMessage(
        id=new_id(), workspace_id=workspace_id, key=body.key, channel=body.channel,
        subject=body.subject, body=body.body, experiment_key=body.experiment_key,
        status="draft", created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, NOTIFIER_CREATED, row.id, {"channel": row.channel}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "channel": row.channel, "status": row.status}


@router.post("/notifier/{message_id}/record", operation_id="recordExperimentNotifierMessage")
def record_message(workspace_id: str, message_id: str,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, ExperimentNotifierMessage, workspace_id, message_id, "notifier message")
    row.status = "recorded_local"
    db.flush()
    _audit(db, workspace_id, NOTIFIER_RECORDED, row.id, {"channel": row.channel}, principal)
    db.commit()
    return {"id": row.id, "status": row.status, "external_delivery": False}


# ---------------------------------------------------------------------------
# Routes - local cache, proxy and refresh jobs
# ---------------------------------------------------------------------------


@router.get("/cache", operation_id="listExperimentCacheEntries")
def list_cache(workspace_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentCacheEntry).where(
        ExperimentCacheEntry.workspace_id == workspace_id
    ).order_by(ExperimentCacheEntry.cache_key)).scalars().all()
    return [{"id": r.id, "cache_key": r.cache_key, "version": r.version,
             "purged": r.purged_at is not None} for r in rows]


@router.post("/cache", status_code=status.HTTP_201_CREATED, operation_id="storeExperimentCacheEntry")
def store_cache(workspace_id: str, body: CacheIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(ExperimentCacheEntry).where(
        ExperimentCacheEntry.workspace_id == workspace_id,
        ExperimentCacheEntry.cache_key == body.cache_key,
    )).scalar_one_or_none()
    if row is None:
        row = ExperimentCacheEntry(id=new_id(), workspace_id=workspace_id,
                                   cache_key=body.cache_key, payload=body.payload,
                                   version=1, created_at=now())
        db.add(row)
    else:
        row.payload = body.payload
        row.version += 1
        row.purged_at = None
    db.flush()
    _audit(db, workspace_id, CACHE_STORED, row.id, {"cache_key": row.cache_key}, principal)
    db.commit()
    return {"id": row.id, "cache_key": row.cache_key, "version": row.version}


@router.post("/cache/purge", operation_id="purgeExperimentCache")
def purge_cache(workspace_id: str, body: CachePurgeIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentCacheEntry).where(
        ExperimentCacheEntry.workspace_id == workspace_id
    )).scalars().all()
    targets = [r for r in rows if r.cache_key.startswith(body.prefix) and r.purged_at is None]
    for row in targets:
        row.purged_at = now()
    purge = ExperimentCachePurge(
        id=new_id(), workspace_id=workspace_id, prefix=body.prefix,
        reason=body.reason, purged_count=len(targets), created_at=now(),
    )
    db.add(purge)
    db.flush()
    _audit(db, workspace_id, CACHE_PURGED, purge.id,
           {"prefix": body.prefix, "count": len(targets)}, principal)
    db.commit()
    return {"id": purge.id, "purged_count": len(targets), "external_cdn_call": False}


@router.get("/proxy", operation_id="listExperimentProxySnapshots")
def list_proxy(workspace_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentProxySnapshot).where(
        ExperimentProxySnapshot.workspace_id == workspace_id
    ).order_by(ExperimentProxySnapshot.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name,
             "stale_if_error": r.stale_if_error} for r in rows]


@router.post("/proxy", status_code=status.HTTP_201_CREATED,
             operation_id="storeExperimentProxySnapshot")
def store_proxy(workspace_id: str, body: ProxyIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if _exists(db, ExperimentProxySnapshot, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="proxy snapshot key already exists")
    row = ExperimentProxySnapshot(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        payload=body.payload, stale_if_error=body.stale_if_error, created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PROXY_STORED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "stale_if_error": row.stale_if_error}


@router.post("/proxy/{snapshot_id}/serve", operation_id="serveExperimentProxySnapshot")
def serve_proxy(workspace_id: str, snapshot_id: str, body: ProxyServeIn,
                principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, ExperimentProxySnapshot, workspace_id, snapshot_id, "proxy snapshot")
    source = "local_snapshot"
    if body.simulate_error:
        if not row.stale_if_error:
            raise HTTPException(status_code=503, detail="upstream error and stale-if-error is disabled")
        source = "local_stale_if_error"
    db.flush()
    _audit(db, workspace_id, PROXY_SERVED, row.id, {"source": source}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "source": source,
            "payload": row.payload, "external_fetch": False}


@router.get("/refresh-jobs", operation_id="listExperimentRefreshJobs")
def list_jobs(workspace_id: str,
              principal: Principal = Depends(require(CONTACT_READ)),
              db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentRefreshJob).where(
        ExperimentRefreshJob.workspace_id == workspace_id
    ).order_by(ExperimentRefreshJob.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "job_type": r.job_type,
             "target_key": r.target_key, "status": r.status,
             "last_result": r.last_result} for r in rows]


@router.post("/refresh-jobs", status_code=status.HTTP_201_CREATED,
             operation_id="scheduleExperimentRefreshJob")
def schedule_job(workspace_id: str, body: RefreshIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if _exists(db, ExperimentRefreshJob, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="refresh job key already exists")
    row = ExperimentRefreshJob(
        id=new_id(), workspace_id=workspace_id, key=body.key, job_type=body.job_type,
        target_key=body.target_key, run_at=body.run_at or now(), status="scheduled",
        created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, REFRESH_SCHEDULED, row.id,
           {"job_type": row.job_type, "target_key": row.target_key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "job_type": row.job_type,
            "target_key": row.target_key, "status": row.status}


@router.post("/refresh-jobs/{job_id}/run", operation_id="runExperimentRefreshJob")
def run_job(workspace_id: str, job_id: str,
            principal: Principal = Depends(require(NOTE_WRITE)),
            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    job = _get(db, ExperimentRefreshJob, workspace_id, job_id, "refresh job")
    if job.job_type == "experiment_results":
        ids = db.execute(select(ExperimentDefinition.id).where(
            ExperimentDefinition.workspace_id == workspace_id,
            ExperimentDefinition.key == job.target_key,
        )).scalars().all()
        observations = []
        if ids:
            observations = db.execute(select(ExperimentObservation).where(
                ExperimentObservation.workspace_id == workspace_id,
                ExperimentObservation.experiment_id.in_(ids),
            )).scalars().all()
        result = {
            "job_type": job.job_type, "experiment_key": job.target_key,
            "definition_count": len(ids), "observation_count": len(observations),
            "variants": sorted({r.variant for r in observations}),
        }
    else:
        points = db.execute(select(TimeSeriesPoint).where(
            TimeSeriesPoint.workspace_id == workspace_id,
            TimeSeriesPoint.experiment_key == job.target_key,
        )).scalars().all()
        result = {
            "job_type": job.job_type, "experiment_key": job.target_key,
            "point_count": len(points),
            "metric_keys": sorted({p.metric_key for p in points}),
            "total_sessions": sum(p.sessions for p in points),
        }
    job.status = "succeeded"
    job.last_result = result
    db.flush()
    _audit(db, workspace_id, REFRESH_RUN, job.id, {"job_type": job.job_type}, principal)
    db.commit()
    return {"id": job.id, "status": job.status, **result}
