"""Analytics and experiments module.

Module-owned SQLAlchemy tables, workspace-scoped endpoints, and aggregate
queries over the shared Contact, Lead, Task and Event tables. All mutations
write an audit event through the shared publish_event() helper.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, Event, Lead, Task, new_id, now
from ..permissions import EVENT_READ, WORKSPACE_MANAGE

EXPERIMENT_CREATED = "experiment.created"
EXPERIMENT_UPDATED = "experiment.updated"
EXPERIMENT_DELETED = "experiment.deleted"
EXPERIMENT_RESULT_RECORDED = "experiment.result_recorded"
EXPERIMENT_STATUS_CHANGED = "experiment.status_changed"
register_event_types(
    EXPERIMENT_CREATED,
    EXPERIMENT_UPDATED,
    EXPERIMENT_DELETED,
    EXPERIMENT_RESULT_RECORDED,
    EXPERIMENT_STATUS_CHANGED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/analytics",
    tags=["analytics"],
)

EXPERIMENT_STATUSES = ("draft", "running", "stopped", "completed")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_experiment_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline: Mapped[float | None] = mapped_column()
    target: Mapped[float | None] = mapped_column()
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "variant", "recorded_at", name="uq_experiment_result_variant_time"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False, index=True)
    variant: Mapped[str] = mapped_column(String(80), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SavedReport(Base):
    __tablename__ = "saved_reports"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_saved_report"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    name: str
    metric_name: str
    hypothesis: str | None = None
    baseline: float | None = None
    target: float | None = None
    status: Literal["draft", "running", "stopped", "completed"] = "draft"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "metric_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class ExperimentUpdate(BaseModel):
    name: str | None = None
    metric_name: str | None = None
    hypothesis: str | None = None
    baseline: float | None = None
    target: float | None = None
    status: Literal["draft", "running", "stopped", "completed"] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "metric_name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("value must not be blank")
        return value.strip() if value is not None else None


class StatusUpdate(BaseModel):
    status: Literal["draft", "running", "stopped", "completed"]

    model_config = ConfigDict(extra="forbid")


class ExperimentOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    hypothesis: str | None
    status: str
    metric_name: str
    baseline: float | None
    target: float | None
    owner_id: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ResultUpsert(BaseModel):
    variant: str
    impressions: int = Field(ge=0)
    conversions: int = Field(ge=0)
    recorded_at: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("variant")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("variant must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def conversions_not_above_impressions(self) -> ResultUpsert:
        if self.conversions > self.impressions:
            raise ValueError("conversions cannot exceed impressions")
        return self


class ResultOut(BaseModel):
    id: str
    experiment_id: str
    variant: str
    impressions: int
    conversions: int
    recorded_at: object

    model_config = ConfigDict(from_attributes=True)


class FunnelSummary(BaseModel):
    contacts: int
    leads: int
    converted_leads: int
    tasks: int


class EventVolume(BaseModel):
    event_type: str
    count: int


class SavedReportCreate(BaseModel):
    name: str
    report_type: str
    filters: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class SavedReportOut(BaseModel):
    id: str
    name: str
    report_type: str
    filters: dict
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class CohortRow(BaseModel):
    cohort: str
    size: int
    retained: int
    retention_rate: float


class ConversionSummary(BaseModel):
    total_contacts: int
    leads: int
    qualified: int
    converted: int
    conversion_rate: float


class DateCompare(BaseModel):
    current: int
    previous: int
    delta: int
    delta_percent: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _experiment_or_404(db: Session, workspace_id: str, experiment_id: str) -> Experiment:
    experiment = db.execute(
        select(Experiment).where(Experiment.id == experiment_id, Experiment.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return experiment


def _parse_datetime(value: str | None, *, label: str) -> datetime | None:
    if value is None:
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {label}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Aggregate endpoints (declared before /{experiment_id} routes)
# ---------------------------------------------------------------------------


@router.get("/funnel", response_model=FunnelSummary)
def funnel_summary(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> FunnelSummary:
    verify_workspace(principal, workspace_id)
    contacts = db.execute(
        select(func.count()).select_from(Contact).where(Contact.workspace_id == workspace_id)
    ).scalar()
    leads = db.execute(
        select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id)
    ).scalar()
    converted = db.execute(
        select(func.count()).select_from(Lead).where(
            Lead.workspace_id == workspace_id, Lead.status == "converted"
        )
    ).scalar()
    tasks = db.execute(
        select(func.count()).select_from(Task).where(Task.workspace_id == workspace_id)
    ).scalar()
    return FunnelSummary(
        contacts=int(contacts or 0),
        leads=int(leads or 0),
        converted_leads=int(converted or 0),
        tasks=int(tasks or 0),
    )


@router.get("/events/volume", response_model=list[EventVolume])
def event_volume(
    workspace_id: str,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[EventVolume]:
    verify_workspace(principal, workspace_id)
    start = _parse_datetime(date_from, label="date_from")
    end = _parse_datetime(date_to, label="date_to")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    query = select(Event.event_type, func.count().label("count")).where(Event.workspace_id == workspace_id)
    if start is not None:
        query = query.where(Event.occurred_at >= start)
    if end is not None:
        query = query.where(Event.occurred_at <= end)
    rows = db.execute(
        query.group_by(Event.event_type).order_by(func.count().desc(), Event.event_type)
    ).all()
    return [EventVolume(event_type=event_type, count=int(count)) for event_type, count in rows]


@router.get("/reports", response_model=list[SavedReportOut])
def list_saved_reports(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[SavedReport]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SavedReport).where(SavedReport.workspace_id == workspace_id).order_by(SavedReport.created_at.desc())
    ).scalars().all()


@router.post("/reports", response_model=SavedReportOut, status_code=status.HTTP_201_CREATED)
def create_saved_report(
    workspace_id: str,
    body: SavedReportCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> SavedReport:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SavedReport).where(SavedReport.workspace_id == workspace_id, SavedReport.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="report name already exists")
    r = SavedReport(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        report_type=body.report_type, filters=body.filters,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(r)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=EXPERIMENT_CREATED,
                  entity_id=r.id, payload={"saved_report": True, "name": r.name},
                  actor_id=principal.user.id)
    db.commit()
    return r


@router.get("/cohorts", response_model=list[CohortRow])
def cohort_analysis(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[CohortRow]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(
            func.strftime("%Y-%m", Contact.created_at).label("cohort"),
            func.count(Contact.id),
        )
        .where(Contact.workspace_id == workspace_id)
        .group_by(func.strftime("%Y-%m", Contact.created_at))
        .order_by(func.strftime("%Y-%m", Contact.created_at))
    ).all()
    result = []
    for cohort_str, size in rows:
        if cohort_str is None:
            continue
        retained = db.execute(
            select(func.count(func.distinct(Task.contact_id)))
            .where(Task.workspace_id == workspace_id, Task.contact_id.isnot(None))
        ).scalar() or 0
        rate = (retained / size * 100.0) if size else 0.0
        result.append(CohortRow(
            cohort=str(cohort_str),
            size=int(size),
            retained=int(retained),
            retention_rate=round(rate, 2),
        ))
    return result


@router.get("/conversions", response_model=ConversionSummary)
def conversion_summary(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> ConversionSummary:
    verify_workspace(principal, workspace_id)
    contacts = db.execute(select(func.count()).select_from(Contact).where(Contact.workspace_id == workspace_id)).scalar() or 0
    leads = db.execute(select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id)).scalar() or 0
    qualified = db.execute(select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id, Lead.status == "qualified")).scalar() or 0
    converted = db.execute(select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id, Lead.status == "converted")).scalar() or 0
    rate = (converted / leads * 100.0) if leads else 0.0
    return ConversionSummary(
        total_contacts=int(contacts), leads=int(leads), qualified=int(qualified),
        converted=int(converted), conversion_rate=round(rate, 2),
    )


@router.get("/compare/contacts", response_model=DateCompare)
def compare_contacts(
    workspace_id: str,
    current_from: str = Query(...),
    current_to: str = Query(...),
    previous_from: str = Query(...),
    previous_to: str = Query(...),
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> DateCompare:
    verify_workspace(principal, workspace_id)
    def _parse(v):
        raw = v.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    cf, ct = _parse(current_from), _parse(current_to)
    pf, pt = _parse(previous_from), _parse(previous_to)
    cur = db.execute(select(func.count()).select_from(Contact).where(
        Contact.workspace_id == workspace_id, Contact.created_at >= cf, Contact.created_at <= ct
    )).scalar() or 0
    prev = db.execute(select(func.count()).select_from(Contact).where(
        Contact.workspace_id == workspace_id, Contact.created_at >= pf, Contact.created_at <= pt
    )).scalar() or 0
    delta = int(cur) - int(prev)
    pct = (delta / int(prev) * 100.0) if prev else 0.0
    return DateCompare(current=int(cur), previous=int(prev), delta=delta, delta_percent=round(pct, 2))


# ---------------------------------------------------------------------------
# Experiment endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ExperimentOut])
def list_experiments(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[Experiment]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Experiment).where(Experiment.workspace_id == workspace_id).order_by(Experiment.created_at.desc())
    ).scalars().all()


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(
    workspace_id: str,
    body: ExperimentCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Experiment:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Experiment).where(Experiment.workspace_id == workspace_id, Experiment.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="an experiment with this name already exists")
    experiment = Experiment(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        hypothesis=body.hypothesis,
        status=body.status,
        metric_name=body.metric_name,
        baseline=body.baseline,
        target=body.target,
        owner_id=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(experiment)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPERIMENT_CREATED,
        entity_id=experiment.id,
        payload={"name": experiment.name, "status": experiment.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return experiment


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(
    workspace_id: str,
    experiment_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> Experiment:
    verify_workspace(principal, workspace_id)
    return _experiment_or_404(db, workspace_id, experiment_id)


@router.patch("/{experiment_id}", response_model=ExperimentOut)
def update_experiment(
    workspace_id: str,
    experiment_id: str,
    body: ExperimentUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Experiment:
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != experiment.name:
        duplicate = db.execute(
            select(Experiment).where(
                Experiment.workspace_id == workspace_id,
                Experiment.name == updates["name"],
                Experiment.id != experiment.id,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="an experiment with this name already exists")
    previous_status = experiment.status
    for key, value in updates.items():
        setattr(experiment, key, value)
    experiment.updated_at = now()
    db.flush()
    if updates.get("status") is not None and updates["status"] != previous_status:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=EXPERIMENT_STATUS_CHANGED,
            entity_id=experiment.id,
            payload={"from": previous_status, "to": experiment.status},
            actor_id=principal.user.id,
        )
    else:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=EXPERIMENT_UPDATED,
            entity_id=experiment.id,
            payload={"fields": sorted(updates.keys())},
            actor_id=principal.user.id,
        )
    db.commit()
    return experiment


@router.delete("/{experiment_id}")
def delete_experiment(
    workspace_id: str,
    experiment_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPERIMENT_DELETED,
        entity_id=experiment.id,
        payload={"name": experiment.name},
        actor_id=principal.user.id,
    )
    db.delete(experiment)
    db.commit()
    return {"deleted": True, "experiment_id": experiment.id}


@router.post("/{experiment_id}/status", response_model=ExperimentOut)
def change_status(
    workspace_id: str,
    experiment_id: str,
    body: StatusUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> Experiment:
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    previous_status = experiment.status
    experiment.status = body.status
    experiment.updated_at = now()
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPERIMENT_STATUS_CHANGED,
        entity_id=experiment.id,
        payload={"from": previous_status, "to": experiment.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return experiment


@router.get("/{experiment_id}/results", response_model=list[ResultOut])
def list_results(
    workspace_id: str,
    experiment_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[ExperimentResult]:
    verify_workspace(principal, workspace_id)
    _experiment_or_404(db, workspace_id, experiment_id)
    return db.execute(
        select(ExperimentResult)
        .where(
            ExperimentResult.workspace_id == workspace_id,
            ExperimentResult.experiment_id == experiment_id,
        )
        .order_by(ExperimentResult.recorded_at, ExperimentResult.variant)
    ).scalars().all()


@router.post("/{experiment_id}/results", response_model=ResultOut)
def upsert_result(
    workspace_id: str,
    experiment_id: str,
    body: ResultUpsert,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ExperimentResult:
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    recorded_at = _parse_datetime(body.recorded_at, label="recorded_at") or now()
    result = db.execute(
        select(ExperimentResult).where(
            ExperimentResult.workspace_id == workspace_id,
            ExperimentResult.experiment_id == experiment.id,
            ExperimentResult.variant == body.variant,
            ExperimentResult.recorded_at == recorded_at,
        )
    ).scalar_one_or_none()
    if result is None:
        result = ExperimentResult(
            id=new_id(),
            workspace_id=workspace_id,
            experiment_id=experiment.id,
            variant=body.variant,
            impressions=body.impressions,
            conversions=body.conversions,
            recorded_at=recorded_at,
        )
        db.add(result)
    else:
        result.impressions = body.impressions
        result.conversions = body.conversions
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPERIMENT_RESULT_RECORDED,
        entity_id=result.id,
        payload={
            "experiment_id": experiment.id,
            "variant": result.variant,
            "impressions": result.impressions,
            "conversions": result.conversions,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return result