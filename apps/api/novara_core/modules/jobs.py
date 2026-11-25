"""Durable background job queue with retry, backoff and dead-letter handling.

Jobs execute only registered *local* handlers (notification creation, metric
aggregation, no-op). A handler never sends an external message and never calls
an external provider. Every state change is published through the shared event
log, so the queue is auditable and recoverable after a worker crash.

Design notes:
- One Job row is the source of truth; the event log is append-only audit.
- A repeated idempotency key inside a workspace returns the original job.
- Claim uses ``SELECT ... FOR UPDATE SKIP_LOCKED`` where the database supports
  it (PostgreSQL). SQLite serialises writes, so the same code is safe there too.
- Handler execution runs in a SAVEPOINT so a partial failure never leaks writes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, SessionLocal, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Notification, new_id, now
from ..permissions import EVENT_READ, WORKSPACE_MANAGE

JOB_QUEUED = "job.queued"
JOB_STARTED = "job.started"
JOB_COMPLETED = "job.completed"
JOB_FAILED = "job.failed"
JOB_RETRIED = "job.retried"
JOB_DEAD_LETTER = "job.dead_letter"
JOB_CANCELLED = "job.cancelled"
JOB_RECOVERED = "job.recovered"
MESSAGE_FAILED = "message.failed"
register_event_types(
    JOB_QUEUED,
    JOB_STARTED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_RETRIED,
    JOB_DEAD_LETTER,
    JOB_CANCELLED,
    JOB_RECOVERED,
    MESSAGE_FAILED,
)

JOB_STATUSES = frozenset(
    {"queued", "running", "succeeded", "dead_letter", "cancelled"}
)
JOB_NOTES = (
    "Jobs execute only registered local handlers. No external message is sent "
    "and no external provider is called."
)

# NV-051: one documented policy per delivery layer. There is deliberately no
# provider retry layer because the provider adapters are local mocks; retrying
# them would fabricate additional delivery attempts.
RETRY_POLICIES = {
    "local_job": {
        "layer": "local job queue",
        "implemented": True,
        "attempts": "max_attempts (1-10), default 3",
        "backoff": "retry_delay_seconds * 2 ** (attempts - 1)",
        "detail": "Job rows are the source of truth; every transition is audited.",
    },
    "provider": {
        "layer": "external provider send",
        "implemented": False,
        "attempts": "1 (no retry)",
        "backoff": "none",
        "detail": "All adapters are local mocks. Nothing is sent, so nothing is retried or reported delivered.",
    },
    "webhook": {
        "layer": "outbound webhook delivery",
        "implemented": False,
        "attempts": "0 (no dispatcher in this build)",
        "backoff": "none",
        "detail": "No outbound webhook endpoint is configured or called.",
    },
}


def retry_policies() -> dict:
    """Return a copy of the documented per-layer retry policy (NV-051)."""
    return {name: dict(policy) for name, policy in RETRY_POLICIES.items()}

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/jobs",
    tags=["jobs"],
)


# --------------------------------------------------------------------------
# Table
# --------------------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # A null idempotency key is allowed many times by SQL unique semantics.
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_job_workspace_idempotency"),
        Index("ix_job_queue", "status", "run_at"),
        Index("ix_job_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageFailure(Base):
    """A real failed local message attempt linked to its job (NV-052).

    There is no delivery DLQ upstream: this is a queryable local failure record
    only, and it never claims that a provider accepted a message.
    """

    __tablename__ = "message_failures"
    __table_args__ = (
        Index("ix_message_failures_workspace", "workspace_id", "channel"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="in_app")
    subscriber_id: Mapped[str | None] = mapped_column(String(100))
    transaction_id: Mapped[str] = mapped_column(String(120), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Local handler registry
# --------------------------------------------------------------------------

Handler = Callable[[Session, dict], dict]
_HANDLERS: dict[str, Handler] = {}


def register_handler(name: str, handler: Handler) -> None:
    """Register a deterministic, local job handler by name."""
    if not name.strip():
        raise ValueError("handler name must not be empty")
    _HANDLERS[name] = handler


def handler_names() -> list[str]:
    return sorted(_HANDLERS)


def _handle_notification(db: Session, payload: dict) -> dict:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("notification.create requires a non-empty message")
    workspace_id = str(payload.get("workspace_id", ""))
    if not workspace_id:
        raise ValueError("notification.create requires workspace_id in its payload")
    user_id = payload.get("user_id")
    row = Notification(
        id=new_id(),
        workspace_id=workspace_id,
        user_id=str(user_id) if user_id else None,
        contact_id=None,
        message=message[:500],
        read=False,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return {"notification_id": row.id}


def _handle_metrics(db: Session, payload: dict) -> dict:
    # Real local aggregates; no network and no fabricated numbers.
    from ..models import Contact, Lead, Task

    workspace_id = str(payload.get("workspace_id", ""))
    if not workspace_id:
        raise ValueError("metrics.refresh requires workspace_id in its payload")
    contacts = db.execute(
        select(func.count()).select_from(Contact).where(Contact.workspace_id == workspace_id)
    ).scalar()
    leads = db.execute(
        select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id)
    ).scalar()
    open_tasks = db.execute(
        select(func.count()).select_from(Task).where(
            Task.workspace_id == workspace_id, Task.status == "open"
        )
    ).scalar()
    return {"contacts": contacts, "leads": leads, "open_tasks": open_tasks}


def _handle_noop(db: Session, payload: dict) -> dict:
    return {"ok": True}


def _document_conversion_actor(db: Session, workspace_id: str) -> str:
    """Use a real workspace owner as the audit actor when none is supplied."""
    from ..models import WorkspaceMember

    owner_id = db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == "owner",
            WorkspaceMember.status == "active",
        ).order_by(WorkspaceMember.created_at).limit(1)
    ).scalar()
    return str(owner_id or workspace_id)[:36]


def _handle_document_conversion(db: Session, payload: dict) -> dict:
    """Run the shared local conversion code from a durable document job (PM-123)."""
    for key in ("workspace_id", "source_file_id", "target_format"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"document_conversion requires a non-empty {key} in its payload")
    # Lazy import: storage owns the conversion code and imports the shared
    # contracts, not the job registry. Importing here also avoids a cycle.
    from .storage import run_document_conversion

    workspace_id = payload["workspace_id"].strip()
    converted = run_document_conversion(
        db,
        workspace_id=workspace_id,
        source_file_id=payload["source_file_id"].strip(),
        target_format=payload["target_format"].strip(),
        actor_id=str(payload.get("actor_id") or _document_conversion_actor(db, workspace_id)),
    )
    return {
        "job_id": converted.id,
        "status": converted.status,
        "result_file_id": converted.result_file_id,
    }


register_handler("notification.create", _handle_notification)
register_handler("metrics.refresh", _handle_metrics)
register_handler("noop", _handle_noop)
register_handler("document_conversion", _handle_document_conversion)


# --------------------------------------------------------------------------
# Queue operations
# --------------------------------------------------------------------------


def enqueue_job(
    db: Session,
    *,
    workspace_id: str,
    job_type: str,
    payload: dict | None = None,
    created_by: str,
    max_attempts: int = 3,
    retry_delay_seconds: int = 60,
    run_at: datetime | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> Job:
    """Create a queued job. A repeated idempotency key returns the first job."""
    if not job_type.strip():
        raise ValueError("job_type must not be empty")
    if max_attempts < 1 or max_attempts > 10:
        raise ValueError("max_attempts must be between 1 and 10")
    if retry_delay_seconds < 1 or retry_delay_seconds > 86400:
        raise ValueError("retry_delay_seconds must be between 1 and 86400")

    if idempotency_key:
        existing = db.execute(
            select(Job).where(
                Job.workspace_id == workspace_id,
                Job.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    job = Job(
        id=new_id(),
        workspace_id=workspace_id,
        job_type=job_type.strip(),
        payload=dict(payload or {}),
        status="queued",
        attempts=0,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        run_at=run_at or now(),
        locked_at=None,
        locked_by=None,
        last_error=None,
        result=None,
        correlation_id=correlation_id or new_id(),
        idempotency_key=idempotency_key,
        created_by=created_by,
        created_at=now(),
        finished_at=None,
    )
    db.add(job)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=JOB_QUEUED,
        entity_id=job.id,
        payload={"job_type": job.job_type, "max_attempts": max_attempts},
        correlation_id=job.correlation_id,
        actor_id=created_by,
    )
    return job


def _job_or_404(db: Session, workspace_id: str, job_id: str) -> Job:
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


def claim_job(
    db: Session,
    *,
    worker_id: str,
    job_types: list[str] | None = None,
    workspace_id: str | None = None,
) -> Job | None:
    """Atomically claim one due queued job for a worker.

    A workspace-scoped caller must pass ``workspace_id`` so a job type shared by
    two workspaces cannot be claimed across the boundary. Direct internal
    callers may omit it to keep the historical global-worker behaviour.
    """
    query = select(Job).where(Job.status == "queued", Job.run_at <= now())
    if workspace_id is not None:
        query = query.where(Job.workspace_id == workspace_id)
    if job_types:
        query = query.where(Job.job_type.in_(job_types))
    query = (
        query.order_by(Job.run_at, Job.created_at)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(query).scalars().first()
    if job is None:
        return None
    job.status = "running"
    job.locked_at = now()
    job.locked_by = worker_id
    db.flush()
    publish_event(
        db,
        workspace_id=job.workspace_id,
        event_type=JOB_STARTED,
        entity_id=job.id,
        payload={"job_type": job.job_type, "worker_id": worker_id, "attempt": job.attempts + 1},
        correlation_id=job.correlation_id,
    )
    return job


def complete_job(db: Session, job: Job, result: dict) -> Job:
    job.status = "succeeded"
    job.result = dict(result)
    job.last_error = None
    job.locked_at = None
    job.locked_by = None
    job.finished_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=job.workspace_id,
        event_type=JOB_COMPLETED,
        entity_id=job.id,
        payload={"job_type": job.job_type, "attempts": job.attempts + 1},
        correlation_id=job.correlation_id,
    )
    return job


def fail_job(db: Session, job: Job, error: str, *, permanent: bool = False) -> Job:
    """Fail a job: retry with exponential backoff or send it to dead-letter."""
    job.attempts += 1
    job.last_error = error[:1000]
    job.locked_at = None
    job.locked_by = None
    if permanent or job.attempts >= job.max_attempts:
        job.status = "dead_letter"
        job.finished_at = now()
        publish_event(
            db,
            workspace_id=job.workspace_id,
            event_type=JOB_DEAD_LETTER,
            entity_id=job.id,
            payload={
                "job_type": job.job_type,
                "attempts": job.attempts,
                "error": job.last_error,
            },
            correlation_id=job.correlation_id,
        )
    else:
        delay = job.retry_delay_seconds * (2 ** (job.attempts - 1))
        job.status = "queued"
        job.run_at = now() + timedelta(seconds=delay)
        publish_event(
            db,
            workspace_id=job.workspace_id,
            event_type=JOB_RETRIED,
            entity_id=job.id,
            payload={
                "job_type": job.job_type,
                "attempts": job.attempts,
                "next_delay_seconds": delay,
            },
            correlation_id=job.correlation_id,
        )
    # Message-level failure records only exist when the job payload really
    # describes a message. No provider success is inferred from a failure.
    if job.payload.get("message") or job.payload.get("channel"):
        failure = MessageFailure(
            id=new_id(),
            workspace_id=job.workspace_id,
            job_id=job.id,
            channel=str(job.payload.get("channel") or "in_app"),
            subscriber_id=(
                job.payload.get("user_id") or job.payload.get("subscriber_id")
            ),
            transaction_id=str(job.payload.get("transaction_id") or job.id),
            error=error[:1000],
            correlation_id=job.correlation_id,
            created_at=now(),
        )
        db.add(failure)
        db.flush()
        publish_event(
            db,
            workspace_id=job.workspace_id,
            event_type=MESSAGE_FAILED,
            entity_id=failure.id,
            payload={
                "channel": failure.channel,
                "transaction_id": failure.transaction_id,
                "error": failure.error,
                "job_id": job.id,
            },
            correlation_id=job.correlation_id,
        )
    db.flush()
    return job


def run_one_job(
    db: Session,
    *,
    worker_id: str,
    job_types: list[str] | None = None,
    workspace_id: str | None = None,
) -> Job | None:
    """Claim and execute one job. Never raises for handler failures."""
    job = claim_job(
        db,
        worker_id=worker_id,
        job_types=job_types,
        workspace_id=workspace_id,
    )
    if job is None:
        return None
    handler = _HANDLERS.get(job.job_type)
    if handler is None:
        fail_job(
            db,
            job,
            f"no local handler registered for job_type: {job.job_type}",
            permanent=True,
        )
        return job
    try:
        with db.begin_nested():
            result = handler(db, job.payload)
    except Exception as exc:  # noqa: BLE001 - handler errors are job failures
        fail_job(db, job, f"{type(exc).__name__}: {exc}")
    else:
        complete_job(db, job, result)
    return job


def run_pending_jobs(
    db: Session,
    *,
    worker_id: str,
    limit: int = 10,
    job_types: list[str] | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Run up to ``limit`` due jobs and report exact outcomes."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    summary = {"claimed": 0, "succeeded": 0, "retried": 0, "dead_lettered": 0}
    for _ in range(limit):
        job = run_one_job(
            db,
            worker_id=worker_id,
            job_types=job_types,
            workspace_id=workspace_id,
        )
        if job is None:
            break
        summary["claimed"] += 1
        if job.status == "succeeded":
            summary["succeeded"] += 1
        elif job.status == "dead_letter":
            summary["dead_lettered"] += 1
        else:
            summary["retried"] += 1
    return summary


def recover_stale_jobs(db: Session, *, stale_after_seconds: int = 300) -> int:
    """Requeue jobs left 'running' by a crashed worker (no attempt consumed)."""
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be positive")
    cutoff = now() - timedelta(seconds=stale_after_seconds)
    stale = db.execute(
        select(Job).where(
            Job.status == "running",
            Job.locked_at.is_not(None),
            Job.locked_at <= cutoff,
        )
    ).scalars().all()
    for job in stale:
        job.status = "queued"
        job.locked_at = None
        job.locked_by = None
        job.run_at = now()
        publish_event(
            db,
            workspace_id=job.workspace_id,
            event_type=JOB_RECOVERED,
            entity_id=job.id,
            payload={"job_type": job.job_type, "previous_worker": job.locked_by or ""},
            correlation_id=job.correlation_id,
        )
    db.flush()
    return len(stale)


class JobWorker:
    """A real polling worker over the durable job table.

    Local stand-in for an external Celery worker: no broker is available in a
    local-first installation, so the worker polls the same workspace-scoped
    ``jobs`` table the API writes, claims due jobs and executes the registered
    local handlers. State survives a crash because every transition lives in the
    database, and ``recover_stale_jobs`` requeues jobs abandoned by a dead
    worker. The worker owns its sessions and never shares a request session.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
        *,
        worker_id: str | None = None,
        job_types: list[str] | None = None,
        workspace_id: str | None = None,
        poll_seconds: float = 1.0,
        batch_limit: int = 10,
        recover_after_seconds: int = 300,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if not 1 <= batch_limit <= 100:
            raise ValueError("batch_limit must be between 1 and 100")
        self._session_factory = session_factory or SessionLocal
        self.worker_id = (worker_id or f"worker-{new_id()[:8]}")[:80]
        self.job_types = job_types
        self.workspace_id = workspace_id
        self.poll_seconds = poll_seconds
        self.batch_limit = batch_limit
        self.recover_after_seconds = recover_after_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> dict:
        """One claim-and-run cycle in its own transaction."""
        db = self._session_factory()
        try:
            recovered = recover_stale_jobs(
                db, stale_after_seconds=self.recover_after_seconds
            )
            summary = run_pending_jobs(
                db,
                worker_id=self.worker_id,
                limit=self.batch_limit,
                job_types=self.job_types,
                workspace_id=self.workspace_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return {**summary, "recovered": recovered, "worker_id": self.worker_id}

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        """Poll until stopped. Safe to run in a background thread."""
        stop = stop_event or self._stop
        while not stop.is_set():
            self.tick()
            stop.wait(self.poll_seconds)

    def start(self) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._thread = threading.Thread(
            target=self.run_forever, name=f"novara-{self.worker_id}", daemon=True
        )
        self._thread.start()
        return self._thread

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class JobCreate(BaseModel):
    job_type: str
    payload: dict = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: int = Field(default=60, ge=1, le=86400)
    run_at: datetime | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("job_type")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("job_type must not be empty")
        return value


class JobRunRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    job_types: list[str] | None = None
    worker_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class JobOut(BaseModel):
    id: str
    workspace_id: str
    job_type: str
    payload: dict
    status: str
    attempts: int
    max_attempts: int
    retry_delay_seconds: int
    run_at: object
    locked_at: object | None
    locked_by: str | None
    last_error: str | None
    result: dict | None
    correlation_id: str
    idempotency_key: str | None
    created_by: str
    created_at: object
    finished_at: object | None
    notes: str = JOB_NOTES

    model_config = ConfigDict(from_attributes=True)


class JobStats(BaseModel):
    workspace_id: str
    queued: int
    running: int
    succeeded: int
    dead_letter: int
    cancelled: int
    total: int
    handlers: list[str]
    notes: str = JOB_NOTES


class JobRunResult(BaseModel):
    claimed: int
    succeeded: int
    retried: int
    dead_lettered: int
    notes: str = JOB_NOTES


class JobRecoverResult(BaseModel):
    recovered: int
    notes: str = JOB_NOTES


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[JobOut])
def list_jobs(
    workspace_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[Job]:
    verify_workspace(principal, workspace_id)
    query = select(Job).where(Job.workspace_id == workspace_id)
    if status_filter:
        query = query.where(Job.status == status_filter)
    if job_type:
        query = query.where(Job.job_type == job_type)
    return db.execute(
        query.order_by(Job.created_at.desc()).limit(limit)
    ).scalars().all()


@router.get("/stats", response_model=JobStats)
def job_stats(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> JobStats:
    verify_workspace(principal, workspace_id)
    counts = dict(
        db.execute(
            select(Job.status, func.count()).where(Job.workspace_id == workspace_id).group_by(Job.status)
        ).all()
    )
    return JobStats(
        workspace_id=workspace_id,
        queued=counts.get("queued", 0),
        running=counts.get("running", 0),
        succeeded=counts.get("succeeded", 0),
        dead_letter=counts.get("dead_letter", 0),
        cancelled=counts.get("cancelled", 0),
        total=sum(counts.values()),
        handlers=handler_names(),
    )


@router.get("/handlers", response_model=list[str])
def list_handlers(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[str]:
    verify_workspace(principal, workspace_id)
    return handler_names()


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    workspace_id: str,
    body: JobCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Job:
    verify_workspace(principal, workspace_id)
    try:
        job = enqueue_job(
            db,
            workspace_id=workspace_id,
            job_type=body.job_type,
            payload=body.payload,
            created_by=principal.user.id,
            max_attempts=body.max_attempts,
            retry_delay_seconds=body.retry_delay_seconds,
            run_at=body.run_at,
            correlation_id=body.correlation_id,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return job


@router.post("/run", response_model=JobRunResult)
def run_jobs(
    workspace_id: str,
    body: JobRunRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobRunResult:
    verify_workspace(principal, workspace_id)
    worker_id = (body.worker_id or principal.user.id)[:80]
    # Only this workspace's jobs may run in a call scoped to this workspace.
    from sqlalchemy import select as _select

    allowed = (
        db.execute(
            _select(Job.job_type).where(Job.workspace_id == workspace_id)
        ).scalars().all()
    )
    job_types = [t for t in (body.job_types or []) if t in allowed]
    if body.job_types and not job_types:
        return JobRunResult(claimed=0, succeeded=0, retried=0, dead_lettered=0)
    try:
        result = run_pending_jobs(
            db,
            worker_id=worker_id,
            limit=body.limit,
            job_types=job_types or None,
            workspace_id=workspace_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return JobRunResult(**result)


@router.post("/recover", response_model=JobRecoverResult)
def recover_jobs(
    workspace_id: str,
    stale_after_seconds: int = Query(default=300, ge=1, le=86400),
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> JobRecoverResult:
    verify_workspace(principal, workspace_id)
    # Recovery only touches this workspace's stale jobs.
    cutoff = now() - timedelta(seconds=stale_after_seconds)
    stale = db.execute(
        select(Job).where(
            Job.workspace_id == workspace_id,
            Job.status == "running",
            Job.locked_at.is_not(None),
            Job.locked_at <= cutoff,
        )
    ).scalars().all()
    for job in stale:
        previous_worker = job.locked_by
        job.status = "queued"
        job.locked_at = None
        job.locked_by = None
        job.run_at = now()
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=JOB_RECOVERED,
            entity_id=job.id,
            payload={"job_type": job.job_type, "previous_worker": previous_worker or ""},
            correlation_id=job.correlation_id,
        )
    db.commit()
    return JobRecoverResult(recovered=len(stale))


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> Job:
    verify_workspace(principal, workspace_id)
    return _job_or_404(db, workspace_id, job_id)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Job:
    verify_workspace(principal, workspace_id)
    job = _job_or_404(db, workspace_id, job_id)
    if job.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="only queued or running jobs can be cancelled")
    previous = job.status
    job.status = "cancelled"
    job.locked_at = None
    job.locked_by = None
    job.finished_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=JOB_CANCELLED,
        entity_id=job.id,
        payload={"job_type": job.job_type, "from": previous},
        correlation_id=job.correlation_id,
        actor_id=principal.user.id,
    )
    db.commit()
    return job


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Job:
    verify_workspace(principal, workspace_id)
    job = _job_or_404(db, workspace_id, job_id)
    if job.status not in {"dead_letter", "cancelled"}:
        raise HTTPException(status_code=409, detail="only dead-letter or cancelled jobs can be retried")
    job.status = "queued"
    job.attempts = 0
    job.last_error = None
    job.result = None
    job.finished_at = None
    job.run_at = now()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=JOB_QUEUED,
        entity_id=job.id,
        payload={"job_type": job.job_type, "action": "manual_retry"},
        correlation_id=job.correlation_id,
        actor_id=principal.user.id,
    )
    db.commit()
    return job


# --------------------------------------------------------------------------
# NV-051 / NV-052: documented retry layers and queryable message failures
# --------------------------------------------------------------------------


class RetryPolicyOut(BaseModel):
    policies: dict
    notes: str = (
        "Only the local job layer retries. Provider adapters are local mocks, "
        "so no send is attempted and no delivery is ever claimed."
    )


class MessageFailureOut(BaseModel):
    id: str
    workspace_id: str
    job_id: str
    channel: str
    subscriber_id: str | None
    transaction_id: str
    error: str
    correlation_id: str
    created_at: object
    notes: str = "Local failure record only; upstream Novu exposes no delivery DLQ."

    model_config = ConfigDict(from_attributes=True)


@router.get("/policy/retry", response_model=RetryPolicyOut)
def get_retry_policy(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> RetryPolicyOut:
    verify_workspace(principal, workspace_id)
    return RetryPolicyOut(policies=retry_policies())


@router.get("/messages/failed", response_model=list[MessageFailureOut])
def list_failed_messages(
    workspace_id: str,
    channel: str | None = None,
    subscriber_id: str | None = None,
    transaction_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[MessageFailure]:
    verify_workspace(principal, workspace_id)
    query = select(MessageFailure).where(MessageFailure.workspace_id == workspace_id)
    if channel:
        query = query.where(MessageFailure.channel == channel)
    if subscriber_id:
        query = query.where(MessageFailure.subscriber_id == subscriber_id)
    if transaction_id:
        query = query.where(MessageFailure.transaction_id == transaction_id)
    return db.execute(
        query.order_by(MessageFailure.created_at.desc()).limit(limit)
    ).scalars().all()
