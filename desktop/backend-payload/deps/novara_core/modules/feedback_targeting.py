"""Clean-room in-app targeting, triggers and survey controls (Formbricks P2).

Layered on the existing Feedback Studio and ``feedback_extensions`` module.
Every decision is computed from workspace-scoped local state and recorded as an
audited event. No survey is injected into a host page, no email is sent and no
external SDK or Formbricks service is contacted.

Feature IDs closed here (evidence: apps/api/tests/test_feedback_targeting_p2c.py):
FB-055..FB-064 (in-app targeting, identity, attributes, actions, triggers,
show conditions, display logic, recontact, cooldown, percentage) and
FB-081..FB-084 (submission limit, scheduling, segments, quotas).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from pydantic import BaseModel, ConfigDict, field_validator

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .feedback import Survey, _survey_or_404
from .feedback_extensions import SurveyAnswer, SurveyDisplay

TARGETING_CHANGED = "survey.targeting_changed"
DECISION_RECORDED = "survey.decision_recorded"
CONTROL_CHANGED = "survey.control_changed"
register_event_types(TARGETING_CHANGED, DECISION_RECORDED, CONTROL_CHANGED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/feedback/targeting",
    tags=["feedback-targeting"],
)

RECONTACT_MODES = ("always", "once", "limited")


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

class SurveyUserProfile(Base):
    """FB-056/057: identified user and their attributes, per workspace."""

    __tablename__ = "survey_user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyActionClass(Base):
    """FB-058: a named action that can trigger a survey."""

    __tablename__ = "survey_action_classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class SurveyTrigger(Base):
    """FB-059..064: targeting rules that decide when to show a survey."""

    __tablename__ = "survey_triggers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    action_class_id: Mapped[str] = mapped_column(ForeignKey("survey_action_classes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    show_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    display_logic: Mapped[dict] = mapped_column(JSON, default=dict)
    recontact: Mapped[dict] = mapped_column(JSON, default=dict)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class TargetingDecision(Base):
    """An audited record of each evaluate() outcome for a user and trigger."""

    __tablename__ = "targeting_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    trigger_id: Mapped[str] = mapped_column(ForeignKey("survey_triggers.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    shown: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyControl(Base):
    """FB-081..084: submission limit, schedule, segment and quotas."""

    __tablename__ = "survey_controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True, unique=True)
    max_responses: Mapped[int | None] = mapped_column(Integer)
    schedule_start: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    schedule_end: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    segment: Mapped[dict] = mapped_column(JSON, default=dict)
    quotas: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class UserIdentify(BaseModel):
    user_id: str
    attributes: dict = {}

    model_config = ConfigDict(extra="forbid")

    @field_validator("user_id")
    @classmethod
    def _uid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("user_id is required")
        return v


class ActionClassCreate(BaseModel):
    name: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v


class TriggerCreate(BaseModel):
    survey_id: str
    action_class_id: str
    name: str
    show_conditions: dict = {}
    display_logic: dict = {}
    recontact: dict = {}
    cooldown_seconds: int = 0
    percentage: int = 100
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("percentage")
    @classmethod
    def _pct(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("percentage must be between 0 and 100")
        return v

    @field_validator("cooldown_seconds")
    @classmethod
    def _cooldown(cls, v):
        if v < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        return v

    @field_validator("recontact")
    @classmethod
    def _recontact(cls, v):
        mode = v.get("mode", "always")
        if mode not in RECONTACT_MODES:
            raise ValueError("invalid recontact mode")
        return v


class TriggerPatch(BaseModel):
    enabled: bool | None = None
    percentage: int | None = None
    cooldown_seconds: int | None = None
    recontact: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("percentage")
    @classmethod
    def _pct(cls, v):
        if v is not None and not 0 <= v <= 100:
            raise ValueError("percentage must be between 0 and 100")
        return v


class EvaluateRequest(BaseModel):
    user_id: str
    action: str
    attributes: dict = {}

    model_config = ConfigDict(extra="forbid")


class ControlUpsert(BaseModel):
    max_responses: int | None = None
    schedule_start: str | None = None
    schedule_end: str | None = None
    segment: dict = {}
    quotas: dict = {}

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_responses")
    @classmethod
    def _max(cls, v):
        if v is not None and v < 0:
            raise ValueError("max_responses cannot be negative")
        return v


class ControlEvaluate(BaseModel):
    attributes: dict = {}

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _action_class_or_404(db: Session, workspace_id: str, action_id: str) -> SurveyActionClass:
    row = db.execute(
        select(SurveyActionClass).where(
            SurveyActionClass.workspace_id == workspace_id,
            SurveyActionClass.id == action_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="action class not found")
    return row


def _trigger_or_404(db: Session, workspace_id: str, trigger_id: str) -> SurveyTrigger:
    row = db.execute(
        select(SurveyTrigger).where(
            SurveyTrigger.workspace_id == workspace_id,
            SurveyTrigger.id == trigger_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="trigger not found")
    return row


def _match_attribute(actual: object, rule: object) -> bool:
    """Evaluate one attribute rule. Plain values mean equality; a dict with an
    ``op`` key supports eq/neq/contains/gt/gte/lt/lte/in."""
    if isinstance(rule, dict) and "op" in rule:
        op = rule["op"]
        expected = rule.get("value")
        try:
            if op == "eq":
                return actual == expected
            if op == "neq":
                return actual != expected
            if op == "contains":
                return expected in (actual or [])
            if op == "gt":
                return actual is not None and actual > expected
            if op == "gte":
                return actual is not None and actual >= expected
            if op == "lt":
                return actual is not None and actual < expected
            if op == "lte":
                return actual is not None and actual <= expected
            if op == "in":
                return actual in (expected or [])
        except TypeError:
            return False
        return False
    return actual == rule


def _conditions_hold(attributes: dict, conditions: dict) -> bool:
    return all(
        key in attributes and _match_attribute(attributes[key], rule)
        for key, rule in conditions.items()
    )


def _bucket(trigger_id: str, user_id: str) -> int:
    """Stable 0..99 bucket so a user is always in or out for a given trigger."""
    digest = hashlib.sha256(f"{trigger_id}:{user_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid datetime: {value}") from exc


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops timezone info on round trip; normalise to UTC for compare."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# User identification and action classes  (FB-056/057/058)
# --------------------------------------------------------------------------

@router.post("/users", status_code=status.HTTP_201_CREATED)
def identify_user(
    workspace_id: str,
    body: UserIdentify,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(SurveyUserProfile).where(
            SurveyUserProfile.workspace_id == workspace_id,
            SurveyUserProfile.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SurveyUserProfile(id=new_id(), workspace_id=workspace_id,
                                user_id=body.user_id, attributes=dict(body.attributes))
        db.add(row)
    else:
        attrs = dict(row.attributes or {})
        attrs.update(body.attributes)
        row.attributes = attrs
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TARGETING_CHANGED,
                  entity_id=row.id, payload={"user_id": body.user_id, "action": "identify"},
                  actor_id=principal.user.id)
    db.commit()
    return {"user_id": row.user_id, "attributes": row.attributes}


@router.get("/users/{user_id}")
def get_user(
    workspace_id: str,
    user_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(SurveyUserProfile).where(
            SurveyUserProfile.workspace_id == workspace_id,
            SurveyUserProfile.user_id == user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"user_id": row.user_id, "attributes": row.attributes}


@router.post("/action-classes", status_code=status.HTTP_201_CREATED)
def create_action_class(
    workspace_id: str,
    body: ActionClassCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if db.execute(select(SurveyActionClass.id).where(
        SurveyActionClass.workspace_id == workspace_id,
        SurveyActionClass.name == body.name,
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="action class already exists")
    row = SurveyActionClass(id=new_id(), workspace_id=workspace_id,
                            name=body.name, description=body.description)
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TARGETING_CHANGED,
                  entity_id=row.id, payload={"name": body.name, "action": "action_class_created"},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": row.id, "name": row.name, "description": row.description}


@router.get("/action-classes")
def list_action_classes(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SurveyActionClass).where(SurveyActionClass.workspace_id == workspace_id)
        .order_by(SurveyActionClass.name)
    ).scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


# --------------------------------------------------------------------------
# Triggers and evaluation  (FB-055/059/060/061/062/063/064)
# --------------------------------------------------------------------------

@router.post("/triggers", status_code=status.HTTP_201_CREATED)
def create_trigger(
    workspace_id: str,
    body: TriggerCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, body.survey_id)
    _action_class_or_404(db, workspace_id, body.action_class_id)
    trigger = SurveyTrigger(
        id=new_id(), workspace_id=workspace_id, survey_id=body.survey_id,
        action_class_id=body.action_class_id, name=body.name,
        show_conditions=body.show_conditions, display_logic=body.display_logic,
        recontact=body.recontact, cooldown_seconds=body.cooldown_seconds,
        percentage=body.percentage, enabled=body.enabled, created_at=now(),
    )
    db.add(trigger)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TARGETING_CHANGED,
                  entity_id=trigger.id, payload={"survey_id": body.survey_id,
                                                 "name": body.name, "action": "trigger_created"},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": trigger.id, "survey_id": trigger.survey_id, "name": trigger.name,
            "enabled": trigger.enabled, "percentage": trigger.percentage}


@router.get("/triggers")
def list_triggers(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SurveyTrigger).where(SurveyTrigger.workspace_id == workspace_id)
        .order_by(SurveyTrigger.created_at)
    ).scalars().all()
    return [{"id": r.id, "survey_id": r.survey_id, "name": r.name,
             "action_class_id": r.action_class_id, "enabled": r.enabled,
             "percentage": r.percentage, "cooldown_seconds": r.cooldown_seconds,
             "show_conditions": r.show_conditions, "display_logic": r.display_logic,
             "recontact": r.recontact} for r in rows]


@router.patch("/triggers/{trigger_id}")
def patch_trigger(
    workspace_id: str,
    trigger_id: str,
    body: TriggerPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    trigger = _trigger_or_404(db, workspace_id, trigger_id)
    if body.enabled is not None:
        trigger.enabled = body.enabled
    if body.percentage is not None:
        trigger.percentage = body.percentage
    if body.cooldown_seconds is not None:
        if body.cooldown_seconds < 0:
            raise HTTPException(status_code=422, detail="cooldown_seconds cannot be negative")
        trigger.cooldown_seconds = body.cooldown_seconds
    if body.recontact is not None:
        if body.recontact.get("mode", "always") not in RECONTACT_MODES:
            raise HTTPException(status_code=422, detail="invalid recontact mode")
        trigger.recontact = body.recontact
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TARGETING_CHANGED,
                  entity_id=trigger.id, payload={"action": "trigger_patched"},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": trigger.id, "enabled": trigger.enabled, "percentage": trigger.percentage,
            "cooldown_seconds": trigger.cooldown_seconds, "recontact": trigger.recontact}


@router.post("/triggers/{trigger_id}/evaluate")
def evaluate_trigger(
    workspace_id: str,
    trigger_id: str,
    body: EvaluateRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    """Compute a show/no-show decision from local state and record it.

    FB-055 in-app targeting, FB-057 attribute matching, FB-060 show conditions,
    FB-061 display logic, FB-062 recontact options, FB-063 cooldown and
    FB-064 percentage rollout are all evaluated here.
    """
    verify_workspace(principal, workspace_id)
    trigger = _trigger_or_404(db, workspace_id, trigger_id)
    action = db.execute(
        select(SurveyActionClass).where(
            SurveyActionClass.id == trigger.action_class_id,
            SurveyActionClass.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if action is None or action.name != body.action:
        return _record(db, workspace_id, trigger, body.user_id, False, "action_mismatch",
                       principal.user.id)

    if not trigger.enabled:
        return _record(db, workspace_id, trigger, body.user_id, False, "trigger_disabled",
                       principal.user.id)

    profile = db.execute(
        select(SurveyUserProfile).where(
            SurveyUserProfile.workspace_id == workspace_id,
            SurveyUserProfile.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    attributes = dict(profile.attributes or {}) if profile else {}
    attributes.update(body.attributes)  # per-call context overrides the stored profile

    if not _conditions_hold(attributes, trigger.show_conditions or {}):
        return _record(db, workspace_id, trigger, body.user_id, False, "show_condition_mismatch",
                       principal.user.id, attributes=attributes)

    logic = trigger.display_logic or {}
    required = logic.get("require_attributes", [])
    if any(key not in attributes for key in required):
        return _record(db, workspace_id, trigger, body.user_id, False, "display_logic_unmet",
                       principal.user.id, attributes=attributes)

    if _bucket(trigger.id, body.user_id) >= trigger.percentage:
        return _record(db, workspace_id, trigger, body.user_id, False, "percentage_excluded",
                       principal.user.id, attributes=attributes)

    prior = db.execute(
        select(TargetingDecision).where(
            TargetingDecision.workspace_id == workspace_id,
            TargetingDecision.trigger_id == trigger.id,
            TargetingDecision.user_id == body.user_id,
            TargetingDecision.shown.is_(True),
        ).order_by(TargetingDecision.created_at)
    ).scalars().all()

    recontact = trigger.recontact or {}
    mode = recontact.get("mode", "always")
    if mode == "once" and prior:
        return _record(db, workspace_id, trigger, body.user_id, False, "recontact_once",
                       principal.user.id, attributes=attributes)
    if mode == "limited" and len(prior) >= int(recontact.get("max_times", 1)):
        return _record(db, workspace_id, trigger, body.user_id, False, "recontact_limit",
                       principal.user.id, attributes=attributes)

    if trigger.cooldown_seconds > 0 and prior:
        last = _aware(prior[-1].created_at)
        if last is not None:
            elapsed = (now() - last).total_seconds()
            if elapsed < trigger.cooldown_seconds:
                return _record(db, workspace_id, trigger, body.user_id, False, "cooldown_active",
                               "system", attributes=attributes)

    return _record(db, workspace_id, trigger, body.user_id, True, "shown",
                   principal.user.id, attributes=attributes, display=True)


def _record(db, workspace_id, trigger, user_id, shown, reason, actor_id,
            attributes=None, display=False):
    decision = TargetingDecision(id=new_id(), workspace_id=workspace_id,
                                 trigger_id=trigger.id, user_id=user_id,
                                 shown=shown, reason=reason, created_at=now())
    db.add(decision)
    if display and shown:
        # Integrate with the shared display-tracking model used by share links.
        db.add(SurveyDisplay(id=new_id(), workspace_id=workspace_id,
                             survey_id=trigger.survey_id, link_id=None,
                             subject=user_id, created_at=now()))
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DECISION_RECORDED,
                  entity_id=decision.id, payload={"trigger_id": trigger.id,
                                                  "user_id": user_id, "shown": shown,
                                                  "reason": reason},
                  actor_id=actor_id)
    db.commit()
    result = {"trigger_id": trigger.id, "user_id": user_id, "shown": shown,
              "reason": reason, "decision_id": decision.id}
    if attributes is not None:
        result["attributes"] = attributes
    return result


@router.get("/triggers/{trigger_id}/decisions")
def list_decisions(
    workspace_id: str,
    trigger_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _trigger_or_404(db, workspace_id, trigger_id)
    rows = db.execute(
        select(TargetingDecision).where(
            TargetingDecision.workspace_id == workspace_id,
            TargetingDecision.trigger_id == trigger_id,
        ).order_by(TargetingDecision.created_at)
    ).scalars().all()
    return [{"id": r.id, "user_id": r.user_id, "shown": r.shown,
             "reason": r.reason, "created_at": r.created_at} for r in rows]


# --------------------------------------------------------------------------
# Survey controls: limit, schedule, segment, quotas  (FB-081..FB-084)
# --------------------------------------------------------------------------

@router.post("/surveys/{survey_id}/controls", status_code=status.HTTP_201_CREATED)
def upsert_control(
    workspace_id: str,
    survey_id: str,
    body: ControlUpsert,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    start = _parse_dt(body.schedule_start)
    end = _parse_dt(body.schedule_end)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="schedule_start must precede schedule_end")
    row = db.execute(
        select(SurveyControl).where(
            SurveyControl.workspace_id == workspace_id,
            SurveyControl.survey_id == survey_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SurveyControl(id=new_id(), workspace_id=workspace_id, survey_id=survey_id)
        db.add(row)
    row.max_responses = body.max_responses
    row.schedule_start = start
    row.schedule_end = end
    row.segment = body.segment
    row.quotas = body.quotas
    row.updated_at = now()
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=CONTROL_CHANGED,
                  entity_id=row.id, payload={"survey_id": survey_id, "action": "upsert"},
                  actor_id=principal.user.id)
    db.commit()
    return {"survey_id": survey_id, "max_responses": row.max_responses,
            "schedule_start": row.schedule_start, "schedule_end": row.schedule_end,
            "segment": row.segment, "quotas": row.quotas}


@router.get("/surveys/{survey_id}/controls")
def get_control(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    row = db.execute(
        select(SurveyControl).where(
            SurveyControl.workspace_id == workspace_id,
            SurveyControl.survey_id == survey_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return {"survey_id": survey_id, "max_responses": None, "segment": {}, "quotas": {}}
    return {"survey_id": survey_id, "max_responses": row.max_responses,
            "schedule_start": row.schedule_start, "schedule_end": row.schedule_end,
            "segment": row.segment, "quotas": row.quotas}


@router.post("/surveys/{survey_id}/controls/evaluate")
def evaluate_control(
    workspace_id: str,
    survey_id: str,
    body: ControlEvaluate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    """Evaluate submission limits, schedule window, segment and quotas from
    real persisted answers. FB-081/082/083/084."""
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    control = db.execute(
        select(SurveyControl).where(
            SurveyControl.workspace_id == workspace_id,
            SurveyControl.survey_id == survey_id,
        )
    ).scalar_one_or_none()
    if control is None:
        return {"eligible": True, "reason": "no_controls"}

    answers = db.execute(
        select(SurveyAnswer).where(
            SurveyAnswer.workspace_id == workspace_id,
            SurveyAnswer.survey_id == survey_id,
        )
    ).scalars().all()

    if control.max_responses is not None and len(answers) >= control.max_responses:
        return _control_result(False, "response_limit_reached", len(answers))

    current = now()
    start, end = _aware(control.schedule_start), _aware(control.schedule_end)
    if start is not None and current < start:
        return _control_result(False, "before_schedule", len(answers))
    if end is not None and current > end:
        return _control_result(False, "after_schedule", len(answers))

    if control.segment and not _conditions_hold(body.attributes, control.segment):
        return _control_result(False, "segment_mismatch", len(answers))

    for key, rule in (control.quotas or {}).items():
        target = rule.get("value") if isinstance(rule, dict) else rule
        limit = rule.get("limit") if isinstance(rule, dict) else None
        if limit is None:
            continue
        count = sum(
            1 for a in answers
            if _match_attribute((a.embedded or {}).get(key), target)
        )
        if count >= limit:
            return _control_result(False, f"quota_full:{key}", len(answers))

    return _control_result(True, "eligible", len(answers))


def _control_result(eligible: bool, reason: str, count: int) -> dict:
    return {"eligible": eligible, "reason": reason, "response_count": count}
