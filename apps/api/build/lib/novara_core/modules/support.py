"""Customer support module: workspace-scoped tickets and their messages.

Module-owned tables, a single APIRouter and all mutations that write through
publish_event() with the verified actor id. No external delivery is performed.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    and_, func, or_, select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import NOTE_CREATED, publish_event, register_event_types
from ..models import Contact, Event, Note, User, Workspace, WorkspaceMember, new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

TICKET_CREATED = "ticket.created"
TICKET_STATUS_CHANGED = "ticket.status_changed"
TICKET_MESSAGE_ADDED = "ticket.message_added"
TICKET_UPDATED = "ticket.updated"
TICKET_ASSIGNED = "ticket.assigned"
TICKET_CONTACT_IDENTIFIED = "ticket.contact_identified"
# P1 additions. Every name is registered here rather than in the shared events
# module so module ownership stays clean.
TICKET_CONTACT_LINKED = "ticket.contact_linked"
TICKET_TEAM_ASSIGNED = "ticket.team_assigned"
TICKET_AUTO_ASSIGNED = "ticket.auto_assigned"
TICKET_LABELED = "ticket.labeled"
TICKET_UNLABELED = "ticket.unlabeled"
TEAM_CREATED = "support.team_created"
TEAM_MEMBER_ADDED = "support.team_member_added"
ROUTING_RULE_CREATED = "support.routing_rule_created"
LABEL_CREATED = "support.label_created"
ATTRIBUTE_CREATED = "support.attribute_created"
ATTRIBUTE_SET = "support.attribute_set"
SAVED_REPLY_EXPANDED = "support.saved_reply_expanded"
MACRO_DRY_RUN = "support.macro_dry_run"
MACRO_APPLIED = "support.macro_applied"
INBOX_CREATED = "support.inbox_created"
INBOX_AGENT_ADDED = "support.inbox_agent_added"
CONVERSATION_RULE_CREATED = "support.conversation_rule_created"
CONVERSATION_RULE_DRY_RUN = "support.conversation_rule_dry_run"
CONVERSATION_RULE_RAN = "support.conversation_rule_ran"
SEGMENT_CREATED = "support.segment_created"
HELP_PORTAL_CREATED = "support.help_portal_created"
HELP_ARTICLE_WRITTEN = "support.help_article_written"
CSAT_SURVEY_CREATED = "support.csat_survey_created"

# Additive extension point for the clean-room CSAT rule engine. A module may
# register a predicate that returns (allowed, reason); when none is registered
# the original local survey behaviour is unchanged.
_CSAT_RULE_EVALUATOR = None


def register_csat_rule_evaluator(evaluator) -> None:
    """Register one workspace-safe CSAT eligibility predicate."""
    global _CSAT_RULE_EVALUATOR
    _CSAT_RULE_EVALUATOR = evaluator


register_event_types(
    TICKET_CREATED, TICKET_STATUS_CHANGED, TICKET_MESSAGE_ADDED, TICKET_UPDATED,
    TICKET_ASSIGNED, TICKET_CONTACT_IDENTIFIED, TICKET_CONTACT_LINKED,
    TICKET_TEAM_ASSIGNED, TICKET_AUTO_ASSIGNED, TICKET_LABELED, TICKET_UNLABELED,
    TEAM_CREATED, TEAM_MEMBER_ADDED, ROUTING_RULE_CREATED, LABEL_CREATED,
    ATTRIBUTE_CREATED, ATTRIBUTE_SET, SAVED_REPLY_EXPANDED, MACRO_DRY_RUN,
    MACRO_APPLIED, INBOX_CREATED, INBOX_AGENT_ADDED, CONVERSATION_RULE_CREATED,
    CONVERSATION_RULE_DRY_RUN, CONVERSATION_RULE_RAN, SEGMENT_CREATED, HELP_PORTAL_CREATED,
    HELP_ARTICLE_WRITTEN, CSAT_SURVEY_CREATED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/tickets",
    tags=["support"],
)

TICKET_STATUSES = ("open", "pending", "resolved", "closed")
TICKET_PRIORITIES = ("low", "normal", "high", "urgent")
TICKET_ORIGINS = ("local", "web_form", "email", "import")
TICKET_CONVERSATION_TYPES = ("question", "incident", "billing", "feedback")
TICKET_DIRECTIONS = ("inbound", "outbound")
TICKET_REASONS = ("customer_reply", "resolved", "escalated", "awaiting_customer", "reopened")

TicketStatus = Literal["open", "pending", "resolved", "closed"]
TicketPriority = Literal["low", "normal", "high", "urgent"]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Ticket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    origin_channel: Mapped[str] = mapped_column(String(40), default="local", nullable=False)
    conversation_type: Mapped[str] = mapped_column(String(40), default="question", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String(36))
    team_id: Mapped[str | None] = mapped_column(String(36))
    inbox_id: Mapped[str | None] = mapped_column(String(36))
    sla_policy_id: Mapped[str | None] = mapped_column(String(36))
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("support_tickets.id"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="outbound", nullable=False)
    channel: Mapped[str] = mapped_column(String(40), default="local", nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketInternalNote(Base):
    __tablename__ = "ticket_internal_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("support_tickets.id"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Saved replies / canned responses
# ---------------------------------------------------------------------------


class SavedReply(Base):
    __tablename__ = "saved_replies"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_saved_reply"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Macros
# ---------------------------------------------------------------------------


class Macro(Base):
    __tablename__ = "macros"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_macro"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    actions: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# SLA policies
# ---------------------------------------------------------------------------


class SlaPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_sla"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_response_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Business hours
# ---------------------------------------------------------------------------


class BusinessHours(Base):
    __tablename__ = "business_hours"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_bh"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC", nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, default=17, nullable=False)
    days: Mapped[str] = mapped_column(String(40), default="1,2,3,4,5", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------


class EscalationRule(Base):
    __tablename__ = "escalation_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_esc"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    condition: Mapped[str] = mapped_column(String(100), default="sla_breach", nullable=False)
    action: Mapped[str] = mapped_column(String(100), default="notify_owner", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# CSAT
# ---------------------------------------------------------------------------


class Csatscore(Base):
    __tablename__ = "csat_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# P1 tables — teams, labels, attributes, inboxes, routing, automation,
# segments, help centre and CSAT surveys. Every table is workspace-scoped.
# ---------------------------------------------------------------------------


class SupportTeam(Base):
    __tablename__ = "support_teams"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_support_team"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SupportTeamMember(Base):
    __tablename__ = "support_team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_support_team_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("support_teams.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SupportLabel(Base):
    __tablename__ = "support_labels"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_support_label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#3B82F6", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketLabel(Base):
    __tablename__ = "ticket_labels"
    __table_args__ = (UniqueConstraint("ticket_id", "label_id", name="uq_ticket_label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(ForeignKey("support_labels.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomAttribute(Base):
    __tablename__ = "support_custom_attributes"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_support_attribute"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CustomAttributeValue(Base):
    __tablename__ = "support_custom_attribute_values"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "attribute_id", "entity_type", "entity_id",
            name="uq_support_attribute_value",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    attribute_id: Mapped[str] = mapped_column(
        ForeignKey("support_custom_attributes.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SupportInbox(Base):
    __tablename__ = "support_inboxes"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_support_inbox"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), default="local", nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    csat_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InboxAgent(Base):
    __tablename__ = "support_inbox_agents"
    __table_args__ = (UniqueConstraint("inbox_id", "user_id", name="uq_inbox_agent"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    inbox_id: Mapped[str] = mapped_column(ForeignKey("support_inboxes.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RoutingRule(Base):
    __tablename__ = "support_routing_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_routing_rule"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), default="any", nullable=False)
    strategy: Mapped[str] = mapped_column(String(30), default="round_robin", nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(36))
    assignee_id: Mapped[str | None] = mapped_column(String(36))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConversationRule(Base):
    __tablename__ = "support_conversation_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_conversation_rule"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger: Mapped[str] = mapped_column(String(60), nullable=False)
    actions: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConversationRuleRun(Base):
    __tablename__ = "support_conversation_rule_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("support_conversation_rules.id"), nullable=False, index=True
    )
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("support_tickets.id"), nullable=False, index=True
    )
    trigger: Mapped[str] = mapped_column(String(60), nullable=False)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContactSegment(Base):
    __tablename__ = "support_contact_segments"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_contact_segment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HelpPortal(Base):
    __tablename__ = "support_help_portals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_help_portal"),
        UniqueConstraint("workspace_id", "slug", name="uq_help_portal_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HelpArticle(Base):
    __tablename__ = "support_help_articles"
    __table_args__ = (UniqueConstraint("portal_id", "slug", name="uq_help_article_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    portal_id: Mapped[str] = mapped_column(ForeignKey("support_help_portals.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CsatSurvey(Base):
    __tablename__ = "support_csat_surveys"
    __table_args__ = (UniqueConstraint("ticket_id", name="uq_csat_survey_ticket"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TicketCreate(BaseModel):
    subject: str
    body: str
    contact_id: str | None = None
    priority: TicketPriority = "normal"
    origin_channel: str = "local"
    conversation_type: str = "question"
    assignee_id: str | None = None
    team_id: str | None = None
    inbox_id: str | None = None
    sla_policy_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("origin_channel")
    @classmethod
    def valid_origin(cls, value: str) -> str:
        if value not in TICKET_ORIGINS:
            raise ValueError("invalid conversation origin")
        return value

    @field_validator("conversation_type")
    @classmethod
    def valid_conversation_type(cls, value: str) -> str:
        if value not in TICKET_CONVERSATION_TYPES:
            raise ValueError("invalid conversation type")
        return value

    @field_validator("subject", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TicketPatch(BaseModel):
    status: TicketStatus | None = None
    status_reason: str | None = None
    priority: TicketPriority | None = None
    assignee_id: str | None = None
    team_id: str | None = None
    inbox_id: str | None = None
    sla_policy_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("status_reason")
    @classmethod
    def valid_reason(cls, value: str | None) -> str | None:
        if value is not None and value not in TICKET_REASONS:
            raise ValueError("invalid status reason")
        return value


class MessageCreate(BaseModel):
    body: str
    direction: str = "outbound"
    channel: str = "local"
    is_internal: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, value: str) -> str:
        if value not in TICKET_DIRECTIONS:
            raise ValueError("invalid message direction")
        return value

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value not in TICKET_ORIGINS:
            raise ValueError("invalid message channel")
        return value

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message body must not be empty")
        return stripped


class TicketOut(BaseModel):
    id: str
    contact_id: str | None
    subject: str
    body: str
    status: str
    priority: str
    origin_channel: str
    conversation_type: str
    assignee_id: str | None
    team_id: str | None = None
    inbox_id: str | None = None
    sla_policy_id: str | None
    first_response_due_at: object
    resolution_due_at: object
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    body: str
    direction: str
    channel: str
    is_internal: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class IdentifyRequest(BaseModel):
    """Pre-chat identity capture. Email is the stable CRM key; the existing
    contact table is the only identity store, so no subscriber duplicate exists."""

    email: str
    full_name: str | None = None
    company_name: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or value.count("@") != 1 or any(ch.isspace() for ch in value):
            raise ValueError("a valid email is required")
        return value


class IdentifyOut(BaseModel):
    contact_id: str
    created: bool
    existing_conversations: int


class AssigneeOut(BaseModel):
    id: str
    display_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class QueueCountsOut(BaseModel):
    total: int
    open: int
    pending: int
    resolved: int
    closed: int
    unassigned: int
    urgent: int


class TicketDetail(BaseModel):
    ticket: TicketOut
    messages: list[MessageOut]


class InternalNoteCreate(BaseModel):
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("note body must not be empty")
        return stripped


class InternalNoteOut(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    body: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SavedReplyCreate(BaseModel):
    name: str
    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class SavedReplyOut(BaseModel):
    id: str
    name: str
    body: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class MacroCreate(BaseModel):
    name: str
    actions: str | list[Any]

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("actions")
    @classmethod
    def normalise_actions(cls, value: str | list[Any]) -> str:
        if isinstance(value, list):
            parsed = value
        else:
            if not value.strip():
                raise ValueError("actions must not be empty")
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("actions must be a JSON list") from exc
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("actions must be a non-empty JSON list")
        # Reject external or unknown actions when the macro is stored, not
        # only when it is executed (CW-024: no external send action is offered).
        # Both the structured and the JSON-string request shapes go through the
        # same allow-list; otherwise a list body could smuggle a send action.
        try:
            _parse_actions(parsed, MACRO_ACTION_TYPES)
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc
        return json.dumps(parsed)


class MacroOut(BaseModel):
    id: str
    name: str
    actions: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SlaCreate(BaseModel):
    name: str
    first_response_minutes: int = 60
    resolution_minutes: int = 1440
    business_hours_only: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class SlaOut(BaseModel):
    id: str
    name: str
    first_response_minutes: int
    resolution_minutes: int
    business_hours_only: bool
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class BusinessHoursCreate(BaseModel):
    name: str
    timezone: str = "UTC"
    start_hour: int = 9
    end_hour: int = 17
    days: str = "1,2,3,4,5"

    model_config = ConfigDict(extra="forbid")


class BusinessHoursOut(BaseModel):
    id: str
    name: str
    timezone: str
    start_hour: int
    end_hour: int
    days: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class EscalationCreate(BaseModel):
    name: str
    condition: str = "sla_breach"
    action: str = "notify_owner"
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")


class EscalationOut(BaseModel):
    id: str
    name: str
    condition: str
    action: str
    enabled: bool
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class CsatscoreCreate(BaseModel):
    ticket_id: str
    score: int
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")


class CsatscoreOut(BaseModel):
    id: str
    ticket_id: str
    score: int
    comment: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ticket_or_404(db: Session, workspace_id: str, ticket_id: str) -> Ticket:
    ticket = db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket


def _queue_counts(db: Session, workspace_id: str) -> dict:
    scope = Ticket.workspace_id == workspace_id
    counts = dict(db.execute(
        select(Ticket.status, func.count(Ticket.id)).where(scope).group_by(Ticket.status)
    ).all())
    return {
        "total": db.execute(select(func.count(Ticket.id)).where(scope)).scalar_one(),
        "open": counts.get("open", 0),
        "pending": counts.get("pending", 0),
        "resolved": counts.get("resolved", 0),
        "closed": counts.get("closed", 0),
        "unassigned": db.execute(
            select(func.count(Ticket.id)).where(scope, Ticket.assignee_id.is_(None))
        ).scalar_one(),
        "urgent": db.execute(
            select(func.count(Ticket.id)).where(scope, Ticket.priority == "urgent")
        ).scalar_one(),
    }


def _contact_is_valid(db: Session, workspace_id: str, contact_id: str | None) -> None:
    if contact_id is None:
        return
    exists = db.execute(
        select(Contact.id).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=422, detail="contact not found in this workspace")


def _assignee_is_valid(db: Session, workspace_id: str, assignee_id: str | None) -> None:
    if assignee_id is None:
        return
    exists = db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == assignee_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=422, detail="assignee must be an active workspace member")


def _apply_sla(ticket: Ticket, sla, now_dt) -> None:
    if sla is None:
        return
    ticket.sla_policy_id = sla.id
    ticket.first_response_due_at = now_dt + timedelta(minutes=sla.first_response_minutes)
    ticket.resolution_due_at = now_dt + timedelta(minutes=sla.resolution_minutes)


# ---------------------------------------------------------------------------
# P1 helpers
# ---------------------------------------------------------------------------

ATTRIBUTE_TYPES = ("text", "number", "boolean", "date")
ATTRIBUTE_TARGETS = ("contact", "ticket", "both")
ATTRIBUTE_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
SEGMENT_FIELDS = frozenset(
    {"email", "full_name", "company_name", "phone", "source", "lifecycle_stage",
     "do_not_contact", "archived"}
)
SEGMENT_OPS = ("eq", "ne", "contains", "gt", "lt")
MACRO_ACTION_TYPES = ("set_status", "set_priority", "assign", "label", "reply", "note")
RULE_ACTION_TYPES = ("set_status", "set_priority", "assign", "label")
RULE_TRIGGERS = ("ticket.created", "ticket.status_changed", "ticket.message_added")
ROUTING_STRATEGIES = ("round_robin", "least_loaded")


def _row_or_404(db: Session, model, workspace_id: str, row_id: str, detail: str):
    row = db.execute(
        select(model).where(model.id == row_id, model.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=detail)
    return row


def _active_member(db: Session, workspace_id: str, user_id: str) -> bool:
    return db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none() is not None


def _team_is_valid(db: Session, workspace_id: str, team_id: str | None) -> None:
    if team_id is not None:
        _row_or_404(db, SupportTeam, workspace_id, team_id, "team not found")


def _inbox_is_valid(db: Session, workspace_id: str, inbox_id: str | None) -> None:
    if inbox_id is not None:
        _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")


def _label_is_valid(db: Session, workspace_id: str, label_id: str | None) -> None:
    if label_id is not None:
        _row_or_404(db, SupportLabel, workspace_id, label_id, "label not found")


def _inbox_is_permitted(db: Session, principal: Principal, inbox) -> bool:
    """Owner/admin may administer every inbox; agents only their own queues."""
    if principal.role in ("owner", "admin"):
        return True
    return db.execute(
        select(InboxAgent.id).where(
            InboxAgent.workspace_id == inbox.workspace_id,
            InboxAgent.inbox_id == inbox.id,
            InboxAgent.user_id == principal.user.id,
        )
    ).scalar_one_or_none() is not None


def _publish_on_ticket(
    db: Session, workspace_id: str, ticket: Ticket, event_type: str,
    *, payload: dict | None = None, actor_id: str, entity_id: str | None = None,
) -> None:
    """All ticket events share the ticket id as correlation id, so the shared
    contact timeline can assemble a conversation in append-only order."""
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=event_type,
        entity_id=entity_id or ticket.id,
        correlation_id=ticket.id,
        payload=payload or {},
        actor_id=actor_id,
    )


def _link_contact_timeline(
    db: Session, workspace_id: str, ticket: Ticket, actor_id: str
) -> None:
    if not ticket.contact_id:
        return
    # main.py's contact_timeline discovers correlation ids from events whose
    # entity_id is the contact. This one row links the local ticket thread to
    # that existing timeline; no second identity or external service is used.
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_CONTACT_LINKED,
        payload={"ticket_id": ticket.id, "subject": ticket.subject},
        actor_id=actor_id, entity_id=ticket.contact_id,
    )


def _coerce_attribute_value(value_type: str, value: Any) -> Any:
    if value_type == "text":
        if not isinstance(value, str):
            raise ValueError("text attribute requires a string")
        return value
    if value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("number attribute requires a number")
        return value
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError("boolean attribute requires a boolean")
        return value
    if value_type == "date":
        if not isinstance(value, str):
            raise ValueError("date attribute requires an ISO date string")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError as exc:
            raise ValueError("date attribute requires an ISO date string") from exc
    raise ValueError("unsupported attribute type")


def _entity_is_valid(db: Session, workspace_id: str, entity_type: str, entity_id: str) -> None:
    model = Contact if entity_type == "contact" else Ticket
    exists = db.execute(
        select(model.id).where(model.id == entity_id, model.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=422, detail=f"{entity_type} not found in this workspace")


def _parse_actions(raw: Any, allowed: tuple[str, ...]) -> list[dict[str, Any]]:
    """Normalise the P0 string format and the P1 structured format into one
    allow-listed, ordered action list. Any outbound action is rejected here."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="actions must be a JSON list") from exc
    else:
        parsed = raw
    if not isinstance(parsed, list) or not parsed:
        raise HTTPException(status_code=422, detail="actions must be a non-empty list")
    actions: list[dict[str, Any]] = []
    for item in parsed:
        if isinstance(item, str):
            if ":" not in item:
                raise HTTPException(status_code=422, detail=f"invalid action: {item}")
            action_type, value = item.split(":", 1)
        elif isinstance(item, dict):
            action_type = item.get("type") or item.get("action")
            if action_type is None and len(item) == 1:
                action_type, value = next(iter(item.items()))
            else:
                value = item.get("value")
        else:
            raise HTTPException(status_code=422, detail="each action must be a string or object")
        action_type = str(action_type).strip()
        if action_type not in allowed:
            raise HTTPException(status_code=422, detail=f"unsupported action: {action_type}")
        actions.append({"type": action_type, "value": value})
    return actions


def _apply_local_action(
    db: Session, workspace_id: str, ticket: Ticket, action: dict[str, Any],
    *, actor_id: str, changes: list[dict[str, Any]], dry_run: bool,
    allow_message: bool,
) -> None:
    kind, value = action["type"], action.get("value")
    if kind == "set_status":
        if value not in TICKET_STATUSES:
            raise HTTPException(status_code=422, detail="invalid status action")
        if not dry_run and ticket.status != value:
            changes.append({"type": kind, "from": ticket.status, "to": value})
            ticket.status = value
            ticket.updated_at = now()
        elif dry_run:
            changes.append({"type": kind, "from": ticket.status, "to": value})
    elif kind == "set_priority":
        if value not in TICKET_PRIORITIES:
            raise HTTPException(status_code=422, detail="invalid priority action")
        if not dry_run and ticket.priority != value:
            changes.append({"type": kind, "from": ticket.priority, "to": value})
            ticket.priority = value
            ticket.updated_at = now()
        elif dry_run:
            changes.append({"type": kind, "from": ticket.priority, "to": value})
    elif kind == "assign":
        _assignee_is_valid(db, workspace_id, value)
        if not dry_run:
            ticket.assignee_id = value
            ticket.updated_at = now()
        changes.append({"type": kind, "to": value})
    elif kind == "label":
        _label_is_valid(db, workspace_id, value)
        exists = db.execute(
            select(TicketLabel.id).where(
                TicketLabel.workspace_id == workspace_id,
                TicketLabel.ticket_id == ticket.id,
                TicketLabel.label_id == value,
            )
        ).scalar_one_or_none()
        if not dry_run and exists is None:
            db.add(TicketLabel(
                id=new_id(), workspace_id=workspace_id,
                ticket_id=ticket.id, label_id=value, created_at=now(),
            ))
        changes.append({"type": kind, "label_id": value, "already_applied": exists is not None})
    elif kind in ("reply", "note"):
        if not allow_message:
            raise HTTPException(status_code=422, detail=f"{kind} is not allowed here")
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=422, detail=f"{kind} action needs text")
        if not dry_run:
            if kind == "reply":
                message = TicketMessage(
                    id=new_id(), workspace_id=workspace_id, ticket_id=ticket.id,
                    author_id=actor_id, body=value.strip(), direction="outbound",
                    channel="local", is_internal=False, created_at=now(),
                )
                db.add(message)
                db.flush()
                _publish_on_ticket(
                    db, workspace_id, ticket, TICKET_MESSAGE_ADDED,
                    payload={"ticket_id": ticket.id, "author_id": actor_id,
                             "direction": "outbound", "channel": "local",
                             "internal": False, "source": "macro"},
                    actor_id=actor_id,
                )
            else:
                note = TicketInternalNote(
                    id=new_id(), workspace_id=workspace_id, ticket_id=ticket.id,
                    author_id=actor_id, body=value.strip(), created_at=now(),
                )
                db.add(note)
                db.flush()
                _publish_on_ticket(
                    db, workspace_id, ticket, TICKET_UPDATED,
                    payload={"ticket_id": ticket.id, "internal_note": True, "source": "macro"},
                    actor_id=actor_id,
                )
        changes.append({"type": kind, "length": len(value.strip())})


def _run_conversation_rules(
    db: Session, workspace_id: str, actor_id: str, trigger: str, ticket: Ticket
) -> list[str]:
    """Apply matching stored rules to local ticket fields and leave a run
    trace. Rule actions never send anything outside the workspace."""
    rules = db.execute(
        select(ConversationRule).where(
            ConversationRule.workspace_id == workspace_id,
            ConversationRule.trigger == trigger,
            ConversationRule.enabled.is_(True),
        ).order_by(ConversationRule.created_at, ConversationRule.id)
    ).scalars().all()
    ran: list[str] = []
    for rule in rules:
        changes: list[dict[str, Any]] = []
        for action in rule.actions:
            _apply_local_action(
                db, workspace_id, ticket, action, actor_id=actor_id,
                changes=changes, dry_run=False, allow_message=False,
            )
        run = ConversationRuleRun(
            id=new_id(), workspace_id=workspace_id, rule_id=rule.id,
            ticket_id=ticket.id, trigger=trigger, changes=changes,
            actor_id=actor_id, created_at=now(),
        )
        db.add(run)
        db.flush()
        publish_event(
            db, workspace_id=workspace_id, event_type=CONVERSATION_RULE_RAN,
            entity_id=run.id, correlation_id=ticket.id,
            payload={"rule_id": rule.id, "ticket_id": ticket.id,
                     "trigger": trigger, "changes": changes},
            actor_id=actor_id,
        )
        ran.append(rule.id)
    return ran


def _auto_assign(db: Session, workspace_id: str, ticket: Ticket, actor_id: str) -> str | None:
    """Deterministic round-robin / least-loaded routing over local members."""
    rules = db.execute(
        select(RoutingRule).where(
            RoutingRule.workspace_id == workspace_id,
            RoutingRule.enabled.is_(True),
            or_(RoutingRule.channel == "any", RoutingRule.channel == ticket.origin_channel),
        ).order_by(RoutingRule.priority, RoutingRule.created_at, RoutingRule.id)
    ).scalars().all()
    for rule in rules:
        if rule.assignee_id:
            candidates = [rule.assignee_id] if _active_member(db, workspace_id, rule.assignee_id) else []
        elif rule.team_id:
            candidates = db.execute(
                select(SupportTeamMember.user_id).where(
                    SupportTeamMember.workspace_id == workspace_id,
                    SupportTeamMember.team_id == rule.team_id,
                )
            ).scalars().all()
        else:
            candidates = db.execute(
                select(WorkspaceMember.user_id).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.status == "active",
                )
            ).scalars().all()
        candidates = [uid for uid in dict.fromkeys(candidates) if _active_member(db, workspace_id, uid)]
        if not candidates:
            continue
        counts = dict(db.execute(
            select(Ticket.assignee_id, func.count(Ticket.id)).where(
                Ticket.workspace_id == workspace_id,
                Ticket.assignee_id.in_(candidates),
            ).group_by(Ticket.assignee_id)
        ).all())
        if rule.strategy == "least_loaded":
            chosen = sorted(candidates, key=lambda uid: (counts.get(uid, 0), uid))[0]
        else:
            chosen = sorted(candidates, key=lambda uid: (counts.get(uid, 0), uid))[0]
        ticket.assignee_id = chosen
        ticket.updated_at = now()
        _publish_on_ticket(
            db, workspace_id, ticket, TICKET_AUTO_ASSIGNED,
            payload={"rule_id": rule.id, "strategy": rule.strategy,
                     "channel": ticket.origin_channel, "team_id": rule.team_id},
            actor_id=actor_id,
        )
        return rule.id
    return None


def _ensure_csat_survey(db: Session, workspace_id: str, ticket: Ticket, actor_id: str) -> bool:
    """Create at most one local survey when a ticket is resolved. There is no
    outbound message: the survey is a row an authorised agent can read."""
    existing = db.execute(
        select(CsatSurvey.id).where(
            CsatSurvey.workspace_id == workspace_id, CsatSurvey.ticket_id == ticket.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    if ticket.inbox_id:
        inbox = db.execute(
            select(SupportInbox).where(
                SupportInbox.id == ticket.inbox_id,
                SupportInbox.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if inbox is None or not inbox.csat_enabled:
            return False
    if _CSAT_RULE_EVALUATOR is not None:
        allowed, _reason = _CSAT_RULE_EVALUATOR(db, workspace_id, ticket)
        if not allowed:
            return False
    survey = CsatSurvey(
        id=new_id(), workspace_id=workspace_id, ticket_id=ticket.id,
        status="pending", created_at=now(),
    )
    db.add(survey)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CSAT_SURVEY_CREATED,
        entity_id=survey.id, correlation_id=ticket.id,
        payload={"ticket_id": ticket.id, "external_delivery": False},
        actor_id=actor_id,
    )
    return True


def _validate_segment_definition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="segment definition must be an object")
    if value.get("match") not in ("all", "any"):
        raise HTTPException(status_code=422, detail="segment match must be all or any")
    conditions = value.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise HTTPException(status_code=422, detail="segment needs conditions")
    for condition in conditions:
        if not isinstance(condition, dict):
            raise HTTPException(status_code=422, detail="condition must be an object")
        field = str(condition.get("field", ""))
        if field.startswith("custom:"):
            if not ATTRIBUTE_KEY.fullmatch(field[7:]):
                raise HTTPException(status_code=422, detail="invalid custom attribute field")
        elif field not in SEGMENT_FIELDS:
            raise HTTPException(status_code=422, detail="field is not allow-listed")
        if condition.get("op") not in SEGMENT_OPS or "value" not in condition:
            raise HTTPException(status_code=422, detail="invalid segment condition")
    return value


def _segment_matches(
    db: Session, workspace_id: str, contact: Contact, definition: dict[str, Any]
) -> bool:
    results: list[bool] = []
    for condition in definition["conditions"]:
        field, op, expected = condition["field"], condition["op"], condition["value"]
        if field.startswith("custom:"):
            key = field[7:]
            row = db.execute(
                select(CustomAttributeValue.value).join(
                    CustomAttribute, CustomAttribute.id == CustomAttributeValue.attribute_id
                ).where(
                    CustomAttributeValue.workspace_id == workspace_id,
                    CustomAttributeValue.entity_type == "contact",
                    CustomAttributeValue.entity_id == contact.id,
                    CustomAttribute.key == key,
                )
            ).scalar_one_or_none()
            actual = row.get("value") if isinstance(row, dict) else None
        else:
            actual = getattr(contact, field)
        if op == "eq":
            results.append(str(actual).lower() == str(expected).lower())
        elif op == "ne":
            results.append(str(actual).lower() != str(expected).lower())
        elif op == "contains":
            results.append(str(expected).lower() in str(actual or "").lower())
        else:
            try:
                left, right = float(actual), float(expected)
            except (TypeError, ValueError):
                left, right = str(actual), str(expected)
            results.append(left > right if op == "gt" else left < right)
    return all(results) if definition["match"] == "all" else any(results)


def _date_filter(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {name}") from exc
    return parsed.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TicketOut])
def list_tickets(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = None,
    assignee_id: str | None = None,
    contact_id: str | None = Query(None),
    mine: bool = Query(False),
    unassigned: bool = Query(False),
    team_id: str | None = None,
    label_id: str | None = None,
    inbox_id: str | None = None,
    channel: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    attr_key: str | None = None,
    attr_value: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    verify_workspace(principal, workspace_id)
    query = select(Ticket).where(Ticket.workspace_id == workspace_id)

    # CW-048: agents only see queues for inboxes they belong to. Workspace
    # owners/admins retain oversight of every local inbox.
    if inbox_id:
        inbox = db.execute(
            select(SupportInbox).where(
                SupportInbox.workspace_id == workspace_id, SupportInbox.id == inbox_id
            )
        ).scalar_one_or_none()
        if inbox is None:
            raise HTTPException(status_code=422, detail="invalid inbox filter")
        if not _inbox_is_permitted(db, principal, inbox):
            raise HTTPException(status_code=403, detail="not a member of this inbox")
        query = query.where(Ticket.inbox_id == inbox_id)
    else:
        inboxes = db.execute(
            select(SupportInbox).where(SupportInbox.workspace_id == workspace_id)
        ).scalars().all()
        permitted = [i.id for i in inboxes if _inbox_is_permitted(db, principal, i)]
        if permitted or inboxes:
            query = query.where(
                or_(Ticket.inbox_id.is_(None), Ticket.inbox_id.in_(permitted))
            )

    if contact_id:
        # CW-014: a contact's support profile reads only conversations linked
        # to that one identity, never another workspace's or a guessed id.
        _contact_is_valid(db, workspace_id, contact_id)
        query = query.where(Ticket.contact_id == contact_id)
    if mine:
        query = query.where(Ticket.assignee_id == principal.user.id)
    elif unassigned:
        query = query.where(Ticket.assignee_id.is_(None))
    elif assignee_id:
        query = query.where(Ticket.assignee_id == assignee_id)
    if status_filter:
        if status_filter not in TICKET_STATUSES:
            raise HTTPException(status_code=422, detail="invalid ticket status filter")
        query = query.where(Ticket.status == status_filter)
    if priority:
        if priority not in TICKET_PRIORITIES:
            raise HTTPException(status_code=422, detail="invalid ticket priority filter")
        query = query.where(Ticket.priority == priority)

    # CW-028: every filter maps to an allow-listed column or join; no client
    # text is ever interpolated into SQL.
    if team_id:
        if db.execute(
            select(SupportTeam.id).where(
                SupportTeam.workspace_id == workspace_id, SupportTeam.id == team_id
            )
        ).scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="invalid team filter")
        query = query.where(Ticket.team_id == team_id)
    if label_id:
        if db.execute(
            select(SupportLabel.id).where(
                SupportLabel.workspace_id == workspace_id, SupportLabel.id == label_id
            )
        ).scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="invalid label filter")
        query = query.where(Ticket.id.in_(
            select(TicketLabel.ticket_id).where(
                TicketLabel.workspace_id == workspace_id, TicketLabel.label_id == label_id
            )
        ))
    if channel:
        if channel not in TICKET_ORIGINS:
            raise HTTPException(status_code=422, detail="invalid channel filter")
        query = query.where(Ticket.origin_channel == channel)
    start, end = _date_filter(created_from, "created_from"), _date_filter(created_to, "created_to")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="created_from must precede created_to")
    if start:
        query = query.where(Ticket.created_at >= start)
    if end:
        query = query.where(Ticket.created_at <= end)
    if attr_key:
        if attr_value is None:
            raise HTTPException(status_code=422, detail="attr_value is required with attr_key")
        attribute = db.execute(
            select(CustomAttribute).where(
                CustomAttribute.workspace_id == workspace_id,
                CustomAttribute.key == attr_key,
            )
        ).scalar_one_or_none()
        if attribute is None:
            raise HTTPException(status_code=422, detail="unknown attribute")
        values = db.execute(
            select(CustomAttributeValue.entity_id, CustomAttributeValue.value).where(
                CustomAttributeValue.workspace_id == workspace_id,
                CustomAttributeValue.attribute_id == attribute.id,
                CustomAttributeValue.entity_type == "ticket",
            )
        ).all()
        matching = [
            entity_id for entity_id, value in values
            if str((value or {}).get("value")) == attr_value
        ]
        query = query.where(Ticket.id.in_(matching) if matching else False)
    return db.execute(query.order_by(Ticket.created_at.desc())).scalars().all()


@router.get("/search", response_model=list[TicketOut])
def search_tickets(
    workspace_id: str,
    q: str = Query(..., min_length=1),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    verify_workspace(principal, workspace_id)
    pattern = f"%{q.strip()}%"
    ticket_ids_with_message = db.execute(
        select(TicketMessage.ticket_id).where(
            TicketMessage.workspace_id == workspace_id,
            TicketMessage.body.ilike(pattern),
        )
    ).scalars().all()
    query = select(Ticket).where(
        Ticket.workspace_id == workspace_id,
        or_(
            Ticket.subject.ilike(pattern),
            Ticket.body.ilike(pattern),
            Ticket.id.in_(ticket_ids_with_message) if ticket_ids_with_message else False,
        ),
    )
    return db.execute(query.order_by(Ticket.created_at.desc())).scalars().all()


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    workspace_id: str,
    body: TicketCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Ticket:
    verify_workspace(principal, workspace_id)
    _contact_is_valid(db, workspace_id, body.contact_id)
    _assignee_is_valid(db, workspace_id, body.assignee_id)
    _team_is_valid(db, workspace_id, body.team_id)
    _inbox_is_valid(db, workspace_id, body.inbox_id)
    if body.inbox_id:
        inbox = db.get(SupportInbox, body.inbox_id)
        if not _inbox_is_permitted(db, principal, inbox):
            raise HTTPException(status_code=403, detail="not a member of this inbox")
    ticket = Ticket(
        id=new_id(),
        workspace_id=workspace_id,
        contact_id=body.contact_id,
        subject=body.subject.strip(),
        body=body.body.strip(),
        status="open",
        priority=body.priority,
        origin_channel=body.origin_channel,
        conversation_type=body.conversation_type,
        assignee_id=body.assignee_id,
        team_id=body.team_id,
        inbox_id=body.inbox_id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(ticket)
    db.flush()
    # apply SLA if provided
    if body.sla_policy_id:
        sla = db.execute(
            select(SlaPolicy).where(SlaPolicy.id == body.sla_policy_id, SlaPolicy.workspace_id == workspace_id)
        ).scalar_one_or_none()
        _apply_sla(ticket, sla, now())
        db.flush()
    routing_rule_id = None
    if body.assignee_id is None:
        routing_rule_id = _auto_assign(db, workspace_id, ticket, principal.user.id)
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_CREATED,
        payload={
            "subject": ticket.subject,
            "priority": ticket.priority,
            "origin_channel": ticket.origin_channel,
            "conversation_type": ticket.conversation_type,
            "contact_id": ticket.contact_id,
            "team_id": ticket.team_id,
            "inbox_id": ticket.inbox_id,
            "routing_rule_id": routing_rule_id,
        },
        actor_id=principal.user.id,
    )
    _link_contact_timeline(db, workspace_id, ticket, principal.user.id)
    _run_conversation_rules(db, workspace_id, principal.user.id, "ticket.created", ticket)
    db.commit()
    return ticket


@router.get("/assignees", response_model=list[AssigneeOut])
def list_assignees(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Active workspace members an agent may assign a conversation to.

    This is deliberately readable with contact:read so the inbox assignment
    control works for agents, without widening the member-management API.
    """
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active",
        )
        .order_by(User.display_name)
    ).scalars().all()


@router.get("/counts", response_model=QueueCountsOut)
def queue_counts(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return _queue_counts(db, workspace_id)


@router.get("/stream", tags=["support"])
def ticket_stream(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    """Real-time queue counts as a local server-sent feed. The browser uses a
    streaming fetch so the bearer token stays in the header."""
    verify_workspace(principal, workspace_id)
    bind = db.get_bind()

    async def event_stream():
        last = None
        for tick in range(720):
            try:
                with Session(bind) as poll_db:
                    snapshot = _queue_counts(poll_db, workspace_id)
            except Exception:
                snapshot = None
            if snapshot is not None and snapshot != last:
                yield "data: " + json.dumps(snapshot) + "\n\n"
                last = snapshot
            elif tick % 12 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/identify", response_model=IdentifyOut, status_code=status.HTTP_201_CREATED)
def identify_contact(
    workspace_id: str,
    body: IdentifyRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> IdentifyOut:
    """Pre-chat identity capture that reuses the single CRM contact identity."""
    verify_workspace(principal, workspace_id)
    contact = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == body.email)
    ).scalar_one_or_none()
    created = contact is None
    if contact is None:
        contact = Contact(
            id=new_id(),
            workspace_id=workspace_id,
            email=body.email,
            full_name=body.full_name,
            company_name=body.company_name,
            source="pre_chat_identity",
            owner_id=principal.user.id,
            created_at=now(),
            updated_at=now(),
        )
        db.add(contact)
        db.flush()
    existing = db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.workspace_id == workspace_id, Ticket.contact_id == contact.id
        )
    ).scalar_one()
    if created:
        publish_event(
            db, workspace_id=workspace_id, event_type=TICKET_CONTACT_IDENTIFIED,
            entity_id=contact.id, actor_id=principal.user.id,
            payload={"created": True, "source": "pre_chat_identity"},
        )
        db.commit()
    return IdentifyOut(
        contact_id=contact.id, created=created, existing_conversations=existing
    )


@router.patch("/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    workspace_id: str,
    ticket_id: str,
    body: TicketPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Ticket:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    updates = body.model_dump(exclude_unset=True)
    status_reason = updates.pop("status_reason", None)
    if "assignee_id" in updates:
        _assignee_is_valid(db, workspace_id, updates["assignee_id"])
    if "team_id" in updates:
        _team_is_valid(db, workspace_id, updates["team_id"])
    if "inbox_id" in updates:
        _inbox_is_valid(db, workspace_id, updates["inbox_id"])
        if updates["inbox_id"]:
            inbox = db.get(SupportInbox, updates["inbox_id"])
            if not _inbox_is_permitted(db, principal, inbox):
                raise HTTPException(status_code=403, detail="not a member of this inbox")
    old_status = ticket.status
    old_assignee = ticket.assignee_id
    old_team = ticket.team_id
    for key, value in updates.items():
        setattr(ticket, key, value)
    ticket.updated_at = now()

    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_UPDATED,
        payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    if "status" in updates and old_status != ticket.status:
        _publish_on_ticket(
            db, workspace_id, ticket, TICKET_STATUS_CHANGED,
            payload={"from": old_status, "to": ticket.status, "reason": status_reason},
            actor_id=principal.user.id,
        )
        if ticket.status == "resolved":
            _ensure_csat_survey(db, workspace_id, ticket, principal.user.id)
    if "assignee_id" in updates and old_assignee != ticket.assignee_id:
        _publish_on_ticket(
            db, workspace_id, ticket, TICKET_ASSIGNED,
            payload={"from": old_assignee, "to": ticket.assignee_id},
            actor_id=principal.user.id,
        )
    if "team_id" in updates and old_team != ticket.team_id:
        _publish_on_ticket(
            db, workspace_id, ticket, TICKET_TEAM_ASSIGNED,
            payload={"from": old_team, "to": ticket.team_id},
            actor_id=principal.user.id,
        )
    if "status" in updates and old_status != ticket.status:
        _run_conversation_rules(
            db, workspace_id, principal.user.id, "ticket.status_changed", ticket
        )
    db.commit()
    return ticket


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
def list_messages(
    workspace_id: str,
    ticket_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[TicketMessage]:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    return db.execute(
        select(TicketMessage)
        .where(
            TicketMessage.workspace_id == workspace_id,
            TicketMessage.ticket_id == ticket.id,
        )
        .order_by(TicketMessage.created_at)
    ).scalars().all()


@router.post(
    "/{ticket_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    workspace_id: str,
    ticket_id: str,
    body: MessageCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> TicketMessage:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    message = TicketMessage(
        id=new_id(),
        workspace_id=workspace_id,
        ticket_id=ticket.id,
        author_id=principal.user.id,
        body=body.body.strip(),
        direction=body.direction,
        channel=body.channel,
        is_internal=body.is_internal,
        created_at=now(),
    )
    db.add(message)
    ticket.updated_at = now()
    db.flush()
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_MESSAGE_ADDED,
        payload={
            "ticket_id": ticket.id, "author_id": principal.user.id,
            "internal": body.is_internal, "direction": body.direction, "channel": body.channel,
        },
        actor_id=principal.user.id, entity_id=message.id,
    )
    _run_conversation_rules(
        db, workspace_id, principal.user.id, "ticket.message_added", ticket
    )
    db.commit()
    return message


# ---------------------------------------------------------------------------
# Private notes
# ---------------------------------------------------------------------------


@router.get("/{ticket_id}/notes", response_model=list[InternalNoteOut])
def list_internal_notes(
    workspace_id: str,
    ticket_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[TicketInternalNote]:
    verify_workspace(principal, workspace_id)
    _ticket_or_404(db, workspace_id, ticket_id)
    return db.execute(
        select(TicketInternalNote)
        .where(
            TicketInternalNote.workspace_id == workspace_id,
            TicketInternalNote.ticket_id == ticket_id,
        )
        .order_by(TicketInternalNote.created_at)
    ).scalars().all()


@router.post(
    "/{ticket_id}/notes",
    response_model=InternalNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def add_internal_note(
    workspace_id: str,
    ticket_id: str,
    body: InternalNoteCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> TicketInternalNote:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    note = TicketInternalNote(
        id=new_id(),
        workspace_id=workspace_id,
        ticket_id=ticket.id,
        author_id=principal.user.id,
        body=body.body.strip(),
        created_at=now(),
    )
    db.add(note)
    ticket.updated_at = now()
    db.flush()
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_UPDATED,
        payload={"ticket_id": ticket.id, "internal_note": True, "note_id": note.id},
        actor_id=principal.user.id, entity_id=note.id,
    )
    db.commit()
    return note


# ---------------------------------------------------------------------------
# Saved replies
# ---------------------------------------------------------------------------


@router.get("/saved-replies", response_model=list[SavedReplyOut])
def list_saved_replies(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SavedReply]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SavedReply).where(SavedReply.workspace_id == workspace_id).order_by(SavedReply.created_at)
    ).scalars().all()


@router.post("/saved-replies", response_model=SavedReplyOut, status_code=status.HTTP_201_CREATED)
def create_saved_reply(
    workspace_id: str,
    body: SavedReplyCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SavedReply:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SavedReply).where(SavedReply.workspace_id == workspace_id, SavedReply.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="saved reply already exists")
    r = SavedReply(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        body=body.body.strip(), created_by=principal.user.id, created_at=now(),
    )
    db.add(r)
    db.commit()
    return r


# ---------------------------------------------------------------------------
# Macros
# ---------------------------------------------------------------------------


@router.get("/macros", response_model=list[MacroOut])
def list_macros(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Macro]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Macro).where(Macro.workspace_id == workspace_id).order_by(Macro.created_at)
    ).scalars().all()


@router.post("/macros", response_model=MacroOut, status_code=status.HTTP_201_CREATED)
def create_macro(
    workspace_id: str,
    body: MacroCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Macro:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Macro).where(Macro.workspace_id == workspace_id, Macro.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="macro already exists")
    m = Macro(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        actions=body.actions.strip(), created_by=principal.user.id, created_at=now(),
    )
    db.add(m)
    db.commit()
    return m


# ---------------------------------------------------------------------------
# SLA policies
# ---------------------------------------------------------------------------


@router.get("/sla-policies", response_model=list[SlaOut])
def list_sla(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SlaPolicy]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SlaPolicy).where(SlaPolicy.workspace_id == workspace_id).order_by(SlaPolicy.created_at)
    ).scalars().all()


@router.post("/sla-policies", response_model=SlaOut, status_code=status.HTTP_201_CREATED)
def create_sla(
    workspace_id: str,
    body: SlaCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SlaPolicy:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SlaPolicy).where(SlaPolicy.workspace_id == workspace_id, SlaPolicy.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="sla policy already exists")
    s = SlaPolicy(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        first_response_minutes=body.first_response_minutes,
        resolution_minutes=body.resolution_minutes,
        business_hours_only=body.business_hours_only,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(s)
    db.commit()
    return s


# ---------------------------------------------------------------------------
# Business hours
# ---------------------------------------------------------------------------


@router.get("/business-hours", response_model=list[BusinessHoursOut])
def list_business_hours(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[BusinessHours]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(BusinessHours).where(BusinessHours.workspace_id == workspace_id).order_by(BusinessHours.created_at)
    ).scalars().all()


@router.post("/business-hours", response_model=BusinessHoursOut, status_code=status.HTTP_201_CREATED)
def create_business_hours(
    workspace_id: str,
    body: BusinessHoursCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> BusinessHours:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(BusinessHours).where(BusinessHours.workspace_id == workspace_id, BusinessHours.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="business hours already exists")
    b = BusinessHours(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        timezone=body.timezone, start_hour=body.start_hour,
        end_hour=body.end_hour, days=body.days,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(b)
    db.commit()
    return b


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------


@router.get("/escalation-rules", response_model=list[EscalationOut])
def list_escalations(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[EscalationRule]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(EscalationRule).where(EscalationRule.workspace_id == workspace_id).order_by(EscalationRule.created_at)
    ).scalars().all()


@router.post("/escalation-rules", response_model=EscalationOut, status_code=status.HTTP_201_CREATED)
def create_escalation(
    workspace_id: str,
    body: EscalationCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> EscalationRule:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(EscalationRule).where(EscalationRule.workspace_id == workspace_id, EscalationRule.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="escalation rule already exists")
    e = EscalationRule(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        condition=body.condition, action=body.action, enabled=body.enabled,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(e)
    db.commit()
    return e


# ---------------------------------------------------------------------------
# CSAT
# ---------------------------------------------------------------------------


@router.post("/csat", response_model=CsatscoreOut, status_code=status.HTTP_201_CREATED)
def record_csat(
    workspace_id: str,
    body: CsatscoreCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Csatscore:
    verify_workspace(principal, workspace_id)
    _ticket_or_404(db, workspace_id, body.ticket_id)
    if not (1 <= body.score <= 5):
        raise HTTPException(status_code=422, detail="score must be 1-5")
    c = Csatscore(
        id=new_id(), workspace_id=workspace_id, ticket_id=body.ticket_id,
        score=body.score, comment=body.comment, created_at=now(),
    )
    db.add(c)
    db.commit()
    return c


@router.get("/csat", response_model=list[CsatscoreOut])
def list_csat(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Csatscore]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Csatscore).where(Csatscore.workspace_id == workspace_id).order_by(Csatscore.created_at.desc())
    ).scalars().all()


# ---------------------------------------------------------------------------
# P1: teams (CW-005)
# ---------------------------------------------------------------------------


class TeamCreate(BaseModel):
    name: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()


class TeamOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class TeamMemberAdd(BaseModel):
    user_id: str

    model_config = ConfigDict(extra="forbid")


class TeamMemberOut(BaseModel):
    id: str
    user_id: str
    display_name: str
    email: str


@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SupportTeam]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SupportTeam).where(SupportTeam.workspace_id == workspace_id)
        .order_by(SupportTeam.name)
    ).scalars().all()


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    workspace_id: str,
    body: TeamCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SupportTeam:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SupportTeam.id).where(
            SupportTeam.workspace_id == workspace_id, SupportTeam.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="team already exists")
    team = SupportTeam(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        description=body.description, created_by=principal.user.id, created_at=now(),
    )
    db.add(team)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=TEAM_CREATED, entity_id=team.id,
        payload={"name": team.name}, actor_id=principal.user.id,
    )
    db.commit()
    return team


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberOut])
def list_team_members(
    workspace_id: str,
    team_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _row_or_404(db, SupportTeam, workspace_id, team_id, "team not found")
    return [
        {"id": membership.id, "user_id": user.id,
         "display_name": user.display_name, "email": user.email}
        for membership, user in db.execute(
            select(SupportTeamMember, User).join(User, User.id == SupportTeamMember.user_id).where(
                SupportTeamMember.workspace_id == workspace_id,
                SupportTeamMember.team_id == team_id,
            ).order_by(User.display_name)
        ).all()
    ]


@router.post(
    "/teams/{team_id}/members",
    response_model=TeamMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    workspace_id: str,
    team_id: str,
    body: TeamMemberAdd,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    team = _row_or_404(db, SupportTeam, workspace_id, team_id, "team not found")
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="member must be active in this workspace")
    exists = db.execute(
        select(SupportTeamMember.id).where(
            SupportTeamMember.workspace_id == workspace_id,
            SupportTeamMember.team_id == team.id,
            SupportTeamMember.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="already a team member")
    membership = SupportTeamMember(
        id=new_id(), workspace_id=workspace_id, team_id=team.id,
        user_id=body.user_id, created_at=now(),
    )
    db.add(membership)
    db.flush()
    user = db.get(User, body.user_id)
    publish_event(
        db, workspace_id=workspace_id, event_type=TEAM_MEMBER_ADDED,
        entity_id=membership.id,
        payload={"team_id": team.id, "user_id": body.user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": membership.id, "user_id": user.id,
            "display_name": user.display_name, "email": user.email}


# ---------------------------------------------------------------------------
# P1: labels (CW-012)
# ---------------------------------------------------------------------------


class LabelCreate(BaseModel):
    name: str
    color: str = "#3B82F6"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError("color must be a #RRGGBB value")
        return value


class LabelOut(BaseModel):
    id: str
    name: str
    color: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class TicketLabelAdd(BaseModel):
    label_id: str

    model_config = ConfigDict(extra="forbid")


class TicketLabelOut(BaseModel):
    id: str
    ticket_id: str
    label_id: str
    name: str
    color: str


class LabelReportOut(BaseModel):
    label_id: str
    name: str
    ticket_count: int


@router.get("/labels", response_model=list[LabelOut])
def list_labels(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SupportLabel]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SupportLabel).where(SupportLabel.workspace_id == workspace_id)
        .order_by(SupportLabel.name)
    ).scalars().all()


@router.post("/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
def create_label(
    workspace_id: str,
    body: LabelCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SupportLabel:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(SupportLabel.id).where(
            SupportLabel.workspace_id == workspace_id, SupportLabel.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="label already exists")
    label = SupportLabel(
        id=new_id(), workspace_id=workspace_id, name=body.name, color=body.color,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(label)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=LABEL_CREATED, entity_id=label.id,
        payload={"name": label.name}, actor_id=principal.user.id,
    )
    db.commit()
    return label


@router.get("/labels/report", response_model=list[LabelReportOut])
def label_report(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SupportLabel.id, SupportLabel.name, func.count(TicketLabel.id))
        .outerjoin(
            TicketLabel,
            and_(TicketLabel.label_id == SupportLabel.id,
                 TicketLabel.workspace_id == workspace_id),
        )
        .where(SupportLabel.workspace_id == workspace_id)
        .group_by(SupportLabel.id, SupportLabel.name)
        .order_by(SupportLabel.name)
    ).all()
    return [{"label_id": row[0], "name": row[1], "ticket_count": row[2]} for row in rows]


@router.get("/{ticket_id}/labels", response_model=list[TicketLabelOut])
def list_ticket_labels(
    workspace_id: str,
    ticket_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _ticket_or_404(db, workspace_id, ticket_id)
    rows = db.execute(
        select(TicketLabel, SupportLabel).join(
            SupportLabel, SupportLabel.id == TicketLabel.label_id
        ).where(
            TicketLabel.workspace_id == workspace_id,
            TicketLabel.ticket_id == ticket_id,
        ).order_by(SupportLabel.name)
    ).all()
    return [
        {"id": link.id, "ticket_id": link.ticket_id, "label_id": link.label_id,
         "name": label.name, "color": label.color}
        for link, label in rows
    ]


@router.post(
    "/{ticket_id}/labels",
    response_model=TicketLabelOut,
    status_code=status.HTTP_201_CREATED,
)
def add_ticket_label(
    workspace_id: str,
    ticket_id: str,
    body: TicketLabelAdd,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    label = _row_or_404(db, SupportLabel, workspace_id, body.label_id, "label not found")
    exists = db.execute(
        select(TicketLabel.id).where(
            TicketLabel.workspace_id == workspace_id,
            TicketLabel.ticket_id == ticket.id,
            TicketLabel.label_id == label.id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="label already applied")
    link = TicketLabel(
        id=new_id(), workspace_id=workspace_id, ticket_id=ticket.id,
        label_id=label.id, created_at=now(),
    )
    db.add(link)
    db.flush()
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_LABELED,
        payload={"label_id": label.id, "name": label.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": link.id, "ticket_id": ticket.id, "label_id": label.id,
            "name": label.name, "color": label.color}


@router.delete("/{ticket_id}/labels/{label_id}", response_model=TicketLabelOut)
def remove_ticket_label(
    workspace_id: str,
    ticket_id: str,
    label_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    label = _row_or_404(db, SupportLabel, workspace_id, label_id, "label not found")
    link = db.execute(
        select(TicketLabel).where(
            TicketLabel.workspace_id == workspace_id,
            TicketLabel.ticket_id == ticket.id,
            TicketLabel.label_id == label.id,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="label is not applied to this ticket")
    result = {"id": link.id, "ticket_id": ticket.id, "label_id": label.id,
              "name": label.name, "color": label.color}
    db.delete(link)
    db.flush()
    _publish_on_ticket(
        db, workspace_id, ticket, TICKET_UNLABELED,
        payload={"label_id": label.id, "name": label.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# P1: typed custom attributes (CW-013)
# ---------------------------------------------------------------------------


class AttributeCreate(BaseModel):
    key: str
    label: str
    value_type: Literal["text", "number", "boolean", "date"]
    target: Literal["contact", "ticket", "both"]

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not ATTRIBUTE_KEY.fullmatch(value):
            raise ValueError("key must be lower snake case")
        return value

    @field_validator("label")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label must not be empty")
        return value.strip()


class AttributeOut(BaseModel):
    id: str
    key: str
    label: str
    value_type: str
    target: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class AttributeValueSet(BaseModel):
    entity_type: Literal["contact", "ticket"]
    entity_id: str
    value: Any

    model_config = ConfigDict(extra="forbid")


class AttributeValueOut(BaseModel):
    attribute_id: str
    key: str
    entity_type: str
    entity_id: str
    value: Any


class AttributeExportRow(BaseModel):
    entity_type: str
    entity_id: str
    key: str
    value: Any


def _attribute_out(value: CustomAttributeValue, key: str) -> dict:
    return {"attribute_id": value.attribute_id, "key": key,
            "entity_type": value.entity_type, "entity_id": value.entity_id,
            "value": (value.value or {}).get("value")}


@router.get("/custom-attributes", response_model=list[AttributeOut])
def list_attributes(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CustomAttribute]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(CustomAttribute).where(CustomAttribute.workspace_id == workspace_id)
        .order_by(CustomAttribute.key)
    ).scalars().all()


@router.post(
    "/custom-attributes",
    response_model=AttributeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_attribute(
    workspace_id: str,
    body: AttributeCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> CustomAttribute:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(CustomAttribute.id).where(
            CustomAttribute.workspace_id == workspace_id, CustomAttribute.key == body.key
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="attribute already exists")
    attribute = CustomAttribute(
        id=new_id(), workspace_id=workspace_id, key=body.key, label=body.label,
        value_type=body.value_type, target=body.target,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(attribute)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=ATTRIBUTE_CREATED,
        entity_id=attribute.id,
        payload={"key": attribute.key, "value_type": attribute.value_type,
                 "target": attribute.target},
        actor_id=principal.user.id,
    )
    db.commit()
    return attribute


@router.post("/custom-attributes/{attribute_id}/values", response_model=AttributeValueOut)
def set_attribute_value(
    workspace_id: str,
    attribute_id: str,
    body: AttributeValueSet,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    attribute = _row_or_404(
        db, CustomAttribute, workspace_id, attribute_id, "attribute not found"
    )
    if attribute.target not in (body.entity_type, "both"):
        raise HTTPException(status_code=422, detail="attribute does not target this entity")
    try:
        normalised = _coerce_attribute_value(attribute.value_type, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _entity_is_valid(db, workspace_id, body.entity_type, body.entity_id)
    row = db.execute(
        select(CustomAttributeValue).where(
            CustomAttributeValue.workspace_id == workspace_id,
            CustomAttributeValue.attribute_id == attribute.id,
            CustomAttributeValue.entity_type == body.entity_type,
            CustomAttributeValue.entity_id == body.entity_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = CustomAttributeValue(
            id=new_id(), workspace_id=workspace_id, attribute_id=attribute.id,
            entity_type=body.entity_type, entity_id=body.entity_id,
            value={"value": normalised}, updated_at=now(),
        )
        db.add(row)
    else:
        row.value = {"value": normalised}
        row.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=ATTRIBUTE_SET, entity_id=row.id,
        payload={"attribute_id": attribute.id, "key": attribute.key,
                 "entity_type": body.entity_type, "entity_id": body.entity_id,
                 "value": normalised},
        actor_id=principal.user.id,
    )
    db.commit()
    return _attribute_out(row, attribute.key)


@router.get("/custom-attributes/values", response_model=list[AttributeValueOut])
def list_attribute_values(
    workspace_id: str,
    entity_type: Literal["contact", "ticket"],
    entity_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _entity_is_valid(db, workspace_id, entity_type, entity_id)
    rows = db.execute(
        select(CustomAttributeValue, CustomAttribute.key).join(
            CustomAttribute, CustomAttribute.id == CustomAttributeValue.attribute_id
        ).where(
            CustomAttributeValue.workspace_id == workspace_id,
            CustomAttributeValue.entity_type == entity_type,
            CustomAttributeValue.entity_id == entity_id,
        ).order_by(CustomAttribute.key)
    ).all()
    return [_attribute_out(value, key) for value, key in rows]


@router.get("/custom-attributes/export", response_model=list[AttributeExportRow])
def export_attribute_values(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(CustomAttributeValue, CustomAttribute.key).join(
            CustomAttribute, CustomAttribute.id == CustomAttributeValue.attribute_id
        ).where(CustomAttributeValue.workspace_id == workspace_id)
        .order_by(CustomAttributeValue.entity_type, CustomAttributeValue.entity_id, CustomAttribute.key)
    ).all()
    return [
        {"entity_type": value.entity_type, "entity_id": value.entity_id,
         "key": key, "value": (value.value or {}).get("value")}
        for value, key in rows
    ]


# ---------------------------------------------------------------------------
# P1: contact notes and correlated history (CW-016, CW-017)
# ---------------------------------------------------------------------------


class ContactNoteOut(BaseModel):
    id: str
    contact_id: str
    author_id: str
    body: str
    created_at: object
    internal_only: bool = True


class ContactNoteCreate(BaseModel):
    """Contact note body only: the contact id is validated from the path, never trusted from the body."""

    body: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("note body must not be empty")
        return stripped


class ContactTimelineItemOut(BaseModel):
    seq: int
    id: str
    event_type: str
    entity_id: str | None
    correlation_id: str
    occurred_at: object
    payload: dict


def _contact_or_404(db: Session, workspace_id: str, contact_id: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact


@router.post(
    "/contacts/{contact_id}/notes",
    response_model=ContactNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_contact_support_note(
    workspace_id: str,
    contact_id: str,
    body: ContactNoteCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Create a CRM note for a contact using the path id and verified actor.

    Notes are internal records in the shared notes table; no ticket message,
    outbound message or external delivery is produced (CW-016).
    """
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    note = Note(
        id=new_id(), workspace_id=workspace_id, contact_id=contact_id,
        author_id=principal.user.id, body=body.body, created_at=now(),
    )
    db.add(note)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=NOTE_CREATED, entity_id=note.id,
        payload={"contact_id": contact_id}, actor_id=principal.user.id,
    )
    db.commit()
    return {
        "id": note.id, "contact_id": note.contact_id, "author_id": note.author_id,
        "body": note.body, "created_at": note.created_at, "internal_only": True,
    }


@router.get("/contacts/{contact_id}/notes", response_model=list[ContactNoteOut])
def contact_support_notes(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Internal CRM notes exposed inside the customer inbox. They are never
    sent as messages and keep the verified author from the shared notes API."""
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    notes = db.execute(
        select(Note).where(
            Note.workspace_id == workspace_id, Note.contact_id == contact_id
        ).order_by(Note.created_at, Note.id)
    ).scalars().all()
    return [
        {"id": note.id, "contact_id": note.contact_id, "author_id": note.author_id,
         "body": note.body, "created_at": note.created_at, "internal_only": True}
        for note in notes
    ]


@router.get("/contacts/{contact_id}/timeline", response_model=list[ContactTimelineItemOut])
def contact_support_timeline(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Ticket events correlated to one contact, in append-only order."""
    verify_workspace(principal, workspace_id)
    _contact_or_404(db, workspace_id, contact_id)
    # Only thread-link events create a contact timeline. Other events addressed
    # to the contact (contact.updated, note.created, ...) have their own random
    # correlation id and would otherwise drag unrelated rows into this thread.
    linked = db.execute(
        select(Event.correlation_id).where(
            Event.workspace_id == workspace_id,
            Event.entity_id == contact_id,
            Event.event_type == TICKET_CONTACT_LINKED,
            Event.correlation_id.is_not(None),
        )
    ).scalars().all()
    # Keep only tickets that still belong to this contact in this workspace, so
    # a stale or foreign link can never leak another conversation into the view.
    ticket_ids = [
        ticket_id for ticket_id in dict.fromkeys(linked)
        if db.execute(
            select(Ticket.id).where(
                Ticket.workspace_id == workspace_id,
                Ticket.id == ticket_id,
                Ticket.contact_id == contact_id,
            )
        ).scalar_one_or_none() is not None
    ]
    if not ticket_ids:
        return []
    events = db.execute(
        select(Event).where(
            Event.workspace_id == workspace_id,
            Event.correlation_id.in_(ticket_ids),
        ).order_by(Event.seq)
    ).scalars().all()
    return [
        {"seq": event.seq, "id": event.id, "event_type": event.event_type,
         "entity_id": event.entity_id, "correlation_id": event.correlation_id,
         "occurred_at": event.occurred_at, "payload": event.payload}
        for event in events
    ]


# ---------------------------------------------------------------------------
# CW-166: signed local inbound webhook
# ---------------------------------------------------------------------------

# Local-only shared secret for this module's signed inbound hook. It is a
# documented development/test value, not a production credential; a deployment
# may override it with NOVARA_SUPPORT_WEBHOOK_SECRET. No provider is contacted:
# the signature is checked entirely inside this workspace.
WEBHOOK_SECRET = os.environ.get(
    "NOVARA_SUPPORT_WEBHOOK_SECRET", "novara-local-inbound-webhook-v1"
)
WEBHOOK_TIMESTAMP_HEADER = "X-Timestamp"
WEBHOOK_SIGNATURE_HEADER = "X-Signature"
WEBHOOK_TOLERANCE_SECONDS = 300
WEBHOOK_TICKET_EVENT = "ticket.created"


def _verify_webhook_signature(body: bytes, timestamp: str | None, signature: str | None) -> None:
    """Verify HMAC-SHA256 over ``"<unix timestamp>.<raw body>"``.

    A missing, malformed, stale or forged signature is authentication failure
    (401) and never reaches the write path.
    """
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="missing webhook signature")
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid webhook timestamp") from exc
    if abs(time.time() - sent_at) > WEBHOOK_TOLERANCE_SECONDS:
        raise HTTPException(status_code=401, detail="webhook timestamp outside tolerance")
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), f"{sent_at}.".encode() + body, hashlib.sha256
    ).hexdigest()
    supplied = signature.strip()
    if supplied.startswith("sha256="):
        supplied = supplied[len("sha256="):]
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="invalid webhook signature")


class WebhookTicketOut(BaseModel):
    ticket_id: str
    workspace_id: str
    external_id: str
    created: bool = True


@router.post(
    "/webhooks/inbound",
    response_model=WebhookTicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def inbound_webhook(
    workspace_id: str, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Accept a signed local event and create exactly one local ticket.

    Signature verification, timestamp tolerance and the idempotency key on the
    event spine are all local checks; there is no external send or callback.
    """
    raw = await request.body()
    _verify_webhook_signature(
        raw,
        request.headers.get(WEBHOOK_TIMESTAMP_HEADER),
        request.headers.get(WEBHOOK_SIGNATURE_HEADER),
    )
    if db.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    ).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="webhook body must be JSON") from exc
    if not isinstance(payload, dict) or payload.get("event") != WEBHOOK_TICKET_EVENT:
        raise HTTPException(status_code=422, detail="unsupported webhook event")
    external_id = str(payload.get("external_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    message = str(payload.get("body") or "").strip()
    if not external_id or not subject or not message:
        raise HTTPException(
            status_code=422, detail="external_id, subject and body are required"
        )
    idempotency_key = f"webhook:{WEBHOOK_TICKET_EVENT}:{workspace_id}:{external_id}"
    if db.execute(
        select(Event.id).where(
            Event.workspace_id == workspace_id,
            Event.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="duplicate webhook event")
    ticket = Ticket(
        id=new_id(), workspace_id=workspace_id, subject=subject[:300], body=message,
        status="open", priority="normal", origin_channel="import",
        conversation_type="question", created_at=now(), updated_at=now(),
    )
    try:
        db.add(ticket)
        db.flush()
        publish_event(
            db, workspace_id=workspace_id, event_type=TICKET_CREATED,
            entity_id=ticket.id, correlation_id=ticket.id,
            idempotency_key=idempotency_key,
            payload={"subject": ticket.subject, "external_id": external_id,
                     "source": "webhook", "external_delivery": False},
            actor_id=None,
        )
        db.commit()
    except IntegrityError as exc:
        # The unique event idempotency key is the final replay guard.
        db.rollback()
        raise HTTPException(status_code=409, detail="duplicate webhook event") from exc
    return {
        "ticket_id": ticket.id, "workspace_id": workspace_id,
        "external_id": external_id, "created": True,
    }


# ---------------------------------------------------------------------------
# P1: saved reply expansion and macro execution (CW-023, CW-024)
# ---------------------------------------------------------------------------


class SavedReplyExpand(BaseModel):
    contact_id: str | None = None
    ticket_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class SavedReplyExpandedOut(BaseModel):
    id: str
    name: str
    body: str
    unresolved: list[str]


REPLY_VARIABLE = re.compile(r"\{\{\s*([A-Za-z_.]+)\s*\}\}")


@router.post("/saved-replies/{reply_id}/expand", response_model=SavedReplyExpandedOut)
def expand_saved_reply(
    workspace_id: str,
    reply_id: str,
    body: SavedReplyExpand,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Expand local shortcodes into a reply draft. No message is sent."""
    verify_workspace(principal, workspace_id)
    reply = _row_or_404(db, SavedReply, workspace_id, reply_id, "saved reply not found")
    contact = None
    ticket = None
    if body.contact_id:
        contact = _contact_or_404(db, workspace_id, body.contact_id)
    if body.ticket_id:
        ticket = _ticket_or_404(db, workspace_id, body.ticket_id)
    values = {
        "contact.name": (contact.full_name or contact.email) if contact else "",
        "contact.email": contact.email if contact else "",
        "contact.company": (contact.company_name or "") if contact else "",
        "ticket.subject": ticket.subject if ticket else "",
        "ticket.id": ticket.id if ticket else "",
    }
    unresolved: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return str(values[key])
        unresolved.append(key)
        return match.group(0)

    expanded = REPLY_VARIABLE.sub(substitute, reply.body)
    publish_event(
        db, workspace_id=workspace_id, event_type=SAVED_REPLY_EXPANDED,
        entity_id=reply.id,
        payload={"contact_id": body.contact_id, "ticket_id": body.ticket_id,
                 "unresolved": unresolved, "delivered": False},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": reply.id, "name": reply.name, "body": expanded,
            "unresolved": unresolved}


class MacroRunRequest(BaseModel):
    ticket_id: str

    model_config = ConfigDict(extra="forbid")


class MacroPlanOut(BaseModel):
    macro_id: str
    name: str
    ticket_id: str
    actions: list[dict[str, Any]]
    changes: list[dict[str, Any]]
    dry_run: bool = True


class MacroApplyOut(BaseModel):
    macro_id: str
    ticket_id: str
    changes: list[dict[str, Any]]
    applied: bool = True


def _macro_rows(db: Session, workspace_id: str, macro_id: str, ticket_id: str):
    macro = _row_or_404(db, Macro, workspace_id, macro_id, "macro not found")
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    return macro, ticket


@router.post("/macros/{macro_id}/dry-run", response_model=MacroPlanOut)
def dry_run_macro(
    workspace_id: str,
    macro_id: str,
    body: MacroRunRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    macro, ticket = _macro_rows(db, workspace_id, macro_id, body.ticket_id)
    actions = _parse_actions(macro.actions, MACRO_ACTION_TYPES)
    changes: list[dict[str, Any]] = []
    for action in actions:
        _apply_local_action(
            db, workspace_id, ticket, action, actor_id=principal.user.id,
            changes=changes, dry_run=True, allow_message=True,
        )
    publish_event(
        db, workspace_id=workspace_id, event_type=MACRO_DRY_RUN,
        entity_id=macro.id, correlation_id=ticket.id,
        payload={"ticket_id": ticket.id, "actions": actions, "changes": changes,
                 "mutated": False},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"macro_id": macro.id, "name": macro.name, "ticket_id": ticket.id,
            "actions": actions, "changes": changes, "dry_run": True}


@router.post("/macros/{macro_id}/apply", response_model=MacroApplyOut)
def apply_macro(
    workspace_id: str,
    macro_id: str,
    body: MacroRunRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    macro, ticket = _macro_rows(db, workspace_id, macro_id, body.ticket_id)
    actions = _parse_actions(macro.actions, MACRO_ACTION_TYPES)
    # Validate the entire sequence before the first write: a bad step must not
    # leave a half-applied macro behind.
    for action in actions:
        _apply_local_action(
            db, workspace_id, ticket, action, actor_id=principal.user.id,
            changes=[], dry_run=True, allow_message=True,
        )
    changes: list[dict[str, Any]] = []
    try:
        for action in actions:
            _apply_local_action(
                db, workspace_id, ticket, action, actor_id=principal.user.id,
                changes=changes, dry_run=False, allow_message=True,
            )
        ticket.updated_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=MACRO_APPLIED,
            entity_id=macro.id, correlation_id=ticket.id,
            payload={"ticket_id": ticket.id, "actions": actions, "changes": changes,
                     "external_delivery": False},
            actor_id=principal.user.id,
        )
        db.commit()
    except Exception:
        # The whole macro is one unit: any failure after the first write must
        # leave no partial local changes behind.
        db.rollback()
        raise
    return {"macro_id": macro.id, "ticket_id": ticket.id,
            "changes": changes, "applied": True}


# ---------------------------------------------------------------------------
# P1: multi-inbox routing (CW-048) and auto-assignment (CW-008)
# ---------------------------------------------------------------------------


class InboxCreate(BaseModel):
    name: str
    channel: str = "local"
    slug: str | None = None
    csat_enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value not in TICKET_ORIGINS:
            raise ValueError("invalid inbox channel")
        return value

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", value):
            raise ValueError("slug must be lower case with dashes")
        return value


class InboxOut(BaseModel):
    id: str
    name: str
    channel: str
    slug: str
    csat_enabled: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class InboxAgentAdd(BaseModel):
    user_id: str

    model_config = ConfigDict(extra="forbid")


class InboxAgentOut(BaseModel):
    id: str
    inbox_id: str
    user_id: str
    display_name: str


class InboxPatch(BaseModel):
    csat_enabled: bool

    model_config = ConfigDict(extra="forbid")


@router.get("/inboxes", response_model=list[InboxOut])
def list_inboxes(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SupportInbox]:
    verify_workspace(principal, workspace_id)
    inboxes = db.execute(
        select(SupportInbox).where(SupportInbox.workspace_id == workspace_id)
        .order_by(SupportInbox.name)
    ).scalars().all()
    return [inbox for inbox in inboxes if _inbox_is_permitted(db, principal, inbox)]


@router.post("/inboxes", response_model=InboxOut, status_code=status.HTTP_201_CREATED)
def create_inbox(
    workspace_id: str,
    body: InboxCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SupportInbox:
    verify_workspace(principal, workspace_id)
    slug = body.slug or re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", slug):
        raise HTTPException(status_code=422, detail="inbox name cannot form a slug")
    duplicate = db.execute(
        select(SupportInbox.id).where(
            SupportInbox.workspace_id == workspace_id,
            or_(SupportInbox.name == body.name, SupportInbox.slug == slug),
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="inbox already exists")
    inbox = SupportInbox(
        id=new_id(), workspace_id=workspace_id, name=body.name, channel=body.channel,
        slug=slug, csat_enabled=body.csat_enabled,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(inbox)
    db.flush()
    db.add(InboxAgent(
        id=new_id(), workspace_id=workspace_id, inbox_id=inbox.id,
        user_id=principal.user.id, created_at=now(),
    ))
    publish_event(
        db, workspace_id=workspace_id, event_type=INBOX_CREATED, entity_id=inbox.id,
        payload={"name": inbox.name, "channel": inbox.channel, "slug": inbox.slug},
        actor_id=principal.user.id,
    )
    db.commit()
    return inbox


@router.get("/inboxes/{inbox_id}/agents", response_model=list[InboxAgentOut])
def list_inbox_agents(
    workspace_id: str,
    inbox_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    inbox = _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")
    if not _inbox_is_permitted(db, principal, inbox):
        raise HTTPException(status_code=403, detail="not a member of this inbox")
    rows = db.execute(
        select(InboxAgent, User).join(User, User.id == InboxAgent.user_id).where(
            InboxAgent.workspace_id == workspace_id, InboxAgent.inbox_id == inbox.id
        ).order_by(User.display_name)
    ).all()
    return [
        {"id": agent.id, "inbox_id": agent.inbox_id, "user_id": agent.user_id,
         "display_name": user.display_name}
        for agent, user in rows
    ]


@router.post(
    "/inboxes/{inbox_id}/agents",
    response_model=InboxAgentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_inbox_agent(
    workspace_id: str,
    inbox_id: str,
    body: InboxAgentAdd,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    inbox = _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")
    if not _inbox_is_permitted(db, principal, inbox):
        raise HTTPException(status_code=403, detail="not a member of this inbox")
    if not _active_member(db, workspace_id, body.user_id):
        raise HTTPException(status_code=422, detail="member must be active in this workspace")
    exists = db.execute(
        select(InboxAgent.id).where(
            InboxAgent.workspace_id == workspace_id,
            InboxAgent.inbox_id == inbox.id,
            InboxAgent.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="already an inbox agent")
    agent = InboxAgent(
        id=new_id(), workspace_id=workspace_id, inbox_id=inbox.id,
        user_id=body.user_id, created_at=now(),
    )
    db.add(agent)
    db.flush()
    user = db.get(User, body.user_id)
    publish_event(
        db, workspace_id=workspace_id, event_type=INBOX_AGENT_ADDED, entity_id=agent.id,
        payload={"inbox_id": inbox.id, "user_id": body.user_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": agent.id, "inbox_id": inbox.id, "user_id": user.id,
            "display_name": user.display_name}


@router.patch("/inboxes/{inbox_id}", response_model=InboxOut)
def patch_inbox(
    workspace_id: str,
    inbox_id: str,
    body: InboxPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SupportInbox:
    verify_workspace(principal, workspace_id)
    inbox = _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")
    if not _inbox_is_permitted(db, principal, inbox):
        raise HTTPException(status_code=403, detail="not a member of this inbox")
    inbox.csat_enabled = body.csat_enabled
    publish_event(
        db, workspace_id=workspace_id, event_type=TICKET_UPDATED, entity_id=inbox.id,
        payload={"inbox_id": inbox.id, "csat_enabled": body.csat_enabled},
        actor_id=principal.user.id,
    )
    db.commit()
    return inbox


@router.get("/inboxes/{inbox_id}/tickets", response_model=list[TicketOut])
def inbox_queue(
    workspace_id: str,
    inbox_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    verify_workspace(principal, workspace_id)
    inbox = _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")
    if not _inbox_is_permitted(db, principal, inbox):
        raise HTTPException(status_code=403, detail="not a member of this inbox")
    return db.execute(
        select(Ticket).where(
            Ticket.workspace_id == workspace_id, Ticket.inbox_id == inbox.id
        ).order_by(Ticket.created_at.desc())
    ).scalars().all()


class RoutingRuleCreate(BaseModel):
    name: str
    channel: str = "any"
    strategy: str = "round_robin"
    team_id: str | None = None
    assignee_id: str | None = None
    enabled: bool = True
    priority: int = 100

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        if value != "any" and value not in TICKET_ORIGINS:
            raise ValueError("invalid routing channel")
        return value

    @field_validator("strategy")
    @classmethod
    def valid_strategy(cls, value: str) -> str:
        if value not in ROUTING_STRATEGIES:
            raise ValueError("invalid routing strategy")
        return value


class RoutingRuleOut(BaseModel):
    id: str
    name: str
    channel: str
    strategy: str
    team_id: str | None
    assignee_id: str | None
    enabled: bool
    priority: int
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/routing-rules", response_model=list[RoutingRuleOut])
def list_routing_rules(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[RoutingRule]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(RoutingRule).where(RoutingRule.workspace_id == workspace_id)
        .order_by(RoutingRule.priority, RoutingRule.created_at)
    ).scalars().all()


@router.post(
    "/routing-rules",
    response_model=RoutingRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_routing_rule(
    workspace_id: str,
    body: RoutingRuleCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> RoutingRule:
    verify_workspace(principal, workspace_id)
    _team_is_valid(db, workspace_id, body.team_id)
    if body.assignee_id:
        _assignee_is_valid(db, workspace_id, body.assignee_id)
    exists = db.execute(
        select(RoutingRule.id).where(
            RoutingRule.workspace_id == workspace_id, RoutingRule.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="routing rule already exists")
    rule = RoutingRule(
        id=new_id(), workspace_id=workspace_id, name=body.name, channel=body.channel,
        strategy=body.strategy, team_id=body.team_id, assignee_id=body.assignee_id,
        enabled=body.enabled, priority=body.priority,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(rule)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=ROUTING_RULE_CREATED,
        entity_id=rule.id,
        payload={"name": rule.name, "channel": rule.channel,
                 "strategy": rule.strategy, "team_id": rule.team_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return rule


# ---------------------------------------------------------------------------
# P1: conversation automation rules (CW-051)
# ---------------------------------------------------------------------------


class ConversationRuleCreate(BaseModel):
    name: str
    trigger: str
    actions: list[Any]
    enabled: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("trigger")
    @classmethod
    def valid_trigger(cls, value: str) -> str:
        if value not in RULE_TRIGGERS:
            raise ValueError("unsupported trigger")
        return value


class ConversationRuleOut(BaseModel):
    id: str
    name: str
    trigger: str
    actions: list[dict[str, Any]]
    enabled: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class RuleRunOut(BaseModel):
    id: str
    rule_id: str
    ticket_id: str
    trigger: str
    changes: list[dict[str, Any]]
    actor_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/conversation-rules", response_model=list[ConversationRuleOut])
def list_conversation_rules(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ConversationRule]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ConversationRule).where(ConversationRule.workspace_id == workspace_id)
        .order_by(ConversationRule.created_at)
    ).scalars().all()


@router.post(
    "/conversation-rules",
    response_model=ConversationRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_rule(
    workspace_id: str,
    body: ConversationRuleCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> ConversationRule:
    verify_workspace(principal, workspace_id)
    actions = _parse_actions(body.actions, RULE_ACTION_TYPES)
    exists = db.execute(
        select(ConversationRule.id).where(
            ConversationRule.workspace_id == workspace_id,
            ConversationRule.name == body.name,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="conversation rule already exists")
    rule = ConversationRule(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        trigger=body.trigger, actions=actions, enabled=body.enabled,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(rule)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONVERSATION_RULE_CREATED,
        entity_id=rule.id,
        payload={"trigger": rule.trigger, "actions": actions},
        actor_id=principal.user.id,
    )
    db.commit()
    return rule


@router.get("/conversation-rules/{rule_id}/runs", response_model=list[RuleRunOut])
def list_conversation_rule_runs(
    workspace_id: str,
    rule_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ConversationRuleRun]:
    verify_workspace(principal, workspace_id)
    _row_or_404(db, ConversationRule, workspace_id, rule_id, "conversation rule not found")
    return db.execute(
        select(ConversationRuleRun).where(
            ConversationRuleRun.workspace_id == workspace_id,
            ConversationRuleRun.rule_id == rule_id,
        ).order_by(ConversationRuleRun.created_at, ConversationRuleRun.id)
    ).scalars().all()


@router.post("/conversation-rules/{rule_id}/dry-run", response_model=MacroPlanOut)
def dry_run_conversation_rule(
    workspace_id: str,
    rule_id: str,
    body: MacroRunRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rule = _row_or_404(db, ConversationRule, workspace_id, rule_id, "conversation rule not found")
    ticket = _ticket_or_404(db, workspace_id, body.ticket_id)
    changes: list[dict[str, Any]] = []
    for action in rule.actions:
        _apply_local_action(
            db, workspace_id, ticket, action, actor_id=principal.user.id,
            changes=changes, dry_run=True, allow_message=False,
        )
    publish_event(
        db, workspace_id=workspace_id, event_type=CONVERSATION_RULE_DRY_RUN,
        entity_id=rule.id, correlation_id=ticket.id,
        payload={"ticket_id": ticket.id, "actions": rule.actions,
                 "changes": changes, "mutated": False},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"macro_id": rule.id, "name": rule.name, "ticket_id": ticket.id,
            "actions": rule.actions, "changes": changes, "dry_run": True}


# ---------------------------------------------------------------------------
# P1: saved contact segments (CW-075)
# ---------------------------------------------------------------------------


class SegmentCreate(BaseModel):
    name: str
    definition: dict[str, Any]

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()


class SegmentOut(BaseModel):
    id: str
    name: str
    definition: dict[str, Any]
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SegmentContactOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    lifecycle_stage: str


@router.get("/segments", response_model=list[SegmentOut])
def list_segments(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ContactSegment]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ContactSegment).where(ContactSegment.workspace_id == workspace_id)
        .order_by(ContactSegment.name)
    ).scalars().all()


@router.post("/segments", response_model=SegmentOut, status_code=status.HTTP_201_CREATED)
def create_segment(
    workspace_id: str,
    body: SegmentCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> ContactSegment:
    verify_workspace(principal, workspace_id)
    definition = _validate_segment_definition(body.definition)
    exists = db.execute(
        select(ContactSegment.id).where(
            ContactSegment.workspace_id == workspace_id, ContactSegment.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="segment already exists")
    segment = ContactSegment(
        id=new_id(), workspace_id=workspace_id, name=body.name,
        definition=definition, created_by=principal.user.id, created_at=now(),
    )
    db.add(segment)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=SEGMENT_CREATED, entity_id=segment.id,
        payload={"name": segment.name, "definition": definition},
        actor_id=principal.user.id,
    )
    db.commit()
    return segment


def _segment_matching_contacts(db: Session, workspace_id: str, segment: ContactSegment):
    contacts = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id).order_by(Contact.email)
    ).scalars().all()
    return [c for c in contacts if _segment_matches(db, workspace_id, c, segment.definition)]


@router.get("/segments/{segment_id}/count")
def segment_count(
    workspace_id: str,
    segment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    segment = _row_or_404(db, ContactSegment, workspace_id, segment_id, "segment not found")
    return {"segment_id": segment.id, "count": len(_segment_matching_contacts(db, workspace_id, segment))}


@router.get("/segments/{segment_id}/contacts", response_model=list[SegmentContactOut])
def segment_contacts(
    workspace_id: str,
    segment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    segment = _row_or_404(db, ContactSegment, workspace_id, segment_id, "segment not found")
    return [
        {"id": c.id, "email": c.email, "full_name": c.full_name,
         "lifecycle_stage": c.lifecycle_stage}
        for c in _segment_matching_contacts(db, workspace_id, segment)
    ]


# ---------------------------------------------------------------------------
# P1: help centre / portals (CW-086)
# ---------------------------------------------------------------------------


class PortalCreate(BaseModel):
    name: str
    slug: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", value):
            raise ValueError("slug must be lower case with dashes")
        return value


class PortalOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ArticleCreate(BaseModel):
    title: str
    slug: str
    body: str
    audience: Literal["public", "agents"] = "public"
    status: Literal["draft", "published"] = "draft"

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "body")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,119}", value):
            raise ValueError("slug must be lower case with dashes")
        return value


class ArticlePatch(BaseModel):
    title: str | None = None
    body: str | None = None
    audience: Literal["public", "agents"] | None = None
    status: Literal["draft", "published"] | None = None

    model_config = ConfigDict(extra="forbid")


class ArticleOut(BaseModel):
    id: str
    portal_id: str
    title: str
    slug: str
    body: str
    audience: str
    status: str
    published_at: object
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/help-portals", response_model=list[PortalOut])
def list_help_portals(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[HelpPortal]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(HelpPortal).where(HelpPortal.workspace_id == workspace_id)
        .order_by(HelpPortal.name)
    ).scalars().all()


@router.post("/help-portals", response_model=PortalOut, status_code=status.HTTP_201_CREATED)
def create_help_portal(
    workspace_id: str,
    body: PortalCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> HelpPortal:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(HelpPortal.id).where(
            HelpPortal.workspace_id == workspace_id,
            or_(HelpPortal.name == body.name, HelpPortal.slug == body.slug),
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="portal already exists")
    portal = HelpPortal(
        id=new_id(), workspace_id=workspace_id, name=body.name, slug=body.slug,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(portal)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=HELP_PORTAL_CREATED,
        entity_id=portal.id, payload={"name": portal.name, "slug": portal.slug},
        actor_id=principal.user.id,
    )
    db.commit()
    return portal


@router.get("/help-portals/{portal_id}/articles", response_model=list[ArticleOut])
def list_portal_articles(
    workspace_id: str,
    portal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[HelpArticle]:
    verify_workspace(principal, workspace_id)
    _row_or_404(db, HelpPortal, workspace_id, portal_id, "portal not found")
    return db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id, HelpArticle.portal_id == portal_id
        ).order_by(HelpArticle.title)
    ).scalars().all()


@router.post(
    "/help-portals/{portal_id}/articles",
    response_model=ArticleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_help_article(
    workspace_id: str,
    portal_id: str,
    body: ArticleCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> HelpArticle:
    verify_workspace(principal, workspace_id)
    _row_or_404(db, HelpPortal, workspace_id, portal_id, "portal not found")
    exists = db.execute(
        select(HelpArticle.id).where(
            HelpArticle.workspace_id == workspace_id,
            HelpArticle.portal_id == portal_id,
            HelpArticle.slug == body.slug,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="article slug already exists")
    article = HelpArticle(
        id=new_id(), workspace_id=workspace_id, portal_id=portal_id,
        title=body.title, slug=body.slug, body=body.body,
        audience=body.audience, status=body.status,
        published_at=now() if body.status == "published" else None,
        created_by=principal.user.id, created_at=now(), updated_at=now(),
    )
    db.add(article)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=HELP_ARTICLE_WRITTEN,
        entity_id=article.id,
        payload={"portal_id": portal_id, "status": article.status,
                 "audience": article.audience},
        actor_id=principal.user.id,
    )
    db.commit()
    return article


@router.patch("/help-articles/{article_id}", response_model=ArticleOut)
def patch_help_article(
    workspace_id: str,
    article_id: str,
    body: ArticlePatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> HelpArticle:
    verify_workspace(principal, workspace_id)
    article = _row_or_404(db, HelpArticle, workspace_id, article_id, "article not found")
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in updates.items():
        setattr(article, key, value)
    if updates.get("status") == "published" and article.published_at is None:
        article.published_at = now()
    if updates.get("status") == "draft":
        article.published_at = None
    article.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=HELP_ARTICLE_WRITTEN,
        entity_id=article.id,
        payload={"portal_id": article.portal_id, "status": article.status,
                 "audience": article.audience, "fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return article


@router.get("/help-articles/{article_id}", response_model=ArticleOut)
def get_help_article(
    workspace_id: str,
    article_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> HelpArticle:
    """Authenticated read covers the agents-only audience and draft previews."""
    verify_workspace(principal, workspace_id)
    return _row_or_404(db, HelpArticle, workspace_id, article_id, "article not found")


@router.get("/public/help/{portal_slug}/articles", response_model=list[ArticleOut])
def public_help_articles(
    workspace_id: str,
    portal_slug: str,
    db: Session = Depends(get_db),
) -> list[HelpArticle]:
    """Public portal read: only published public articles are ever returned.
    No bearer is required and no private or draft row can leak through here."""
    portal = db.execute(
        select(HelpPortal).where(
            HelpPortal.workspace_id == workspace_id, HelpPortal.slug == portal_slug
        )
    ).scalar_one_or_none()
    if portal is None:
        raise HTTPException(status_code=404, detail="portal not found")
    # CW-091: private pages must stay invisible to every unauthenticated reader.
    # Imported lazily to keep the two help-centre modules free of an import cycle.
    from .help_centre_governance import PageVisibility

    hidden = select(PageVisibility.article_id).where(
        PageVisibility.workspace_id == workspace_id,
        PageVisibility.visibility == "internal",
    )
    return db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id,
            HelpArticle.portal_id == portal.id,
            HelpArticle.status == "published",
            HelpArticle.audience == "public",
            HelpArticle.id.notin_(hidden),
        ).order_by(HelpArticle.title)
    ).scalars().all()


@router.get("/public/help/{portal_slug}/articles/{article_slug}", response_model=ArticleOut)
def public_help_article(
    workspace_id: str,
    portal_slug: str,
    article_slug: str,
    db: Session = Depends(get_db),
) -> HelpArticle:
    portal = db.execute(
        select(HelpPortal).where(
            HelpPortal.workspace_id == workspace_id, HelpPortal.slug == portal_slug
        )
    ).scalar_one_or_none()
    if portal is None:
        raise HTTPException(status_code=404, detail="portal not found")
    from .help_centre_governance import PageVisibility

    hidden = select(PageVisibility.article_id).where(
        PageVisibility.workspace_id == workspace_id,
        PageVisibility.visibility == "internal",
    )
    article = db.execute(
        select(HelpArticle).where(
            HelpArticle.workspace_id == workspace_id,
            HelpArticle.portal_id == portal.id,
            HelpArticle.slug == article_slug,
            HelpArticle.status == "published",
            HelpArticle.audience == "public",
            HelpArticle.id.notin_(hidden),
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return article


# ---------------------------------------------------------------------------
# P1: support reporting (CW-093, CW-095, CW-100)
# ---------------------------------------------------------------------------


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    a, b = _naive(start), _naive(end)
    if a is None or b is None or b < a:
        return None
    return (b - a).total_seconds() / 60


def _report_range(created_from: str | None, created_to: str | None):
    start, end = _date_filter(created_from, "created_from"), _date_filter(created_to, "created_to")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="created_from must precede created_to")
    return start, end


def _count_by(rows, attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(getattr(row, attribute))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


@router.get("/reports/overview")
def support_overview(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    counts = _queue_counts(db, workspace_id)
    overdue = db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.workspace_id == workspace_id,
            Ticket.status.in_(("open", "pending")),
            Ticket.first_response_due_at.is_not(None),
            Ticket.first_response_due_at < now(),
        )
    ).scalar_one()
    counts.update({
        "teams": db.execute(
            select(func.count(SupportTeam.id)).where(SupportTeam.workspace_id == workspace_id)
        ).scalar_one(),
        "labels": db.execute(
            select(func.count(SupportLabel.id)).where(SupportLabel.workspace_id == workspace_id)
        ).scalar_one(),
        "inboxes": db.execute(
            select(func.count(SupportInbox.id)).where(SupportInbox.workspace_id == workspace_id)
        ).scalar_one(),
        "published_articles": db.execute(
            select(func.count(HelpArticle.id)).where(
                HelpArticle.workspace_id == workspace_id, HelpArticle.status == "published"
            )
        ).scalar_one(),
        "sla_breaches": overdue,
    })
    return counts


@router.get("/reports/conversations")
def conversation_report(
    workspace_id: str,
    created_from: str | None = None,
    created_to: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    start, end = _report_range(created_from, created_to)
    query = select(Ticket).where(Ticket.workspace_id == workspace_id)
    if start:
        query = query.where(Ticket.created_at >= start)
    if end:
        query = query.where(Ticket.created_at <= end)
    tickets = db.execute(query.order_by(Ticket.created_at)).scalars().all()
    ticket_ids = {ticket.id for ticket in tickets}
    messages = db.execute(
        select(TicketMessage).where(TicketMessage.workspace_id == workspace_id)
    ).scalars().all()
    first_responses: list[float] = []
    for ticket in tickets:
        outbound = [
            m for m in messages
            if m.ticket_id == ticket.id and m.direction == "outbound"
        ]
        if outbound:
            first = min(outbound, key=lambda m: _naive(m.created_at) or _naive(ticket.created_at))
            minutes = _minutes_between(ticket.created_at, first.created_at)
            if minutes is not None:
                first_responses.append(minutes)
    resolution_events = db.execute(
        select(Event).where(Event.workspace_id == workspace_id)
    ).scalars().all()
    resolutions: list[float] = []
    for event in resolution_events:
        if event.payload.get("to") != "resolved" or event.entity_id not in ticket_ids:
            continue
        ticket = next(t for t in tickets if t.id == event.entity_id)
        minutes = _minutes_between(ticket.created_at, event.occurred_at)
        if minutes is not None:
            resolutions.append(minutes)
    average = lambda values: round(sum(values) / len(values), 2) if values else None
    return {
        "volume": len(tickets),
        "by_status": _count_by(tickets, "status"),
        "by_channel": _count_by(tickets, "origin_channel"),
        "first_response_minutes": average(first_responses),
        "resolution_minutes": average(resolutions),
        "first_response_samples": len(first_responses),
        "resolution_samples": len(resolutions),
    }


@router.get("/reports/csat")
def csat_report(
    workspace_id: str,
    created_from: str | None = None,
    created_to: str | None = None,
    inbox_id: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    start, end = _report_range(created_from, created_to)
    if inbox_id:
        inbox = _row_or_404(db, SupportInbox, workspace_id, inbox_id, "inbox not found")
        if not _inbox_is_permitted(db, principal, inbox):
            raise HTTPException(status_code=403, detail="not a member of this inbox")
    ticket_query = select(Ticket).where(
        Ticket.workspace_id == workspace_id, Ticket.status.in_(("resolved", "closed"))
    )
    if inbox_id:
        ticket_query = ticket_query.where(Ticket.inbox_id == inbox_id)
    if start:
        ticket_query = ticket_query.where(Ticket.created_at >= start)
    if end:
        ticket_query = ticket_query.where(Ticket.created_at <= end)
    eligible = db.execute(
        select(func.count()).select_from(ticket_query.subquery())
    ).scalar_one()
    score_query = select(Csatscore).join(
        Ticket, Ticket.id == Csatscore.ticket_id
    ).where(
        Csatscore.workspace_id == workspace_id,
        Ticket.workspace_id == workspace_id,
    )
    if inbox_id:
        score_query = score_query.where(Ticket.inbox_id == inbox_id)
    if start:
        score_query = score_query.where(Csatscore.created_at >= start)
    if end:
        score_query = score_query.where(Csatscore.created_at <= end)
    scores = db.execute(score_query.order_by(Csatscore.created_at)).scalars().all()
    average = round(sum(s.score for s in scores) / len(scores), 2) if scores else None
    return {
        "responses": len(scores),
        "eligible_tickets": eligible,
        "average_score": average,
        "response_rate": round(len(scores) / eligible, 4) if eligible else 0.0,
        "comments": [
            {"ticket_id": s.ticket_id, "score": s.score,
             "comment": s.comment, "created_at": s.created_at}
            for s in scores if s.comment
        ],
    }


# ---------------------------------------------------------------------------
# P1: local CSAT surveys (CW-102)
# ---------------------------------------------------------------------------


class CsatSurveyOut(BaseModel):
    id: str
    ticket_id: str
    status: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


@router.get("/csat-surveys", response_model=list[CsatSurveyOut])
def list_csat_surveys(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[CsatSurvey]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(CsatSurvey).where(CsatSurvey.workspace_id == workspace_id)
        .order_by(CsatSurvey.created_at, CsatSurvey.id)
    ).scalars().all()


# This dynamic route stays last: if it were registered before the static
# sub-resources above, a GET to /saved-replies, /macros, /sla-policies and the
# others would be captured as a ticket id and return a misleading 404.
@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    workspace_id: str,
    ticket_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> TicketDetail:
    verify_workspace(principal, workspace_id)
    ticket = _ticket_or_404(db, workspace_id, ticket_id)
    messages = db.execute(
        select(TicketMessage)
        .where(
            TicketMessage.workspace_id == workspace_id,
            TicketMessage.ticket_id == ticket.id,
        )
        .order_by(TicketMessage.created_at)
    ).scalars().all()
    return TicketDetail(
        ticket=TicketOut.model_validate(ticket),
        messages=[MessageOut.model_validate(message) for message in messages],
    )