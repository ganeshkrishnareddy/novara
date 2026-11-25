"""Local experiment data exploration and reporting (GrowthBook P2/P3 cluster).

Clean-room implementation of GB-024 (custom reports), GB-027 (discovery
queries), GB-028 (fact tables), GB-034 (assignment queries), GB-035 (identifier
types and joins), GB-037 (funnel analysis) and GB-101 (carryover bias guidance).

Important delivery boundary: these are local logical views over NOVARA's own
workspace-scoped experiment, flag-assignment, exposure and time-series rows.
No warehouse SQL is executed, no external data source is contacted and no
GrowthBook source is copied. Definitions, queries, mappings, reports and
assessments are persisted locally and every mutation is audited.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .analytics import Experiment, ExperimentResult
from .experiment_stats import ExperimentDefinition, ExperimentObservation
from .experiment_operations import TimeSeriesPoint
from .feature_flags import FeatureFlag, FlagAssignment, FlagExposure

FACT_CREATED = "experiment.fact_table_created"
QUERY_CREATED = "experiment.discovery_query_created"
ASSIGNMENT_QUERY_CREATED = "experiment.assignment_query_created"
IDENTIFIER_CREATED = "experiment.identifier_type_created"
JOIN_CREATED = "experiment.identifier_join_created"
FUNNEL_CREATED = "experiment.funnel_created"
REPORT_CREATED = "experiment.custom_report_created"
REPORT_RUN = "experiment.custom_report_run"
CARRYOVER_ASSESSED = "experiment.carryover_assessed"
CARRYOVER_ACKED = "experiment.carryover_acknowledged"
register_event_types(
    FACT_CREATED, QUERY_CREATED, ASSIGNMENT_QUERY_CREATED, IDENTIFIER_CREATED,
    JOIN_CREATED, FUNNEL_CREATED, REPORT_CREATED, REPORT_RUN,
    CARRYOVER_ASSESSED, CARRYOVER_ACKED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-queries",
    tags=["experiment-queries"],
)

KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FILTER_OPS = frozenset({"eq", "ne", "in", "gt", "gte", "lt", "lte", "contains", "exists"})
FUNNEL_STAGES = ("assigned", "exposed", "converted")
REPORT_TYPES = frozenset({"experiment_summary", "timeseries_summary", "funnel_summary"})

# Local sources are logical fact tables, never warehouse queries.
FACT_SOURCES: dict[str, dict[str, tuple]] = {
    "observations": {
        "model": ExperimentObservation,
        "fields": ("experiment_id", "metric_id", "variant", "sessions", "conversions",
                   "value_sum", "numerator_sum", "denominator_sum", "created_at"),
    },
    "results": {
        "model": ExperimentResult,
        "fields": ("experiment_id", "variant", "impressions", "conversions", "recorded_at"),
    },
    "exposures": {
        "model": FlagExposure,
        "fields": ("flag_id", "user_key", "variant", "experiment_key", "created_at"),
    },
    "assignments": {
        "model": FlagAssignment,
        "fields": ("flag_id", "user_key", "variant", "assigned_at"),
    },
    "timeseries": {
        "model": TimeSeriesPoint,
        "fields": ("experiment_key", "metric_key", "dimension", "day", "sessions",
                   "conversions", "value_sum"),
    },
}


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _clean_ref(value: str) -> str:
    """An experiment identifier may be a local definition key or an existing
    workspace experiment id; both are plain safe reference strings."""
    ref = (value or "").strip()
    if not REF_RE.match(ref):
        raise ValueError("experiment reference must be 1-64 letters, digits, '_' or '-'")
    return ref


def _validate_filters(value: list, allowed: set[str] | None = None) -> list:
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("filters must be a list of at most 50 entries")
    for item in value:
        if not isinstance(item, dict) or not item.get("field"):
            raise ValueError("each filter needs a field")
        if allowed is not None and item["field"] not in allowed:
            raise ValueError(f"field {item['field']} is not available for this fact table")
        if item.get("op", "eq") not in FILTER_OPS:
            raise ValueError("unsupported filter operator")
        if item.get("op") == "in" and not isinstance(item.get("value"), list):
            raise ValueError("the 'in' operator needs a list value")
    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _matches(actual: Any, expected: Any, op: str) -> bool:
    if op == "exists":
        return (actual is not None) == (bool(expected) if isinstance(expected, bool) else True)
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return isinstance(expected, list) and actual in expected
    if op == "contains":
        return isinstance(actual, (str, list, tuple)) and expected in actual
    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
    except TypeError:
        return False
    return False


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


# ---------------------------------------------------------------------------
# Tables (all additive and workspace-scoped)
# ---------------------------------------------------------------------------


class QueryFactTable(Base):
    __tablename__ = "experiment_query_fact_tables"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_query_fact_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DiscoveryQuery(Base):
    __tablename__ = "experiment_discovery_queries"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_discovery_query_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fact_table_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_query_fact_tables.id"), nullable=False, index=True)
    filters: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AssignmentQuery(Base):
    __tablename__ = "experiment_assignment_queries"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_assignment_query_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default="both", nullable=False)
    filters: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdentifierType(Base):
    __tablename__ = "experiment_identifier_types"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_identifier_type_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    attribute: Mapped[str] = mapped_column(String(120), nullable=False)
    pattern: Mapped[str | None] = mapped_column(String(500))
    normalization: Mapped[str] = mapped_column(String(20), default="lower", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdentifierJoin(Base):
    __tablename__ = "experiment_identifier_joins"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_identifier_join_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    left_type_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_identifier_types.id"), nullable=False, index=True)
    right_type_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_identifier_types.id"), nullable=False, index=True)
    mappings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentFunnel(Base):
    __tablename__ = "experiment_funnels"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_funnel_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomReport(Base):
    __tablename__ = "experiment_custom_reports"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_custom_report_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CarryoverAssessment(Base):
    __tablename__ = "experiment_carryover_assessments"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_carryover_assessment_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_end: Mapped[str] = mapped_column(String(10), nullable=False)
    restart: Mapped[str] = mapped_column(String(10), nullable=False)
    washout_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    gap_days: Mapped[int] = mapped_column(Integer, nullable=False)
    warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guidance: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FactTableIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    source: str
    fields: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("source")
    @classmethod
    def _source(cls, value):
        if value not in FACT_SOURCES:
            raise ValueError("unsupported local fact source")
        return value

    @field_validator("fields")
    @classmethod
    def _fields(cls, value):
        if not value:
            raise ValueError("at least one field is required")
        if len(value) > 40 or len(set(value)) != len(value):
            raise ValueError("fields must be unique and at most 40 entries")
        return value


class DiscoveryQueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    fact_table_id: str
    filters: list = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class AssignmentQueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    experiment_key: str
    source: str = "both"
    filters: list = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("experiment_key")
    @classmethod
    def _experiment_key(cls, value):
        return _clean_ref(value)

    @field_validator("source")
    @classmethod
    def _source(cls, value):
        if value not in {"exposures", "assignments", "both"}:
            raise ValueError("source must be exposures, assignments or both")
        return value


class IdentifierTypeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    attribute: str
    pattern: str | None = None
    normalization: str = "lower"

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("attribute")
    @classmethod
    def _attribute(cls, value):
        if not (value or "").strip():
            raise ValueError("an attribute is required")
        return value.strip()

    @field_validator("normalization")
    @classmethod
    def _normalization(cls, value):
        if value not in {"none", "lower", "strip", "strip_lower"}:
            raise ValueError("unsupported normalization")
        return value

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, value):
        if value:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError("invalid identifier pattern") from exc
        return value


class NormalizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=512)


class JoinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    left_type_id: str
    right_type_id: str
    mappings: list[dict] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("mappings")
    @classmethod
    def _mappings(cls, value):
        if len(value) > 1000:
            raise ValueError("at most 1000 mappings are allowed")
        for item in value:
            if not isinstance(item.get("left"), str) or not isinstance(item.get("right"), str):
                raise ValueError("each mapping needs a left and a right string")
        return value


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=512)
    direction: str = "left_to_right"

    @field_validator("direction")
    @classmethod
    def _direction(cls, value):
        if value not in {"left_to_right", "right_to_left"}:
            raise ValueError("unsupported join direction")
        return value


class FunnelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    experiment_key: str
    steps: list[str] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("experiment_key")
    @classmethod
    def _experiment_key(cls, value):
        return _clean_ref(value)

    @field_validator("steps")
    @classmethod
    def _steps(cls, value):
        if len(value) < 2 or len(value) > len(FUNNEL_STAGES):
            raise ValueError("a funnel needs 2-3 steps")
        if list(value) != list(FUNNEL_STAGES[:len(value)]):
            raise ValueError("steps must be an ordered prefix of assigned, exposed, converted")
        return value


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    report_type: str
    config: dict = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("report_type")
    @classmethod
    def _type(cls, value):
        if value not in REPORT_TYPES:
            raise ValueError("unsupported report type")
        return value


class CarryoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    experiment_key: str
    previous_end: str
    restart: str
    washout_days: int = Field(default=7, ge=0, le=365)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("experiment_key")
    @classmethod
    def _experiment_key(cls, value):
        return _clean_ref(value)

    @field_validator("previous_end", "restart")
    @classmethod
    def _day(cls, value):
        if not DAY_RE.match(value or ""):
            raise ValueError("dates must be YYYY-MM-DD")
        date.fromisoformat(value)
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    )).first() is not None


def _experiment_ids(db, workspace_id, experiment_key: str) -> list[str]:
    rows = db.execute(select(ExperimentDefinition.id).where(
        ExperimentDefinition.workspace_id == workspace_id,
        ExperimentDefinition.key == experiment_key,
    )).scalars().all()
    return list(rows)


def _units(db, workspace_id, experiment_key: str, source: str, filters: list) -> list[dict]:
    units: dict[tuple[str, str], dict] = {}
    allowed = {"user_key", "variant"}
    _validate_filters(filters, allowed)
    if source in {"exposures", "both"}:
        rows = db.execute(select(FlagExposure).where(
            FlagExposure.workspace_id == workspace_id,
            FlagExposure.experiment_key == experiment_key,
        )).scalars().all()
        for row in rows:
            item = {"user_key": row.user_key, "variant": row.variant, "source": "exposure"}
            if all(_matches(item.get(f["field"]), f.get("value"), f.get("op", "eq"))
                   for f in filters):
                units[(row.user_key, "exposure")] = item
    if source in {"assignments", "both"}:
        flag_ids = db.execute(select(FlagExposure.flag_id).where(
            FlagExposure.workspace_id == workspace_id,
            FlagExposure.experiment_key == experiment_key,
        )).scalars().all()
        if flag_ids:
            rows = db.execute(select(FlagAssignment).where(
                FlagAssignment.workspace_id == workspace_id,
                FlagAssignment.flag_id.in_(set(flag_ids)),
            )).scalars().all()
            for row in rows:
                item = {"user_key": row.user_key, "variant": row.variant, "source": "assignment"}
                if all(_matches(item.get(f["field"]), f.get("value"), f.get("op", "eq"))
                       for f in filters):
                    units[(row.user_key, "assignment")] = item
    return [units[k] for k in sorted(units)]


def _funnel_analysis(db, workspace_id, funnel: ExperimentFunnel) -> dict:
    assigned = _units(db, workspace_id, funnel.experiment_key, "assignments", [])
    exposed = _units(db, workspace_id, funnel.experiment_key, "exposures", [])
    experiment_ids = _experiment_ids(db, workspace_id, funnel.experiment_key)
    # Results are stored against the analytics experiment id, so also resolve
    # a workspace experiment whose name matches this local reference.
    experiment_ids += db.execute(select(Experiment.id).where(
        Experiment.workspace_id == workspace_id,
        Experiment.name == funnel.experiment_key,
    )).scalars().all()
    conversions = 0
    if experiment_ids:
        conversions = db.execute(
            select(ExperimentResult.conversions).where(
                ExperimentResult.workspace_id == workspace_id,
                ExperimentResult.experiment_id.in_(experiment_ids),
            )
        ).scalars().all()
        conversions = sum(conversions)
    counts = {"assigned": len(assigned), "exposed": len(exposed), "converted": conversions}
    steps = []
    previous = None
    for stage in funnel.steps:
        count = counts[stage]
        steps.append({
            "stage": stage,
            "count": count,
            "step_rate": None if previous is None or previous == 0 else count / previous,
        })
        previous = count
    return {
        "funnel_id": funnel.id, "experiment_key": funnel.experiment_key,
        "steps": steps, "counts": counts,
        "overall_conversion": (conversions / len(exposed)) if exposed else 0.0,
    }


# ---------------------------------------------------------------------------
# Routes - contract and fact tables
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="experimentQueriesContract")
def api_contract():
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["factTables", "discoveryQueries", "assignmentQueries",
                      "identifierTypes", "identifierJoins", "funnels", "reports",
                      "carryoverAssessments"],
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-queries",
        "fact_sources": sorted(FACT_SOURCES),
    }


@router.get("/fact-tables", operation_id="listQueryFactTables")
def list_fact_tables(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(QueryFactTable).where(
        QueryFactTable.workspace_id == workspace_id
    ).order_by(QueryFactTable.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "source": r.source,
             "fields": r.fields} for r in rows]


@router.post("/fact-tables", status_code=status.HTTP_201_CREATED, operation_id="createQueryFactTable")
def create_fact_table(workspace_id: str, body: FactTableIn,
                      principal: Principal = Depends(require(NOTE_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    """GB-028: a shared local row set on which discovery queries are defined."""
    verify_workspace(principal, workspace_id)
    allowed = set(FACT_SOURCES[body.source]["fields"])
    unknown = [f for f in body.fields if f not in allowed]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown fields: {', '.join(unknown)}")
    if _exists(db, QueryFactTable, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="fact table key already exists")
    row = QueryFactTable(id=new_id(), workspace_id=workspace_id, key=body.key,
                         name=body.name, source=body.source, fields=body.fields,
                         description=body.description, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, FACT_CREATED, row.id, {"source": row.source}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "source": row.source, "fields": row.fields}


@router.get("/fact-tables/{fact_id}/preview", operation_id="previewQueryFactTable")
def preview_fact_table(workspace_id: str, fact_id: str,
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    fact = _get(db, QueryFactTable, workspace_id, fact_id, "fact table")
    model = FACT_SOURCES[fact.source]["model"]
    model_fields = FACT_SOURCES[fact.source]["fields"]
    columns = [getattr(model, f) for f in fact.fields]
    rows = db.execute(select(*columns).where(
        model.workspace_id == workspace_id
    ).limit(20)).all()
    return {"fact_table_id": fact.id, "source": fact.source,
            "rows": [{f: _jsonable(v) for f, v in zip(fact.fields, row)} for row in rows],
            "available_fields": list(model_fields)}


@router.get("/discovery-queries", operation_id="listDiscoveryQueries")
def list_discovery_queries(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                           db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(DiscoveryQuery).where(
        DiscoveryQuery.workspace_id == workspace_id
    ).order_by(DiscoveryQuery.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "fact_table_id": r.fact_table_id,
             "filters": r.filters, "fields": r.fields, "limit": r.limit} for r in rows]


@router.post("/discovery-queries", status_code=status.HTTP_201_CREATED,
             operation_id="createDiscoveryQuery")
def create_discovery_query(workspace_id: str, body: DiscoveryQueryIn,
                           principal: Principal = Depends(require(NOTE_WRITE)),
                           db: Session = Depends(get_db)) -> dict:
    """GB-027: a saved query that discovers facts and metric candidates."""
    verify_workspace(principal, workspace_id)
    fact = _get(db, QueryFactTable, workspace_id, body.fact_table_id, "fact table")
    allowed = set(fact.fields)
    unknown = [f for f in body.fields if f not in allowed]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown fields: {', '.join(unknown)}")
    try:
        filters = _validate_filters(body.filters, allowed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if _exists(db, DiscoveryQuery, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="discovery query key already exists")
    row = DiscoveryQuery(id=new_id(), workspace_id=workspace_id, key=body.key,
                         name=body.name, fact_table_id=fact.id, filters=filters,
                         fields=body.fields or list(fact.fields), limit=body.limit,
                         created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, QUERY_CREATED, row.id, {"fact_table_id": fact.id}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "fields": row.fields, "filters": row.filters}


@router.post("/discovery-queries/{query_id}/run", operation_id="runDiscoveryQuery")
def run_discovery_query(workspace_id: str, query_id: str,
                        principal: Principal = Depends(require(CONTACT_READ)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    query = _get(db, DiscoveryQuery, workspace_id, query_id, "discovery query")
    fact = _get(db, QueryFactTable, workspace_id, query.fact_table_id, "fact table")
    model = FACT_SOURCES[fact.source]["model"]
    columns = [getattr(model, f) for f in query.fields]
    raw = db.execute(select(*columns).where(
        model.workspace_id == workspace_id
    ).limit(max(query.limit * 5, 100))).all()
    matched = []
    for row in raw:
        item = {f: _jsonable(v) for f, v in zip(query.fields, row)}
        if all(_matches(item.get(f["field"]), f.get("value"), f.get("op", "eq"))
               for f in query.filters):
            matched.append(item)
        if len(matched) >= query.limit:
            break
    return {"query_id": query.id, "fact_table_id": fact.id, "source": fact.source,
            "count": len(matched), "rows": matched}


# ---------------------------------------------------------------------------
# Routes - assignment queries, identifiers and joins
# ---------------------------------------------------------------------------


@router.get("/assignment-queries", operation_id="listAssignmentQueries")
def list_assignment_queries(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                            db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AssignmentQuery).where(
        AssignmentQuery.workspace_id == workspace_id
    ).order_by(AssignmentQuery.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "experiment_key": r.experiment_key,
             "source": r.source} for r in rows]


@router.post("/assignment-queries", status_code=status.HTTP_201_CREATED,
             operation_id="createAssignmentQuery")
def create_assignment_query(workspace_id: str, body: AssignmentQueryIn,
                            principal: Principal = Depends(require(NOTE_WRITE)),
                            db: Session = Depends(get_db)) -> dict:
    """GB-034: identify exposed units from local assignment and exposure rows."""
    verify_workspace(principal, workspace_id)
    try:
        filters = _validate_filters(body.filters, {"user_key", "variant"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if _exists(db, AssignmentQuery, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="assignment query key already exists")
    row = AssignmentQuery(id=new_id(), workspace_id=workspace_id, key=body.key,
                          name=body.name, experiment_key=body.experiment_key,
                          source=body.source, filters=filters, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ASSIGNMENT_QUERY_CREATED, row.id,
           {"experiment_key": row.experiment_key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "experiment_key": row.experiment_key,
            "source": row.source}


@router.post("/assignment-queries/{query_id}/run", operation_id="runAssignmentQuery")
def run_assignment_query(workspace_id: str, query_id: str,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    query = _get(db, AssignmentQuery, workspace_id, query_id, "assignment query")
    units = _units(db, workspace_id, query.experiment_key, query.source, query.filters)
    return {"query_id": query.id, "experiment_key": query.experiment_key,
            "count": len(units), "units": units}


@router.get("/identifier-types", operation_id="listIdentifierTypes")
def list_identifier_types(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                          db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(IdentifierType).where(
        IdentifierType.workspace_id == workspace_id
    ).order_by(IdentifierType.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "attribute": r.attribute,
             "pattern": r.pattern, "normalization": r.normalization} for r in rows]


@router.post("/identifier-types", status_code=status.HTTP_201_CREATED,
             operation_id="createIdentifierType")
def create_identifier_type(workspace_id: str, body: IdentifierTypeIn,
                           principal: Principal = Depends(require(NOTE_WRITE)),
                           db: Session = Depends(get_db)) -> dict:
    """GB-035: configure unit identifiers used by joins and reports."""
    verify_workspace(principal, workspace_id)
    if _exists(db, IdentifierType, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="identifier type key already exists")
    row = IdentifierType(id=new_id(), workspace_id=workspace_id, key=body.key,
                         name=body.name, attribute=body.attribute, pattern=body.pattern,
                         normalization=body.normalization, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, IDENTIFIER_CREATED, row.id,
           {"attribute": row.attribute}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "attribute": row.attribute,
            "normalization": row.normalization}


@router.post("/identifier-types/{type_id}/normalize", operation_id="normalizeIdentifier")
def normalize_identifier(workspace_id: str, type_id: str, body: NormalizeIn,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, IdentifierType, workspace_id, type_id, "identifier type")
    value = body.value
    if row.normalization in {"lower", "strip_lower"}:
        value = value.lower()
    if row.normalization in {"strip", "strip_lower"}:
        value = value.strip()
    valid = bool(re.fullmatch(row.pattern, value)) if row.pattern else True
    return {"type_id": row.id, "input": body.value, "normalized": value,
            "valid": valid, "attribute": row.attribute}


@router.get("/identifier-joins", operation_id="listIdentifierJoins")
def list_identifier_joins(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                          db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(IdentifierJoin).where(
        IdentifierJoin.workspace_id == workspace_id
    ).order_by(IdentifierJoin.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "left_type_id": r.left_type_id,
             "right_type_id": r.right_type_id, "mappings": len(r.mappings)} for r in rows]


@router.post("/identifier-joins", status_code=status.HTTP_201_CREATED,
             operation_id="createIdentifierJoin")
def create_identifier_join(workspace_id: str, body: JoinIn,
                           principal: Principal = Depends(require(NOTE_WRITE)),
                           db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    left = _get(db, IdentifierType, workspace_id, body.left_type_id, "left identifier type")
    right = _get(db, IdentifierType, workspace_id, body.right_type_id, "right identifier type")
    if left.id == right.id:
        raise HTTPException(status_code=422, detail="join needs two different identifier types")
    if _exists(db, IdentifierJoin, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="identifier join key already exists")
    row = IdentifierJoin(id=new_id(), workspace_id=workspace_id, key=body.key,
                         name=body.name, left_type_id=left.id, right_type_id=right.id,
                         mappings=body.mappings, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, JOIN_CREATED, row.id,
           {"left": left.key, "right": right.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "mappings": len(row.mappings)}


@router.post("/identifier-joins/{join_id}/resolve", operation_id="resolveIdentifierJoin")
def resolve_identifier_join(workspace_id: str, join_id: str, body: ResolveIn,
                            principal: Principal = Depends(require(CONTACT_READ)),
                            db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    join = _get(db, IdentifierJoin, workspace_id, join_id, "identifier join")
    source, target = (("left", "right") if body.direction == "left_to_right"
                      else ("right", "left"))
    matches = sorted({item[target] for item in join.mappings if item.get(source) == body.value})
    return {"join_id": join.id, "direction": body.direction, "value": body.value,
            "count": len(matches), "matches": matches}


# ---------------------------------------------------------------------------
# Routes - funnels, reports and carryover guidance
# ---------------------------------------------------------------------------


@router.get("/funnels", operation_id="listExperimentFunnels")
def list_funnels(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentFunnel).where(
        ExperimentFunnel.workspace_id == workspace_id
    ).order_by(ExperimentFunnel.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "experiment_key": r.experiment_key,
             "steps": r.steps} for r in rows]


@router.post("/funnels", status_code=status.HTTP_201_CREATED, operation_id="createExperimentFunnel")
def create_funnel(workspace_id: str, body: FunnelIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    """GB-037: ordered step conversion measurement over local experiment rows."""
    verify_workspace(principal, workspace_id)
    if _exists(db, ExperimentFunnel, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="funnel key already exists")
    row = ExperimentFunnel(id=new_id(), workspace_id=workspace_id, key=body.key,
                           name=body.name, experiment_key=body.experiment_key,
                           steps=body.steps, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, FUNNEL_CREATED, row.id,
           {"experiment_key": row.experiment_key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "steps": row.steps}


@router.get("/funnels/{funnel_id}/result", operation_id="experimentFunnelResult")
def funnel_result(workspace_id: str, funnel_id: str,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    funnel = _get(db, ExperimentFunnel, workspace_id, funnel_id, "funnel")
    return _funnel_analysis(db, workspace_id, funnel)


@router.get("/reports", operation_id="listCustomReports")
def list_reports(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(CustomReport).where(
        CustomReport.workspace_id == workspace_id
    ).order_by(CustomReport.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "report_type": r.report_type,
             "config": r.config} for r in rows]


@router.post("/reports", status_code=status.HTTP_201_CREATED, operation_id="createCustomReport")
def create_report(workspace_id: str, body: ReportIn,
                  principal: Principal = Depends(require(NOTE_WRITE)),
                  db: Session = Depends(get_db)) -> dict:
    """GB-024: a bespoke report view over local experiment results."""
    verify_workspace(principal, workspace_id)
    if body.report_type == "funnel_summary":
        funnel_id = body.config.get("funnel_id")
        if not funnel_id:
            raise HTTPException(status_code=422, detail="funnel_summary needs a funnel_id")
        _get(db, ExperimentFunnel, workspace_id, funnel_id, "funnel")
    elif "experiment_key" not in body.config:
        raise HTTPException(status_code=422, detail="config needs an experiment_key")
    try:
        _clean_ref(body.config["experiment_key"]) if "experiment_key" in body.config else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if _exists(db, CustomReport, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="custom report key already exists")
    row = CustomReport(id=new_id(), workspace_id=workspace_id, key=body.key,
                       name=body.name, report_type=body.report_type,
                       config=body.config, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, REPORT_CREATED, row.id,
           {"report_type": row.report_type}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "report_type": row.report_type, "config": row.config}


@router.post("/reports/{report_id}/run", operation_id="runCustomReport")
def run_report(workspace_id: str, report_id: str,
               principal: Principal = Depends(require(CONTACT_READ)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    report = _get(db, CustomReport, workspace_id, report_id, "custom report")
    if report.report_type == "funnel_summary":
        funnel = _get(db, ExperimentFunnel, workspace_id,
                      report.config["funnel_id"], "funnel")
        result = {"report_type": "funnel_summary", **_funnel_analysis(db, workspace_id, funnel)}
        db.flush()
        _audit(db, workspace_id, REPORT_RUN, report.id,
               {"report_type": report.report_type}, principal)
        db.commit()
        return {"report_id": report.id, "name": report.name, **result}
    experiment_key = _clean_ref(report.config.get("experiment_key", ""))
    if report.report_type == "experiment_summary":
        ids = _experiment_ids(db, workspace_id, experiment_key)
        rows = []
        if ids:
            rows = db.execute(select(ExperimentObservation).where(
                ExperimentObservation.workspace_id == workspace_id,
                ExperimentObservation.experiment_id.in_(ids),
            ).order_by(ExperimentObservation.variant)).scalars().all()
        data = [{"variant": r.variant, "sessions": r.sessions, "conversions": r.conversions,
                 "rate": (r.conversions / r.sessions) if r.sessions else 0.0} for r in rows]
        result = {"report_type": "experiment_summary", "experiment_key": experiment_key,
                  "variants": data,
                  "total_sessions": sum(r["sessions"] for r in data),
                  "total_conversions": sum(r["conversions"] for r in data)}
    elif report.report_type == "timeseries_summary":
        points = db.execute(select(TimeSeriesPoint).where(
            TimeSeriesPoint.workspace_id == workspace_id,
            TimeSeriesPoint.experiment_key == experiment_key,
        ).order_by(TimeSeriesPoint.day)).scalars().all()
        result = {"report_type": "timeseries_summary", "experiment_key": experiment_key,
                  "points": [{"day": p.day, "metric_key": p.metric_key,
                              "dimension": p.dimension, "sessions": p.sessions,
                              "conversions": p.conversions, "value_sum": p.value_sum}
                             for p in points]}
    db.flush()
    _audit(db, workspace_id, REPORT_RUN, report.id,
           {"report_type": report.report_type}, principal)
    db.commit()
    return {"report_id": report.id, "name": report.name, **result}


@router.get("/carryover", operation_id="listCarryoverAssessments")
def list_carryover(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(CarryoverAssessment).where(
        CarryoverAssessment.workspace_id == workspace_id
    ).order_by(CarryoverAssessment.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "experiment_key": r.experiment_key,
             "gap_days": r.gap_days, "washout_days": r.washout_days,
             "warning": r.warning, "acknowledged": r.acknowledged,
             "guidance": r.guidance} for r in rows]


@router.post("/carryover", status_code=status.HTTP_201_CREATED,
             operation_id="assessCarryoverRisk")
def assess_carryover(workspace_id: str, body: CarryoverIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    """GB-101: warn when a restart may carry over learning between variants."""
    verify_workspace(principal, workspace_id)
    previous = date.fromisoformat(body.previous_end)
    restart = date.fromisoformat(body.restart)
    gap = (restart - previous).days
    if gap < 0:
        raise HTTPException(status_code=422, detail="restart must follow the previous end")
    if _exists(db, CarryoverAssessment, workspace_id, body.key):
        raise HTTPException(status_code=409, detail="carryover assessment key already exists")
    warning = gap < body.washout_days
    if warning:
        guidance = (
            f"Only {gap} day(s) elapsed before restart; the configured washout is "
            f"{body.washout_days} day(s). Re-randomise users or wait for the full washout "
            "before interpreting results, because prior-variant learning can carry over."
        )
    else:
        guidance = (
            f"{gap} day(s) elapsed, meeting the {body.washout_days}-day washout. "
            "Carryover risk from prior-variant learning is low; still record the restart."
        )
    row = CarryoverAssessment(id=new_id(), workspace_id=workspace_id, key=body.key,
                              experiment_key=body.experiment_key,
                              previous_end=body.previous_end, restart=body.restart,
                              washout_days=body.washout_days, gap_days=gap,
                              warning=warning, guidance=guidance, acknowledged=False,
                              created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, CARRYOVER_ASSESSED, row.id,
           {"experiment_key": row.experiment_key, "warning": warning}, principal)
    db.commit()
    return {"id": row.id, "gap_days": gap, "warning": warning, "guidance": guidance}


@router.post("/carryover/{assessment_id}/acknowledge", operation_id="acknowledgeCarryoverRisk")
def acknowledge_carryover(workspace_id: str, assessment_id: str,
                          principal: Principal = Depends(require(NOTE_WRITE)),
                          db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _get(db, CarryoverAssessment, workspace_id, assessment_id, "carryover assessment")
    row.acknowledged = True
    db.flush()
    _audit(db, workspace_id, CARRYOVER_ACKED, row.id, {}, principal)
    db.commit()
    return {"id": row.id, "acknowledged": True}
