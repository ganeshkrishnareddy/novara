"""Marketing campaigns and daily campaign metrics.

Campaigns and their metrics stay inside the caller's workspace. Metrics are
upserted per campaign and date, rolled up in SQL, and every mutation publishes
an event with the authenticated actor id. Nothing is sent externally.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    Date,
    JSON,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, Event, WorkspaceMember, new_id, now
from ..permissions import (
    CONTACT_READ,
    CONTACT_WRITE,
    EVENT_READ,
    LEAD_READ,
    WORKSPACE_MANAGE,
    has_permission,
)

Channel = Literal["email", "ads", "social", "other"]
CampaignStatus = Literal["draft", "active", "paused", "completed"]

CAMPAIGN_CREATED = "campaign.created"
CAMPAIGN_UPDATED = "campaign.updated"
CAMPAIGN_STATUS_CHANGED = "campaign.status_changed"
CAMPAIGN_METRIC_RECORDED = "campaign.metric_recorded"

# MT-115 — NOVARA-native lifecycle events (03-plane-mautic.md section 2.15).
# These are local analytics records only: recording one never delivers a
# message, opens a network connection or publishes a page.
CONTACT_SEGMENTED = "contact.segmented"
CAMPAIGN_ENTERED = "campaign.entered"
CAMPAIGN_EXITED = "campaign.exited"
EMAIL_SENT = "email.sent"
EMAIL_OPENED = "email.opened"
EMAIL_CLICKED = "email.clicked"
FORM_SUBMITTED = "form.submitted"
PAGE_VISITED = "page.visited"
WEBHOOK_RECEIVED = "webhook.received"
JOURNEY_STEP_COMPLETED = "journey.step_completed"
JOURNEY_CONDITION_EVALUATED = "journey.condition_evaluated"
JOURNEY_DECISION_EVALUATED = "journey.decision_evaluated"

# The lifecycle kinds a journey step may record. Form/page/webhook intake is
# recorded through the dedicated local endpoint, not as a journey step.
JOURNEY_ACTIONS = (EMAIL_SENT, EMAIL_OPENED, EMAIL_CLICKED)
JOURNEY_STEP_KINDS = ("condition", "decision", "action")
CONDITION_OPERATORS = ("eq", "ne", "in", "contains", "exists", "gt", "gte", "lt", "lte")
# "broadcast" is the original one-off campaign kind and is retained for
# backward compatibility with existing workspaces and callers.
CAMPAIGN_TYPES = ("standard", "broadcast", "time_driven", "event_driven")
SCHEDULE_CADENCES = ("once", "daily", "weekly")
CAMPAIGN_SOURCE_TYPES = ("segment", "form", "combined")
LIFECYCLE_EVENTS = (
    CONTACT_SEGMENTED,
    CAMPAIGN_ENTERED,
    CAMPAIGN_EXITED,
    EMAIL_SENT,
    EMAIL_OPENED,
    EMAIL_CLICKED,
    FORM_SUBMITTED,
    PAGE_VISITED,
    WEBHOOK_RECEIVED,
    JOURNEY_STEP_COMPLETED,
)
# MT-027 editor events are validated/emitted by the journey editor itself and
# are deliberately NOT part of LIFECYCLE_EVENTS (that tuple is the exact set an
# intake-driven run emits, asserted by test_marketing_journey_p0.py).
EDITOR_EVENTS = (JOURNEY_CONDITION_EVALUATED, JOURNEY_DECISION_EVALUATED)
CAMPAIGN_EVENT_TRIGGERED = "campaign.event_triggered"
INTAKE_EVENTS = {
    "form.submitted": FORM_SUBMITTED,
    "page.visited": PAGE_VISITED,
    "webhook.received": WEBHOOK_RECEIVED,
}

register_event_types(
    CAMPAIGN_CREATED,
    CAMPAIGN_UPDATED,
    CAMPAIGN_STATUS_CHANGED,
    CAMPAIGN_METRIC_RECORDED,
    CAMPAIGN_EVENT_TRIGGERED,
    *LIFECYCLE_EVENTS,
    *EDITOR_EVENTS,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/campaigns",
    tags=["marketing"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_campaign_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(40), default="standard", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    cadence: Mapped[str] = mapped_column(String(20), default="once", nullable=False)
    trigger_event: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(20), default="segment", nullable=False)
    source_segment_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_form_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    __table_args__ = (UniqueConstraint("campaign_id", "date", name="uq_metric_campaign_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class JourneyStep(Base):
    """One local, consent-gated action in a campaign journey.

    A step only records an analytics event and advances the enrollment. It
    never delivers an email, message or webhook to an external system.
    """

    __tablename__ = "journey_steps"
    __table_args__ = (
        UniqueConstraint("campaign_id", "position", name="uq_journey_step_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # MT-027: journey editor nodes are typed. Action nodes keep the legacy
    # local event recording; condition and decision nodes carry a validated
    # declarative configuration and produce their own analytics event.
    step_kind: Mapped[str] = mapped_column(String(20), default="action", nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CampaignEnrollment(Base):
    """A contact's local progress through one campaign journey."""

    __tablename__ = "campaign_enrollments"
    __table_args__ = (
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_enrollment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    exited_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str
    channel: Channel
    campaign_type: str = "standard"
    status: CampaignStatus = "draft"
    goal: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    cadence: str = "once"
    trigger_event: str | None = None
    source_type: str = "segment"
    source_segment_ids: list[str] = Field(default_factory=list)
    source_form_ids: list[str] = Field(default_factory=list)
    owner_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("campaign name is required")
        return value

    @field_validator("goal")
    @classmethod
    def goal_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("campaign_type")
    @classmethod
    def type_valid(cls, value: str) -> str:
        if value not in CAMPAIGN_TYPES:
            raise ValueError("unsupported campaign_type")
        return value

    @model_validator(mode="after")
    def schedule_shape(self):
        _validate_campaign_type(self.campaign_type, self.trigger_event)
        if self.cadence != "once" and self.campaign_type != "time_driven":
            raise ValueError("recurring cadence requires a time-driven campaign")
        return self

    @field_validator("cadence")
    @classmethod
    def cadence_valid(cls, value: str) -> str:
        if value not in SCHEDULE_CADENCES:
            raise ValueError("unsupported cadence")
        return value

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, value: str) -> str:
        if value not in CAMPAIGN_SOURCE_TYPES:
            raise ValueError("unsupported campaign source type")
        return value


class CampaignUpdate(BaseModel):
    name: str | None = None
    channel: Channel | None = None
    campaign_type: str | None = None
    status: CampaignStatus | None = None
    goal: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    cadence: str | None = None
    trigger_event: str | None = None
    source_type: str | None = None
    source_segment_ids: list[str] | None = None
    source_form_ids: list[str] | None = None
    owner_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("campaign name is required")
        return value


class MetricUpsert(BaseModel):
    date: date
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    spend: Decimal = Field(default=Decimal("0"), ge=0)

    model_config = ConfigDict(extra="forbid")


class CampaignOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    channel: str
    campaign_type: str
    status: str
    goal: str | None
    start_at: object
    end_at: object
    cadence: str
    trigger_event: str | None
    source_type: str
    source_segment_ids: list[str]
    source_form_ids: list[str]
    owner_id: str | None
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class MetricOut(BaseModel):
    id: str
    workspace_id: str
    campaign_id: str
    date: date
    impressions: int
    clicks: int
    leads: int
    spend: float
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class CampaignDetail(BaseModel):
    campaign: CampaignOut
    metric_days: int
    total_impressions: int
    total_clicks: int
    total_leads: int
    total_spend: float


class CampaignPerformance(BaseModel):
    campaign_id: str
    name: str
    status: str
    metric_days: int
    total_impressions: int
    total_clicks: int
    total_leads: int
    total_spend: float


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _campaign_or_404(db: Session, workspace_id: str, campaign_id: str) -> Campaign:
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return campaign


def _validate_owner(db: Session, workspace_id: str, owner_id: str | None) -> None:
    if owner_id is None:
        return
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == owner_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=400, detail="owner must be an active member")


def _reject_duplicate(
    db: Session,
    workspace_id: str,
    name: str,
    exclude_campaign_id: str | None = None,
) -> None:
    query = select(Campaign).where(Campaign.workspace_id == workspace_id, Campaign.name == name)
    if exclude_campaign_id is not None:
        query = query.where(Campaign.id != exclude_campaign_id)
    if db.execute(query).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="a campaign with this name already exists")


# --------------------------------------------------------------------------
# MT-008 / MT-026 / MT-027 declarative validation helpers. Every rule is an
# allow-listed tree: no expression parser, no eval and no attribute traversal.
# --------------------------------------------------------------------------


def _normalize_criteria(criteria: dict) -> dict:
    """Return criteria in the canonical allow-listed structured form.

    Two shapes are accepted so pre-existing callers keep working:

    * legacy shorthand -- ``{"source": "website"}`` or
      ``{"score": {"gte": 80}}`` (field to scalar/condition map);
    * canonical -- ``{"field": "score", "op": "gte", "value": 80}`` leaves and
      ``{"all": [...]}`` / ``{"any": [...]}`` / ``{"not": {...}}`` trees.

    No expression parser, ``eval`` or attribute traversal is involved.
    """
    if not isinstance(criteria, dict) or not criteria:
        return criteria
    if "field" in criteria and isinstance(criteria["field"], str):
        return criteria
    if any(key in criteria for key in ("all", "any", "not")):
        tree: dict = {}
        for key in ("all", "any"):
            if key in criteria and isinstance(criteria[key], list):
                tree[key] = [_normalize_criteria(child) for child in criteria[key]]
        if "not" in criteria:
            tree["not"] = _normalize_criteria(criteria["not"])
        return tree
    rules = []
    for field, condition in criteria.items():
        if isinstance(condition, dict):
            for op, value in condition.items():
                rules.append({"field": field, "op": op, "value": value})
        else:
            rules.append({"field": field, "op": "eq", "value": condition})
    return {"all": rules} if len(rules) > 1 else rules[0]


def _validate_criteria(criteria: dict) -> None:
    if not isinstance(criteria, dict):
        raise ValueError("criteria must be an object")
    if not criteria:
        return

    def check(rule: object) -> None:
        if not isinstance(rule, dict):
            raise ValueError("criteria rules must be objects")
        for key in ("all", "any"):
            if key in rule:
                children = rule[key]
                if not isinstance(children, list) or not children:
                    raise ValueError(f"{key} must be a non-empty list")
                for child in children:
                    check(child)
                return
        if "not" in rule:
            check(rule["not"])
            return
        field = rule.get("field")
        op = rule.get("op", "eq")
        if not isinstance(field, str) or not field:
            raise ValueError("criteria rule requires a field")
        if op not in CONDITION_OPERATORS:
            raise ValueError("unsupported criteria operator")
        if op == "in" and not isinstance(rule.get("value"), (list, tuple)):
            raise ValueError("in requires a list value")

    check(criteria)


def _contact_facts(contact: Contact) -> dict:
    """Flatten the allow-listed contact fields used by segment and journey rules."""
    facts = {
        "id": contact.id,
        "email": contact.email,
        "full_name": contact.full_name,
        "company_name": contact.company_name,
        "phone": contact.phone,
        "source": contact.source,
        "lifecycle_stage": contact.lifecycle_stage,
        "do_not_contact": bool(contact.do_not_contact),
        "archived": bool(contact.archived),
        "tags": list(contact.tags or []),
    }
    custom = contact.custom_fields or {}
    if isinstance(custom, dict):
        for key, value in custom.items():
            facts.setdefault(str(key), value)
    return facts


def _rule_matches(rule: dict, facts: dict) -> bool:
    if not rule:
        return True
    rule = _normalize_criteria(rule)
    if "all" in rule:
        return all(_rule_matches(child, facts) for child in rule["all"])
    if "any" in rule:
        return any(_rule_matches(child, facts) for child in rule["any"])
    if "not" in rule:
        return not _rule_matches(rule["not"], facts)
    field = rule["field"]
    actual = facts.get(field)
    op = rule.get("op", "eq")
    expected = rule.get("value")
    if op == "exists":
        return field in facts
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return isinstance(expected, (list, tuple)) and actual in expected
    if op == "contains":
        return isinstance(actual, (list, tuple, str, dict)) and expected in actual
    if op in ("gt", "gte", "lt", "lte"):
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return {
                "gt": actual > expected,
                "gte": actual >= expected,
                "lt": actual < expected,
                "lte": actual <= expected,
            }[op]
    return False


def _validate_journey_node(step_kind: str, action: str, config: dict) -> None:
    if step_kind not in JOURNEY_STEP_KINDS:
        raise ValueError("unsupported journey step kind")
    if not isinstance(config, dict):
        raise ValueError("journey step config must be an object")
    if step_kind == "action":
        if action not in JOURNEY_ACTIONS:
            raise ValueError("action must be a local recording step")
        return
    if step_kind == "condition":
        if action != JOURNEY_CONDITION_EVALUATED:
            raise ValueError("condition steps must record journey.condition_evaluated")
        _validate_criteria(config)
        if not config:
            raise ValueError("condition step requires criteria")
        return
    if action != JOURNEY_DECISION_EVALUATED:
        raise ValueError("decision steps must record journey.decision_evaluated")
    field = config.get("field")
    branches = config.get("branches")
    if not isinstance(field, str) or not field:
        raise ValueError("decision step requires a field")
    if not isinstance(branches, list) or len(branches) < 2:
        raise ValueError("decision step requires at least two branches")
    for branch in branches:
        if not isinstance(branch, dict) or "value" not in branch:
            raise ValueError("each decision branch requires a value")
        if not str(branch.get("label", "")).strip():
            raise ValueError("each decision branch requires a label")


def _validate_campaign_type(campaign_type: str, trigger_event: str | None) -> None:
    if campaign_type not in CAMPAIGN_TYPES:
        raise ValueError("unsupported campaign_type")
    if campaign_type == "event_driven" and not (trigger_event or "").strip():
        raise ValueError("event-driven campaigns require a trigger_event")


def _metric_totals(db: Session, workspace_id: str, campaign_id: str) -> tuple:
    return db.execute(
        select(
            func.count(CampaignMetric.id),
            func.coalesce(func.sum(CampaignMetric.impressions), 0),
            func.coalesce(func.sum(CampaignMetric.clicks), 0),
            func.coalesce(func.sum(CampaignMetric.leads), 0),
            func.coalesce(func.sum(CampaignMetric.spend), Decimal("0")),
        ).where(
            CampaignMetric.workspace_id == workspace_id,
            CampaignMetric.campaign_id == campaign_id,
        )
    ).one()


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    workspace_id: str,
    status_filter: CampaignStatus | None = Query(None, alias="status"),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Campaign]:
    verify_workspace(principal, workspace_id)
    query = select(Campaign).where(Campaign.workspace_id == workspace_id)
    if status_filter is not None:
        query = query.where(Campaign.status == status_filter)
    return db.execute(query.order_by(Campaign.created_at.desc())).scalars().all()


@router.get("/performance", response_model=list[CampaignPerformance])
def campaign_performance(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CampaignPerformance]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(
            Campaign.id,
            Campaign.name,
            Campaign.status,
            func.count(CampaignMetric.id),
            func.coalesce(func.sum(CampaignMetric.impressions), 0),
            func.coalesce(func.sum(CampaignMetric.clicks), 0),
            func.coalesce(func.sum(CampaignMetric.leads), 0),
            func.coalesce(func.sum(CampaignMetric.spend), Decimal("0")),
        )
        .outerjoin(
            CampaignMetric,
            and_(
                CampaignMetric.campaign_id == Campaign.id,
                CampaignMetric.workspace_id == workspace_id,
            ),
        )
        .where(Campaign.workspace_id == workspace_id)
        .group_by(Campaign.id, Campaign.name, Campaign.status)
        .order_by(Campaign.name)
    ).all()
    return [
        CampaignPerformance(
            campaign_id=row[0],
            name=row[1],
            status=row[2],
            metric_days=row[3],
            total_impressions=row[4],
            total_clicks=row[5],
            total_leads=row[6],
            total_spend=float(row[7]),
        )
        for row in rows
    ]


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    workspace_id: str,
    body: CampaignCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Campaign:
    verify_workspace(principal, workspace_id)
    _reject_duplicate(db, workspace_id, body.name)
    _validate_owner(db, workspace_id, body.owner_id)
    if body.start_at is not None and body.end_at is not None and body.end_at < body.start_at:
        raise HTTPException(status_code=422, detail="end_at must be after start_at")
    campaign = Campaign(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        channel=body.channel,
        campaign_type=body.campaign_type,
        status=body.status,
        goal=body.goal,
        start_at=body.start_at,
        end_at=body.end_at,
        cadence=body.cadence,
        trigger_event=body.trigger_event,
        source_type=body.source_type,
        source_segment_ids=list(body.source_segment_ids),
        source_form_ids=list(body.source_form_ids),
        owner_id=body.owner_id or principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(campaign)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CAMPAIGN_CREATED,
        entity_id=campaign.id,
        payload={"name": campaign.name, "channel": campaign.channel, "status": campaign.status},
        actor_id=principal.user.id,
    )
    db.commit()
    return campaign


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(
    workspace_id: str,
    campaign_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> CampaignDetail:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    totals = _metric_totals(db, workspace_id, campaign.id)
    return CampaignDetail(
        campaign=CampaignOut.model_validate(campaign),
        metric_days=totals[0],
        total_impressions=totals[1],
        total_clicks=totals[2],
        total_leads=totals[3],
        total_spend=float(totals[4]),
    )


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    workspace_id: str,
    campaign_id: str,
    body: CampaignUpdate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Campaign:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    updates = body.model_dump(exclude_unset=True)
    if "campaign_type" in updates and updates["campaign_type"] is not None:
        try:
            _validate_campaign_type(
                updates["campaign_type"], updates.get("trigger_event", campaign.trigger_event)
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, allowed in (
        ("cadence", SCHEDULE_CADENCES),
        ("source_type", CAMPAIGN_SOURCE_TYPES),
    ):
        if key in updates and updates[key] is not None and updates[key] not in allowed:
            raise HTTPException(status_code=422, detail=f"unsupported {key}")
    old_status = campaign.status
    if "name" in updates and updates["name"] is not None:
        _reject_duplicate(db, workspace_id, updates["name"], exclude_campaign_id=campaign.id)
    if "owner_id" in updates:
        _validate_owner(db, workspace_id, updates["owner_id"])
    start_at = updates.get("start_at", campaign.start_at)
    end_at = updates.get("end_at", campaign.end_at)
    if start_at is not None and end_at is not None and end_at < start_at:
        raise HTTPException(status_code=422, detail="end_at must be after start_at")
    for key, value in updates.items():
        setattr(campaign, key, value)
    campaign.updated_at = now()
    status_changed = "status" in updates and updates["status"] != old_status
    event_type = CAMPAIGN_STATUS_CHANGED if status_changed else CAMPAIGN_UPDATED
    payload = {
        "fields": sorted(updates.keys()),
        "from_status": old_status if status_changed else None,
        "to_status": campaign.status if status_changed else None,
    }
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=event_type,
        entity_id=campaign.id,
        payload=payload,
        actor_id=principal.user.id,
    )
    db.commit()
    return campaign


@router.get("/{campaign_id}/metrics", response_model=list[MetricOut])
def list_metrics(
    workspace_id: str,
    campaign_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CampaignMetric]:
    verify_workspace(principal, workspace_id)
    _campaign_or_404(db, workspace_id, campaign_id)
    return db.execute(
        select(CampaignMetric)
        .where(
            CampaignMetric.workspace_id == workspace_id,
            CampaignMetric.campaign_id == campaign_id,
        )
        .order_by(CampaignMetric.date)
    ).scalars().all()


def _upsert_metric(
    workspace_id: str,
    campaign_id: str,
    body: MetricUpsert,
    principal: Principal,
    db: Session,
) -> CampaignMetric:
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    metric = db.execute(
        select(CampaignMetric).where(
            CampaignMetric.workspace_id == workspace_id,
            CampaignMetric.campaign_id == campaign.id,
            CampaignMetric.date == body.date,
        )
    ).scalar_one_or_none()
    if metric is None:
        metric = CampaignMetric(
            id=new_id(),
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            date=body.date,
            created_at=now(),
        )
        db.add(metric)
    metric.impressions = body.impressions
    metric.clicks = body.clicks
    metric.leads = body.leads
    metric.spend = Decimal(str(body.spend))
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CAMPAIGN_METRIC_RECORDED,
        entity_id=metric.id,
        payload={
            "campaign_id": campaign.id,
            "date": body.date.isoformat(),
            "impressions": metric.impressions,
            "clicks": metric.clicks,
            "leads": metric.leads,
            "spend": float(metric.spend),
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return metric


# ---------------------------------------------------------------------------
# Segments (MT-008)
# ---------------------------------------------------------------------------


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_segment_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # MT-008: static segments store explicit membership; dynamic segments are
    # recomputed from their declarative criteria against stored contacts.
    segment_type: Mapped[str] = mapped_column(String(20), default="static", nullable=False)
    criteria: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SegmentMember(Base):
    """Materialised segment membership, refreshed from criteria for dynamic lists."""

    __tablename__ = "segment_members"
    __table_args__ = (UniqueConstraint("segment_id", "contact_id", name="uq_segment_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SegmentCreate(BaseModel):
    name: str
    description: str | None = None
    segment_type: str = "static"
    criteria: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("segment name is required")
        return value

    @field_validator("segment_type")
    @classmethod
    def valid_segment_type(cls, value: str) -> str:
        if value not in ("static", "dynamic"):
            raise ValueError("segment_type must be static or dynamic")
        return value

    @field_validator("criteria")
    @classmethod
    def valid_criteria(cls, value: dict) -> dict:
        value = _normalize_criteria(value)
        _validate_criteria(value)
        return value


class SegmentOut(BaseModel):
    id: str
    name: str
    description: str | None
    segment_type: str
    criteria: dict
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/segments", response_model=list[SegmentOut])
def list_segments(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Segment]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Segment).where(Segment.workspace_id == workspace_id).order_by(Segment.created_at.desc())
    ).scalars().all()


@router.post("/segments", response_model=SegmentOut, status_code=status.HTTP_201_CREATED)
def create_segment(
    workspace_id: str,
    body: SegmentCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Segment:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Segment).where(Segment.workspace_id == workspace_id, Segment.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="segment already exists")
    segment = Segment(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name.strip(),
        description=body.description,
        segment_type=body.segment_type,
        criteria=dict(body.criteria),
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(segment)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CAMPAIGN_CREATED,
        entity_id=segment.id,
        payload={"segment": True, "name": segment.name, "segment_type": segment.segment_type},
        actor_id=principal.user.id,
    )
    db.commit()
    return segment


class SegmentMemberIds(BaseModel):
    contact_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SegmentMemberOut(BaseModel):
    contact_id: str
    created_at: object


def _segment_or_404(db: Session, workspace_id: str, segment_id: str) -> Segment:
    segment = db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if segment is None:
        raise HTTPException(status_code=404, detail="segment not found")
    return segment


@router.get("/segments/{segment_id}/members", response_model=list[SegmentMemberOut])
def list_segment_members(
    workspace_id: str,
    segment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SegmentMember]:
    verify_workspace(principal, workspace_id)
    _segment_or_404(db, workspace_id, segment_id)
    return db.execute(
        select(SegmentMember).where(
            SegmentMember.workspace_id == workspace_id,
            SegmentMember.segment_id == segment_id,
        ).order_by(SegmentMember.created_at)
    ).scalars().all()


@router.post("/segments/{segment_id}/members", status_code=status.HTTP_201_CREATED)
def set_static_segment_members(
    workspace_id: str,
    segment_id: str,
    body: SegmentMemberIds,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Replace explicit membership of a static segment; dynamic lists use /refresh."""
    verify_workspace(principal, workspace_id)
    segment = _segment_or_404(db, workspace_id, segment_id)
    if segment.segment_type != "static":
        raise HTTPException(status_code=409, detail="dynamic segment membership is criteria-driven")
    contacts = db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id, Contact.id.in_(set(body.contact_ids))
        )
    ).scalars().all() if body.contact_ids else []
    known = {contact.id for contact in contacts}
    current = db.execute(
        select(SegmentMember).where(
            SegmentMember.workspace_id == workspace_id, SegmentMember.segment_id == segment.id
        )
    ).scalars().all()
    for member in current:
        if member.contact_id not in known:
            db.delete(member)
    existing = {member.contact_id for member in current}
    for contact_id in known:
        if contact_id not in existing:
            db.add(SegmentMember(
                id=new_id(), workspace_id=workspace_id, segment_id=segment.id,
                contact_id=contact_id, created_at=now(),
            ))
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_SEGMENTED,
        entity_id=segment.id,
        payload={"segment_id": segment.id, "contact_ids": sorted(known), "static": True},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"segment_id": segment.id, "members": len(known)}


@router.post("/segments/{segment_id}/refresh")
def refresh_dynamic_segment(
    workspace_id: str,
    segment_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Recompute materialised membership of a dynamic segment from its criteria."""
    verify_workspace(principal, workspace_id)
    segment = _segment_or_404(db, workspace_id, segment_id)
    if segment.segment_type != "dynamic":
        raise HTTPException(status_code=409, detail="static segment membership is explicit")
    contacts = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id)
    ).scalars().all()
    matching = [
        contact.id for contact in contacts
        if not contact.archived and _rule_matches(segment.criteria, _contact_facts(contact))
    ]
    current = db.execute(
        select(SegmentMember).where(
            SegmentMember.workspace_id == workspace_id, SegmentMember.segment_id == segment.id
        )
    ).scalars().all()
    for member in current:
        db.delete(member)
    db.flush()
    for contact_id in matching:
        db.add(SegmentMember(
            id=new_id(), workspace_id=workspace_id, segment_id=segment.id,
            contact_id=contact_id, created_at=now(),
        ))
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_SEGMENTED,
        entity_id=segment.id,
        payload={"segment_id": segment.id, "contact_ids": sorted(matching), "dynamic": True},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"segment_id": segment.id, "members": len(matching)}


# ---------------------------------------------------------------------------
# Email templates (MT-012)
# ---------------------------------------------------------------------------


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_email_template_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "subject", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class EmailTemplateOut(BaseModel):
    id: str
    name: str
    subject: str
    body: str
    created_by: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/email-templates", response_model=list[EmailTemplateOut])
def list_email_templates(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[EmailTemplate]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(EmailTemplate).where(EmailTemplate.workspace_id == workspace_id).order_by(EmailTemplate.created_at.desc())
    ).scalars().all()


@router.post("/email-templates", response_model=EmailTemplateOut, status_code=status.HTTP_201_CREATED)
def create_email_template(
    workspace_id: str,
    body: EmailTemplateCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> EmailTemplate:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(EmailTemplate).where(EmailTemplate.workspace_id == workspace_id, EmailTemplate.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="email template already exists")
    template = EmailTemplate(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name.strip(),
        subject=body.subject.strip(),
        body=body.body.strip(),
        created_by=principal.user.id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(template)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=CAMPAIGN_CREATED,
        entity_id=template.id,
        payload={"email_template": True, "name": template.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return template


@router.put("/{campaign_id}/metrics", response_model=MetricOut)
@router.post("/{campaign_id}/metrics", response_model=MetricOut, status_code=status.HTTP_201_CREATED)
def upsert_metric(
    workspace_id: str,
    campaign_id: str,
    body: MetricUpsert,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> CampaignMetric:
    verify_workspace(principal, workspace_id)
    return _upsert_metric(workspace_id, campaign_id, body, principal, db)


# ---------------------------------------------------------------------------
# MT-025 / MT-112 / MT-115 — local journey, scheduling and lifecycle analytics
# ---------------------------------------------------------------------------


class JourneyStepCreate(BaseModel):
    position: int = Field(ge=1)
    channel: Channel = "email"
    action: str
    label: str
    step_kind: str = "action"
    config: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("label")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("step label is required")
        return value

    @model_validator(mode="after")
    def validate_node(self):
        # MT-027: the editor validates the complete node contract. Legacy
        # callers that omit step_kind keep the local action behaviour.
        try:
            _validate_journey_node(self.step_kind, self.action, self.config)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class JourneyStepUpdate(BaseModel):
    channel: Channel | None = None
    label: str | None = None
    action: str | None = None
    step_kind: str | None = None
    config: dict | None = None

    model_config = ConfigDict(extra="forbid")


class JourneyStepOut(BaseModel):
    id: str
    campaign_id: str
    position: int
    channel: str
    action: str
    label: str
    step_kind: str
    config: dict

    model_config = ConfigDict(from_attributes=True)


class EnrollmentCreate(BaseModel):
    contact_id: str
    segment_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class EnrollmentOut(BaseModel):
    id: str
    campaign_id: str
    contact_id: str
    status: str
    current_step: int
    entered_at: object
    exited_at: object

    model_config = ConfigDict(from_attributes=True)


class ScheduleBody(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("end_at")
    @classmethod
    def after_start(cls, value: datetime | None, info) -> datetime | None:
        start = info.data.get("start_at")
        if value is not None and start is not None and value <= start:
            raise ValueError("end_at must be after start_at")
        return value


class RunOut(BaseModel):
    advanced: int
    completed: int
    blocked: int
    event_types: list[str]


class EngagementCreate(BaseModel):
    contact_id: str
    kind: Literal["opened", "clicked"]

    model_config = ConfigDict(extra="forbid")


class LifecycleIntake(BaseModel):
    kind: Literal["form.submitted", "page.visited", "webhook.received"]
    source: str
    contact_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("source")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source is required")
        return value


class LifecycleEventOut(BaseModel):
    id: str
    event_type: str
    entity_id: str | None
    occurred_at: object
    payload: dict


def _contact_or_404(db: Session, workspace_id: str, contact_id: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found in this workspace")
    return contact


def _email_blocked(db: Session, workspace_id: str, contact: Contact) -> bool:
    """Mirror the broadcast consent gate without importing at module load."""
    from .email_campaigns import ConsentRecord, SuppressionEntry

    if contact.do_not_contact:
        return True
    suppressed = db.execute(
        select(SuppressionEntry.id).where(
            SuppressionEntry.workspace_id == workspace_id,
            SuppressionEntry.email == contact.email,
        )
    ).scalar_one_or_none()
    if suppressed is not None:
        return True
    latest = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.contact_id == contact.id,
            ConsentRecord.channel == "email",
        ).order_by(ConsentRecord.recorded_at.desc())
    ).scalars().first()
    return latest is not None and not bool(latest.granted)


def _enrollment_or_404(
    db: Session, workspace_id: str, campaign_id: str, contact_id: str
) -> CampaignEnrollment:
    row = db.execute(
        select(CampaignEnrollment).where(
            CampaignEnrollment.workspace_id == workspace_id,
            CampaignEnrollment.campaign_id == campaign_id,
            CampaignEnrollment.contact_id == contact_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return row


@router.post("/{campaign_id}/schedule", response_model=CampaignOut)
def schedule_campaign(
    workspace_id: str,
    campaign_id: str,
    body: ScheduleBody,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Campaign:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    campaign.start_at = body.start_at
    campaign.end_at = body.end_at
    campaign.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_UPDATED,
        entity_id=campaign.id,
        payload={"scheduled": True, "fields": ["start_at", "end_at"]},
        actor_id=principal.user.id,
    )
    db.commit()
    return campaign


@router.post("/due", response_model=list[CampaignOut])
def activate_due_campaigns(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> list[Campaign]:
    """Move scheduled drafts whose window has opened to active.

    Purely local status work. No message, page or webhook is delivered.
    """
    verify_workspace(principal, workspace_id)
    current = now()
    due = db.execute(
        select(Campaign).where(
            Campaign.workspace_id == workspace_id,
            Campaign.status == "draft",
            Campaign.start_at.is_not(None),
            Campaign.start_at <= current,
        )
    ).scalars().all()
    for campaign in due:
        end_at = campaign.end_at
        if end_at is not None and end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=current.tzinfo)
        if end_at is not None and end_at <= current:
            continue
        campaign.status = "active"
        campaign.updated_at = current
        publish_event(
            db, workspace_id=workspace_id, event_type=CAMPAIGN_STATUS_CHANGED,
            entity_id=campaign.id,
            payload={"status": "active", "reason": "scheduled"},
            actor_id=principal.user.id,
        )
    db.commit()
    return due


@router.post(
    "/{campaign_id}/journey-steps",
    response_model=JourneyStepOut,
    status_code=status.HTTP_201_CREATED,
)
def create_journey_step(
    workspace_id: str,
    campaign_id: str,
    body: JourneyStepCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> JourneyStep:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    exists = db.execute(
        select(JourneyStep.id).where(
            JourneyStep.workspace_id == workspace_id,
            JourneyStep.campaign_id == campaign.id,
            JourneyStep.position == body.position,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="position already used in this journey")
    step = JourneyStep(
        id=new_id(), workspace_id=workspace_id, campaign_id=campaign.id,
        position=body.position, channel=body.channel, action=body.action,
        label=body.label, step_kind=body.step_kind, config=dict(body.config),
        created_at=now(),
    )
    db.add(step)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_UPDATED,
        entity_id=campaign.id,
        payload={
            "journey_step": step.label, "action": step.action,
            "step_kind": step.step_kind, "validated": True,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return step


class JourneyStepPatch(BaseModel):
    label: str | None = None
    action: str | None = None
    step_kind: str | None = None
    config: dict | None = None

    model_config = ConfigDict(extra="forbid")


@router.patch("/{campaign_id}/journey-steps/{step_id}", response_model=JourneyStepOut)
def edit_journey_step(
    workspace_id: str,
    campaign_id: str,
    step_id: str,
    body: JourneyStepPatch,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> JourneyStep:
    """MT-027: edit an existing editor node, revalidating the whole contract."""
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    step = db.execute(
        select(JourneyStep).where(
            JourneyStep.id == step_id,
            JourneyStep.workspace_id == workspace_id,
            JourneyStep.campaign_id == campaign.id,
        )
    ).scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=404, detail="journey step not found")
    next_kind = body.step_kind if body.step_kind is not None else step.step_kind
    next_action = body.action if body.action is not None else step.action
    next_config = body.config if body.config is not None else dict(step.config)
    if body.label is not None:
        label = body.label.strip()
        if not label:
            raise HTTPException(status_code=422, detail="step label is required")
        step.label = label
    try:
        _validate_journey_node(next_kind, next_action, next_config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    step.step_kind = next_kind
    step.action = next_action
    step.config = next_config
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_UPDATED,
        entity_id=campaign.id,
        payload={
            "journey_step_edited": step.id, "step_kind": step.step_kind,
            "action": step.action, "validated": True,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return step


@router.get("/{campaign_id}/journey-steps", response_model=list[JourneyStepOut])
def list_journey_steps(
    workspace_id: str,
    campaign_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[JourneyStep]:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    return db.execute(
        select(JourneyStep).where(
            JourneyStep.workspace_id == workspace_id,
            JourneyStep.campaign_id == campaign.id,
        ).order_by(JourneyStep.position)
    ).scalars().all()


@router.post(
    "/{campaign_id}/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
def enroll_contact(
    workspace_id: str,
    campaign_id: str,
    body: EnrollmentCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> CampaignEnrollment:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    contact = _contact_or_404(db, workspace_id, body.contact_id)
    if _email_blocked(db, workspace_id, contact):
        raise HTTPException(status_code=409, detail="contact is suppressed or has withdrawn consent")
    existing = db.execute(
        select(CampaignEnrollment).where(
            CampaignEnrollment.workspace_id == workspace_id,
            CampaignEnrollment.campaign_id == campaign.id,
            CampaignEnrollment.contact_id == contact.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="contact already enrolled")
    if body.segment_id is not None:
        segment = db.execute(
            select(Segment.id).where(
                Segment.id == body.segment_id, Segment.workspace_id == workspace_id
            )
        ).scalar_one_or_none()
        if segment is None:
            raise HTTPException(status_code=404, detail="segment not found")
        publish_event(
            db, workspace_id=workspace_id, event_type=CONTACT_SEGMENTED,
            entity_id=contact.id,
            payload={"segment_id": segment, "campaign_id": campaign.id},
            actor_id=principal.user.id,
        )
    enrollment = CampaignEnrollment(
        id=new_id(), workspace_id=workspace_id, campaign_id=campaign.id,
        contact_id=contact.id, status="active", entered_at=now(), created_at=now(),
    )
    db.add(enrollment)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_ENTERED,
        entity_id=enrollment.id,
        payload={"campaign_id": campaign.id, "contact_id": contact.id},
        idempotency_key=f"campaign-entered:{enrollment.id}",
        actor_id=principal.user.id,
    )
    db.commit()
    return enrollment


class SourceEnrollmentBody(BaseModel):
    segment_ids: list[str] | None = None
    form_ids: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


@router.post("/{campaign_id}/enroll-from-sources")
def enroll_from_sources(
    workspace_id: str,
    campaign_id: str,
    body: SourceEnrollmentBody,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """MT-028: enrol the correct contacts once from segments, forms or both."""
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    segment_ids = body.segment_ids if body.segment_ids is not None else list(campaign.source_segment_ids)
    form_ids = body.form_ids if body.form_ids is not None else list(campaign.source_form_ids)
    if campaign.source_type == "segment" and not body.form_ids:
        form_ids = []
    if campaign.source_type == "form" and not body.segment_ids:
        segment_ids = []
    if not segment_ids and not form_ids:
        raise HTTPException(status_code=422, detail="campaign has no contact sources")

    contact_ids: list[str] = []
    if segment_ids:
        segments = db.execute(
            select(Segment).where(
                Segment.workspace_id == workspace_id, Segment.id.in_(set(segment_ids))
            )
        ).scalars().all()
        if len(segments) != len(set(segment_ids)):
            raise HTTPException(status_code=404, detail="segment source not found")
        for segment in segments:
            if segment.segment_type == "dynamic":
                contacts = db.execute(
                    select(Contact).where(Contact.workspace_id == workspace_id)
                ).scalars().all()
                for contact in contacts:
                    if _rule_matches(segment.criteria, _contact_facts(contact)):
                        contact_ids.append(contact.id)
        rows = db.execute(
            select(SegmentMember.contact_id).where(
                SegmentMember.workspace_id == workspace_id,
                SegmentMember.segment_id.in_(set(segment_ids)),
            )
        ).scalars().all()
        contact_ids.extend(rows)
    if form_ids:
        forms = db.execute(
            select(MarketingForm.id).where(
                MarketingForm.workspace_id == workspace_id, MarketingForm.id.in_(set(form_ids))
            )
        ).scalars().all()
        if len(forms) != len(set(form_ids)):
            raise HTTPException(status_code=404, detail="form source not found")
        rows = db.execute(
            select(FormSubmission.contact_id).where(
                FormSubmission.workspace_id == workspace_id,
                FormSubmission.form_id.in_(set(form_ids)),
            )
        ).scalars().all()
        contact_ids.extend(rows)

    existing = set(db.execute(
        select(CampaignEnrollment.contact_id).where(
            CampaignEnrollment.workspace_id == workspace_id,
            CampaignEnrollment.campaign_id == campaign.id,
        )
    ).scalars().all())
    enrolled: list[str] = []
    skipped: list[str] = []
    for contact_id in dict.fromkeys(contact_ids):
        if contact_id in existing:
            skipped.append(contact_id)
            continue
        contact = db.get(Contact, contact_id)
        if contact is None or contact.workspace_id != workspace_id or _email_blocked(db, workspace_id, contact):
            skipped.append(contact_id)
            continue
        enrollment = CampaignEnrollment(
            id=new_id(), workspace_id=workspace_id, campaign_id=campaign.id,
            contact_id=contact_id, status="active", entered_at=now(), created_at=now(),
        )
        db.add(enrollment)
        db.flush()
        publish_event(
            db, workspace_id=workspace_id, event_type=CAMPAIGN_ENTERED,
            entity_id=enrollment.id,
            payload={
                "campaign_id": campaign.id, "contact_id": contact_id,
                "source_type": campaign.source_type,
                "segment_ids": sorted(set(segment_ids)), "form_ids": sorted(set(form_ids)),
            },
            idempotency_key=f"campaign-entered:{enrollment.id}",
            actor_id=principal.user.id,
        )
        enrolled.append(contact_id)
    db.commit()
    return {
        "campaign_id": campaign.id,
        "source_type": campaign.source_type,
        "enrolled": enrolled,
        "already_enrolled_or_blocked": sorted(set(skipped)),
    }


@router.get("/{campaign_id}/enrollments", response_model=list[EnrollmentOut])
def list_enrollments(
    workspace_id: str,
    campaign_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CampaignEnrollment]:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    return db.execute(
        select(CampaignEnrollment).where(
            CampaignEnrollment.workspace_id == workspace_id,
            CampaignEnrollment.campaign_id == campaign.id,
        ).order_by(CampaignEnrollment.entered_at)
    ).scalars().all()


@router.delete("/{campaign_id}/enrollments/{contact_id}", status_code=status.HTTP_200_OK)
def exit_campaign(
    workspace_id: str,
    campaign_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    enrollment = _enrollment_or_404(db, workspace_id, campaign.id, contact_id)
    if enrollment.status == "active":
        enrollment.status = "exited"
        enrollment.exited_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=CAMPAIGN_EXITED,
            entity_id=enrollment.id,
            payload={"campaign_id": campaign.id, "contact_id": contact_id, "reason": "removed"},
            idempotency_key=f"campaign-exited:{enrollment.id}",
            actor_id=principal.user.id,
        )
    db.commit()
    return {"exited": True, "contact_id": contact_id}


@router.post("/{campaign_id}/run", response_model=RunOut)
def run_journey(
    workspace_id: str,
    campaign_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> RunOut:
    """Advance every active enrollment by one local step.

    Step events are analytics records in this workspace. Nothing is sent.
    """
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    steps = db.execute(
        select(JourneyStep).where(
            JourneyStep.workspace_id == workspace_id,
            JourneyStep.campaign_id == campaign.id,
        ).order_by(JourneyStep.position)
    ).scalars().all()
    enrollments = db.execute(
        select(CampaignEnrollment).where(
            CampaignEnrollment.workspace_id == workspace_id,
            CampaignEnrollment.campaign_id == campaign.id,
            CampaignEnrollment.status == "active",
        )
    ).scalars().all()
    advanced = completed = blocked = 0
    emitted: list[str] = []
    for enrollment in enrollments:
        contact = db.get(Contact, enrollment.contact_id)
        if enrollment.current_step >= len(steps):
            _finish_enrollment(db, workspace_id, campaign.id, enrollment, "journey_complete", principal.user.id)
            completed += 1
            emitted.append(CAMPAIGN_EXITED)
            continue
        step = steps[enrollment.current_step]
        if step.action == EMAIL_SENT and contact is not None and _email_blocked(db, workspace_id, contact):
            blocked += 1
            continue
        publish_event(
            db, workspace_id=workspace_id, event_type=step.action,
            entity_id=enrollment.id,
            payload={
                "campaign_id": campaign.id, "contact_id": enrollment.contact_id,
                "step_id": step.id, "channel": step.channel, "local_only": True,
            },
            idempotency_key=f"journey-step:{enrollment.id}:{step.id}",
            actor_id=principal.user.id,
        )
        publish_event(
            db, workspace_id=workspace_id, event_type=JOURNEY_STEP_COMPLETED,
            entity_id=enrollment.id,
            payload={"campaign_id": campaign.id, "step_id": step.id},
            idempotency_key=f"journey-completed:{enrollment.id}:{step.id}",
            actor_id=principal.user.id,
        )
        emitted.extend((step.action, JOURNEY_STEP_COMPLETED))
        enrollment.current_step += 1
        advanced += 1
        if enrollment.current_step >= len(steps):
            _finish_enrollment(db, workspace_id, campaign.id, enrollment, "journey_complete", principal.user.id)
            completed += 1
            emitted.append(CAMPAIGN_EXITED)
    db.commit()
    return RunOut(advanced=advanced, completed=completed, blocked=blocked,
                  event_types=sorted(set(emitted)))


def _finish_enrollment(db, workspace_id, campaign_id, enrollment, reason, actor_id) -> None:
    enrollment.status = "exited"
    enrollment.exited_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_EXITED,
        entity_id=enrollment.id,
        payload={"campaign_id": campaign_id, "contact_id": enrollment.contact_id, "reason": reason},
        idempotency_key=f"campaign-exited:{enrollment.id}",
        actor_id=actor_id,
    )


@router.post("/{campaign_id}/engagement", status_code=status.HTTP_201_CREATED)
def record_engagement(
    workspace_id: str,
    campaign_id: str,
    body: EngagementCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Record a locally observed open/click. No tracking pixel or remote hit."""
    verify_workspace(principal, workspace_id)
    campaign = _campaign_or_404(db, workspace_id, campaign_id)
    _enrollment_or_404(db, workspace_id, campaign.id, body.contact_id)
    event_type = EMAIL_OPENED if body.kind == "opened" else EMAIL_CLICKED
    publish_event(
        db, workspace_id=workspace_id, event_type=event_type,
        entity_id=body.contact_id,
        payload={"campaign_id": campaign.id, "local_only": True},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"recorded": event_type}


@router.post("/analytics/lifecycle", status_code=status.HTTP_201_CREATED)
def record_lifecycle_intake(
    workspace_id: str,
    body: LifecycleIntake,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Record a form submission, page visit or received webhook locally."""
    verify_workspace(principal, workspace_id)
    event_type = INTAKE_EVENTS[body.kind]
    if body.contact_id is not None:
        _contact_or_404(db, workspace_id, body.contact_id)
    publish_event(
        db, workspace_id=workspace_id, event_type=event_type,
        entity_id=body.contact_id,
        payload={"source": body.source, "local_only": True},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"recorded": event_type}


@router.get("/analytics/lifecycle", response_model=list[LifecycleEventOut])
def list_lifecycle_events(
    workspace_id: str,
    kind: str | None = Query(None, alias="kind"),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Event]:
    verify_workspace(principal, workspace_id)
    if kind is not None and kind not in LIFECYCLE_EVENTS:
        raise HTTPException(status_code=422, detail="unknown lifecycle event type")
    query = select(Event).where(
        Event.workspace_id == workspace_id,
        Event.event_type.in_(LIFECYCLE_EVENTS),
    )
    if kind is not None:
        query = query.where(Event.event_type == kind)
    return db.execute(query.order_by(Event.occurred_at.desc())).scalars().all()


# ---------------------------------------------------------------------------
# MT-003 — NOVARA module extension contract (clean-room)
# ---------------------------------------------------------------------------

# Contract (MT-003): an extension is a plain Python object with (1) a unique
# snake_case ``name``, (2) a non-empty ``events`` collection naming the local
# event types it subscribes to, and (3) a ``handle(event_type, context)``
# callable. Registration is explicit and in-process; dispatch passes a copy of
# the context and propagates errors so a caller never records a successful
# action that an extension failed to observe. There is no plugin discovery, no
# remote code and no shared-state mutation outside the registry.
MARKETING_EXTENSION_CONTRACT = (
    "name: unique snake_case identifier; "
    "events: non-empty collection of registered event types; "
    "handle(event_type, context): synchronous local observer"
)

# MT-107 — explicit scope record. No Mautic-derived code or asset is shipped,
# so derivative distribution is out of scope and legal review is not requested.
DERIVATIVE_DISTRIBUTION_STATUS = {
    "status": "out_of_scope",
    "scope": "clean-room NOVARA code only; no Mautic source, assets or derivative distribution",
    "review": "legal review is required only if derivative distribution is ever proposed",
}


class MarketingExtension(Protocol):
    name: str
    events: frozenset[str] | set[str] | tuple[str, ...]
    def handle(self, event_type: str, context: dict) -> None: ...


_MARKETING_EXTENSIONS: dict[str, MarketingExtension] = {}


def register_marketing_extension(extension: MarketingExtension) -> str:
    """Register a local observer. Returns its name. Raises ValueError on a bad contract."""
    name = getattr(extension, "name", None)
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", name):
        raise ValueError("extension name must be snake_case")
    if name in _MARKETING_EXTENSIONS:
        raise ValueError("extension name already registered")
    events = getattr(extension, "events", None)
    if not isinstance(events, (set, frozenset, tuple, list)) or not events:
        raise ValueError("extension must subscribe to at least one event")
    if not all(isinstance(item, str) and item for item in events):
        raise ValueError("extension event names must be non-empty strings")
    if not callable(getattr(extension, "handle", None)):
        raise ValueError("extension must implement handle(event_type, context)")
    _MARKETING_EXTENSIONS[name] = extension
    return name


def unregister_marketing_extension(name: str) -> None:
    _MARKETING_EXTENSIONS.pop(name, None)


def dispatch_marketing_extension(event_type: str, context: dict) -> list[str]:
    """Notify interested local extensions; return the names that observed it."""
    called: list[str] = []
    for name, extension in sorted(_MARKETING_EXTENSIONS.items()):
        if event_type in extension.events:
            extension.handle(event_type, dict(context))
            called.append(name)
    return called


# ---------------------------------------------------------------------------
# MT-114 — deterministic legacy scope -> NOVARA RBAC translation
# ---------------------------------------------------------------------------

# The audit requires an adapter-boundary map. Mautic source is not consulted;
# each key is a documented legacy capability and each value is an existing
# NOVARA permission constant. NOVARA RBAC remains authoritative.
LEGACY_SCOPE_TO_PERMISSION: dict[str, str] = {
    "lead:view": CONTACT_READ,
    "lead:edit": CONTACT_WRITE,
    "contact:view": CONTACT_READ,
    "contact:edit": CONTACT_WRITE,
    "company:view": CONTACT_READ,
    "campaign:view": CONTACT_READ,
    "campaign:edit": CONTACT_WRITE,
    "campaign:publish": CONTACT_WRITE,
    "form:view": CONTACT_READ,
    "form:edit": CONTACT_WRITE,
    "email:view": CONTACT_READ,
    "email:edit": CONTACT_WRITE,
    "report:view": EVENT_READ,
    "event:view": EVENT_READ,
    "stage:edit": CONTACT_WRITE,
    "score:edit": LEAD_READ,
    "webhook:manage": WORKSPACE_MANAGE,
    "settings:manage": WORKSPACE_MANAGE,
}


def translate_legacy_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    """Translate legacy scopes to a stable, de-duplicated NOVARA permission tuple."""
    if isinstance(scopes, (str, bytes)):
        raise ValueError("scopes must be an iterable of scope strings")
    translated: list[str] = []
    for scope in scopes:
        if not isinstance(scope, str):
            raise ValueError("scope must be a string")
        key = scope.strip().lower()
        if key not in LEGACY_SCOPE_TO_PERMISSION:
            raise ValueError("unsupported legacy scope")
        permission = LEGACY_SCOPE_TO_PERMISSION[key]
        if permission not in translated:
            translated.append(permission)
    return tuple(translated)


def role_satisfies_legacy_scopes(role: str, scopes: Iterable[str]) -> bool:
    """True only when the verified NOVARA role grants every translated permission."""
    return all(has_permission(role, permission) for permission in translate_legacy_scopes(scopes))


# ---------------------------------------------------------------------------
# MT-030 / MT-047 / MT-069 — forms, configurable reports and scheduled jobs
# ---------------------------------------------------------------------------

FORM_CREATED = "marketing_form.created"
MARKETING_REPORT_CREATED = "marketing_report.created"
MARKETING_JOB_COMPLETED = "marketing.job_completed"
register_event_types(FORM_CREATED, MARKETING_REPORT_CREATED, MARKETING_JOB_COMPLETED)

FORM_TOKEN_SECRET = os.getenv("NOVARA_FORM_TOKEN_SECRET", "novara-dev-form-token-secret").encode("utf-8")
FORM_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30
FORM_FIELD_TYPES = ("text", "email", "number", "date", "boolean", "select")
FORM_ACTIONS = ("tag", "lifecycle", "campaign_enroll")


class MarketingForm(Base):
    """A workspace-owned form definition with explicit fields and local actions."""

    __tablename__ = "marketing_forms"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_marketing_form_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class FormSubmission(Base):
    """A real submission linked to the contact it created or updated."""

    __tablename__ = "marketing_form_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("marketing_forms.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    actions_applied: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class FormField(BaseModel):
    key: str
    type: Literal["text", "email", "number", "date", "boolean", "select"]
    label: str | None = None
    required: bool = False
    options: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", value or ""):
            raise ValueError("field key must be snake_case")
        return value

    @field_validator("options")
    @classmethod
    def valid_options(cls, value: list[str]) -> list[str]:
        if len(value) > 50 or any(not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError("invalid select options")
        return value


class FormAction(BaseModel):
    type: Literal["tag", "lifecycle", "campaign_enroll"]
    value: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("value")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("action value is required")
        return value


class FormCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    fields: list[FormField]
    actions: list[FormAction] = Field(default_factory=list)
    status: Literal["draft", "active"] = "active"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "slug")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,79}", value):
            raise ValueError("slug must be lowercase kebab-case")
        return value

    @field_validator("fields")
    @classmethod
    def check_fields(cls, value: list[FormField]) -> list[FormField]:
        if not value:
            raise ValueError("at least one field is required")
        if len({field.key for field in value}) != len(value):
            raise ValueError("duplicate field key")
        if not any(field.type == "email" for field in value):
            raise ValueError("a form needs one email field to resolve the contact")
        return value


class FormSubmit(BaseModel):
    answers: dict

    model_config = ConfigDict(extra="forbid")


class FormOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    slug: str
    description: str | None
    fields: list[dict]
    actions: list[dict]
    status: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class FormSubmitOut(BaseModel):
    submission_id: str
    contact_id: str
    contact_created: bool
    actions_applied: list[str]
    observed_by: list[str]


def _form_token(workspace_id: str, form_id: str) -> str:
    expires = int(time.time()) + FORM_TOKEN_TTL_SECONDS
    payload = f"form:{workspace_id}:{form_id}:{expires}"
    signature = hmac.new(FORM_TOKEN_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _verify_form_token(token: str, workspace_id: str, form_id: str) -> bool:
    parts = token.split(":")
    if len(parts) != 5 or parts[0] != "form" or parts[1] != workspace_id or parts[2] != form_id:
        return False
    payload = ":".join(parts[:4])
    expected = hmac.new(FORM_TOKEN_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[4]):
        return False
    try:
        return int(parts[3]) >= int(time.time())
    except ValueError:
        return False


def _form_or_404(db: Session, workspace_id: str, form_id: str) -> MarketingForm:
    form = db.execute(
        select(MarketingForm).where(
            MarketingForm.id == form_id,
            MarketingForm.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if form is None:
        raise HTTPException(status_code=404, detail="form not found")
    return form


def _validate_answers(form: MarketingForm, answers: dict) -> None:
    if not isinstance(answers, dict):
        raise HTTPException(status_code=422, detail="answers must be an object")
    definitions = {field["key"]: field for field in form.fields}
    unknown = set(answers) - set(definitions)
    if unknown:
        raise HTTPException(status_code=422, detail="unknown form field")
    for key, definition in definitions.items():
        value = answers.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if definition.get("required"):
                raise HTTPException(status_code=422, detail=f"field {key} is required")
            continue
        kind = definition["type"]
        if kind == "email":
            if not isinstance(value, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise HTTPException(status_code=422, detail=f"field {key} must be an email")
        elif kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(status_code=422, detail=f"field {key} must be a number")
        elif kind == "date":
            try:
                date.fromisoformat(str(value))
            except ValueError:
                raise HTTPException(status_code=422, detail=f"field {key} must be an ISO date") from None
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"field {key} must be a boolean")
        elif kind == "select":
            if value not in definition.get("options", []):
                raise HTTPException(status_code=422, detail=f"field {key} is not an allowed option")
        elif not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"field {key} must be text")
    if len(str(answers)) > 20000:
        raise HTTPException(status_code=422, detail="answers are too large")


@router.post("/forms", response_model=FormOut, status_code=status.HTTP_201_CREATED)
def create_form(
    workspace_id: str,
    body: FormCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> MarketingForm:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(MarketingForm.id).where(
            MarketingForm.workspace_id == workspace_id, MarketingForm.slug == body.slug
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="form slug already exists")
    form = MarketingForm(
        id=new_id(), workspace_id=workspace_id, name=body.name, slug=body.slug,
        description=body.description, fields=[f.model_dump() for f in body.fields],
        actions=[a.model_dump() for a in body.actions], status=body.status,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(form)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=FORM_CREATED, entity_id=form.id,
        payload={"slug": form.slug, "fields": [f["key"] for f in form.fields]},
        actor_id=principal.user.id,
    )
    db.commit()
    return form


@router.get("/forms/list", response_model=list[FormOut])
def list_forms(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[MarketingForm]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(MarketingForm).where(MarketingForm.workspace_id == workspace_id)
        .order_by(MarketingForm.created_at.desc())
    ).scalars().all()


@router.get("/forms/{form_id}", response_model=FormOut)
def get_form(
    workspace_id: str,
    form_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> MarketingForm:
    verify_workspace(principal, workspace_id)
    return _form_or_404(db, workspace_id, form_id)


@router.get("/forms/{form_id}/token")
def form_submission_token(
    workspace_id: str,
    form_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Signed, expiring capability for public submission of one form."""
    verify_workspace(principal, workspace_id)
    form = _form_or_404(db, workspace_id, form_id)
    if form.status != "active":
        raise HTTPException(status_code=409, detail="form is not active")
    return {"token": _form_token(workspace_id, form.id), "form_id": form.id, "expires_in": FORM_TOKEN_TTL_SECONDS}


@router.post(
    "/forms/{form_id}/submit",
    response_model=FormSubmitOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_form(
    workspace_id: str,
    form_id: str,
    body: FormSubmit,
    x_form_token: str | None = Header(default=None, alias="X-Form-Token"),
    db: Session = Depends(get_db),
) -> FormSubmitOut:
    """Public, token-gated submission. Creates or updates a real workspace contact.

    The capability token travels in the X-Form-Token header (not a query
    parameter). It is verified before any write; invalid answers are rejected
    with 422 only after a valid token has been presented.
    """
    if x_form_token is None or not _verify_form_token(x_form_token, workspace_id, form_id):
        raise HTTPException(status_code=401, detail="invalid or expired form token")
    form = _form_or_404(db, workspace_id, form_id)
    if form.status != "active":
        raise HTTPException(status_code=409, detail="form is not active")
    _validate_answers(form, body.answers)
    email_field = next(field["key"] for field in form.fields if field["type"] == "email")
    email = str(body.answers[email_field]).strip().lower()
    contact = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == email)
    ).scalar_one_or_none()
    contact_created = contact is None
    if contact is None:
        contact = Contact(
            id=new_id(), workspace_id=workspace_id, email=email,
            full_name=str(body.answers.get("full_name") or body.answers.get("name") or "")[:200] or None,
            phone=str(body.answers.get("phone") or "")[:50] or None,
            source=f"form:{form.slug}", custom_fields=dict(body.answers),
            tags=[], lifecycle_stage="lead", created_at=now(), updated_at=now(),
        )
        db.add(contact)
        db.flush()
    else:
        for key in ("full_name", "name"):
            if key in body.answers and body.answers[key]:
                contact.full_name = str(body.answers[key])[:200]
        if body.answers.get("phone"):
            contact.phone = str(body.answers["phone"])[:50]
        custom = dict(contact.custom_fields or {})
        custom.update(body.answers)
        contact.custom_fields = custom
        contact.updated_at = now()
    applied: list[str] = []
    for action in form.actions:
        kind, value = action["type"], action["value"]
        if kind == "tag":
            tags = list(contact.tags or [])
            if value not in tags:
                tags.append(value)
                contact.tags = tags
        elif kind == "lifecycle":
            contact.lifecycle_stage = value
        elif kind == "campaign_enroll":
            campaign = db.execute(
                select(Campaign).where(Campaign.id == value, Campaign.workspace_id == workspace_id)
            ).scalar_one_or_none()
            if campaign is None:
                raise HTTPException(status_code=404, detail="action campaign not found")
            existing = db.execute(
                select(CampaignEnrollment.id).where(
                    CampaignEnrollment.workspace_id == workspace_id,
                    CampaignEnrollment.campaign_id == campaign.id,
                    CampaignEnrollment.contact_id == contact.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                enrollment = CampaignEnrollment(
                    id=new_id(), workspace_id=workspace_id, campaign_id=campaign.id,
                    contact_id=contact.id, status="active", entered_at=now(), created_at=now(),
                )
                db.add(enrollment)
                db.flush()
                publish_event(
                    db, workspace_id=workspace_id, event_type=CAMPAIGN_ENTERED,
                    entity_id=enrollment.id,
                    payload={"campaign_id": campaign.id, "contact_id": contact.id, "source": "form"},
                    idempotency_key=f"campaign-entered:{enrollment.id}", actor_id=None,
                )
        applied.append(f"{kind}:{value}")
    submission = FormSubmission(
        id=new_id(), workspace_id=workspace_id, form_id=form.id, contact_id=contact.id,
        answers=dict(body.answers), actions_applied=applied, created_at=now(),
    )
    db.add(submission)
    db.flush()
    context = {
        "form_id": form.id, "form_slug": form.slug, "contact_id": contact.id,
        "workspace_id": workspace_id, "contact_created": contact_created,
    }
    observed_by = dispatch_marketing_extension(FORM_SUBMITTED, context)
    publish_event(
        db, workspace_id=workspace_id, event_type=FORM_SUBMITTED,
        entity_id=submission.id, payload=context, actor_id=None,
    )
    db.commit()
    return FormSubmitOut(
        submission_id=submission.id, contact_id=contact.id,
        contact_created=contact_created, actions_applied=applied, observed_by=observed_by,
    )


@router.get("/forms/{form_id}/submissions")
def list_form_submissions(
    workspace_id: str,
    form_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _form_or_404(db, workspace_id, form_id)
    rows = db.execute(
        select(FormSubmission).where(
            FormSubmission.workspace_id == workspace_id, FormSubmission.form_id == form_id
        ).order_by(FormSubmission.created_at)
    ).scalars().all()
    return [
        {"id": row.id, "contact_id": row.contact_id, "answers": row.answers,
         "actions_applied": row.actions_applied, "created_at": row.created_at}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# MT-047 — configurable marketing reports
# ---------------------------------------------------------------------------

REPORT_METRICS: dict[str, frozenset[str]] = {
    "campaign_metrics": frozenset({"impressions", "clicks", "leads", "spend", "days"}),
    "campaigns": frozenset({"campaigns", "active", "paused", "completed"}),
    "enrollments": frozenset({"active", "exited", "entered"}),
    "form_submissions": frozenset({"submissions", "contacts", "actions"}),
}


class MarketingReportDefinition(Base):
    __tablename__ = "marketing_report_definitions"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_marketing_report_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ReportCreate(BaseModel):
    name: str
    entity: str
    metrics: list[str]
    filters: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("report name is required")
        return value

    @field_validator("entity")
    @classmethod
    def known_entity(cls, value: str) -> str:
        if value not in REPORT_METRICS:
            raise ValueError("unknown report entity")
        return value

    @field_validator("metrics")
    @classmethod
    def known_metrics(cls, value: list[str], info) -> list[str]:
        entity = info.data.get("entity")
        allowed = REPORT_METRICS.get(entity, frozenset())
        if not value or len(set(value)) != len(value) or any(m not in allowed for m in value):
            raise ValueError("invalid metrics for report entity")
        return value

    @field_validator("filters")
    @classmethod
    def valid_filters(cls, value: dict) -> dict:
        allowed = {"campaign_id", "form_id", "date_from", "date_to", "status"}
        if set(value) - allowed:
            raise ValueError("unsupported report filter")
        for key in ("date_from", "date_to"):
            if key in value:
                try:
                    date.fromisoformat(str(value[key]))
                except ValueError:
                    raise ValueError(f"invalid {key}") from None
        return value


class ReportOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    entity: str
    metrics: list[str]
    filters: dict
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ReportRunOut(BaseModel):
    report_id: str
    entity: str
    rows: list[dict]
    totals: dict
    generated_at: object


def _report_or_404(db: Session, workspace_id: str, report_id: str) -> MarketingReportDefinition:
    report = db.execute(
        select(MarketingReportDefinition).where(
            MarketingReportDefinition.id == report_id,
            MarketingReportDefinition.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_marketing_report(
    workspace_id: str,
    body: ReportCreate,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> MarketingReportDefinition:
    verify_workspace(principal, workspace_id)
    if "campaign_id" in body.filters:
        _campaign_or_404(db, workspace_id, body.filters["campaign_id"])
    if "form_id" in body.filters:
        _form_or_404(db, workspace_id, body.filters["form_id"])
    if "date_from" in body.filters and "date_to" in body.filters:
        if body.filters["date_from"] > body.filters["date_to"]:
            raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    exists = db.execute(
        select(MarketingReportDefinition.id).where(
            MarketingReportDefinition.workspace_id == workspace_id,
            MarketingReportDefinition.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="report name already exists")
    report = MarketingReportDefinition(
        id=new_id(), workspace_id=workspace_id, name=body.name, entity=body.entity,
        metrics=body.metrics, filters=body.filters,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(report)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=MARKETING_REPORT_CREATED,
        entity_id=report.id, payload={"entity": report.entity, "metrics": report.metrics},
        actor_id=principal.user.id,
    )
    db.commit()
    return report


@router.get("/reports/list", response_model=list[ReportOut])
def list_marketing_reports(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[MarketingReportDefinition]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(MarketingReportDefinition)
        .where(MarketingReportDefinition.workspace_id == workspace_id)
        .order_by(MarketingReportDefinition.created_at.desc())
    ).scalars().all()


def _run_report(db: Session, workspace_id: str, report: MarketingReportDefinition) -> ReportRunOut:
    filters = report.filters
    rows: list[dict] = []
    totals: dict = {}
    if report.entity == "campaign_metrics":
        query = (
            select(
                Campaign.id, Campaign.name,
                func.count(CampaignMetric.id),
                func.coalesce(func.sum(CampaignMetric.impressions), 0),
                func.coalesce(func.sum(CampaignMetric.clicks), 0),
                func.coalesce(func.sum(CampaignMetric.leads), 0),
                func.coalesce(func.sum(CampaignMetric.spend), Decimal("0")),
            )
            .outerjoin(
                CampaignMetric,
                and_(
                    CampaignMetric.campaign_id == Campaign.id,
                    CampaignMetric.workspace_id == workspace_id,
                ),
            )
            .where(Campaign.workspace_id == workspace_id)
            .group_by(Campaign.id, Campaign.name)
            .order_by(Campaign.name)
        )
        if "campaign_id" in filters:
            query = query.where(Campaign.id == filters["campaign_id"])
        if "date_from" in filters:
            query = query.where(CampaignMetric.date >= date.fromisoformat(filters["date_from"]))
        if "date_to" in filters:
            query = query.where(CampaignMetric.date <= date.fromisoformat(filters["date_to"]))
        for row in db.execute(query).all():
            item = {
                "campaign_id": row[0], "name": row[1], "days": int(row[2]),
                "impressions": int(row[3]), "clicks": int(row[4]),
                "leads": int(row[5]), "spend": float(row[6]),
            }
            rows.append({key: item[key] for key in ("campaign_id", "name", *report.metrics)})
        for metric in report.metrics:
            totals[metric] = round(sum(float(r[metric]) for r in rows), 2)
    elif report.entity == "campaigns":
        query = select(Campaign.status, func.count(Campaign.id)).where(
            Campaign.workspace_id == workspace_id
        ).group_by(Campaign.status).order_by(Campaign.status)
        if "status" in filters:
            query = query.where(Campaign.status == filters["status"])
        rows = [{"status": status, "campaigns": int(count)} for status, count in db.execute(query).all()]
        for metric in report.metrics:
            totals[metric] = sum(int(r.get(metric, 0)) for r in rows)
    elif report.entity == "enrollments":
        query = select(
            CampaignEnrollment.campaign_id, CampaignEnrollment.status, func.count(CampaignEnrollment.id)
        ).where(CampaignEnrollment.workspace_id == workspace_id).group_by(
            CampaignEnrollment.campaign_id, CampaignEnrollment.status
        )
        if "campaign_id" in filters:
            query = query.where(CampaignEnrollment.campaign_id == filters["campaign_id"])
        rows = [
            {"campaign_id": cid, "status": status, "count": int(count)}
            for cid, status, count in db.execute(query).all()
        ]
        for metric in report.metrics:
            totals[metric] = sum(
                int(r["count"]) for r in rows
                if (metric == "active" and r["status"] == "active")
                or (metric == "exited" and r["status"] == "exited")
                or metric == "entered"
            )
    else:  # form_submissions
        query = select(FormSubmission).where(FormSubmission.workspace_id == workspace_id)
        if "form_id" in filters:
            query = query.where(FormSubmission.form_id == filters["form_id"])
        submissions = db.execute(query.order_by(FormSubmission.created_at)).scalars().all()
        grouped: dict[str, dict] = {}
        for submission in submissions:
            group = grouped.setdefault(submission.form_id, {
                "form_id": submission.form_id, "submissions": 0, "contacts": set(), "actions": 0,
            })
            group["submissions"] += 1
            group["contacts"].add(submission.contact_id)
            group["actions"] += len(submission.actions_applied or [])
        rows = [
            {"form_id": fid, "submissions": g["submissions"],
             "contacts": len(g["contacts"]), "actions": g["actions"]}
            for fid, g in sorted(grouped.items())
        ]
        for metric in report.metrics:
            totals[metric] = sum(int(r[metric]) for r in rows)
    return ReportRunOut(
        report_id=report.id, entity=report.entity, rows=rows,
        totals=totals, generated_at=now(),
    )


@router.get("/reports/{report_id}/run", response_model=ReportRunOut)
def run_marketing_report(
    workspace_id: str,
    report_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> ReportRunOut:
    verify_workspace(principal, workspace_id)
    return _run_report(db, workspace_id, _report_or_404(db, workspace_id, report_id))


# ---------------------------------------------------------------------------
# MT-069 — observable scheduled maintenance jobs
# ---------------------------------------------------------------------------

JOB_TYPES = ("activate_due_campaigns", "metrics_rollup", "enrollment_cleanup")


class MarketingJob(Base):
    __tablename__ = "marketing_jobs"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_marketing_job_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class MarketingJobRun(Base):
    __tablename__ = "marketing_job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("marketing_jobs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobCreate(BaseModel):
    name: str
    job_type: str
    interval_minutes: int = Field(default=1440, ge=1, le=10080)
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("job name is required")
        return value

    @field_validator("job_type")
    @classmethod
    def known_job(cls, value: str) -> str:
        if value not in JOB_TYPES:
            raise ValueError("unknown job type")
        return value


class JobOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    job_type: str
    interval_minutes: int
    enabled: bool
    last_run_at: object
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class JobRunOut(BaseModel):
    run_id: str
    job_id: str
    status: str
    details: dict
    started_at: object
    finished_at: object


def _job_or_404(db: Session, workspace_id: str, job_id: str) -> MarketingJob:
    job = db.execute(
        select(MarketingJob).where(
            MarketingJob.id == job_id, MarketingJob.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_marketing_job(
    workspace_id: str,
    body: JobCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> MarketingJob:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(MarketingJob.id).where(
            MarketingJob.workspace_id == workspace_id, MarketingJob.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="job name already exists")
    job = MarketingJob(
        id=new_id(), workspace_id=workspace_id, name=body.name, job_type=body.job_type,
        interval_minutes=body.interval_minutes, enabled=body.enabled,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(job)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CAMPAIGN_CREATED,
        entity_id=job.id, payload={"job_created": True, "job_type": job.job_type},
        actor_id=principal.user.id,
    )
    db.commit()
    return job


@router.get("/jobs/list", response_model=list[JobOut])
def list_marketing_jobs(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[MarketingJob]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(MarketingJob).where(MarketingJob.workspace_id == workspace_id)
        .order_by(MarketingJob.created_at.desc())
    ).scalars().all()


@router.post("/jobs/{job_id}/run", response_model=JobRunOut)
def run_marketing_job(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> JobRunOut:
    """Execute one local maintenance job and leave an observable run record."""
    verify_workspace(principal, workspace_id)
    job = _job_or_404(db, workspace_id, job_id)
    if not job.enabled:
        raise HTTPException(status_code=409, detail="job is disabled")
    started = now()
    details: dict = {}
    if job.job_type == "activate_due_campaigns":
        activated = activate_due_campaigns(workspace_id=workspace_id, principal=principal, db=db)
        details = {"activated": sum(1 for row in activated if row.status == "active")}
    elif job.job_type == "metrics_rollup":
        totals = db.execute(
            select(
                func.count(CampaignMetric.id),
                func.coalesce(func.sum(CampaignMetric.impressions), 0),
                func.coalesce(func.sum(CampaignMetric.clicks), 0),
                func.coalesce(func.sum(CampaignMetric.leads), 0),
            ).where(CampaignMetric.workspace_id == workspace_id)
        ).one()
        details = {
            "metric_days": int(totals[0]), "impressions": int(totals[1]),
            "clicks": int(totals[2]), "leads": int(totals[3]),
        }
    else:  # enrollment_cleanup
        current = now()
        enrollments = db.execute(
            select(CampaignEnrollment, Campaign.end_at).join(
                Campaign, Campaign.id == CampaignEnrollment.campaign_id
            ).where(
                CampaignEnrollment.workspace_id == workspace_id,
                CampaignEnrollment.status == "active",
                Campaign.end_at.is_not(None),
                Campaign.end_at < current,
            )
        ).all()
        closed = 0
        for enrollment, end_at in enrollments:
            _finish_enrollment(db, workspace_id, enrollment.campaign_id, enrollment, "window_ended", principal.user.id)
            closed += 1
        details = {"closed": closed}
        db.commit()
    run = MarketingJobRun(
        id=new_id(), workspace_id=workspace_id, job_id=job.id, status="completed",
        details=details, started_at=started, finished_at=now(),
    )
    db.add(run)
    job.last_run_at = started
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=MARKETING_JOB_COMPLETED,
        entity_id=run.id, payload={"job_id": job.id, "job_type": job.job_type, "details": details},
        actor_id=principal.user.id,
    )
    db.commit()
    return JobRunOut(
        run_id=run.id, job_id=job.id, status=run.status, details=details,
        started_at=run.started_at, finished_at=run.finished_at,
    )


@router.get("/jobs/{job_id}/runs")
def list_marketing_job_runs(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _job_or_404(db, workspace_id, job_id)
    runs = db.execute(
        select(MarketingJobRun).where(
            MarketingJobRun.workspace_id == workspace_id, MarketingJobRun.job_id == job_id
        ).order_by(MarketingJobRun.started_at)
    ).scalars().all()
    return [
        {"id": run.id, "status": run.status, "details": run.details,
         "started_at": run.started_at, "finished_at": run.finished_at}
        for run in runs
    ]


# ---------------------------------------------------------------------------
# MT-117 — funnel, engagement and attribution computed from local events
# ---------------------------------------------------------------------------

FUNNEL_STAGES = (
    FORM_SUBMITTED, CAMPAIGN_ENTERED, EMAIL_SENT, EMAIL_OPENED, EMAIL_CLICKED, CAMPAIGN_EXITED,
)


def _event_contact_id(event: Event) -> str | None:
    payload = event.payload or {}
    value = payload.get("contact_id") if isinstance(payload, dict) else None
    return str(value) if value else event.entity_id


def _event_campaign_id(event: Event) -> str | None:
    payload = event.payload or {}
    value = payload.get("campaign_id") if isinstance(payload, dict) else None
    return str(value) if value else None


def _as_comparable(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


@router.get("/analytics/funnel")
def marketing_funnel(
    workspace_id: str,
    campaign_id: str | None = Query(None),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if campaign_id is not None:
        _campaign_or_404(db, workspace_id, campaign_id)
    events = db.execute(
        select(Event).where(
            Event.workspace_id == workspace_id, Event.event_type.in_(FUNNEL_STAGES)
        ).order_by(Event.occurred_at)
    ).scalars().all()
    # A form submission happens before campaign entry and therefore carries no
    # campaign_id in its payload. When a campaign is selected, attribute only
    # form submissions from contacts with a real local enrollment in that
    # campaign, and only those recorded no later than the entry event.
    entry_times: dict[str, datetime] = {}
    if campaign_id is not None:
        enrollments = db.execute(
            select(CampaignEnrollment.contact_id, CampaignEnrollment.entered_at).where(
                CampaignEnrollment.workspace_id == workspace_id,
                CampaignEnrollment.campaign_id == campaign_id,
            )
        ).all()
        entry_times = {
            contact_id: _as_comparable(entered_at)
            for contact_id, entered_at in enrollments
            if contact_id and entered_at
        }
    selected = []
    for event in events:
        if campaign_id is None or _event_campaign_id(event) == campaign_id:
            selected.append(event)
        elif event.event_type == FORM_SUBMITTED:
            contact = _event_contact_id(event)
            entered_at = entry_times.get(contact) if contact else None
            if entered_at is not None and _as_comparable(event.occurred_at) <= entered_at:
                selected.append(event)
    stages = {
        name: len({cid for event in selected if event.event_type == name
                   and (cid := _event_contact_id(event))})
        for name in FUNNEL_STAGES
    }
    entered = stages[CAMPAIGN_ENTERED]
    return {
        "campaign_id": campaign_id,
        "stages": stages,
        "entry_to_sent_rate": round(stages[EMAIL_SENT] / entered, 4) if entered else 0.0,
        "sent_to_opened_rate": round(stages[EMAIL_OPENED] / stages[EMAIL_SENT], 4) if stages[EMAIL_SENT] else 0.0,
        "opened_to_clicked_rate": round(stages[EMAIL_CLICKED] / stages[EMAIL_OPENED], 4) if stages[EMAIL_OPENED] else 0.0,
        "source": "local_events",
    }


@router.get("/analytics/engagement")
def marketing_engagement(
    workspace_id: str,
    campaign_id: str | None = Query(None),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if campaign_id is not None:
        _campaign_or_404(db, workspace_id, campaign_id)
    kinds = (EMAIL_SENT, EMAIL_OPENED, EMAIL_CLICKED)
    events = db.execute(
        select(Event).where(
            Event.workspace_id == workspace_id, Event.event_type.in_(kinds)
        )
    ).scalars().all()
    grouped: dict[str, dict[str, set[str]]] = {}
    for event in events:
        cid = _event_campaign_id(event)
        if cid is None or (campaign_id is not None and cid != campaign_id):
            continue
        contact = _event_contact_id(event)
        if contact is None:
            continue
        grouped.setdefault(cid, {kind: set() for kind in kinds})[event.event_type].add(contact)
    rows = []
    for cid, by_kind in sorted(grouped.items()):
        sent, opened, clicked = (len(by_kind[kind]) for kind in kinds)
        rows.append({
            "campaign_id": cid, "sent": sent, "opened": opened, "clicked": clicked,
            "open_rate": round(opened / sent, 4) if sent else 0.0,
            "click_rate": round(clicked / sent, 4) if sent else 0.0,
        })
    return {"campaign_id": campaign_id, "rows": rows, "source": "local_events"}


@router.get("/analytics/attribution")
def marketing_attribution(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    events = db.execute(
        select(Event).where(
            Event.workspace_id == workspace_id,
            Event.event_type.in_((FORM_SUBMITTED, CAMPAIGN_ENTERED, EMAIL_CLICKED)),
        ).order_by(Event.occurred_at)
    ).scalars().all()
    entries: list[tuple[datetime, str]] = []
    entered: list[tuple[datetime, str]] = []
    clicked: list[tuple[datetime, str]] = []
    for event in events:
        contact = _event_contact_id(event)
        if contact is None:
            continue
        moment = _as_comparable(event.occurred_at)
        if event.event_type == FORM_SUBMITTED:
            source = (event.payload or {}).get("source")
            if isinstance(source, str) and source.strip():
                entries.append((moment, f"{contact}|{source}"))
        elif event.event_type == CAMPAIGN_ENTERED:
            entered.append((moment, contact))
        else:
            clicked.append((moment, contact))
    grouped: dict[str, dict[str, int | set[str]]] = {}
    for moment, key in entries:
        contact, source = key.split("|", 1)
        group = grouped.setdefault(source, {
            "submissions": 0, "contacts": set(), "entered": 0, "clicked": 0,
        })
        group["submissions"] += 1
        group["contacts"].add(contact)
        group["entered"] += sum(
            1 for tm, who in entered if who == contact and tm >= moment
        )
        group["clicked"] += sum(
            1 for tm, who in clicked if who == contact and tm >= moment
        )
    rows = [
        {
            "source": source, "submissions": group["submissions"],
            "contacts": len(group["contacts"]), "entered": group["entered"],
            "clicked": group["clicked"],
        }
        for source, group in sorted(grouped.items())
    ]
    return {"rows": rows, "source": "local_events"}


# FastAPI matches routes in declaration order. Literal single-segment routes
# (e.g. /segments, /email-templates) must be considered before the /{campaign_id}
# catch-all, otherwise a collection URL is mistaken for a campaign id.
router.routes.sort(key=lambda route: getattr(route, 'path', '').count('{'))
