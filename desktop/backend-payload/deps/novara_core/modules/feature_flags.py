"""Feature flags and experimentation (GrowthBook-compatible, clean-room).

Deterministic, workspace-isolated flag evaluation with immutable feature keys,
kill switches, default values, built-in environments, per-environment state,
ordered targeting rules, percentage rollouts, local experiment links, exposure
tracking and local SDK delivery/evaluation. No external service is required and
no GrowthBook source is vendored.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, WORKSPACE_MANAGE

FLAG_CREATED = "flag.created"
FLAG_UPDATED = "flag.updated"
FLAG_DELETED = "flag.deleted"
FLAG_EVALUATED = "flag.evaluated"
FLAG_RULE_ADDED = "flag.rule_added"
FLAG_RULE_UPDATED = "flag.rule_updated"
FLAG_RULE_DELETED = "flag.rule_deleted"
FLAG_ENVIRONMENT_UPDATED = "flag.environment_updated"
EXPERIMENT_ASSIGNMENT = "experiment.assignment"
EXPOSURE_RECORDED = "experiment.exposure_recorded"
EXPERIMENT_LINKED = "flag.experiment_linked"
SDK_CONNECTION_CREATED = "sdk_connection.created"
SDK_CONNECTION_REVOKED = "sdk_connection.revoked"
register_event_types(
    FLAG_CREATED, FLAG_UPDATED, FLAG_DELETED, FLAG_EVALUATED,
    FLAG_RULE_ADDED, FLAG_RULE_UPDATED, FLAG_RULE_DELETED,
    FLAG_ENVIRONMENT_UPDATED, EXPERIMENT_ASSIGNMENT, EXPOSURE_RECORDED,
    EXPERIMENT_LINKED, SDK_CONNECTION_CREATED, SDK_CONNECTION_REVOKED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/flags",
    tags=["feature-flags"],
)

# Built-in environments available to every workspace (no paid tiers).
ENVIRONMENTS = ("production", "dev", "staging", "test")
RULE_OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "exists")
FLAG_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


# ---------------------------------------------------------------------------
# Tables (module-owned; no external store)
# ---------------------------------------------------------------------------


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_flag_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    variants: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    environment: Mapped[str] = mapped_column(String(40), default="production", nullable=False)
    default_value: Mapped[str] = mapped_column(String(200), default="off", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FlagRule(Base):
    """One ordered rule on a flag. The lowest position matching a user wins."""

    __tablename__ = "flag_rules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "flag_id", "position", name="uq_flag_rule_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    value: Mapped[str | None] = mapped_column(String(200))
    experiment_key: Mapped[str | None] = mapped_column(String(200))
    weights: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FlagEnvironmentState(Base):
    """Per-environment overrides; the flag row keeps its production defaults."""

    __tablename__ = "flag_environment_states"
    __table_args__ = (
        UniqueConstraint("workspace_id", "flag_id", "environment", name="uq_flag_env_state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FlagAssignment(Base):
    __tablename__ = "flag_assignments"
    __table_args__ = (UniqueConstraint("workspace_id", "flag_id", "user_key", name="uq_flag_assignment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(200), nullable=False)
    variant: Mapped[str] = mapped_column(String(80), nullable=False, default="on")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FlagExposure(Base):
    """Local exposure callback records: one first assignment per flag and user."""

    __tablename__ = "flag_exposures"
    __table_args__ = (
        UniqueConstraint("workspace_id", "flag_id", "user_key", name="uq_flag_exposure"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id"), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(200), nullable=False)
    variant: Mapped[str] = mapped_column(String(200), nullable=False)
    experiment_key: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SdkConnection(Base):
    """A workspace-scoped, revocable local SDK key. No outbound webhooks."""

    __tablename__ = "sdk_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_sdk_connection_workspace_name"),
        UniqueConstraint("sdk_key", name="uq_sdk_connection_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), default="production", nullable=False)
    sdk_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _clean_key(value: str) -> str:
    key = value.strip()
    if not FLAG_KEY_RE.fullmatch(key):
        raise ValueError("key must start alphanumeric and use only letters, digits, _, ., : or -")
    return key


def _clean_environment(value: str) -> str:
    environment = value.strip()
    if environment not in ENVIRONMENTS:
        raise ValueError("environment must be one of: " + ", ".join(ENVIRONMENTS))
    return environment


def _ensure_environment(value: str) -> str:
    try:
        return _clean_environment(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class FlagCreate(BaseModel):
    key: str
    description: str | None = None
    enabled: bool = False
    rollout_percent: int = Field(default=0, ge=0, le=100)
    attributes: dict = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    environment: str = "production"
    default_value: str = "off"

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        return _clean_key(value)

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str) -> str:
        return _clean_environment(value)

    @field_validator("default_value")
    @classmethod
    def default_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("default_value must not be blank")
        return value.strip()


class FlagUpdate(BaseModel):
    description: str | None = None
    enabled: bool | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)
    attributes: dict | None = None
    prerequisites: list[str] | None = None
    variants: list[str] | None = None
    environment: str | None = None
    default_value: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str | None) -> str | None:
        return _clean_environment(value) if value is not None else None

    @field_validator("default_value")
    @classmethod
    def default_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("default_value must not be blank")
        return value.strip() if value is not None else None


class FlagOut(BaseModel):
    id: str
    key: str
    description: str | None
    enabled: bool
    rollout_percent: int
    attributes: dict
    prerequisites: list
    variants: list
    environment: str
    default_value: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ConditionIn(BaseModel):
    attribute: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "exists"] = "eq"
    value: Any = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("attribute")
    @classmethod
    def attribute_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("attribute must not be blank")
        return value.strip()


def _validate_weights(weights: dict[str, int]) -> dict[str, int]:
    if not weights:
        return {}
    clean: dict[str, int] = {}
    for name, weight in weights.items():
        if not name.strip():
            raise ValueError("variant names must not be blank")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 0 <= weight <= 100:
            raise ValueError("variant weights must be integers between 0 and 100")
        clean[name.strip()] = weight
    if sum(clean.values()) != 100:
        raise ValueError("variant weights must sum to 100")
    return clean


class RuleCreate(BaseModel):
    position: int | None = Field(default=None, ge=0)
    conditions: list[ConditionIn] = Field(default_factory=list)
    rollout_percent: int = Field(default=100, ge=0, le=100)
    value: str | None = None
    experiment_key: str | None = None
    weights: dict[str, int] = Field(default_factory=dict)
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_weights(value)

    @model_validator(mode="after")
    def check_experiment(self):
        if self.experiment_key is not None:
            if not self.experiment_key.strip():
                raise ValueError("experiment_key must not be blank")
            if not self.weights:
                raise ValueError("experiment rules need variant weights summing to 100")
        return self


class RuleUpdate(BaseModel):
    conditions: list[ConditionIn] | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)
    value: str | None = None
    experiment_key: str | None = None
    weights: dict[str, int] | None = None
    enabled: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        return _validate_weights(value) if value is not None else None


class RuleOut(BaseModel):
    id: str
    position: int
    conditions: list
    rollout_percent: int
    value: str | None
    experiment_key: str | None
    weights: dict
    enabled: bool
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class RuleReorder(BaseModel):
    rule_ids: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class EnvironmentStateIn(BaseModel):
    enabled: bool
    rollout_percent: int = Field(default=0, ge=0, le=100)

    model_config = ConfigDict(extra="forbid")


class EnvironmentStateOut(BaseModel):
    environment: str
    enabled: bool
    rollout_percent: int
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class EvaluateRequest(BaseModel):
    user_key: str
    attributes: dict = Field(default_factory=dict)
    environment: str = "production"

    model_config = ConfigDict(extra="forbid")

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str) -> str:
        return _clean_environment(value)

    @field_validator("user_key")
    @classmethod
    def user_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_key must not be blank")
        return value.strip()

    @field_validator("attributes")
    @classmethod
    def attributes_valid(cls, value: dict) -> dict:
        if len(value) > 100:
            raise ValueError("at most 100 targeting attributes are accepted")
        for name in value:
            if not str(name).strip():
                raise ValueError("attribute names must not be blank")
        return value


class EvaluateOut(BaseModel):
    flag_key: str
    enabled: bool
    variant: str
    reason: str


class ExposureIn(BaseModel):
    user_key: str
    variant: str | None = None
    experiment_key: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("user_key")
    @classmethod
    def user_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_key must not be blank")
        return value.strip()


class ExposureOut(BaseModel):
    id: str
    flag_key: str
    user_key: str
    variant: str
    experiment_key: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SdkConnectionCreate(BaseModel):
    name: str
    environment: str = "production"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str) -> str:
        return _clean_environment(value)


class SdkConnectionOut(BaseModel):
    id: str
    name: str
    environment: str
    created_at: object
    revoked_at: object

    model_config = ConfigDict(from_attributes=True)


class SdkConnectionCreatedOut(SdkConnectionOut):
    sdk_key: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flag_or_404(db, workspace_id, key_or_id):
    f = db.execute(
        select(FeatureFlag).where(
            FeatureFlag.workspace_id == workspace_id,
            (FeatureFlag.key == key_or_id) | (FeatureFlag.id == key_or_id),
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="flag not found")
    return f


def _rule_or_404(db, workspace_id, flag: FeatureFlag, rule_id: str) -> FlagRule:
    rule = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id,
            FlagRule.flag_id == flag.id,
            FlagRule.id == rule_id,
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule


def _bucket_for(seed: str, user_key: str) -> int:
    h = hashlib.sha256(f"{seed}:{user_key}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def _bucket(user_key: str, flag_key: str) -> int:
    return _bucket_for(flag_key, user_key)


def _variant_from_weights(seed: str, user_key: str, weights: dict) -> str:
    bucket = _bucket_for(seed, user_key)
    cumulative = 0
    for name in sorted(weights):
        cumulative += int(weights[name])
        if bucket < cumulative:
            return name
    return sorted(weights)[-1]


def _conditions_match(conditions: list[dict], attrs: dict) -> bool:
    for condition in conditions or []:
        attribute = condition["attribute"]
        op = condition.get("op", "eq")
        expected = condition.get("value")
        actual = attrs.get(attribute)
        present = attribute in attrs
        if op == "exists":
            wanted = bool(expected) if isinstance(expected, bool) else True
            if present != wanted:
                return False
        elif op == "eq" and actual != expected:
            return False
        elif op == "ne" and actual == expected:
            return False
        elif op == "in":
            if not isinstance(expected, list) or actual not in expected:
                return False
        elif op == "contains":
            if not (isinstance(actual, (str, list, tuple)) and expected in actual):
                return False
        elif op in ("gt", "gte", "lt", "lte"):
            try:
                okay = {
                    "gt": actual > expected,
                    "gte": actual >= expected,
                    "lt": actual < expected,
                    "lte": actual <= expected,
                }[op]
            except TypeError:
                return False
            if not okay:
                return False
    return True


def _environment_state(db, workspace_id, flag: FeatureFlag, environment: str):
    return db.execute(
        select(FlagEnvironmentState).where(
            FlagEnvironmentState.workspace_id == workspace_id,
            FlagEnvironmentState.flag_id == flag.id,
            FlagEnvironmentState.environment == environment,
        )
    ).scalar_one_or_none()


def _record_exposure(db, workspace_id, flag: FeatureFlag, user_key, variant, experiment_key=None):
    exposure = db.execute(
        select(FlagExposure).where(
            FlagExposure.workspace_id == workspace_id,
            FlagExposure.flag_id == flag.id,
            FlagExposure.user_key == user_key,
        )
    ).scalar_one_or_none()
    if exposure is not None:
        return exposure
    exposure = FlagExposure(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        flag_id=flag.id,
        user_key=user_key,
        variant=variant,
        experiment_key=experiment_key,
        created_at=now(),
    )
    db.add(exposure)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPOSURE_RECORDED,
        entity_id=flag.id,
        payload={"flag_key": flag.key, "user_key": user_key, "variant": variant,
                 "experiment_key": experiment_key},
        actor_id=None,
    )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=EXPERIMENT_ASSIGNMENT,
        entity_id=flag.id,
        payload={"flag_key": flag.key, "user_key": user_key, "variant": variant},
        actor_id=None,
    )
    return exposure


def _evaluate(db, workspace_id, flag, user_key, attrs, environment="production", record_exposure=False):
    default = flag.default_value or "off"
    state = _environment_state(db, workspace_id, flag, environment)
    if not flag.enabled or (state is not None and not state.enabled):
        return False, default, "environment_disabled" if state is not None else "disabled"
    rollout = state.rollout_percent if state is not None else (flag.rollout_percent or 0)
    # prerequisites
    for prereq_key in flag.prerequisites or []:
        prereq = db.execute(
            select(FeatureFlag).where(
                FeatureFlag.workspace_id == workspace_id, FeatureFlag.key == prereq_key
            )
        ).scalar_one_or_none()
        if prereq is None or not prereq.enabled:
            return False, default, "prerequisite_failed"
    # attribute matching (legacy flag-level conditions)
    for attr, expected in (flag.attributes or {}).items():
        if attrs.get(attr) != expected:
            return False, default, "attribute_mismatch"
    # ordered rules: first matching rule wins over the default value
    rules = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id,
            FlagRule.flag_id == flag.id,
        ).order_by(FlagRule.position)
    ).scalars().all()
    for rule in rules:
        if not rule.enabled or not _conditions_match(rule.conditions, attrs):
            continue
        if rule.experiment_key:
            variant = _variant_from_weights(rule.experiment_key, user_key, rule.weights)
            if record_exposure:
                _record_exposure(db, workspace_id, flag, user_key, variant, rule.experiment_key)
            return True, variant, "experiment_rule"
        if rule.rollout_percent and _bucket_for(flag.key, user_key) < rule.rollout_percent:
            return True, rule.value or default, "rule_match"
    # Deterministic bucketing is the sticky assignment: the same user always
    # lands in the same bucket. A previously stored "off" is never allowed to
    # override a later rollout increase, so rollout changes take effect.
    bucket = _bucket(user_key, flag.key)
    existing = db.execute(
        select(FlagAssignment).where(
            FlagAssignment.workspace_id == workspace_id,
            FlagAssignment.flag_id == flag.id,
            FlagAssignment.user_key == user_key,
        )
    ).scalar_one_or_none()
    if existing is not None and existing.variant not in ("off", default) and bucket < rollout:
        return True, existing.variant, "sticky"
    on = bucket < rollout
    if flag.variants:
        variant = flag.variants[bucket % len(flag.variants)] if on else default
    else:
        variant = (default if default not in ("off", "") else "on") if on else default
    if existing is not None:
        existing.variant = variant
        existing.assigned_at = now()
    else:
        db.add(FlagAssignment(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            flag_id=flag.id,
            user_key=user_key,
            variant=variant,
            assigned_at=now(),
        ))
    db.flush()
    return on, variant, "rollout"


def _sdk_payload(db, workspace_id, environment: str) -> dict:
    flags = db.execute(
        select(FeatureFlag).where(FeatureFlag.workspace_id == workspace_id)
        .order_by(FeatureFlag.created_at)
    ).scalars().all()
    features: dict[str, dict] = {}
    environments: dict[str, dict] = {}
    for flag in flags:
        features[flag.key] = {
            "key": flag.key,
            "enabled": flag.enabled,
            "rollout_percent": flag.rollout_percent,
            "attributes": flag.attributes or {},
            "prerequisites": flag.prerequisites or [],
            "variants": flag.variants or [],
            "default_value": flag.default_value,
            "environment": flag.environment,
        }
        rules = db.execute(
            select(FlagRule).where(
                FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
            ).order_by(FlagRule.position)
        ).scalars().all()
        features[flag.key]["rules"] = [
            {
                "position": rule.position,
                "conditions": rule.conditions or [],
                "rollout_percent": rule.rollout_percent,
                "value": rule.value,
                "experiment_key": rule.experiment_key,
                "weights": rule.weights or {},
                "enabled": rule.enabled,
            }
            for rule in rules
        ]
        states = db.execute(
            select(FlagEnvironmentState).where(
                FlagEnvironmentState.workspace_id == workspace_id,
                FlagEnvironmentState.flag_id == flag.id,
            )
        ).scalars().all()
        if states:
            environments[flag.key] = {
                state.environment: {
                    "enabled": state.enabled,
                    "rollout_percent": state.rollout_percent,
                }
                for state in states
            }
    return {
        "workspace_id": workspace_id,
        "environment": environment,
        "environments": ENVIRONMENTS,
        "features": features,
        "environment_state": environments,
    }


def evaluate_local(payload: dict, user_key: str, attributes: dict | None = None,
                   environment: str = "production") -> dict:
    """Pure, HTTP-free evaluation of an SDK payload (GB-056).

    Uses the same deterministic hashing, rule ordering, targeting operators and
    variant weighting as the server, so an embedded SDK needs no round trip.
    """
    if environment not in ENVIRONMENTS:
        raise ValueError("unsupported environment")
    if not user_key.strip():
        raise ValueError("user_key must not be blank")
    attrs = attributes or {}
    features = payload.get("features", {})
    overrides = payload.get("environment_state", {})
    results: dict[str, dict] = {}
    for key, feature in features.items():
        default = feature.get("default_value") or "off"
        override = (overrides.get(key) or {}).get(environment)
        enabled = bool(feature.get("enabled"))
        rollout = int(feature.get("rollout_percent") or 0)
        if override is not None:
            enabled = bool(override.get("enabled"))
            rollout = int(override.get("rollout_percent") or 0)
        if not enabled:
            results[key] = {"enabled": False, "value": default, "reason": "disabled"}
            continue
        if any(not _conditions_match([{"attribute": a, "op": "eq", "value": v}], attrs)
               for a, v in (feature.get("attributes") or {}).items()):
            results[key] = {"enabled": False, "value": default, "reason": "attribute_mismatch"}
            continue
        matched = False
        for rule in sorted(feature.get("rules") or [], key=lambda r: r["position"]):
            if not rule.get("enabled", True) or not _conditions_match(rule.get("conditions") or [], attrs):
                continue
            if rule.get("experiment_key"):
                variant = _variant_from_weights(
                    rule["experiment_key"], user_key, rule.get("weights") or {}
                )
                results[key] = {"enabled": True, "value": variant, "reason": "experiment_rule"}
                matched = True
                break
            if (rule.get("rollout_percent") or 0) and _bucket_for(key, user_key) < rule["rollout_percent"]:
                results[key] = {
                    "enabled": True,
                    "value": rule.get("value") or default,
                    "reason": "rule_match",
                }
                matched = True
                break
        if matched:
            continue
        bucket = _bucket_for(key, user_key)
        on = bucket < rollout
        variants = feature.get("variants") or []
        if variants:
            value = variants[bucket % len(variants)] if on else default
        else:
            value = (default if default not in ("off", "") else "on") if on else default
        results[key] = {"enabled": on, "value": value, "reason": "rollout"}
    return {"user_key": user_key, "environment": environment, "features": results}


def _require_sdk_key(x_sdk_key: str | None, workspace_id: str, db) -> SdkConnection:
    if not x_sdk_key:
        raise HTTPException(status_code=401, detail="SDK key required")
    connection = db.execute(
        select(SdkConnection).where(
            SdkConnection.workspace_id == workspace_id,
            SdkConnection.sdk_key == x_sdk_key,
            SdkConnection.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=401, detail="invalid SDK key")
    return connection


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[FlagOut])
def list_flags(
    workspace_id: str,
    environment: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[FeatureFlag]:
    verify_workspace(principal, workspace_id)
    if environment is not None:
        _ensure_environment(environment)
    q = select(FeatureFlag).where(FeatureFlag.workspace_id == workspace_id)
    if environment:
        q = q.where(FeatureFlag.environment == environment)
    return db.execute(q.order_by(FeatureFlag.created_at.desc())).scalars().all()


@router.post("", response_model=FlagOut, status_code=status.HTTP_201_CREATED)
def create_flag(
    workspace_id: str,
    body: FlagCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> FeatureFlag:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(FeatureFlag).where(FeatureFlag.workspace_id == workspace_id, FeatureFlag.key == body.key)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="flag key already exists")
    flag = FeatureFlag(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        key=body.key,
        description=body.description,
        enabled=body.enabled,
        rollout_percent=body.rollout_percent,
        attributes=body.attributes,
        prerequisites=body.prerequisites,
        variants=body.variants,
        environment=body.environment,
        default_value=body.default_value,
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(flag)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_CREATED,
        entity_id=flag.id, payload={"key": flag.key}, actor_id=principal.user.id,
    )
    db.commit()
    return flag


@router.get("/environments")
def list_environments(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-005: built-in environments exist in every workspace without a plan."""
    verify_workspace(principal, workspace_id)
    return {"environments": list(ENVIRONMENTS)}


@router.get("/sdk/connections", response_model=list[SdkConnectionOut])
def list_sdk_connections(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SdkConnection]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SdkConnection).where(SdkConnection.workspace_id == workspace_id)
        .order_by(SdkConnection.created_at)
    ).scalars().all()


@router.post("/sdk/connections", response_model=SdkConnectionCreatedOut,
             status_code=status.HTTP_201_CREATED)
def create_sdk_connection(
    workspace_id: str,
    body: SdkConnectionCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> SdkConnectionCreatedOut:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SdkConnection).where(
            SdkConnection.workspace_id == workspace_id, SdkConnection.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="SDK connection name already exists")
    connection = SdkConnection(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=body.name,
        environment=body.environment,
        sdk_key="nv_sdk_" + secrets.token_urlsafe(24),
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(connection)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=SDK_CONNECTION_CREATED,
        entity_id=connection.id, payload={"name": connection.name, "environment": connection.environment},
        actor_id=principal.user.id,
    )
    db.commit()
    return SdkConnectionCreatedOut.model_validate(connection)


@router.post("/sdk/connections/{connection_id}/revoke", response_model=SdkConnectionOut)
def revoke_sdk_connection(
    workspace_id: str,
    connection_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> SdkConnection:
    verify_workspace(principal, workspace_id)
    connection = db.execute(
        select(SdkConnection).where(
            SdkConnection.workspace_id == workspace_id, SdkConnection.id == connection_id
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="SDK connection not found")
    if connection.revoked_at is None:
        connection.revoked_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=SDK_CONNECTION_REVOKED,
            entity_id=connection.id, payload={"name": connection.name}, actor_id=principal.user.id,
        )
        db.commit()
    return connection


@router.get("/sdk/payload")
def sdk_payload(
    workspace_id: str,
    environment: str = "production",
    x_sdk_key: str | None = Header(default=None, alias="X-SDK-Key"),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-055/GB-057: local SDK configuration, scoped by a revocable key."""
    verify_workspace(principal, workspace_id)
    _ensure_environment(environment)
    connection = _require_sdk_key(x_sdk_key, workspace_id, db)
    if connection.environment != environment:
        raise HTTPException(status_code=403, detail="SDK key is scoped to another environment")
    return _sdk_payload(db, workspace_id, environment)


@router.get("/{flag_key}", response_model=FlagOut)
def get_flag(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> FeatureFlag:
    verify_workspace(principal, workspace_id)
    return _flag_or_404(db, workspace_id, flag_key)


@router.patch("/{flag_key}", response_model=FlagOut)
def update_flag(
    workspace_id: str,
    flag_key: str,
    body: FlagUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> FeatureFlag:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(flag, k, v)
    flag.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_UPDATED,
        entity_id=flag.id, payload={"fields": sorted(updates.keys())}, actor_id=principal.user.id,
    )
    db.commit()
    return flag


@router.delete("/{flag_key}")
def delete_flag(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_DELETED,
        entity_id=flag.id, payload={"key": flag.key}, actor_id=principal.user.id,
    )
    deleted_key = flag.key
    db.delete(flag)
    db.commit()
    return {"deleted": True, "key": deleted_key}


@router.get("/{flag_key}/rules", response_model=list[RuleOut])
def list_rules(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[FlagRule]:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    return db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
        ).order_by(FlagRule.position)
    ).scalars().all()


@router.post("/{flag_key}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    workspace_id: str,
    flag_key: str,
    body: RuleCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> FlagRule:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    if body.experiment_key:
        # Local-only link: the referenced experiment must exist in this workspace.
        from .analytics import Experiment

        experiment = db.execute(
            select(Experiment).where(
                Experiment.workspace_id == workspace_id, Experiment.id == body.experiment_key
            )
        ).scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=422, detail="experiment not found in this workspace")
    last = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
        ).order_by(FlagRule.position.desc())
    ).scalars().first()
    position = body.position if body.position is not None else (last.position + 1 if last else 0)
    clash = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id,
            FlagRule.flag_id == flag.id,
            FlagRule.position == position,
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(status_code=409, detail="rule position already used")
    rule = FlagRule(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        flag_id=flag.id,
        position=position,
        conditions=[c.model_dump() for c in body.conditions],
        rollout_percent=body.rollout_percent,
        value=body.value,
        experiment_key=body.experiment_key,
        weights=body.weights,
        enabled=body.enabled,
        created_at=now(),
        updated_at=now(),
    )
    db.add(rule)
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_RULE_ADDED,
        entity_id=flag.id, payload={"rule_id": rule.id, "position": rule.position},
        actor_id=principal.user.id,
    )
    if rule.experiment_key:
        publish_event(
            db, workspace_id=workspace_id, event_type=EXPERIMENT_LINKED,
            entity_id=flag.id, payload={"experiment_key": rule.experiment_key},
            actor_id=principal.user.id,
        )
    db.commit()
    return rule


@router.post("/{flag_key}/rules/reorder", response_model=list[RuleOut])
def reorder_rules(
    workspace_id: str,
    flag_key: str,
    body: RuleReorder,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[FlagRule]:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    rules = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
        )
    ).scalars().all()
    by_id = {rule.id: rule for rule in rules}
    if len(set(body.rule_ids)) != len(body.rule_ids) or any(r not in by_id for r in body.rule_ids):
        raise HTTPException(status_code=422, detail="rule_ids must list each rule exactly once")
    if len(body.rule_ids) != len(rules):
        raise HTTPException(status_code=422, detail="all rules must be included in a reorder")
    # Temporary negative positions avoid clashing with the unique constraint.
    for index, rule_id in enumerate(body.rule_ids):
        by_id[rule_id].position = -index - 1
    db.flush()
    for index, rule_id in enumerate(body.rule_ids):
        by_id[rule_id].position = index
        by_id[rule_id].updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_RULE_UPDATED,
        entity_id=flag.id, payload={"order": body.rule_ids}, actor_id=principal.user.id,
    )
    db.commit()
    return sorted(rules, key=lambda r: r.position)


@router.patch("/{flag_key}/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    workspace_id: str,
    flag_key: str,
    rule_id: str,
    body: RuleUpdate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> FlagRule:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    rule = _rule_or_404(db, workspace_id, flag, rule_id)
    updates = body.model_dump(exclude_unset=True)
    if "conditions" in updates:
        updates["conditions"] = [c.model_dump() for c in body.conditions]
    if updates.get("experiment_key"):
        from .analytics import Experiment

        experiment = db.execute(
            select(Experiment).where(
                Experiment.workspace_id == workspace_id, Experiment.id == updates["experiment_key"]
            )
        ).scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=422, detail="experiment not found in this workspace")
    for key, value in updates.items():
        setattr(rule, key, value)
    rule.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_RULE_UPDATED,
        entity_id=flag.id, payload={"rule_id": rule.id, "fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return rule


@router.delete("/{flag_key}/rules/{rule_id}")
def delete_rule(
    workspace_id: str,
    flag_key: str,
    rule_id: str,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    rule = _rule_or_404(db, workspace_id, flag, rule_id)
    db.delete(rule)
    db.flush()
    for index, remaining in enumerate(
        db.execute(
            select(FlagRule).where(
                FlagRule.workspace_id == workspace_id, FlagRule.flag_id == flag.id
            ).order_by(FlagRule.position)
        ).scalars().all()
    ):
        remaining.position = index
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_RULE_DELETED,
        entity_id=flag.id, payload={"rule_id": rule.id}, actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "rule_id": rule_id}


@router.get("/{flag_key}/environments", response_model=list[EnvironmentStateOut])
def list_environment_states(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[FlagEnvironmentState]:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    return db.execute(
        select(FlagEnvironmentState).where(
            FlagEnvironmentState.workspace_id == workspace_id,
            FlagEnvironmentState.flag_id == flag.id,
        ).order_by(FlagEnvironmentState.environment)
    ).scalars().all()


@router.put("/{flag_key}/environments/{environment}", response_model=EnvironmentStateOut)
def set_environment_state(
    workspace_id: str,
    flag_key: str,
    environment: str,
    body: EnvironmentStateIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> FlagEnvironmentState:
    verify_workspace(principal, workspace_id)
    _ensure_environment(environment)
    flag = _flag_or_404(db, workspace_id, flag_key)
    state = _environment_state(db, workspace_id, flag, environment)
    if state is None:
        state = FlagEnvironmentState(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            flag_id=flag.id,
            environment=environment,
            created_at=now(),
        )
        db.add(state)
    state.enabled = body.enabled
    state.rollout_percent = body.rollout_percent
    state.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_ENVIRONMENT_UPDATED,
        entity_id=flag.id,
        payload={"environment": environment, "enabled": state.enabled,
                 "rollout_percent": state.rollout_percent},
        actor_id=principal.user.id,
    )
    db.commit()
    return state


@router.post("/{flag_key}/exposures", response_model=ExposureOut,
             status_code=status.HTTP_201_CREATED)
def record_exposure(
    workspace_id: str,
    flag_key: str,
    body: ExposureIn,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> ExposureOut:
    """GB-036: SDK exposure callback records the served variant locally."""
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    variant = body.variant or (flag.default_value if flag.enabled else "off")
    exposure = _record_exposure(db, workspace_id, flag, body.user_key, variant, body.experiment_key)
    db.commit()
    return ExposureOut(
        id=exposure.id, flag_key=flag.key, user_key=exposure.user_key,
        variant=exposure.variant, experiment_key=exposure.experiment_key,
        created_at=exposure.created_at,
    )


@router.get("/{flag_key}/exposures", response_model=list[ExposureOut])
def list_exposures(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ExposureOut]:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    rows = db.execute(
        select(FlagExposure).where(
            FlagExposure.workspace_id == workspace_id, FlagExposure.flag_id == flag.id
        ).order_by(FlagExposure.created_at)
    ).scalars().all()
    return [
        ExposureOut(
            id=row.id, flag_key=flag.key, user_key=row.user_key,
            variant=row.variant, experiment_key=row.experiment_key, created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/{flag_key}/experiment/results")
def experiment_results(
    workspace_id: str,
    flag_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-019: per-variant comparison served from local experiment rows."""
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    link = db.execute(
        select(FlagRule).where(
            FlagRule.workspace_id == workspace_id,
            FlagRule.flag_id == flag.id,
            FlagRule.experiment_key.is_not(None),
        ).order_by(FlagRule.position)
    ).scalars().first()
    if link is None:
        raise HTTPException(status_code=404, detail="no linked experiment")
    from .analytics import Experiment, ExperimentResult

    experiment = db.execute(
        select(Experiment).where(
            Experiment.workspace_id == workspace_id, Experiment.id == link.experiment_key
        )
    ).scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    rows = db.execute(
        select(ExperimentResult).where(
            ExperimentResult.workspace_id == workspace_id,
            ExperimentResult.experiment_id == experiment.id,
        ).order_by(ExperimentResult.variant)
    ).scalars().all()
    comparison = []
    for row in rows:
        rate = (row.conversions / row.impressions) if row.impressions else 0.0
        baseline = experiment.baseline
        comparison.append({
            "variant": row.variant,
            "impressions": row.impressions,
            "conversions": row.conversions,
            "conversion_rate": rate,
            "delta_vs_baseline": (rate - baseline) if baseline is not None else None,
        })
    return {
        "experiment_id": experiment.id,
        "experiment_name": experiment.name,
        "metric_name": experiment.metric_name,
        "baseline": experiment.baseline,
        "rows": comparison,
    }


@router.post("/{flag_key}/evaluate", response_model=EvaluateOut)
def evaluate_flag(
    workspace_id: str,
    flag_key: str,
    body: EvaluateRequest,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> EvaluateOut:
    verify_workspace(principal, workspace_id)
    flag = _flag_or_404(db, workspace_id, flag_key)
    enabled, variant, reason = _evaluate(
        db, workspace_id, flag, body.user_key, body.attributes,
        environment=body.environment, record_exposure=True,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=FLAG_EVALUATED,
        entity_id=flag.id, payload={"user_key": body.user_key, "enabled": enabled, "variant": variant},
        actor_id=principal.user.id,
    )
    db.commit()
    return EvaluateOut(flag_key=flag.key, enabled=enabled, variant=variant, reason=reason)


@router.post("/evaluate-all")
def evaluate_all(
    workspace_id: str,
    body: EvaluateRequest,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    flags = db.execute(
        select(FeatureFlag).where(FeatureFlag.workspace_id == workspace_id)
    ).scalars().all()
    results = {}
    for flag in flags:
        enabled, variant, reason = _evaluate(
            db, workspace_id, flag, body.user_key, body.attributes,
            environment=body.environment, record_exposure=True,
        )
        results[flag.key] = {"enabled": enabled, "variant": variant, "reason": reason}
    db.commit()
    return {"user_key": body.user_key, "environment": body.environment, "flags": results}
