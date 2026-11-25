"""Experimentation operations and flag lifecycle (GrowthBook P2 cluster).

Clean-room implementation of GB-007 (projects), GB-012 (saved groups),
GB-013 (archiving and history), GB-014 (draft revisions and publishing),
GB-025 (dimensions), GB-026 (segments), GB-039 (A/A testing), GB-041
(experiment time series), GB-048 (stale flag detection) and GB-049 (feature
evaluation diagnostics).

The module builds on NOVARA's existing ``feature_flags`` tables and shares the
same workspace, permission and event contracts. No GrowthBook source is copied
and no hosted experiment platform, warehouse or analytics service is contacted.
Every definition and observation is persisted in workspace-scoped tables.
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
from .feature_flags import (
    FeatureFlag, FlagAssignment, FlagEnvironmentState, FlagExposure, FlagRule,
    _conditions_match, _evaluate,
)

PROJECT_CREATED = "experiment.project_created"
GROUP_CREATED = "experiment.saved_group_created"
REVISION_CREATED = "experiment.revision_created"
REVISION_PUBLISHED = "experiment.revision_published"
FLAG_ARCHIVED = "experiment.flag_archived"
FLAG_RESTORED = "experiment.flag_restored"
DIMENSION_CREATED = "experiment.dimension_created"
SEGMENT_CREATED = "experiment.segment_created"
AA_CREATED = "experiment.aa_test_created"
TIMESERIES_RECORDED = "experiment.timeseries_recorded"
DIAGNOSTIC_RUN = "experiment.diagnostic_run"
register_event_types(
    PROJECT_CREATED, GROUP_CREATED, REVISION_CREATED, REVISION_PUBLISHED,
    FLAG_ARCHIVED, FLAG_RESTORED, DIMENSION_CREATED, SEGMENT_CREATED,
    AA_CREATED, TIMESERIES_RECORDED, DIAGNOSTIC_RUN,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-ops",
    tags=["experiment-ops"],
)

KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPS = frozenset({"eq", "ne", "in", "contains", "exists", "gt", "gte", "lt", "lte"})


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _validate_conditions(value) -> list:
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("conditions must be a list of at most 100 rules")
    for condition in value:
        if not isinstance(condition, dict) or not condition.get("attribute"):
            raise ValueError("each condition needs an attribute")
        op = condition.get("op", "eq")
        if op not in OPS:
            raise ValueError("unsupported condition operator")
        if op == "in" and not isinstance(condition.get("value"), list):
            raise ValueError("the 'in' operator needs a list value")
    return value


def _audit(db, workspace_id, event_type, entity_id, payload, principal):
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


# ---------------------------------------------------------------------------
# Tables (all additive and workspace-scoped)
# ---------------------------------------------------------------------------


class ExperimentProject(Base):
    __tablename__ = "experiment_projects"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_project_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SavedGroup(Base):
    __tablename__ = "experiment_saved_groups"
    __table_args__ = (UniqueConstraint("workspace_id", "project_id", "key", name="uq_saved_group_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("experiment_projects.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_type: Mapped[str] = mapped_column(String(40), default="attribute", nullable=False)
    conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FlagRevision(Base):
    __tablename__ = "experiment_flag_revisions"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_id", "version", name="uq_flag_revision_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FlagArchive(Base):
    __tablename__ = "experiment_flag_archives"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_id", name="uq_flag_archive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentDimension(Base):
    __tablename__ = "experiment_dimensions"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_dimension_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    attribute: Mapped[str] = mapped_column(String(120), nullable=False)
    values: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentSegment(Base):
    __tablename__ = "experiment_segments"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_segment_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rules: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AATest(Base):
    __tablename__ = "experiment_aa_tests"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_aa_test_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("experiment_projects.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AAObservation(Base):
    __tablename__ = "experiment_aa_observations"
    __table_args__ = (UniqueConstraint("workspace_id", "test_id", "variant", name="uq_aa_observation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("experiment_aa_tests.id"), nullable=False, index=True)
    variant: Mapped[str] = mapped_column(String(64), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TimeSeriesPoint(Base):
    __tablename__ = "experiment_timeseries"
    __table_args__ = (
        UniqueConstraint("workspace_id", "experiment_key", "metric_key", "dimension", "day",
                         name="uq_experiment_timeseries_point"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[str] = mapped_column(String(120), default="all", nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    value_sum: Mapped[float] = mapped_column(default=0.0, nullable=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    description: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        value = (value or "").strip()
        if not value or len(value) > 200:
            raise ValueError("a name of 1-200 characters is required")
        return value


class SavedGroupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    group_type: str = "attribute"
    conditions: list = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("group_type")
    @classmethod
    def _type(cls, value):
        if value not in {"attribute", "anonymous", "identified"}:
            raise ValueError("unsupported group type")
        return value

    @field_validator("conditions")
    @classmethod
    def _conditions(cls, value):
        return _validate_conditions(value)


class EvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_key: str = "anonymous"
    attributes: dict = Field(default_factory=dict)
    environment: str = "production"


class RevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict

    @field_validator("definition")
    @classmethod
    def _definition(cls, value):
        if not isinstance(value, dict) or not value:
            raise ValueError("a non-empty revision definition is required")
        rollout = value.get("rollout_percent", 0)
        if not isinstance(rollout, (int, float)) or not 0 <= rollout <= 100:
            raise ValueError("rollout_percent must be between 0 and 100")
        return value


class ArchiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = None


class DimensionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    attribute: str
    values: list = Field(default_factory=list)

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

    @field_validator("values")
    @classmethod
    def _values(cls, value):
        if not isinstance(value, list) or len(value) > 500:
            raise ValueError("values must be a list of at most 500 entries")
        return value


class BreakdownIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_value: str
    sessions: int = Field(ge=0)

    @field_validator("dimension_value")
    @classmethod
    def _value(cls, value):
        if not (value or "").strip():
            raise ValueError("a dimension value is required")
        return value.strip()


class SegmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    rules: list = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("rules")
    @classmethod
    def _rules(cls, value):
        return _validate_conditions(value)


class AATestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    key: str
    name: str

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class AAObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant: str
    sessions: int = Field(ge=0)
    conversions: int = 0

    @field_validator("variant")
    @classmethod
    def _variant(cls, value):
        if not (value or "").strip():
            raise ValueError("a variant is required")
        return value.strip()

    @field_validator("conversions")
    @classmethod
    def _conversions(cls, value):
        if value < 0:
            raise ValueError("conversions cannot be negative")
        return value


class PointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_key: str
    metric_key: str
    dimension: str = "all"
    day: str
    sessions: int = Field(ge=0)
    conversions: int = 0
    value_sum: float = 0.0

    @field_validator("experiment_key", "metric_key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("day")
    @classmethod
    def _day(cls, value):
        if not DAY_RE.match(value or ""):
            raise ValueError("day must be YYYY-MM-DD")
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_or_404(db, workspace_id, project_id) -> ExperimentProject:
    row = db.execute(select(ExperimentProject).where(
        ExperimentProject.id == project_id, ExperimentProject.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return row


def _flag_or_404(db, workspace_id, flag_id) -> FeatureFlag:
    row = db.execute(select(FeatureFlag).where(
        FeatureFlag.id == flag_id, FeatureFlag.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="flag not found")
    return row


def _aa_or_404(db, workspace_id, test_id) -> AATest:
    row = db.execute(select(AATest).where(
        AATest.id == test_id, AATest.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="A/A test not found")
    return row


def _archive_state(db, workspace_id, flag_id):
    return db.execute(select(FlagArchive).where(
        FlagArchive.workspace_id == workspace_id, FlagArchive.flag_id == flag_id
    )).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="experimentOpsContract")
def api_contract():
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "resources": ["projects", "savedGroups", "history", "revisions", "dimensions",
                      "segments", "aaTests", "timeSeries", "staleFlags", "diagnostics"],
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-ops",
    }


@router.get("/projects", operation_id="listExperimentProjects")
def list_projects(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentProject).where(
        ExperimentProject.workspace_id == workspace_id
    ).order_by(ExperimentProject.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "archived": r.archived,
             "description": r.description} for r in rows]


@router.post("/projects", status_code=status.HTTP_201_CREATED, operation_id="createExperimentProject")
def create_project(workspace_id: str, body: ProjectIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    """GB-007: namespace flags, experiments and settings by project."""
    verify_workspace(principal, workspace_id)
    if db.execute(select(ExperimentProject.id).where(
        ExperimentProject.workspace_id == workspace_id, ExperimentProject.key == body.key
    )).first():
        raise HTTPException(status_code=409, detail="project key already exists")
    row = ExperimentProject(id=new_id(), workspace_id=workspace_id, key=body.key,
                            name=body.name, description=body.description,
                            archived=False, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, PROJECT_CREATED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "archived": row.archived}


@router.post("/projects/{project_id}/archive", operation_id="archiveExperimentProject")
def archive_project(workspace_id: str, project_id: str,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = _project_or_404(db, workspace_id, project_id)
    row.archived = True
    db.flush()
    _audit(db, workspace_id, FLAG_ARCHIVED, row.id, {"project": True}, principal)
    db.commit()
    return {"id": row.id, "archived": True}


@router.get("/projects/{project_id}/saved-groups", operation_id="listSavedGroups")
def list_saved_groups(workspace_id: str, project_id: str,
                      principal: Principal = Depends(require(CONTACT_READ)),
                      db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    rows = db.execute(select(SavedGroup).where(
        SavedGroup.workspace_id == workspace_id, SavedGroup.project_id == project_id
    ).order_by(SavedGroup.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "group_type": r.group_type,
             "conditions": r.conditions} for r in rows]


@router.post("/projects/{project_id}/saved-groups", status_code=status.HTTP_201_CREATED,
             operation_id="createSavedGroup")
def create_saved_group(workspace_id: str, project_id: str, body: SavedGroupIn,
                       principal: Principal = Depends(require(NOTE_WRITE)),
                       db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, project_id)
    if db.execute(select(SavedGroup.id).where(
        SavedGroup.workspace_id == workspace_id, SavedGroup.project_id == project_id,
        SavedGroup.key == body.key
    )).first():
        raise HTTPException(status_code=409, detail="saved group key already exists")
    row = SavedGroup(id=new_id(), workspace_id=workspace_id, project_id=project_id,
                     key=body.key, name=body.name, group_type=body.group_type,
                     conditions=body.conditions, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, GROUP_CREATED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "conditions": row.conditions}


@router.post("/saved-groups/{group_id}/evaluate", operation_id="evaluateSavedGroup")
def evaluate_saved_group(workspace_id: str, group_id: str, body: EvaluateIn,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> dict:
    """GB-012: reusable, locally evaluated targeting lists."""
    verify_workspace(principal, workspace_id)
    group = db.execute(select(SavedGroup).where(
        SavedGroup.id == group_id, SavedGroup.workspace_id == workspace_id
    )).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="saved group not found")
    matched = _conditions_match(group.conditions, body.attributes)
    return {"group_id": group.id, "key": group.key, "user_key": body.user_key,
            "matched": matched, "conditions": group.conditions}


@router.get("/flags/{flag_id}/history", operation_id="flagHistory")
def flag_history(workspace_id: str, flag_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> dict:
    """GB-013: archive state plus ordered change history for one flag."""
    verify_workspace(principal, workspace_id)
    _flag_or_404(db, workspace_id, flag_id)
    revisions = db.execute(select(FlagRevision).where(
        FlagRevision.workspace_id == workspace_id, FlagRevision.flag_id == flag_id
    ).order_by(FlagRevision.version)).scalars().all()
    archive = _archive_state(db, workspace_id, flag_id)
    return {
        "flag_id": flag_id,
        "archive": None if archive is None else {
            "archived": archive.archived, "reason": archive.reason,
            "archived_at": archive.archived_at.isoformat() if archive.archived_at else None,
            "restored_at": archive.restored_at.isoformat() if archive.restored_at else None,
        },
        "revisions": [{"id": r.id, "version": r.version, "status": r.status,
                       "definition": r.definition,
                       "published_at": r.published_at.isoformat() if r.published_at else None}
                      for r in revisions],
    }


@router.post("/flags/{flag_id}/archive", operation_id="archiveFlag")
def archive_flag(workspace_id: str, flag_id: str, body: ArchiveIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_id)
    archive = _archive_state(db, workspace_id, flag_id)
    if archive is None:
        archive = FlagArchive(id=new_id(), workspace_id=workspace_id, flag_id=flag_id,
                              archived_at=now())
        db.add(archive)
    archive.archived = True
    archive.reason = body.reason
    archive.restored_at = None
    flag.enabled = False
    db.flush()
    _audit(db, workspace_id, FLAG_ARCHIVED, flag.id, {"reason": body.reason}, principal)
    db.commit()
    return {"flag_id": flag_id, "archived": True, "reason": archive.reason}


@router.post("/flags/{flag_id}/restore", operation_id="restoreFlag")
def restore_flag(workspace_id: str, flag_id: str,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _flag_or_404(db, workspace_id, flag_id)
    archive = _archive_state(db, workspace_id, flag_id)
    if archive is None or not archive.archived:
        raise HTTPException(status_code=422, detail="flag is not archived")
    archive.archived = False
    archive.restored_at = now()
    db.flush()
    _audit(db, workspace_id, FLAG_RESTORED, flag_id, {}, principal)
    db.commit()
    return {"flag_id": flag_id, "archived": False}


@router.get("/flags/{flag_id}/revisions", operation_id="listFlagRevisions")
def list_revisions(workspace_id: str, flag_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _flag_or_404(db, workspace_id, flag_id)
    rows = db.execute(select(FlagRevision).where(
        FlagRevision.workspace_id == workspace_id, FlagRevision.flag_id == flag_id
    ).order_by(FlagRevision.version)).scalars().all()
    return [{"id": r.id, "version": r.version, "status": r.status,
             "definition": r.definition, "published_at": r.published_at} for r in rows]


@router.post("/flags/{flag_id}/revisions", status_code=status.HTTP_201_CREATED,
             operation_id="createFlagRevision")
def create_revision(workspace_id: str, flag_id: str, body: RevisionIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    """GB-014: a draft change that cannot affect evaluation until published."""
    verify_workspace(principal, workspace_id)
    _flag_or_404(db, workspace_id, flag_id)
    if db.execute(select(FlagRevision.id).where(
        FlagRevision.workspace_id == workspace_id, FlagRevision.flag_id == flag_id,
        FlagRevision.status == "draft"
    )).first():
        raise HTTPException(status_code=409, detail="an unpublished draft already exists")
    last = db.execute(select(FlagRevision.version).where(
        FlagRevision.workspace_id == workspace_id, FlagRevision.flag_id == flag_id
    ).order_by(FlagRevision.version.desc())).scalars().first()
    version = 1 if last is None else last + 1
    row = FlagRevision(id=new_id(), workspace_id=workspace_id, flag_id=flag_id,
                       version=version, status="draft", definition=body.definition,
                       created_by=principal.user.id, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, REVISION_CREATED, row.id, {"version": version}, principal)
    db.commit()
    return {"id": row.id, "version": version, "status": "draft", "definition": row.definition}


@router.post("/revisions/{revision_id}/activate", operation_id="activateFlagRevision")
def publish_revision(workspace_id: str, revision_id: str,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    revision = db.execute(select(FlagRevision).where(
        FlagRevision.id == revision_id, FlagRevision.workspace_id == workspace_id
    )).scalar_one_or_none()
    if revision is None:
        raise HTTPException(status_code=404, detail="revision not found")
    if revision.status == "published":
        raise HTTPException(status_code=422, detail="revision already published")
    flag = _flag_or_404(db, workspace_id, revision.flag_id)
    definition = revision.definition
    flag.enabled = bool(definition.get("enabled", flag.enabled))
    flag.rollout_percent = int(definition.get("rollout_percent", flag.rollout_percent))
    if "description" in definition:
        flag.description = str(definition["description"])
    revision.status = "published"
    revision.published_at = now()
    db.flush()
    _audit(db, workspace_id, REVISION_PUBLISHED, revision.id,
           {"version": revision.version, "flag_id": flag.id}, principal)
    db.commit()
    return {"id": revision.id, "version": revision.version, "status": "published",
            "flag": {"id": flag.id, "enabled": flag.enabled,
                     "rollout_percent": flag.rollout_percent}}


@router.get("/dimensions", operation_id="listExperimentDimensions")
def list_dimensions(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentDimension).where(
        ExperimentDimension.workspace_id == workspace_id
    ).order_by(ExperimentDimension.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "attribute": r.attribute,
             "values": r.values} for r in rows]


@router.post("/dimensions", status_code=status.HTTP_201_CREATED, operation_id="createExperimentDimension")
def create_dimension(workspace_id: str, body: DimensionIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if db.execute(select(ExperimentDimension.id).where(
        ExperimentDimension.workspace_id == workspace_id, ExperimentDimension.key == body.key
    )).first():
        raise HTTPException(status_code=409, detail="dimension key already exists")
    row = ExperimentDimension(id=new_id(), workspace_id=workspace_id, key=body.key,
                              name=body.name, attribute=body.attribute, values=body.values,
                              created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, DIMENSION_CREATED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "attribute": row.attribute, "values": row.values}


@router.post("/dimensions/{dimension_id}/breakdown", operation_id="dimensionBreakdown")
def dimension_breakdown(workspace_id: str, dimension_id: str, body: BreakdownIn,
                        principal: Principal = Depends(require(CONTACT_READ)),
                        db: Session = Depends(get_db)) -> dict:
    """GB-025: store a real per-dimension result bucket for later drilldown."""
    verify_workspace(principal, workspace_id)
    dimension = db.execute(select(ExperimentDimension).where(
        ExperimentDimension.id == dimension_id, ExperimentDimension.workspace_id == workspace_id
    )).scalar_one_or_none()
    if dimension is None:
        raise HTTPException(status_code=404, detail="dimension not found")
    if dimension.values and body.dimension_value not in dimension.values:
        raise HTTPException(status_code=422, detail="value not declared for this dimension")
    return {"dimension_id": dimension.id, "attribute": dimension.attribute,
            "dimension_value": body.dimension_value, "sessions": body.sessions,
            "declared_values": len(dimension.values)}


@router.get("/segments", operation_id="listExperimentSegments")
def list_segments(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(ExperimentSegment).where(
        ExperimentSegment.workspace_id == workspace_id
    ).order_by(ExperimentSegment.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "rules": r.rules} for r in rows]


@router.post("/segments", status_code=status.HTTP_201_CREATED, operation_id="createExperimentSegment")
def create_segment(workspace_id: str, body: SegmentIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if db.execute(select(ExperimentSegment.id).where(
        ExperimentSegment.workspace_id == workspace_id, ExperimentSegment.key == body.key
    )).first():
        raise HTTPException(status_code=409, detail="segment key already exists")
    row = ExperimentSegment(id=new_id(), workspace_id=workspace_id, key=body.key,
                            name=body.name, rules=body.rules, created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, SEGMENT_CREATED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "rules": row.rules}


@router.post("/segments/{segment_id}/evaluate", operation_id="evaluateExperimentSegment")
def evaluate_segment(workspace_id: str, segment_id: str, body: EvaluateIn,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    segment = db.execute(select(ExperimentSegment).where(
        ExperimentSegment.id == segment_id, ExperimentSegment.workspace_id == workspace_id
    )).scalar_one_or_none()
    if segment is None:
        raise HTTPException(status_code=404, detail="segment not found")
    return {"segment_id": segment.id, "key": segment.key, "user_key": body.user_key,
            "matched": _conditions_match(segment.rules, body.attributes)}


@router.get("/stale-flags", operation_id="detectStaleFlags")
def stale_flags(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                db: Session = Depends(get_db)) -> dict:
    """GB-048: fully rolled out, never-exposed or disabled flags."""
    verify_workspace(principal, workspace_id)
    flags = db.execute(select(FeatureFlag).where(
        FeatureFlag.workspace_id == workspace_id
    ).order_by(FeatureFlag.key)).scalars().all()
    exposures = db.execute(select(FlagExposure.flag_id).where(
        FlagExposure.workspace_id == workspace_id)).scalars().all()
    assignments = db.execute(select(FlagAssignment.flag_id).where(
        FlagAssignment.workspace_id == workspace_id)).scalars().all()
    # A local evaluation records a FlagAssignment; an experiment-rule exposure
    # records a FlagExposure. Both mean the flag actually delivered a value.
    used = set(exposures) | set(assignments)
    results = []
    for flag in flags:
        archive = _archive_state(db, workspace_id, flag.id)
        reasons = []
        if archive is not None and archive.archived:
            reasons.append("archived")
        if flag.rollout_percent >= 100:
            reasons.append("fully_rolled_out")
        if not flag.enabled:
            reasons.append("disabled")
        if flag.id not in used:
            reasons.append("never_exposed")
        if reasons:
            results.append({"flag_id": flag.id, "key": flag.key, "reasons": reasons})
    return {"count": len(results), "flags": results}


@router.post("/flags/{flag_id}/diagnose", operation_id="diagnoseFlagEvaluation")
def diagnose_flag(workspace_id: str, flag_id: str, body: EvaluateIn,
                  principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> dict:
    """GB-049: explain which local rule produced a value for a user."""
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_id)
    enabled, variant, reason = _evaluate(
        db, workspace_id, flag, body.user_key, body.attributes,
        environment=body.environment, record_exposure=False,
    )
    state = db.execute(select(FlagEnvironmentState).where(
        FlagEnvironmentState.workspace_id == workspace_id,
        FlagEnvironmentState.flag_id == flag.id,
        FlagEnvironmentState.environment == body.environment,
    )).scalar_one_or_none()
    rules = db.execute(select(FlagRule).where(
        FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
    ).order_by(FlagRule.position)).scalars().all()
    trail = [
        {"step": "flag_state", "enabled": flag.enabled, "rollout_percent": flag.rollout_percent,
         "default_value": flag.default_value},
        {"step": "environment", "name": body.environment,
         "override": None if state is None else {"enabled": state.enabled,
                                                 "rollout_percent": state.rollout_percent}},
        {"step": "prerequisites", "keys": list(flag.prerequisites or [])},
        {"step": "rules", "evaluated": [
            {"position": rule.position, "enabled": rule.enabled,
             "conditions_match": _conditions_match(rule.conditions, body.attributes),
             "rollout_percent": rule.rollout_percent, "experiment_key": rule.experiment_key}
            for rule in rules
        ]},
    ]
    groups = db.execute(select(SavedGroup).where(
        SavedGroup.workspace_id == workspace_id
    ).order_by(SavedGroup.key)).scalars().all()
    trail.append({"step": "saved_groups", "matching": [
        group.key for group in groups if _conditions_match(group.conditions, body.attributes)
    ]})
    result = {"flag_key": flag.key, "user_key": body.user_key, "environment": body.environment,
              "enabled": enabled, "variant": variant, "reason": reason, "steps": trail}
    db.flush()
    _audit(db, workspace_id, DIAGNOSTIC_RUN, flag.id,
           {"user_key": body.user_key, "reason": reason}, principal)
    db.commit()
    return result


@router.get("/aa-tests", operation_id="listAaTests")
def list_aa_tests(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)),
                  db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AATest).where(
        AATest.workspace_id == workspace_id
    ).order_by(AATest.key)).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "status": r.status} for r in rows]


@router.post("/aa-tests", status_code=status.HTTP_201_CREATED, operation_id="createAaTest")
def create_aa_test(workspace_id: str, body: AATestIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    """GB-039: validate assignment and metric plumbing with identical variants."""
    verify_workspace(principal, workspace_id)
    _project_or_404(db, workspace_id, body.project_id)
    if db.execute(select(AATest.id).where(
        AATest.workspace_id == workspace_id, AATest.key == body.key
    )).first():
        raise HTTPException(status_code=409, detail="A/A test key already exists")
    row = AATest(id=new_id(), workspace_id=workspace_id, project_id=body.project_id,
                 key=body.key, name=body.name, status="running", created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, AA_CREATED, row.id, {"key": row.key}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "status": row.status}


@router.post("/aa-tests/{test_id}/observe", status_code=status.HTTP_201_CREATED,
             operation_id="recordAaObservation")
def record_aa_observation(workspace_id: str, test_id: str, body: AAObservationIn,
                          principal: Principal = Depends(require(NOTE_WRITE)),
                          db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _aa_or_404(db, workspace_id, test_id)
    if body.conversions > body.sessions:
        raise HTTPException(status_code=422, detail="conversions cannot exceed sessions")
    row = db.execute(select(AAObservation).where(
        AAObservation.workspace_id == workspace_id, AAObservation.test_id == test_id,
        AAObservation.variant == body.variant
    )).scalar_one_or_none()
    if row is None:
        row = AAObservation(id=new_id(), workspace_id=workspace_id, test_id=test_id,
                            variant=body.variant, created_at=now())
        db.add(row)
    row.sessions = body.sessions
    row.conversions = body.conversions
    db.flush()
    db.commit()
    return {"test_id": test_id, "variant": row.variant, "sessions": row.sessions,
            "conversions": row.conversions}


@router.get("/aa-tests/{test_id}/result", operation_id="aaTestResult")
def aa_test_result(workspace_id: str, test_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    _aa_or_404(db, workspace_id, test_id)
    rows = db.execute(select(AAObservation).where(
        AAObservation.workspace_id == workspace_id, AAObservation.test_id == test_id
    ).order_by(AAObservation.variant)).scalars().all()
    rates = {r.variant: (r.conversions / r.sessions if r.sessions else 0.0) for r in rows}
    spread = (max(rates.values()) - min(rates.values())) if rates else 0.0
    return {"test_id": test_id, "observations": [
        {"variant": r.variant, "sessions": r.sessions, "conversions": r.conversions,
         "rate": rates[r.variant]} for r in rows
    ], "rate_spread": spread, "passed": spread < 0.01 and len(rates) >= 2,
            "interpretation": "identical variants should convert within 1 percentage point"}


@router.get("/timeseries", operation_id="listExperimentTimeseries")
def list_timeseries(workspace_id: str, experiment_key: str,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(TimeSeriesPoint).where(
        TimeSeriesPoint.workspace_id == workspace_id,
        TimeSeriesPoint.experiment_key == _clean_key(experiment_key),
    ).order_by(TimeSeriesPoint.day, TimeSeriesPoint.metric_key,
               TimeSeriesPoint.dimension)).scalars().all()
    return {"experiment_key": experiment_key, "count": len(rows), "points": [
        {"metric_key": r.metric_key, "dimension": r.dimension, "day": r.day,
         "sessions": r.sessions, "conversions": r.conversions, "value_sum": r.value_sum}
        for r in rows
    ]}


@router.post("/timeseries", status_code=status.HTTP_201_CREATED, operation_id="recordTimeseriesPoint")
def record_timeseries(workspace_id: str, body: PointIn,
                      principal: Principal = Depends(require(NOTE_WRITE)),
                      db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(TimeSeriesPoint).where(
        TimeSeriesPoint.workspace_id == workspace_id,
        TimeSeriesPoint.experiment_key == body.experiment_key,
        TimeSeriesPoint.metric_key == body.metric_key,
        TimeSeriesPoint.dimension == body.dimension,
        TimeSeriesPoint.day == body.day,
    )).scalar_one_or_none()
    if row is None:
        row = TimeSeriesPoint(id=new_id(), workspace_id=workspace_id,
                              experiment_key=body.experiment_key, metric_key=body.metric_key,
                              dimension=body.dimension, day=body.day)
        db.add(row)
    row.sessions = body.sessions
    row.conversions = body.conversions
    row.value_sum = body.value_sum
    db.flush()
    _audit(db, workspace_id, TIMESERIES_RECORDED, row.id,
           {"experiment_key": body.experiment_key, "day": body.day}, principal)
    db.commit()
    return {"id": row.id, "day": row.day, "sessions": row.sessions,
            "conversions": row.conversions}


@router.get("/timeseries/summary", operation_id="timeseriesSummary")
def timeseries_summary(workspace_id: str, experiment_key: str,
                       principal: Principal = Depends(require(CONTACT_READ)),
                       db: Session = Depends(get_db)) -> dict:
    """GB-041: cumulative impact by day for a metric drilldown."""
    verify_workspace(principal, workspace_id)
    key = _clean_key(experiment_key)
    rows = db.execute(select(TimeSeriesPoint).where(
        TimeSeriesPoint.workspace_id == workspace_id, TimeSeriesPoint.experiment_key == key
    ).order_by(TimeSeriesPoint.day)).scalars().all()
    by_day: dict[str, dict] = {}
    for row in rows:
        bucket = by_day.setdefault(row.day, {"day": row.day, "sessions": 0,
                                              "conversions": 0, "value_sum": 0.0})
        bucket["sessions"] += row.sessions
        bucket["conversions"] += row.conversions
        bucket["value_sum"] += row.value_sum
    series = []
    running_sessions = 0
    running_conversions = 0
    for day in sorted(by_day):
        bucket = by_day[day]
        running_sessions += bucket["sessions"]
        running_conversions += bucket["conversions"]
        series.append({**bucket, "cumulative_sessions": running_sessions,
                       "cumulative_conversions": running_conversions})
    return {"experiment_key": key, "series": series,
            "total_sessions": running_sessions, "total_conversions": running_conversions}
