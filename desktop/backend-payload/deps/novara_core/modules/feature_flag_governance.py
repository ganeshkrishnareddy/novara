"""Advanced feature-flag governance (GrowthBook P2 commercial-tier clean room).

Clean-room implementations from the documented public method of fourteen
commercial capabilities:

* GB-183 scheduled feature flags
* GB-196 hash-secure targeting attributes
* GB-206 sticky bucketing
* GB-209 prerequisites
* GB-210 prerequisite targeting conditions
* GB-211 redirect rule results
* GB-224 environment inheritance
* GB-225 reusable flag templates
* GB-231 safe rollouts with guardrail rollback
* GB-232 / GB-233 require-project workspace settings
* GB-247 ramp schedules
* GB-248 scheduled revisions
* GB-249 typed feature configurations

All logic runs locally with the Python standard library. No GrowthBook source,
SDK, hosted endpoint, licence server, warehouse or external service is used.
State is persisted in workspace-scoped additive tables and every mutation is
published to NOVARA's shared event spine.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

FG_PREFIX = "/api/v1/workspaces/{workspace_id}/flag-governance"

GOVERNANCE_CHANGED = "flag.governance_changed"
register_event_types(GOVERNANCE_CHANGED)

router = APIRouter(prefix=FG_PREFIX, tags=["flag-governance"])

KEY_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{1,63}$")
ENV_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{1,31}$")
VALID_STATES = frozenset({"on", "off", "variant"})


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _parse_ts(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def schedule_state(schedules: list[dict], at: str) -> dict | None:
    """GB-183: return the most recent schedule that has started by ``at``."""
    when = _parse_ts(at)
    eligible = [s for s in schedules if _parse_ts(s["starts_at"]) <= when]
    if not eligible:
        return None
    chosen = max(eligible, key=lambda s: (_parse_ts(s["starts_at"]), s["id"]))
    return chosen


def ramp_percent(start: int, end: int, starts_at: str, ends_at: str, at: str) -> int:
    """GB-247: linear traffic ramp between two percentages over a time window."""
    begin, finish, when = _parse_ts(starts_at), _parse_ts(ends_at), _parse_ts(at)
    if finish <= begin:
        raise ValueError("ramp end must be after start")
    if not 0 <= start <= 100 or not 0 <= end <= 100:
        raise ValueError("percentages must be between 0 and 100")
    if when <= begin:
        return start
    if when >= finish:
        return end
    fraction = (when - begin).total_seconds() / (finish - begin).total_seconds()
    return int(round(start + (end - start) * fraction))


def hash_attribute(value: str, salt: str) -> str:
    """GB-196: deterministic salted SHA-256 of a sensitive attribute value."""
    if not value or not salt:
        raise ValueError("value and salt are required")
    return hashlib.sha256((salt + ":" + value).encode("utf-8")).hexdigest()


def sticky_bucket(user_key: str, flag_key: str, percent: int) -> bool:
    """GB-206: deterministic, stable bucketing for a user and flag."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    digest = hashlib.sha256(("novara-sticky:" + flag_key + ":" + user_key).encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 10000
    return bucket < int(percent * 100)


def condition_match(condition: dict, attrs: dict) -> bool:
    """Evaluate a simple saved targeting condition (all clauses must match)."""
    clauses = condition.get("all") if isinstance(condition, dict) else None
    if clauses is None:
        return False
    for clause in clauses:
        if not isinstance(clause, dict):
            return False
        attr, op, expected = clause.get("attr"), clause.get("op"), clause.get("value")
        actual = attrs.get(attr)
        if op == "eq" and actual != expected:
            return False
        if op == "neq" and actual == expected:
            return False
        if op == "in" and actual not in (expected or []):
            return False
        if op not in ("eq", "neq", "in"):
            return False
    return True


def prerequisites_met(prereqs: list[dict], flag_values: dict[str, str], attrs: dict) -> tuple[bool, str]:
    """GB-209/210: check required values and optional targeting conditions."""
    for prereq in prereqs:
        key = prereq.get("flag_key")
        current = flag_values.get(key)
        required = prereq.get("required_value", "on")
        if current is None or current != required:
            return False, "prerequisite_value:" + str(key)
        condition = prereq.get("target_condition")
        if condition and not condition_match(condition, attrs):
            return False, "prerequisite_targeting:" + str(key)
    return True, "prerequisites_met"


def safe_rollout_decision(current_percent: int, observed_rate: float,
                          baseline_rate: float, threshold: float) -> dict:
    """GB-231: hold or roll back when a guardrail regresses past the threshold."""
    if not 0 <= current_percent <= 100 or not 0 <= threshold <= 1:
        raise ValueError("percent/threshold out of range")
    delta = observed_rate - baseline_rate
    if delta < -threshold:
        return {"action": "rollback", "next_percent": 0, "delta": delta}
    if delta > threshold:
        return {"action": "hold", "next_percent": current_percent, "delta": delta}
    return {"action": "promote", "next_percent": min(100, current_percent + 10), "delta": delta}


def revision_at(revisions: list[dict], at: str) -> dict | None:
    """GB-248: choose the latest revision effective by ``at``."""
    when = _parse_ts(at)
    eligible = [r for r in revisions if r["status"] == "applied" and _parse_ts(r["effective_at"]) <= when]
    if not eligible:
        return None
    return max(eligible, key=lambda r: _parse_ts(r["effective_at"]))


def template_flag(template: dict, flag_key: str) -> dict:
    """GB-225: instantiate a flag definition from a reusable template."""
    definition = template.get("definition")
    if not isinstance(definition, dict):
        raise ValueError("template definition must be an object")
    result = dict(definition)
    result["key"] = flag_key
    result["template_key"] = template.get("key")
    return result


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class FgSchedule(Base):
    __tablename__ = "fg_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    starts_at: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class FgSecureAttribute(Base):
    __tablename__ = "fg_secure_attributes"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_key", "attribute", name="uq_fg_secure_attr"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attribute: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    hashed_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class FgStickyAssignment(Base):
    __tablename__ = "fg_sticky_assignments"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_key", "environment", "user_key",
                                       name="uq_fg_sticky"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    user_key: Mapped[str] = mapped_column(String(320), nullable=False)
    variant: Mapped[str] = mapped_column(String(128), nullable=False)


class FgPrerequisite(Base):
    __tablename__ = "fg_prerequisites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prerequisite_key: Mapped[str] = mapped_column(String(128), nullable=False)
    required_value: Mapped[str] = mapped_column(String(128), nullable=False, default="on")
    target_condition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class FgRedirect(Base):
    __tablename__ = "fg_redirects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FgEnvironment(Base):
    __tablename__ = "fg_environments"
    __table_args__ = (UniqueConstraint("workspace_id", "environment", name="uq_fg_environment"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class FgTemplate(Base):
    __tablename__ = "fg_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_fg_template"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)


class FgSafeRollout(Base):
    __tablename__ = "fg_safe_rollouts"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_key", name="uq_fg_safe_rollout"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    guardrail_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    current_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="monitoring")


class FgSetting(Base):
    __tablename__ = "fg_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, unique=True)
    require_project_for_features: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_project_for_sdk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FgRamp(Base):
    __tablename__ = "fg_ramps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    start_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    end_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[str] = mapped_column(String(40), nullable=False)
    ends_at: Mapped[str] = mapped_column(String(40), nullable=False)


class FgRevision(Base):
    __tablename__ = "fg_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class FgConfig(Base):
    __tablename__ = "fg_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_key", "environment", name="uq_fg_config"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    environment: str = "production"
    starts_at: str
    state: dict[str, Any]


class SecureAttrIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    attribute: str = Field(min_length=1, max_length=64)
    salt: str = Field(min_length=4, max_length=64)
    value: str = Field(min_length=1, max_length=320)


class StickyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    environment: str = "production"
    user_key: str = Field(min_length=1, max_length=320)
    percent: int = 50


class PrereqIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    prerequisite_key: str = Field(min_length=1, max_length=128)
    required_value: str = "on"
    target_condition: dict[str, Any] = Field(default_factory=dict)


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_values: dict[str, str] = Field(default_factory=dict)
    attrs: dict[str, Any] = Field(default_factory=dict)


class RedirectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    rule_id: str = Field(min_length=1, max_length=128)
    target_url: str = Field(min_length=4, max_length=500)
    active: bool = True


class EnvIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment: str
    parent_environment: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    definition: dict[str, Any]


class InstantiateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    template_key: str = Field(min_length=1, max_length=128)


class SafeRolloutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    guardrail_metric: str = Field(min_length=1, max_length=128)
    threshold: float
    current_percent: int = 10

    @field_validator("threshold")
    @classmethod
    def _threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("threshold must be between 0 and 1")
        return value


class RolloutEvalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    observed_rate: float
    baseline_rate: float


class SettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    require_project_for_features: bool = False
    require_project_for_sdk: bool = False


class RampIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    environment: str = "production"
    start_percent: int
    end_percent: int
    starts_at: str
    ends_at: str


class AtIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: str


class RevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    effective_at: str
    config: dict[str, Any]


class ApplyRevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    revision_id: str | None = None


class ConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_key: str = Field(min_length=1, max_length=128)
    environment: str = "production"
    value_type: str
    value: dict[str, Any]

    @field_validator("value_type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value not in ("json", "number", "string", "boolean"):
            raise ValueError("unsupported value type")
        return value


# ---------------------------------------------------------------------------
# Helpers and routes
# ---------------------------------------------------------------------------


def _audit(db: Session, workspace_id: str, entity_id: str, payload: dict, principal: Principal) -> None:
    publish_event(db, workspace_id=workspace_id, event_type=GOVERNANCE_CHANGED,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _rows(db: Session, model, workspace_id: str, **filters):
    query = select(model).where(model.workspace_id == workspace_id)
    for field, value in filters.items():
        query = query.where(getattr(model, field) == value)
    return list(db.execute(query).scalars().all())


@router.get("/api-contract", operation_id="flagGovernanceContract")
def api_contract() -> dict:
    return {"external_calls": False,
            "source": "NOVARA clean-room; algorithms implemented locally from the documented method",
            "capabilities": ["GB-183", "GB-196", "GB-206", "GB-209", "GB-210", "GB-211",
                             "GB-224", "GB-225", "GB-231", "GB-232", "GB-233", "GB-247",
                             "GB-248", "GB-249"]}


@router.post("/schedules", status_code=status.HTTP_201_CREATED, operation_id="createFlagSchedule")
def create_schedule(workspace_id: str, body: ScheduleIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    try:
        _parse_ts(body.starts_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.state.get("state") not in VALID_STATES:
        raise HTTPException(status_code=422, detail="state must be on/off/variant")
    if not KEY_RE.match(body.flag_key) or not ENV_RE.match(body.environment):
        raise HTTPException(status_code=422, detail="invalid flag key or environment")
    row = FgSchedule(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                     environment=body.environment, starts_at=body.starts_at, state=body.state,
                     created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "schedule"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "starts_at": row.starts_at, "state": row.state}


@router.post("/schedules/resolve", operation_id="resolveFlagSchedule")
def resolve_schedule(workspace_id: str, body: CheckIn,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    """Resolve scheduled state for each flag using the request's ``at`` attribute."""
    verify_workspace(principal, workspace_id)
    at = body.attrs.get("at")
    if not isinstance(at, str):
        raise HTTPException(status_code=422, detail="attrs.at is required")
    result = {}
    for flag_key in set(body.flag_values) | set(body.attrs.get("flag_keys", [])):
        rows = _rows(db, FgSchedule, workspace_id, flag_key=flag_key)
        chosen = schedule_state([{"id": r.id, "starts_at": r.starts_at, "state": r.state} for r in rows], at)
        result[flag_key] = chosen["state"] if chosen else None
    return {"at": at, "states": result}


@router.post("/secure-attributes", status_code=status.HTTP_201_CREATED, operation_id="secureFlagAttribute")
def secure_attribute(workspace_id: str, body: SecureAttrIn,
                     principal: Principal = Depends(require(NOTE_WRITE)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(FgSecureAttribute).where(
        FgSecureAttribute.workspace_id == workspace_id,
        FgSecureAttribute.flag_key == body.flag_key,
        FgSecureAttribute.attribute == body.attribute,
    )).scalar_one_or_none()
    if row is None:
        row = FgSecureAttribute(id=new_id(), workspace_id=workspace_id,
                                flag_key=body.flag_key, attribute=body.attribute,
                                salt=body.salt, hashed_values={})
        db.add(row)
    try:
        digest = hash_attribute(body.value, row.salt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row.hashed_values[digest] = True
    row.hashed_values["latest:" + body.attribute] = digest
    db.flush()
    _audit(db, workspace_id, row.id, {"attribute": row.attribute, "kind": "secure_attribute"}, principal)
    db.commit()
    return {"flag_key": row.flag_key, "attribute": row.attribute, "digest": digest}


@router.post("/secure-attributes/match", operation_id="matchSecureAttribute")
def match_secure_attribute(workspace_id: str, body: SecureAttrIn,
                           principal: Principal = Depends(require(CONTACT_READ)),
                           db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(FgSecureAttribute).where(
        FgSecureAttribute.workspace_id == workspace_id,
        FgSecureAttribute.flag_key == body.flag_key,
        FgSecureAttribute.attribute == body.attribute,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="secure attribute not found")
    digest = hash_attribute(body.value, row.salt)
    return {"matched": bool(row.hashed_values.get(digest, False)), "digest": digest}


@router.post("/sticky", status_code=status.HTTP_201_CREATED, operation_id="assignStickyVariant")
def sticky(workspace_id: str, body: StickyIn,
           principal: Principal = Depends(require(NOTE_WRITE)),
           db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    try:
        included = sticky_bucket(body.user_key, body.flag_key, body.percent)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = db.execute(select(FgStickyAssignment).where(
        FgStickyAssignment.workspace_id == workspace_id,
        FgStickyAssignment.flag_key == body.flag_key,
        FgStickyAssignment.environment == body.environment,
        FgStickyAssignment.user_key == body.user_key,
    )).scalar_one_or_none()
    if row is None:
        row = FgStickyAssignment(id=new_id(), workspace_id=workspace_id,
                                 flag_key=body.flag_key, environment=body.environment,
                                 user_key=body.user_key, variant="")
        db.add(row)
    if not row.variant:
        row.variant = "in" if included else "out"
        db.flush()
        _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "sticky"}, principal)
        db.commit()
    return {"flag_key": row.flag_key, "user_key": row.user_key,
            "variant": row.variant, "sticky": True}


@router.post("/prerequisites", status_code=status.HTTP_201_CREATED, operation_id="createFlagPrerequisite")
def create_prerequisite(workspace_id: str, body: PrereqIn,
                        principal: Principal = Depends(require(NOTE_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = FgPrerequisite(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                         prerequisite_key=body.prerequisite_key, required_value=body.required_value,
                         target_condition=body.target_condition)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "prerequisite"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "prerequisite_key": row.prerequisite_key}


@router.post("/prerequisites/check", operation_id="checkFlagPrerequisites")
def check_prerequisites(workspace_id: str, body: CheckIn,
                        principal: Principal = Depends(require(CONTACT_READ)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag_key = body.attrs.get("flag_key")
    if not isinstance(flag_key, str):
        raise HTTPException(status_code=422, detail="attrs.flag_key is required")
    prereqs = _rows(db, FgPrerequisite, workspace_id, flag_key=flag_key)
    try:
        met, reason = prerequisites_met(
            [{"flag_key": r.prerequisite_key, "required_value": r.required_value,
              "target_condition": r.target_condition} for r in prereqs],
            body.flag_values, body.attrs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"flag_key": flag_key, "met": met, "reason": reason, "count": len(prereqs)}


@router.post("/redirects", status_code=status.HTTP_201_CREATED, operation_id="createFlagRedirect")
def create_redirect(workspace_id: str, body: RedirectIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if not body.target_url.startswith(("/", "https://", "http://")):
        raise HTTPException(status_code=422, detail="target_url must be a relative or http(s) URL")
    row = FgRedirect(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                     rule_id=body.rule_id, target_url=body.target_url, active=body.active)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "redirect"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "rule_id": row.rule_id,
            "target_url": row.target_url}


@router.post("/redirects/resolve", operation_id="resolveFlagRedirect")
def resolve_redirect(workspace_id: str, body: CheckIn,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag_key, rule_id = body.attrs.get("flag_key"), body.attrs.get("rule_id")
    if not isinstance(flag_key, str) or not isinstance(rule_id, str):
        raise HTTPException(status_code=422, detail="attrs.flag_key and attrs.rule_id are required")
    row = db.execute(select(FgRedirect).where(
        FgRedirect.workspace_id == workspace_id, FgRedirect.flag_key == flag_key,
        FgRedirect.rule_id == rule_id, FgRedirect.active.is_(True))).scalar_one_or_none()
    if row is None:
        return {"redirect": None}
    return {"redirect": {"flag_key": row.flag_key, "rule_id": row.rule_id,
                         "target_url": row.target_url}}


@router.post("/environments", status_code=status.HTTP_201_CREATED, operation_id="setEnvironmentInheritance")
def set_environment(workspace_id: str, body: EnvIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if not ENV_RE.match(body.environment):
        raise HTTPException(status_code=422, detail="invalid environment")
    if body.parent_environment and not ENV_RE.match(body.parent_environment):
        raise HTTPException(status_code=422, detail="invalid parent environment")
    row = db.execute(select(FgEnvironment).where(
        FgEnvironment.workspace_id == workspace_id,
        FgEnvironment.environment == body.environment)).scalar_one_or_none()
    if row is None:
        row = FgEnvironment(id=new_id(), workspace_id=workspace_id, environment=body.environment)
        db.add(row)
    row.parent_environment, row.overrides = body.parent_environment, body.overrides
    db.flush()
    _audit(db, workspace_id, row.id, {"environment": row.environment, "kind": "inheritance"}, principal)
    db.commit()
    return {"environment": row.environment, "parent_environment": row.parent_environment,
            "overrides": row.overrides}


@router.post("/environments/resolve", operation_id="resolveEffectiveEnvironment")
def resolve_environment(workspace_id: str, body: CheckIn,
                        principal: Principal = Depends(require(CONTACT_READ)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    environment = body.attrs.get("environment")
    if not isinstance(environment, str):
        raise HTTPException(status_code=422, detail="attrs.environment is required")
    chain = []
    seen = set()
    current = environment
    while current and current not in seen:
        seen.add(current)
        row = db.execute(select(FgEnvironment).where(
            FgEnvironment.workspace_id == workspace_id,
            FgEnvironment.environment == current)).scalar_one_or_none()
        if row is None:
            break
        chain.append({"environment": row.environment, "overrides": row.overrides})
        current = row.parent_environment
    effective: dict[str, Any] = {}
    for link in reversed(chain):
        effective.update(link["overrides"])
    return {"environment": environment, "chain": [c["environment"] for c in chain],
            "effective": effective}


@router.post("/templates", status_code=status.HTTP_201_CREATED, operation_id="createFlagTemplate")
def create_template(workspace_id: str, body: TemplateIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if not KEY_RE.match(body.key):
        raise HTTPException(status_code=422, detail="invalid template key")
    exists = db.execute(select(FgTemplate.id).where(
        FgTemplate.workspace_id == workspace_id, FgTemplate.key == body.key)).first()
    if exists:
        raise HTTPException(status_code=409, detail="template already exists")
    row = FgTemplate(id=new_id(), workspace_id=workspace_id, key=body.key, definition=body.definition)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"key": row.key, "kind": "template"}, principal)
    db.commit()
    return {"id": row.id, "key": row.key, "definition": row.definition}


@router.get("/templates", operation_id="listFlagTemplates")
def list_templates(workspace_id: str,
                   principal: Principal = Depends(require(CONTACT_READ)),
                   db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    return [{"key": r.key, "definition": r.definition} for r in _rows(db, FgTemplate, workspace_id)]


@router.post("/templates/instantiate", operation_id="instantiateFlagTemplate")
def instantiate_template(workspace_id: str, body: InstantiateIn,
                         principal: Principal = Depends(require(CONTACT_READ)),
                         db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    template_key = body.template_key
    row = db.execute(select(FgTemplate).where(
        FgTemplate.workspace_id == workspace_id, FgTemplate.key == template_key)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="template not found")
    try:
        result = template_flag({"key": row.key, "definition": row.definition}, body.flag_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/safe-rollouts", status_code=status.HTTP_201_CREATED, operation_id="createSafeRollout")
def create_safe_rollout(workspace_id: str, body: SafeRolloutIn,
                        principal: Principal = Depends(require(NOTE_WRITE)),
                        db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    if not 0 <= body.current_percent <= 100:
        raise HTTPException(status_code=422, detail="current_percent out of range")
    exists = db.execute(select(FgSafeRollout.id).where(
        FgSafeRollout.workspace_id == workspace_id,
        FgSafeRollout.flag_key == body.flag_key)).first()
    if exists:
        raise HTTPException(status_code=409, detail="safe rollout already exists")
    row = FgSafeRollout(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                        guardrail_metric=body.guardrail_metric, threshold=body.threshold,
                        current_percent=body.current_percent, status="monitoring")
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "safe_rollout"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "current_percent": row.current_percent,
            "status": row.status}


@router.post("/safe-rollouts/evaluate", operation_id="evaluateSafeRollout")
def evaluate_safe_rollout(workspace_id: str, body: RolloutEvalIn,
                          principal: Principal = Depends(require(CONTACT_READ)),
                          db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag_key = body.flag_key
    row = db.execute(select(FgSafeRollout).where(
        FgSafeRollout.workspace_id == workspace_id,
        FgSafeRollout.flag_key == flag_key)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="safe rollout not found")
    try:
        decision = safe_rollout_decision(row.current_percent, body.observed_rate,
                                         body.baseline_rate, row.threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"flag_key": flag_key, "guardrail_metric": row.guardrail_metric, **decision}


@router.get("/settings", operation_id="getFlagSettings")
def get_settings(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(FgSetting).where(FgSetting.workspace_id == workspace_id)).scalar_one_or_none()
    if row is None:
        return {"require_project_for_features": False, "require_project_for_sdk": False}
    return {"require_project_for_features": row.require_project_for_features,
            "require_project_for_sdk": row.require_project_for_sdk}


@router.put("/settings", operation_id="setFlagSettings")
def set_settings(workspace_id: str, body: SettingIn,
                 principal: Principal = Depends(require(NOTE_WRITE)),
                 db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(FgSetting).where(FgSetting.workspace_id == workspace_id)).scalar_one_or_none()
    if row is None:
        row = FgSetting(id=new_id(), workspace_id=workspace_id)
        db.add(row)
    row.require_project_for_features = body.require_project_for_features
    row.require_project_for_sdk = body.require_project_for_sdk
    db.flush()
    _audit(db, workspace_id, row.id, {"kind": "settings"}, principal)
    db.commit()
    return {"require_project_for_features": row.require_project_for_features,
            "require_project_for_sdk": row.require_project_for_sdk}


@router.post("/ramps", status_code=status.HTTP_201_CREATED, operation_id="createRampSchedule")
def create_ramp(workspace_id: str, body: RampIn,
                principal: Principal = Depends(require(NOTE_WRITE)),
                db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    try:
        begin, end = _parse_ts(body.starts_at), _parse_ts(body.ends_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if end <= begin or not 0 <= body.start_percent <= 100 or not 0 <= body.end_percent <= 100:
        raise HTTPException(status_code=422, detail="invalid ramp window or percentages")
    row = FgRamp(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                 environment=body.environment, start_percent=body.start_percent,
                 end_percent=body.end_percent, starts_at=body.starts_at, ends_at=body.ends_at)
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "ramp"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "start_percent": row.start_percent,
            "end_percent": row.end_percent}


@router.post("/ramps/percent-at", operation_id="rampPercentAt")
def ramp_percent_at(workspace_id: str, body: CheckIn,
                    principal: Principal = Depends(require(CONTACT_READ)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag_key, at = body.attrs.get("flag_key"), body.attrs.get("at")
    if not isinstance(flag_key, str) or not isinstance(at, str):
        raise HTTPException(status_code=422, detail="attrs.flag_key and attrs.at are required")
    rows = _rows(db, FgRamp, workspace_id, flag_key=flag_key)
    if not rows:
        raise HTTPException(status_code=404, detail="ramp not found")
    ramp = rows[-1]
    try:
        percent = ramp_percent(ramp.start_percent, ramp.end_percent, ramp.starts_at, ramp.ends_at, at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"flag_key": flag_key, "at": at, "percent": percent}


@router.post("/revisions", status_code=status.HTTP_201_CREATED, operation_id="createFlagGovernanceRevision")
def create_revision(workspace_id: str, body: RevisionIn,
                    principal: Principal = Depends(require(NOTE_WRITE)),
                    db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    try:
        _parse_ts(body.effective_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = FgRevision(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                     effective_at=body.effective_at, config=body.config, status="pending")
    db.add(row)
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "revision"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "effective_at": row.effective_at,
            "status": row.status}


@router.post("/revisions/apply", operation_id="applyFlagRevision")
def apply_revision(workspace_id: str, body: ApplyRevisionIn,
                   principal: Principal = Depends(require(NOTE_WRITE)),
                   db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = None
    if body.revision_id:
        row = db.execute(select(FgRevision).where(
            FgRevision.id == body.revision_id,
            FgRevision.workspace_id == workspace_id)).scalar_one_or_none()
    if row is None:
        # fall back to latest pending revision for the flag
        row = db.execute(select(FgRevision).where(
            FgRevision.workspace_id == workspace_id, FgRevision.flag_key == body.flag_key,
            FgRevision.status == "pending").order_by(FgRevision.effective_at.desc())).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="pending revision not found")
    row.status = "applied"
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "revision_applied"}, principal)
    db.commit()
    return {"id": row.id, "flag_key": row.flag_key, "status": row.status, "config": row.config}


@router.post("/revisions/resolve", operation_id="resolveFlagRevision")
def resolve_revision(workspace_id: str, body: CheckIn,
                     principal: Principal = Depends(require(CONTACT_READ)),
                     db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    flag_key, at = body.attrs.get("flag_key"), body.attrs.get("at")
    if not isinstance(flag_key, str) or not isinstance(at, str):
        raise HTTPException(status_code=422, detail="attrs.flag_key and attrs.at are required")
    rows = _rows(db, FgRevision, workspace_id, flag_key=flag_key)
    chosen = revision_at([{"effective_at": r.effective_at, "config": r.config,
                           "status": r.status} for r in rows], at)
    return {"flag_key": flag_key, "revision": chosen}


@router.post("/configs", status_code=status.HTTP_201_CREATED, operation_id="setFeatureConfig")
def set_config(workspace_id: str, body: ConfigIn,
               principal: Principal = Depends(require(NOTE_WRITE)),
               db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(FgConfig).where(
        FgConfig.workspace_id == workspace_id, FgConfig.flag_key == body.flag_key,
        FgConfig.environment == body.environment)).scalar_one_or_none()
    if row is None:
        row = FgConfig(id=new_id(), workspace_id=workspace_id, flag_key=body.flag_key,
                       environment=body.environment)
        db.add(row)
    row.value_type, row.value = body.value_type, body.value
    db.flush()
    _audit(db, workspace_id, row.id, {"flag_key": row.flag_key, "kind": "config"}, principal)
    db.commit()
    return {"flag_key": row.flag_key, "environment": row.environment,
            "value_type": row.value_type, "value": row.value}


@router.get("/configs", operation_id="listFeatureConfigs")
def list_configs(workspace_id: str,
                 principal: Principal = Depends(require(CONTACT_READ)),
                 db: Session = Depends(get_db)) -> list[dict]:
    verify_workspace(principal, workspace_id)
    return [{"flag_key": r.flag_key, "environment": r.environment,
             "value_type": r.value_type, "value": r.value} for r in _rows(db, FgConfig, workspace_id)]
