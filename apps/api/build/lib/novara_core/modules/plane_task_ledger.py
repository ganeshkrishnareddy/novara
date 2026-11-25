"""Clean-room P2/P3 Plane local background-task ledger.

Documented/public behaviour implemented from scratch (no upstream source copied,
no external service contacted):

- PL-073: a finished local task leaves a durable, queryable result record.
- PL-076: notification-email generation is opt-in; the default install never
  sends and an explicit, authorized configuration is still local-only.
- PL-078: locally recorded webhook deliveries are signed, retried and auditable.
- PL-081: a work-item export completes and downloads workspace-scoped data.
- PL-082: a chart export reuses the same aggregate shown by the chart series
  endpoint, so the export cannot disagree with the display.
- PL-083: each page edit enqueues a version task that creates a retrievable
  version.
- PL-084: file asset metadata is created only after real local storage
  processing succeeds.
- PL-086: workspace seeding is idempotent and creates only expected defaults.

All new state lives in additive ``plt_*`` tables. Existing job, project, page,
storage and event records are referenced by id only and are never altered. The
shared durable ``jobs`` table provides execution; this module owns the local
task records and the workspace-scoped API surface.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Event, new_id, now
from ..permissions import EVENT_READ, WORKSPACE_MANAGE
from ..security import hash_token
from .jobs import enqueue_job, register_handler, run_pending_jobs
from .projects import ProjectItem, ProjectPage
from .storage import StoredFile

TASK_EVENT = "plane_task_ledger.changed"
register_event_types(TASK_EVENT)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/plane-tasks",
    tags=["plane-task-ledger"],
)

# Deliberately explicit: an installation never opts into outbound email by
# default, and this phrase is an authorization act, not a credential.
EMAIL_AUTHORIZATION = "EXPLICIT-LOCAL-AUTHORIZATION"
LOCAL_JOB_TYPES = (
    "plane.result",
    "plane.email.generate",
    "plane.webhook.deliver",
    "plane.export.work_items",
    "plane.export.chart",
    "plane.page.version",
    "plane.asset.process",
    "plane.workspace.seed",
)
SEED_DEFAULTS = {
    "result_retention": {"days": 30, "scope": "workspace"},
    "delivery_policy": {"transport": "local", "external_sends": False},
    "task_labels": {"values": ["background", "local", "auditable"]},
}
LOCAL_NOTES = (
    "Local clean-room task ledger. No broker, outbound email, outbound webhook "
    "or external service is contacted."
)


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class TaskResult(Base):
    __tablename__ = "plt_task_results"
    __table_args__ = (UniqueConstraint("workspace_id", "request_key", name="uq_plt_result_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmailPolicy(Base):
    __tablename__ = "plt_email_policies"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_plt_email_policy"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authorized_by: Mapped[str | None] = mapped_column(String(36))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmailDraft(Base):
    __tablename__ = "plt_email_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    dispatch_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="local_only")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookEndpoint(Base):
    __tablename__ = "plt_webhook_endpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_hint: Mapped[str] = mapped_column(String(300), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failures_before_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookDelivery(Base):
    __tablename__ = "plt_webhook_deliveries"
    __table_args__ = (UniqueConstraint("endpoint_id", "attempt", name="uq_plt_webhook_attempt"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("plt_webhook_endpoints.id"), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(30), nullable=False, default="hmac-sha256")
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LocalExport(Base):
    __tablename__ = "plt_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(30), nullable=False)
    export_format: Mapped[str] = mapped_column(String(10), nullable=False)
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PageVersion(Base):
    __tablename__ = "plt_page_versions"
    __table_args__ = (UniqueConstraint("page_id", "version", name="uq_plt_page_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("project_pages.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    editor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AssetProcessing(Base):
    __tablename__ = "plt_asset_processings"
    __table_args__ = (UniqueConstraint("file_id", name="uq_plt_asset_file"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("stored_files.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processed")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SeedDefault(Base):
    __tablename__ = "plt_seed_defaults"
    __table_args__ = (UniqueConstraint("workspace_id", "seed_key", name="uq_plt_seed_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    seed_key: Mapped[str] = mapped_column(String(80), nullable=False)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Local helpers shared by the display surface and the task handlers
# ---------------------------------------------------------------------------


def _payload_workspace(payload: dict) -> str:
    value = str(payload.get("workspace_id") or "").strip()
    if not value:
        raise ValueError("task payload requires workspace_id")
    return value


def chart_series(db: Session, workspace_id: str) -> list[dict]:
    """The one aggregate used by both the chart surface and chart exports."""
    rows = db.execute(
        select(Event.event_type, func.count())
        .where(
            Event.workspace_id == workspace_id,
            Event.event_type.notlike("job.%"),
            Event.event_type.notlike("plane_task_ledger.%"),
        )
        .group_by(Event.event_type)
        .order_by(Event.event_type)
    ).all()
    return [{"event_type": name, "count": count} for name, count in rows]


def _canonical_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _signature(secret_hash: str, canonical_payload: str) -> str:
    return hmac.new(
        bytes.fromhex(secret_hash), canonical_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _record_event(
    db: Session, workspace_id: str, entity_id: str, action: str, actor_id: str
) -> None:
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=TASK_EVENT,
        entity_id=entity_id,
        payload={"action": action},
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Local job handlers (registered on the shared durable queue)
# ---------------------------------------------------------------------------


def _handle_result(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("plane.result requires a JSON object result")
    request_key = str(payload.get("request_key") or "").strip()
    if not request_key:
        raise ValueError("plane.result requires a request_key")
    existing = db.execute(
        select(TaskResult).where(
            TaskResult.workspace_id == workspace_id,
            TaskResult.request_key == request_key,
        )
    ).scalar_one_or_none()
    if existing is None:
        row = TaskResult(
            id=new_id(),
            workspace_id=workspace_id,
            request_key=request_key,
            task_type=str(payload.get("task_type") or "local"),
            result=dict(result),
            created_by=str(payload.get("created_by") or workspace_id)[:36],
            created_at=now(),
        )
        db.add(row)
        db.flush()
    return {"request_key": request_key, "result": dict(result)}


def _handle_email_generate(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    policy = db.execute(
        select(EmailPolicy).where(EmailPolicy.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if policy is None or not policy.enabled or not policy.authorized_by:
        raise ValueError("notification email generation is not enabled and authorized")
    draft = EmailDraft(
        id=new_id(),
        workspace_id=workspace_id,
        recipient=str(payload.get("recipient") or "").strip(),
        subject=str(payload.get("subject") or "").strip(),
        body=str(payload.get("body") or ""),
        dispatch_mode="local_only",
        created_by=str(payload.get("created_by") or policy.authorized_by)[:36],
        created_at=now(),
    )
    if not draft.recipient or not draft.subject:
        raise ValueError("notification email generation requires recipient and subject")
    db.add(draft)
    db.flush()
    return {"draft_id": draft.id, "dispatch_mode": draft.dispatch_mode}


def _handle_webhook_deliver(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    endpoint_id = str(payload.get("endpoint_id") or "")
    endpoint = db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if endpoint is None:
        raise ValueError("webhook endpoint not found in this workspace")
    attempt = int(payload.get("attempt") or 0)
    if attempt < 1:
        raise ValueError("webhook attempt must be positive")
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    canonical = _canonical_payload(body)
    signature = _signature(endpoint.secret_hash, canonical)
    failed = attempt <= endpoint.failures_before_success
    max_attempts = max(1, min(10, int(payload.get("max_attempts") or 3)))
    outcome = "failed"
    error = None
    if not failed:
        outcome = "succeeded"
    elif attempt >= max_attempts:
        outcome = "dead_letter"
        error = "local retry budget exhausted"
    delivery = WebhookDelivery(
        id=new_id(),
        workspace_id=workspace_id,
        endpoint_id=endpoint.id,
        attempt=attempt,
        canonical_payload=canonical,
        signature=signature,
        algorithm="hmac-sha256",
        outcome=outcome,
        error=error,
        created_at=now(),
    )
    db.add(delivery)
    db.flush()
    if outcome == "failed":
        enqueue_job(
            db,
            workspace_id=workspace_id,
            job_type="plane.webhook.deliver",
            payload={
                "workspace_id": workspace_id,
                "endpoint_id": endpoint.id,
                "attempt": attempt + 1,
                "max_attempts": max_attempts,
                "body": body,
                "created_by": str(payload.get("created_by") or endpoint.created_by),
            },
            created_by=str(payload.get("created_by") or endpoint.created_by),
            idempotency_key=f"plt-webhook-{endpoint.id}-{attempt + 1}",
        )
    return {"attempt": attempt, "outcome": outcome, "signature": signature}


def _handle_work_item_export(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    export_format = str(payload.get("format") or "csv")
    if export_format not in {"csv", "json"}:
        raise ValueError("export format must be csv or json")
    items = db.execute(
        select(ProjectItem)
        .where(ProjectItem.workspace_id == workspace_id)
        .order_by(ProjectItem.id)
    ).scalars().all()
    rows = [[item.id, item.title, item.status, item.priority] for item in items]
    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["id", "title", "status", "priority"])
        writer.writerows(rows)
        content = buffer.getvalue()
        filename = "work-items.csv"
    else:
        content = json.dumps(
            [dict(zip(("id", "title", "status", "priority"), row)) for row in rows],
            indent=2,
            sort_keys=True,
        )
        filename = "work-items.json"
    export = LocalExport(
        id=new_id(),
        workspace_id=workspace_id,
        export_type="work_items",
        export_format=export_format,
        filename=filename,
        content=content,
        checksum_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        row_count=len(rows),
        created_by=str(payload.get("created_by") or workspace_id)[:36],
        created_at=now(),
    )
    db.add(export)
    db.flush()
    return {"export_id": export.id, "row_count": export.row_count}


def _handle_chart_export(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    series = chart_series(db, workspace_id)
    content = json.dumps(series, indent=2, sort_keys=True)
    export = LocalExport(
        id=new_id(),
        workspace_id=workspace_id,
        export_type="chart",
        export_format="json",
        filename="chart-series.json",
        content=content,
        checksum_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        row_count=len(series),
        created_by=str(payload.get("created_by") or workspace_id)[:36],
        created_at=now(),
    )
    db.add(export)
    db.flush()
    return {"export_id": export.id, "row_count": export.row_count}


def _handle_page_version(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    page_id = str(payload.get("page_id") or "")
    page = db.execute(
        select(ProjectPage).where(
            ProjectPage.id == page_id, ProjectPage.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if page is None:
        raise ValueError("page not found in this workspace")
    latest = db.execute(
        select(func.max(PageVersion.version)).where(PageVersion.page_id == page_id)
    ).scalar()
    version = int(latest or 0) + 1
    row = PageVersion(
        id=new_id(),
        workspace_id=workspace_id,
        page_id=page_id,
        version=version,
        title=page.title,
        body=page.body,
        editor_id=str(payload.get("editor_id") or page.author_id)[:36],
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return {"page_id": page_id, "version": version}


def _handle_asset_process(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    file_id = str(payload.get("file_id") or "")
    stored = db.execute(
        select(StoredFile).where(
            StoredFile.id == file_id,
            StoredFile.workspace_id == workspace_id,
            StoredFile.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if stored is None:
        raise ValueError("stored file not found in this workspace")
    data = Path(stored.storage_path).read_bytes()
    if len(data) != stored.size_bytes:
        raise ValueError("stored file size changed during processing")
    checksum = hashlib.sha256(data).hexdigest()
    if checksum != stored.checksum_sha256:
        raise ValueError("stored file checksum mismatch")
    row = AssetProcessing(
        id=new_id(),
        workspace_id=workspace_id,
        file_id=stored.id,
        status="processed",
        size_bytes=len(data),
        checksum_sha256=checksum,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return {"file_id": stored.id, "size_bytes": len(data)}


def _handle_workspace_seed(db: Session, payload: dict) -> dict:
    workspace_id = _payload_workspace(payload)
    existing = set(
        db.execute(
            select(SeedDefault.seed_key).where(SeedDefault.workspace_id == workspace_id)
        ).scalars().all()
    )
    created = []
    for key, values in sorted(SEED_DEFAULTS.items()):
        if key in existing:
            continue
        db.add(
            SeedDefault(
                id=new_id(),
                workspace_id=workspace_id,
                seed_key=key,
                values=dict(values),
                created_at=now(),
            )
        )
        created.append(key)
    db.flush()
    return {"created": created, "keys": sorted(SEED_DEFAULTS)}


register_handler("plane.result", _handle_result)
register_handler("plane.email.generate", _handle_email_generate)
register_handler("plane.webhook.deliver", _handle_webhook_deliver)
register_handler("plane.export.work_items", _handle_work_item_export)
register_handler("plane.export.chart", _handle_chart_export)
register_handler("plane.page.version", _handle_page_version)
register_handler("plane.asset.process", _handle_asset_process)
register_handler("plane.workspace.seed", _handle_workspace_seed)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ResultRequest(BaseModel):
    task_type: str
    result: dict = Field(default_factory=dict)
    request_key: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("task_type")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task_type must not be empty")
        return value[:80]


class ResultOut(BaseModel):
    request_key: str
    task_type: str
    result: dict
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class EmailPolicyIn(BaseModel):
    enabled: bool
    authorization: str | None = None
    authorized_by: str | None = None

    model_config = ConfigDict(extra="forbid")


class EmailPolicyOut(BaseModel):
    enabled: bool
    authorized_by: str | None
    authorized_at: object | None
    notes: str = (
        "The default install has no policy and sends nothing. Enabling requires "
        "an explicit authorization act and still only creates local drafts."
    )


class EmailDraftIn(BaseModel):
    recipient: str
    subject: str
    body: str = ""

    model_config = ConfigDict(extra="forbid")

    @field_validator("recipient", "subject")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("recipient and subject must not be empty")
        return value


class EmailDraftOut(BaseModel):
    id: str
    recipient: str
    subject: str
    body: str
    dispatch_mode: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class WebhookIn(BaseModel):
    name: str
    target_hint: str
    failures_before_success: int = Field(default=0, ge=0, le=8)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "target_hint")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name and target_hint must not be empty")
        return value


class WebhookOut(BaseModel):
    id: str
    name: str
    target_hint: str
    algorithm: str = "hmac-sha256"
    failures_before_success: int

    model_config = ConfigDict(from_attributes=True)


class WebhookCreatedOut(WebhookOut):
    signing_secret: str
    notes: str = "Shown once; only its hash is stored."


class WebhookDeliverIn(BaseModel):
    body: dict = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=10)

    model_config = ConfigDict(extra="forbid")


class DeliveryOut(BaseModel):
    endpoint_id: str
    attempt: int
    signature: str
    algorithm: str
    outcome: str
    error: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ExportIn(BaseModel):
    format: str = "csv"

    model_config = ConfigDict(extra="forbid")

    @field_validator("format")
    @classmethod
    def valid_format(cls, value: str) -> str:
        if value not in {"csv", "json"}:
            raise ValueError("format must be csv or json")
        return value


class ExportOut(BaseModel):
    id: str
    export_type: str
    export_format: str
    filename: str
    checksum_sha256: str
    row_count: int
    created_at: object
    notes: str = LOCAL_NOTES

    model_config = ConfigDict(from_attributes=True)


class VersionIn(BaseModel):
    editor_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class VersionOut(BaseModel):
    page_id: str
    version: int
    title: str
    body: str
    editor_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class AssetOut(BaseModel):
    file_id: str
    status: str
    size_bytes: int
    checksum_sha256: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SeedOut(BaseModel):
    seed_key: str
    values: dict
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class JobAccepted(BaseModel):
    job_id: str
    job_type: str
    status: str = "queued"
    notes: str = LOCAL_NOTES


class WorkerCycleOut(BaseModel):
    claimed: int
    succeeded: int
    retried: int
    dead_lettered: int
    notes: str = LOCAL_NOTES


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/jobs/run", response_model=WorkerCycleOut)
def run_local_cycle(
    workspace_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    worker_id: str | None = None,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> WorkerCycleOut:
    verify_workspace(principal, workspace_id)
    result = run_pending_jobs(
        db,
        worker_id=(worker_id or principal.user.id)[:80],
        limit=limit,
        job_types=list(LOCAL_JOB_TYPES),
        workspace_id=workspace_id,
    )
    db.commit()
    return WorkerCycleOut(**result)


@router.post("/results", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def create_result_task(
    workspace_id: str,
    body: ResultRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    request_key = (body.request_key or new_id()).strip()
    if len(request_key) > 120:
        raise HTTPException(status_code=422, detail="request_key is too long")
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.result",
        payload={
            "workspace_id": workspace_id,
            "task_type": body.task_type,
            "result": body.result,
            "request_key": request_key,
            "created_by": principal.user.id,
        },
        created_by=principal.user.id,
        idempotency_key=f"plt-result-{request_key}",
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/results/{request_key}", response_model=ResultOut)
def get_result(
    workspace_id: str,
    request_key: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> TaskResult:
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(TaskResult).where(
            TaskResult.workspace_id == workspace_id,
            TaskResult.request_key == request_key,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="task result not found")
    return row


@router.get("/email/policy", response_model=EmailPolicyOut)
def get_email_policy(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> EmailPolicyOut:
    verify_workspace(principal, workspace_id)
    policy = db.execute(
        select(EmailPolicy).where(EmailPolicy.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if policy is None:
        return EmailPolicyOut(enabled=False, authorized_by=None, authorized_at=None)
    return EmailPolicyOut(
        enabled=policy.enabled,
        authorized_by=policy.authorized_by,
        authorized_at=policy.authorized_at,
    )


@router.put("/email/policy", response_model=EmailPolicyOut)
def set_email_policy(
    workspace_id: str,
    body: EmailPolicyIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> EmailPolicyOut:
    verify_workspace(principal, workspace_id)
    if body.enabled and body.authorization != EMAIL_AUTHORIZATION:
        raise HTTPException(
            status_code=403, detail="opt-in email requires explicit authorization"
        )
    policy = db.execute(
        select(EmailPolicy).where(EmailPolicy.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if policy is None:
        policy = EmailPolicy(
            id=new_id(), workspace_id=workspace_id, updated_by=principal.user.id
        )
        db.add(policy)
    policy.enabled = body.enabled
    policy.authorized_by = (body.authorized_by or principal.user.id)[:36] if body.enabled else None
    policy.authorized_at = now() if body.enabled else None
    policy.updated_by = principal.user.id
    policy.updated_at = now()
    db.commit()
    return EmailPolicyOut(
        enabled=policy.enabled,
        authorized_by=policy.authorized_by,
        authorized_at=policy.authorized_at,
    )


@router.post("/email/drafts", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def create_email_draft(
    workspace_id: str,
    body: EmailDraftIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.email.generate",
        payload={
            "workspace_id": workspace_id,
            "recipient": body.recipient,
            "subject": body.subject,
            "body": body.body,
            "created_by": principal.user.id,
        },
        created_by=principal.user.id,
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/email/drafts", response_model=list[EmailDraftOut])
def list_email_drafts(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[EmailDraft]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(EmailDraft)
        .where(EmailDraft.workspace_id == workspace_id)
        .order_by(EmailDraft.created_at.desc())
        .limit(100)
    ).scalars().all()


@router.post("/webhooks", response_model=WebhookCreatedOut, status_code=status.HTTP_201_CREATED)
def create_webhook(
    workspace_id: str,
    body: WebhookIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> WebhookCreatedOut:
    verify_workspace(principal, workspace_id)
    secret = secrets.token_urlsafe(32)
    endpoint = WebhookEndpoint(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        target_hint=body.target_hint,
        secret_hash=hash_token(secret),
        failures_before_success=body.failures_before_success,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(endpoint)
    db.commit()
    return WebhookCreatedOut(
        id=endpoint.id,
        name=endpoint.name,
        target_hint=endpoint.target_hint,
        failures_before_success=endpoint.failures_before_success,
        signing_secret=secret,
    )


@router.get("/webhooks", response_model=list[WebhookOut])
def list_webhooks(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[WebhookEndpoint]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.workspace_id == workspace_id)
    ).scalars().all()


@router.post("/webhooks/{endpoint_id}/deliveries", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def deliver_webhook(
    workspace_id: str,
    endpoint_id: str,
    body: WebhookDeliverIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    endpoint = db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if endpoint is None:
        raise HTTPException(status_code=404, detail="webhook endpoint not found")
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.webhook.deliver",
        payload={
            "workspace_id": workspace_id,
            "endpoint_id": endpoint.id,
            "attempt": 1,
            "max_attempts": body.max_attempts,
            "body": body.body,
            "created_by": principal.user.id,
        },
        created_by=principal.user.id,
        idempotency_key=f"plt-webhook-{endpoint.id}-1-{new_id()[:8]}",
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/webhooks/{endpoint_id}/deliveries", response_model=list[DeliveryOut])
def list_deliveries(
    workspace_id: str,
    endpoint_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[WebhookDelivery]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.workspace_id == workspace_id,
            WebhookDelivery.endpoint_id == endpoint_id,
        ).order_by(WebhookDelivery.attempt)
    ).scalars().all()


@router.get("/charts/series")
def get_chart_series(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return {"workspace_id": workspace_id, "series": chart_series(db, workspace_id), "notes": LOCAL_NOTES}


@router.post("/exports/work-items", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def create_work_item_export(
    workspace_id: str,
    body: ExportIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.export.work_items",
        payload={
            "workspace_id": workspace_id,
            "format": body.format,
            "created_by": principal.user.id,
        },
        created_by=principal.user.id,
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.post("/exports/chart", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def create_chart_export(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.export.chart",
        payload={"workspace_id": workspace_id, "created_by": principal.user.id},
        created_by=principal.user.id,
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/exports", response_model=list[ExportOut])
def list_exports(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[LocalExport]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(LocalExport)
        .where(LocalExport.workspace_id == workspace_id)
        .order_by(LocalExport.created_at.desc())
        .limit(100)
    ).scalars().all()


def _export_or_404(db: Session, workspace_id: str, export_id: str) -> LocalExport:
    row = db.execute(
        select(LocalExport).where(
            LocalExport.id == export_id, LocalExport.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="export not found")
    return row


@router.get("/exports/{export_id}/download")
def download_export(
    workspace_id: str,
    export_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    verify_workspace(principal, workspace_id)
    row = _export_or_404(db, workspace_id, export_id)
    media = "text/csv; charset=utf-8" if row.export_format == "csv" else "application/json"
    return Response(
        content=row.content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
    )


@router.post("/pages/{page_id}/versions", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def create_page_version(
    workspace_id: str,
    page_id: str,
    body: VersionIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    page = db.execute(
        select(ProjectPage).where(
            ProjectPage.id == page_id, ProjectPage.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.page.version",
        payload={
            "workspace_id": workspace_id,
            "page_id": page_id,
            "editor_id": (body.editor_id or principal.user.id)[:36],
        },
        created_by=principal.user.id,
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/pages/{page_id}/versions", response_model=list[VersionOut])
def list_page_versions(
    workspace_id: str,
    page_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[PageVersion]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(PageVersion).where(
            PageVersion.workspace_id == workspace_id, PageVersion.page_id == page_id
        ).order_by(PageVersion.version)
    ).scalars().all()


@router.post("/assets/{file_id}/process", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def process_asset(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.asset.process",
        payload={"workspace_id": workspace_id, "file_id": file_id},
        created_by=principal.user.id,
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[AssetProcessing]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(AssetProcessing).where(AssetProcessing.workspace_id == workspace_id)
    ).scalars().all()


@router.post("/workspace/seed", response_model=JobAccepted, status_code=status.HTTP_201_CREATED)
def seed_workspace(
    workspace_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobAccepted:
    verify_workspace(principal, workspace_id)
    job = enqueue_job(
        db,
        workspace_id=workspace_id,
        job_type="plane.workspace.seed",
        payload={"workspace_id": workspace_id},
        created_by=principal.user.id,
        idempotency_key=f"plt-seed-{workspace_id}",
    )
    db.commit()
    return JobAccepted(job_id=job.id, job_type=job.job_type)


@router.get("/workspace/seed/defaults", response_model=list[SeedOut])
def list_seed_defaults(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[SeedDefault]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SeedDefault)
        .where(SeedDefault.workspace_id == workspace_id)
        .order_by(SeedDefault.seed_key)
    ).scalars().all()
