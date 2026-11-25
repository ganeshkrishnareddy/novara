"""Clean-room support reporting and CSAT governance (Chatwoot P2 cluster).

This module closes CW-096/097/098/099/101/104/114/117 with real, local,
workspace-scoped behaviour. Report rows are derived from the persisted support
tickets, messages, labels and audit events owned by the existing ``support``
module. CSAT rules, one-time response tokens and responses are new additive
tables. No Chatwoot source, Rails bundle, hosted service, outbound HTTP,
webhook callback or real message delivery is used.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import WorkspaceMember, new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE
from ..security import hash_token, new_raw_token
from . import support

REPORT_GENERATED = "support.report_generated"
REPORT_EXPORTED = "support.report_exported"
CSAT_RULE_CREATED = "support.csat_rule_created"
CSAT_TOKEN_ISSUED = "support.csat_response_token_issued"
CSAT_RESPONSE_RECORDED = "support.csat_response_recorded"

register_event_types(
    REPORT_GENERATED, REPORT_EXPORTED, CSAT_RULE_CREATED,
    CSAT_TOKEN_ISSUED, CSAT_RESPONSE_RECORDED,
)

SUPPORT_PREFIX = "/api/v1/workspaces/{workspace_id}/tickets"
REPORT_PREFIX = "/api/v1/workspaces/{workspace_id}/support-reporting"
PUBLIC_PREFIX = "/api/v1/public/support-surveys"

router = APIRouter(prefix=REPORT_PREFIX, tags=["support-reporting"])
public_router = APIRouter(prefix=PUBLIC_PREFIX, tags=["support-reporting"])

DIMENSIONS = ("agents", "teams", "inboxes", "labels")
MAX_RESPONSE_ATTEMPTS = 3
TOKEN_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Additive tables
# ---------------------------------------------------------------------------


class SupportReportRun(Base):
    __tablename__ = "support_report_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CsatSurveyRule(Base):
    __tablename__ = "support_csat_survey_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_csat_rule_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    include_labels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclude_labels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CsatResponseToken(Base):
    __tablename__ = "support_csat_response_tokens"
    __table_args__ = (UniqueConstraint("workspace_id", "token_hash", name="uq_csat_token_workspace_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("support_csat_surveys.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CsatResponse(Base):
    __tablename__ = "support_csat_responses"
    __table_args__ = (UniqueConstraint("token_id", name="uq_csat_response_token"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("support_csat_surveys.id"), nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(ForeignKey("support_csat_response_tokens.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CsatRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    include_labels: list[str] = Field(default_factory=list)
    exclude_labels: list[str] = Field(default_factory=list)
    enabled: bool = True
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("rule name must not be empty")
        return stripped


class CsatRuleOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    include_labels: list[str]
    exclude_labels: list[str]
    enabled: bool
    created_at: object
    model_config = ConfigDict(from_attributes=True)


class ReportRunCreate(BaseModel):
    dimension: Literal["agents", "teams", "inboxes", "labels"]
    status: str | None = None
    priority: str | None = None
    assignee_id: str | None = None
    team_id: str | None = None
    inbox_id: str | None = None
    label_id: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    model_config = ConfigDict(extra="forbid")


class ReportRunOut(BaseModel):
    id: str
    dimension: str
    filters: dict[str, Any]
    summary: dict[str, Any]
    created_at: object
    model_config = ConfigDict(from_attributes=True)


class CsatTokenOut(BaseModel):
    token: str
    survey_id: str
    ticket_id: str
    expires_at: object
    delivery: str = "local-token-only"
    external_calls: bool = False


class CsatSubmitIn(BaseModel):
    score: int
    comment: str | None = Field(default=None, max_length=2000)
    model_config = ConfigDict(extra="forbid")


class CsatSubmitOut(BaseModel):
    response_id: str
    ticket_id: str
    survey_id: str
    score: int
    external_delivery: bool = False
    replay_protected: bool = True


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _row_or_404(db: Session, model, workspace_id: str, row_id: str, detail: str):
    row = db.execute(
        select(model).where(model.id == row_id, model.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=detail)
    return row


def _label_ids(db: Session, workspace_id: str, ticket_id: str) -> set[str]:
    return set(db.execute(
        select(support.TicketLabel.label_id).where(
            support.TicketLabel.workspace_id == workspace_id,
            support.TicketLabel.ticket_id == ticket_id,
        )
    ).scalars().all())


def _csat_rule_allows(db: Session, workspace_id: str, ticket: support.Ticket) -> tuple[bool, str]:
    """Evaluate enabled local rules; with no rules the original behaviour holds."""
    rules = db.execute(
        select(CsatSurveyRule).where(
            CsatSurveyRule.workspace_id == workspace_id,
            CsatSurveyRule.enabled.is_(True),
        ).order_by(CsatSurveyRule.created_at)
    ).scalars().all()
    if not rules:
        return True, "no_rules"
    label_ids = _label_ids(db, workspace_id, ticket.id)
    labels = set(db.execute(
        select(support.SupportLabel.name).where(
            support.SupportLabel.workspace_id == workspace_id,
            support.SupportLabel.id.in_(label_ids),
        )
    ).scalars().all()) if label_ids else set()
    for rule in rules:
        include = set(rule.include_labels or [])
        exclude = set(rule.exclude_labels or [])
        if exclude & labels:
            continue
        if include and not (include & labels):
            continue
        return True, rule.name
    return False, "no enabled rule matched this resolution"


support.register_csat_rule_evaluator(_csat_rule_allows)


def _validate_filters(
    db: Session,
    workspace_id: str,
    principal: Principal,
    *,
    status_value: str | None,
    priority: str | None,
    assignee_id: str | None,
    team_id: str | None,
    inbox_id: str | None,
    label_id: str | None,
    created_from: str | None,
    created_to: str | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "status": status_value, "priority": priority, "assignee_id": assignee_id,
        "team_id": team_id, "inbox_id": inbox_id, "label_id": label_id,
        "created_from": created_from, "created_to": created_to,
    }
    if status_value is not None and status_value not in support.TICKET_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status filter")
    if priority is not None and priority not in support.TICKET_PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid priority filter")
    start, end = support._report_range(created_from, created_to)
    if assignee_id is not None:
        member = db.execute(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == assignee_id,
                WorkspaceMember.status == "active",
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(status_code=422, detail="invalid assignee filter")
    if team_id is not None:
        _row_or_404(db, support.SupportTeam, workspace_id, team_id, "team not found")
    if label_id is not None:
        _row_or_404(db, support.SupportLabel, workspace_id, label_id, "label not found")
    if inbox_id is not None:
        inbox = _row_or_404(db, support.SupportInbox, workspace_id, inbox_id, "inbox not found")
        if not support._inbox_is_permitted(db, principal, inbox):
            raise HTTPException(status_code=403, detail="not a member of this inbox")
    filters["_start"] = start
    filters["_end"] = end
    return filters


def _filtered_tickets(db: Session, workspace_id: str, filters: dict[str, Any]) -> list[support.Ticket]:
    query = select(support.Ticket).where(support.Ticket.workspace_id == workspace_id)
    if filters["status"]:
        query = query.where(support.Ticket.status == filters["status"])
    if filters["priority"]:
        query = query.where(support.Ticket.priority == filters["priority"])
    if filters["assignee_id"]:
        query = query.where(support.Ticket.assignee_id == filters["assignee_id"])
    if filters["team_id"]:
        query = query.where(support.Ticket.team_id == filters["team_id"])
    if filters["inbox_id"]:
        query = query.where(support.Ticket.inbox_id == filters["inbox_id"])
    if filters["label_id"]:
        query = query.where(support.Ticket.id.in_(select(
            support.TicketLabel.ticket_id
        ).where(
            support.TicketLabel.workspace_id == workspace_id,
            support.TicketLabel.label_id == filters["label_id"],
        )))
    if filters["_start"]:
        query = query.where(support.Ticket.created_at >= filters["_start"])
    if filters["_end"]:
        query = query.where(support.Ticket.created_at <= filters["_end"])
    return db.execute(query.order_by(support.Ticket.created_at, support.Ticket.id)).scalars().all()


def _response_minutes(db: Session, workspace_id: str, tickets: list[support.Ticket]) -> dict[str, float | None]:
    ticket_ids = {ticket.id for ticket in tickets}
    messages = db.execute(
        select(support.TicketMessage).where(
            support.TicketMessage.workspace_id == workspace_id,
            support.TicketMessage.ticket_id.in_(ticket_ids),
            support.TicketMessage.direction == "outbound",
        )
    ).scalars().all()
    first: dict[str, datetime] = {}
    for message in messages:
        current = first.get(message.ticket_id)
        if current is None or message.created_at < current:
            first[message.ticket_id] = message.created_at
    result: dict[str, float | None] = {}
    for ticket in tickets:
        sent = first.get(ticket.id)
        result[ticket.id] = support._minutes_between(ticket.created_at, sent) if sent else None
    return result


def _build_report(
    db: Session,
    workspace_id: str,
    dimension: str,
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, float | None]:
    if dimension not in DIMENSIONS:
        raise HTTPException(status_code=422, detail="invalid report dimension")
    tickets = _filtered_tickets(db, workspace_id, filters)
    responses = _response_minutes(db, workspace_id, tickets)
    labels = {
        row.id: row.name for row in db.execute(
            select(support.SupportLabel).where(support.SupportLabel.workspace_id == workspace_id)
        ).scalars().all()
    }
    grouped: dict[str, list[support.Ticket]] = {}
    if dimension == "labels":
        links = db.execute(
            select(support.TicketLabel).where(
                support.TicketLabel.workspace_id == workspace_id,
                support.TicketLabel.ticket_id.in_({t.id for t in tickets}),
            )
        ).scalars().all()
        by_ticket: dict[str, list[str]] = {}
        for link in links:
            by_ticket.setdefault(link.ticket_id, []).append(link.label_id)
        for ticket in tickets:
            for label_id in by_ticket.get(ticket.id, []):
                grouped.setdefault(label_id, []).append(ticket)
    else:
        attribute = {
            "agents": "assignee_id", "teams": "team_id", "inboxes": "inbox_id",
        }[dimension]
        for ticket in tickets:
            key = getattr(ticket, attribute)
            if key is not None:
                grouped.setdefault(key, []).append(ticket)

    rows: list[dict[str, Any]] = []
    # A ticket-level filter is a reported population, not a row to keep when
    # that ticket has no matching label. This keeps a label_id filter honest.
    if filters.get("label_id") and dimension == "labels":
        wanted = {filters["label_id"]}
        grouped = {key: group for key, group in grouped.items() if key in wanted}
    for key, group in grouped.items():
        samples = [responses[t.id] for t in group if responses.get(t.id) is not None]
        rows.append({
            "key": key,
            "name": labels.get(key, "") if dimension == "labels" else key,
            "tickets": len(group),
            "resolved": sum(1 for t in group if t.status in ("resolved", "closed")),
            "avg_first_response_minutes": round(sum(samples) / len(samples), 2) if samples else None,
        })
    rows.sort(key=lambda row: (-row["tickets"], str(row["key"])))
    total = sum(row["tickets"] for row in rows)
    all_samples = [value for value in responses.values() if value is not None]
    overall = round(sum(all_samples) / len(all_samples), 2) if all_samples else None
    return rows, total, overall


def _query_filters(
    status: str | None, priority: str | None, assignee_id: str | None,
    team_id: str | None, inbox_id: str | None, label_id: str | None,
    created_from: str | None, created_to: str | None,
) -> dict[str, Any]:
    return {
        "status": status, "priority": priority, "assignee_id": assignee_id,
        "team_id": team_id, "inbox_id": inbox_id, "label_id": label_id,
        "created_from": created_from, "created_to": created_to,
    }


def _report_response(rows, tickets_count, overall) -> dict[str, Any]:
    return {
        "rows": rows,
        "tickets_count": tickets_count,
        "avg_first_response_minutes": overall,
        "source": "persisted_local_support_rows",
        "external_calls": False,
    }


# ---------------------------------------------------------------------------
# Report endpoints — CW-096/097/098/099
# ---------------------------------------------------------------------------


@router.get("/reports/agents")
def agent_report(
    workspace_id: str,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    team_id: str | None = None,
    inbox_id: str | None = None,
    label_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    filters = _validate_filters(
        db, workspace_id, principal, status_value=status, priority=priority,
        assignee_id=assignee_id, team_id=team_id, inbox_id=inbox_id,
        label_id=label_id, created_from=created_from, created_to=created_to,
    )
    rows, total, overall = _build_report(db, workspace_id, "agents", filters)
    return _report_response(rows, total, overall)


@router.get("/reports/teams")
def team_report(
    workspace_id: str,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    team_id: str | None = None,
    inbox_id: str | None = None,
    label_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    filters = _validate_filters(
        db, workspace_id, principal, status_value=status, priority=priority,
        assignee_id=assignee_id, team_id=team_id, inbox_id=inbox_id,
        label_id=label_id, created_from=created_from, created_to=created_to,
    )
    rows, total, overall = _build_report(db, workspace_id, "teams", filters)
    return _report_response(rows, total, overall)


@router.get("/reports/inboxes")
def inbox_report(
    workspace_id: str,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    team_id: str | None = None,
    inbox_id: str | None = None,
    label_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    filters = _validate_filters(
        db, workspace_id, principal, status_value=status, priority=priority,
        assignee_id=assignee_id, team_id=team_id, inbox_id=inbox_id,
        label_id=label_id, created_from=created_from, created_to=created_to,
    )
    rows, total, overall = _build_report(db, workspace_id, "inboxes", filters)
    return _report_response(rows, total, overall)


@router.get("/reports/labels")
def label_report(
    workspace_id: str,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    team_id: str | None = None,
    inbox_id: str | None = None,
    label_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    filters = _validate_filters(
        db, workspace_id, principal, status_value=status, priority=priority,
        assignee_id=assignee_id, team_id=team_id, inbox_id=inbox_id,
        label_id=label_id, created_from=created_from, created_to=created_to,
    )
    rows, total, overall = _build_report(db, workspace_id, "labels", filters)
    return _report_response(rows, total, overall)


@router.get("/reports/export")
def export_report(
    workspace_id: str,
    dimension: Literal["agents", "teams", "inboxes", "labels"] = "agents",
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    team_id: str | None = None,
    inbox_id: str | None = None,
    label_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    verify_workspace(principal, workspace_id)
    filters = _validate_filters(
        db, workspace_id, principal, status_value=status, priority=priority,
        assignee_id=assignee_id, team_id=team_id, inbox_id=inbox_id,
        label_id=label_id, created_from=created_from, created_to=created_to,
    )
    rows, _total, _overall = _build_report(db, workspace_id, dimension, filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["key", "name", "tickets", "resolved", "avg_first_response_minutes"])
    for row in rows:
        writer.writerow([
            row["key"], row["name"], row["tickets"], row["resolved"],
            "" if row["avg_first_response_minutes"] is None else row["avg_first_response_minutes"],
        ])
    publish_event(
        db, workspace_id=workspace_id, event_type=REPORT_EXPORTED,
        entity_id=f"{dimension}:{workspace_id}", payload={
            "dimension": dimension, "filters": {
                k: v for k, v in filters.items() if not k.startswith("_")
            },
            "rows": len(rows), "external_delivery": False,
        }, actor_id=principal.user.id,
    )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="support-{dimension}.csv"'},
    )


@router.post("/reports/runs", response_model=ReportRunOut, status_code=status.HTTP_201_CREATED)
def save_report_run(
    workspace_id: str,
    body: ReportRunCreate,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> ReportRun:
    verify_workspace(principal, workspace_id)
    raw_filters = _query_filters(
        body.status, body.priority, body.assignee_id, body.team_id, body.inbox_id,
        body.label_id, body.created_from, body.created_to,
    )
    filters = _validate_filters(
        db, workspace_id, principal, status_value=body.status, priority=body.priority,
        assignee_id=body.assignee_id, team_id=body.team_id, inbox_id=body.inbox_id,
        label_id=body.label_id, created_from=body.created_from, created_to=body.created_to,
    )
    rows, total, overall = _build_report(db, workspace_id, body.dimension, filters)
    run = SupportReportRun(
        id=new_id(), workspace_id=workspace_id, dimension=body.dimension,
        filters=raw_filters,
        summary={"rows": rows, "tickets_count": total, "avg_first_response_minutes": overall},
        created_by=principal.user.id, created_at=now(),
    )
    db.add(run)
    publish_event(
        db, workspace_id=workspace_id, event_type=REPORT_GENERATED,
        entity_id=run.id, payload={
            "dimension": body.dimension, "rows": len(rows), "tickets_count": total,
        }, actor_id=principal.user.id,
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/reports/runs", response_model=list[ReportRunOut])
def list_report_runs(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SupportReportRun]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SupportReportRun).where(
            SupportReportRun.workspace_id == workspace_id
        ).order_by(SupportReportRun.created_at.desc())
    ).scalars().all()


# ---------------------------------------------------------------------------
# CSAT rules — CW-104
# ---------------------------------------------------------------------------


@router.post("/csat-rules", response_model=CsatRuleOut, status_code=status.HTTP_201_CREATED)
def create_csat_rule(
    workspace_id: str,
    body: CsatRuleCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> CsatSurveyRule:
    verify_workspace(principal, workspace_id)
    existing = db.execute(
        select(CsatSurveyRule.id).where(
            CsatSurveyRule.workspace_id == workspace_id,
            CsatSurveyRule.name == body.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="rule name already exists")
    names = {row.name for row in db.execute(
        select(support.SupportLabel).where(support.SupportLabel.workspace_id == workspace_id)
    ).scalars().all()}
    for label in body.include_labels + body.exclude_labels:
        if label not in names:
            raise HTTPException(status_code=422, detail=f"unknown label: {label}")
    if set(body.include_labels) & set(body.exclude_labels):
        raise HTTPException(status_code=422, detail="a label cannot be included and excluded")
    rule = CsatSurveyRule(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        include_labels=body.include_labels, exclude_labels=body.exclude_labels,
        enabled=body.enabled, created_by=principal.user.id, created_at=now(),
    )
    db.add(rule)
    publish_event(
        db, workspace_id=workspace_id, event_type=CSAT_RULE_CREATED,
        entity_id=rule.id, payload={
            "name": rule.name, "include_labels": rule.include_labels,
            "exclude_labels": rule.exclude_labels, "enabled": rule.enabled,
            "external_delivery": False,
        }, actor_id=principal.user.id,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/csat-rules", response_model=list[CsatRuleOut])
def list_csat_rules(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CsatSurveyRule]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(CsatSurveyRule).where(
            CsatSurveyRule.workspace_id == workspace_id
        ).order_by(CsatSurveyRule.created_at)
    ).scalars().all()


# ---------------------------------------------------------------------------
# One-time survey responses — CW-114
# ---------------------------------------------------------------------------


@router.post("/csat-surveys/{survey_id}/response-token", response_model=CsatTokenOut,
             status_code=status.HTTP_201_CREATED)
def issue_response_token(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    survey = _row_or_404(db, support.CsatSurvey, workspace_id, survey_id, "survey not found")
    raw = new_raw_token()
    expires = now() + timedelta(days=TOKEN_TTL_DAYS)
    token = CsatResponseToken(
        id=new_id(), workspace_id=workspace_id, survey_id=survey.id,
        ticket_id=survey.ticket_id, token_hash=hash_token(raw), attempts=0,
        created_at=now(), expires_at=expires,
    )
    db.add(token)
    publish_event(
        db, workspace_id=workspace_id, event_type=CSAT_TOKEN_ISSUED,
        entity_id=token.id, correlation_id=survey.ticket_id, payload={
            "survey_id": survey.id, "ticket_id": survey.ticket_id,
            "token_disclosed": False, "external_delivery": False,
        }, actor_id=principal.user.id,
    )
    db.commit()
    return {
        "token": raw, "survey_id": survey.id, "ticket_id": survey.ticket_id,
        "expires_at": expires, "delivery": "local-token-only", "external_calls": False,
    }


@public_router.post("/workspaces/{workspace_id}/responses/{token}", response_model=CsatSubmitOut)
def submit_csat_response(
    workspace_id: str,
    token: str,
    body: CsatSubmitIn,
    db: Session = Depends(get_db),
) -> dict:
    """Redeem one opaque, high-entropy token. No bearer token is required; the
    workspace id in the path and the stored hash keep the action scoped."""
    record = db.execute(
        select(CsatResponseToken).where(
            CsatResponseToken.workspace_id == workspace_id,
            CsatResponseToken.token_hash == hash_token(token),
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="unknown response token")
    existing = db.execute(
        select(CsatResponse.id).where(CsatResponse.token_id == record.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="response token already used")
    if support._naive(record.expires_at) < support._naive(now()):
        raise HTTPException(status_code=410, detail="response token expired")
    if record.attempts >= MAX_RESPONSE_ATTEMPTS:
        raise HTTPException(status_code=429, detail="response token rate limit reached")
    if body.score < 1 or body.score > 5:
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=422, detail="score must be 1-5")
    response = CsatResponse(
        id=new_id(), workspace_id=workspace_id, ticket_id=record.ticket_id,
        survey_id=record.survey_id, token_id=record.id, score=body.score,
        comment=body.comment, created_at=now(),
    )
    record.attempts += 1
    db.add(response)
    survey = db.get(support.CsatSurvey, record.survey_id)
    if survey is not None and survey.workspace_id == workspace_id:
        survey.status = "completed"
    publish_event(
        db, workspace_id=workspace_id, event_type=CSAT_RESPONSE_RECORDED,
        entity_id=response.id, correlation_id=record.ticket_id, payload={
            "ticket_id": record.ticket_id, "survey_id": record.survey_id,
            "score": body.score, "external_delivery": False,
        },
    )
    db.commit()
    return {
        "response_id": response.id, "ticket_id": record.ticket_id,
        "survey_id": record.survey_id, "score": body.score,
        "external_delivery": False, "replay_protected": True,
    }


@router.get("/csat-responses", response_model=list[dict])
def list_csat_responses(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(CsatResponse, support.Csatscore).outerjoin(
            support.Csatscore, support.Csatscore.ticket_id == CsatResponse.ticket_id
        ).where(CsatResponse.workspace_id == workspace_id)
    ).all()
    return [{
        "id": response.id, "ticket_id": response.ticket_id,
        "survey_id": response.survey_id, "score": response.score,
        "comment": response.comment, "created_at": response.created_at,
    } for response, _legacy in rows]


# ---------------------------------------------------------------------------
# Generated local OpenAPI contract — CW-117
# ---------------------------------------------------------------------------


@router.get("/api-contract")
def support_api_contract(request: Request) -> dict:
    """Derive a 3.1 contract from the live app instead of a checked-in snapshot."""
    schema = request.app.openapi()
    prefixes = (SUPPORT_PREFIX, REPORT_PREFIX, PUBLIC_PREFIX)
    routes: list[dict[str, Any]] = []
    for path, operations in sorted(schema.get("paths", {}).items()):
        if not path.startswith(prefixes):
            continue
        methods = [method.upper() for method in operations if method.lower() in
                   ("get", "post", "patch", "put", "delete")]
        security = []
        for method in methods:
            operation = operations.get(method.lower()) or {}
            security.append({
                "method": method,
                "security": operation.get("security", []),
                "parameters": len(operation.get("parameters", [])),
            })
        routes.append({"path": path, "methods": sorted(methods), "operations": security})
    return {
        "openapi": schema.get("openapi", "3.1.0"),
        "generated_from": "live FastAPI application",
        "support_routes": routes,
        "route_count": len(routes),
        "delivery": "local-only",
        "external_calls": False,
        "external_delivery": False,
    }
