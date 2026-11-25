"""CRM intelligence: duplicate detection, lead scoring, lifecycle transitions."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, Event, Lead, Task, new_id, now
from ..permissions import (
    CONTACT_READ,
    CONTACT_WRITE,
    EVENT_READ,
    LEAD_READ,
    LEAD_WRITE,
    WORKSPACE_MANAGE,
)

LEAD_SCORED = "lead.scored"
DUPLICATE_DETECTED = "duplicate.detected"
LIFECYCLE_CHANGED = "lifecycle.changed"
register_event_types(LEAD_SCORED, DUPLICATE_DETECTED, LIFECYCLE_CHANGED)

# MT-007 / MT-011 / MT-033 / MT-035 / MT-122 — profile, custom field, scoring,
# stage and anonymization events. All are local audit records.
CONTACT_PROFILE_UPDATED = "contact.profile_updated"
CONTACT_FIELD_DEFINED = "contact.field_defined"
CONTACT_FIELD_UPDATED = "contact.field_updated"
CONTACT_PUBLIC_FIELD_UPDATED = "contact.public_field_updated"
SCORING_RULE_CREATED = "scoring.rule_created"
SCORING_RULE_UPDATED = "scoring.rule_updated"
STAGE_DEFINED = "stage.defined"
STAGE_TRANSITION_RECORDED = "stage.transition_recorded"
CONTACT_ANONYMIZED = "contact.anonymized"
register_event_types(
    CONTACT_PROFILE_UPDATED, CONTACT_FIELD_DEFINED, CONTACT_FIELD_UPDATED,
    CONTACT_PUBLIC_FIELD_UPDATED, SCORING_RULE_CREATED, SCORING_RULE_UPDATED,
    STAGE_DEFINED, STAGE_TRANSITION_RECORDED, CONTACT_ANONYMIZED,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/crm",
    tags=["crm-intelligence"],
)


class DuplicateGroup(BaseModel):
    email: str
    contact_ids: list[str]


class ScoreRequest(BaseModel):
    contact_id: str
    score: int

    model_config = ConfigDict(extra="forbid")


class LifecycleRequest(BaseModel):
    contact_id: str
    stage: str

    model_config = ConfigDict(extra="forbid")


@router.get("/duplicates")
def detect_duplicates(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    # group contacts by email
    from sqlalchemy import func

    groups = db.execute(
        select(Contact.email, func.count(Contact.id))
        .where(Contact.workspace_id == workspace_id)
        .group_by(Contact.email)
        .having(func.count(Contact.id) > 1)
    ).all()
    result = []
    for email, cnt in groups:
        ids = db.execute(
            select(Contact.id).where(Contact.workspace_id == workspace_id, Contact.email == email)
        ).scalars().all()
        result.append({"email": email, "count": int(cnt), "contact_ids": list(ids)})
    return result


@router.post("/score-lead")
def score_lead(
    workspace_id: str,
    body: ScoreRequest,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    from ..models import Lead as _Lead

    lead = db.execute(
        select(_Lead).where(_Lead.workspace_id == workspace_id, _Lead.contact_id == body.contact_id)
    ).scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="lead not found for contact")
    lead.score = body.score
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=LEAD_SCORED,
        entity_id=lead.id, payload={"contact_id": body.contact_id, "score": body.score},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"scored": True, "lead_id": lead.id, "score": lead.score}


@router.post("/lifecycle")
def change_lifecycle(
    workspace_id: str,
    body: LifecycleRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = db.execute(
        select(Contact).where(Contact.id == body.contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    old = contact.lifecycle_stage
    contact.lifecycle_stage = body.stage
    contact.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=LIFECYCLE_CHANGED,
        entity_id=contact.id, payload={"from": old, "to": body.stage},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"changed": True, "contact_id": contact.id, "stage": contact.lifecycle_stage}


@router.get("/lead-scoring-model")
def lead_scoring_model(workspace_id: str, principal: Principal = Depends(require(CONTACT_READ)), db: Session = Depends(get_db)) -> dict:
    verify_workspace(principal, workspace_id)
    # Simple heuristic model description (not fabricated data)
    return {
        "factors": [
            {"name": "email_present", "weight": 10},
            {"name": "company_present", "weight": 15},
            {"name": "phone_present", "weight": 10},
            {"name": "tags_count", "weight": 5},
        ],
        "max_score": 100,
    }


# ---------------------------------------------------------------------------
# MT-011 — configurable custom contact fields
# ---------------------------------------------------------------------------

FIELD_TYPES = ("text", "email", "number", "date", "boolean", "select")
FIELD_OPERATORS = ("equals", "contains", "present")
RESERVED_FIELD_KEYS = frozenset({"email", "full_name", "phone", "company_name", "lifecycle_stage", "tags"})
PUBLIC_FIELD_SECRET = os.getenv("NOVARA_PUBLIC_FIELD_SECRET", "novara-dev-public-field-secret").encode("utf-8")
PUBLIC_FIELD_TTL = 60 * 60 * 24 * 30


class ContactFieldDefinition(Base):
    __tablename__ = "contact_field_definitions"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_contact_field_ws_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    public_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class FieldDefinitionCreate(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    public_update: bool = False
    options: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", value or "") or value in RESERVED_FIELD_KEYS:
            raise ValueError("invalid or reserved field key")
        return value

    @field_validator("label")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field label is required")
        return value

    @field_validator("type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value not in FIELD_TYPES:
            raise ValueError("unsupported field type")
        return value

    @field_validator("options")
    @classmethod
    def valid_options(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("options must be non-empty strings")
        return value


class FieldDefinitionPatch(BaseModel):
    label: str | None = None
    required: bool | None = None
    public_update: bool | None = None
    options: list[str] | None = None
    active: bool | None = None

    model_config = ConfigDict(extra="forbid")


class FieldDefinitionOut(BaseModel):
    id: str
    workspace_id: str
    key: str
    label: str
    field_type: str
    required: bool
    public_update: bool
    options: list[str]
    active: bool
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class PublicFieldUpdate(BaseModel):
    token: str
    values: dict

    model_config = ConfigDict(extra="forbid")


def _public_field_token(workspace_id: str, contact_id: str) -> str:
    expires = int(time.time()) + PUBLIC_FIELD_TTL
    payload = f"cfield:{workspace_id}:{contact_id}:{expires}"
    signature = hmac.new(PUBLIC_FIELD_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _verify_public_field_token(token: str, workspace_id: str, contact_id: str) -> bool:
    parts = token.split(":")
    if len(parts) != 5 or parts[:3] != ["cfield", workspace_id, contact_id]:
        return False
    expected = hmac.new(
        PUBLIC_FIELD_SECRET, ":".join(parts[:4]).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, parts[4]):
        return False
    try:
        return int(parts[3]) >= int(time.time())
    except ValueError:
        return False


def _definition_or_404(db: Session, workspace_id: str, definition_id: str) -> ContactFieldDefinition:
    definition = db.execute(
        select(ContactFieldDefinition).where(
            ContactFieldDefinition.id == definition_id,
            ContactFieldDefinition.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="field definition not found")
    return definition


def _validate_field_values(
    db: Session,
    workspace_id: str,
    values: dict,
    *,
    public_only: bool = False,
) -> dict:
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="values must be an object")
    definitions = {
        row.key: row for row in db.execute(
            select(ContactFieldDefinition).where(
                ContactFieldDefinition.workspace_id == workspace_id,
                ContactFieldDefinition.active.is_(True),
            )
        ).scalars().all()
    }
    unknown = set(values) - set(definitions)
    if unknown:
        raise HTTPException(status_code=422, detail="unknown custom field")
    for key, definition in definitions.items():
        value = values.get(key)
        empty = value is None or (isinstance(value, str) and not value.strip())
        if definition.required and empty:
            raise HTTPException(status_code=422, detail=f"field {key} is required")
        if empty:
            continue
        if public_only and not definition.public_update:
            raise HTTPException(status_code=422, detail=f"field {key} is not publicly updatable")
        kind = definition.field_type
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
            if value not in definition.options:
                raise HTTPException(status_code=422, detail=f"field {key} is not an allowed option")
        elif not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"field {key} must be text")
    return dict(values)


@router.post("/contact-fields", response_model=FieldDefinitionOut, status_code=status.HTTP_201_CREATED)
def define_contact_field(
    workspace_id: str,
    body: FieldDefinitionCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ContactFieldDefinition:
    verify_workspace(principal, workspace_id)
    if body.type == "select" and not body.options:
        raise HTTPException(status_code=422, detail="select fields need options")
    if body.type != "select" and body.options:
        raise HTTPException(status_code=422, detail="only select fields take options")
    exists = db.execute(
        select(ContactFieldDefinition.id).where(
            ContactFieldDefinition.workspace_id == workspace_id,
            ContactFieldDefinition.key == body.key,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="field key already defined")
    definition = ContactFieldDefinition(
        id=new_id(), workspace_id=workspace_id, key=body.key, label=body.label,
        field_type=body.type, required=body.required, public_update=body.public_update,
        options=body.options, active=True, created_by=principal.user.id, created_at=now(),
    )
    db.add(definition)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_FIELD_DEFINED,
        entity_id=definition.id,
        payload={"key": definition.key, "type": definition.field_type,
                 "required": definition.required, "public_update": definition.public_update},
        actor_id=principal.user.id,
    )
    db.commit()
    return definition


@router.get("/contact-fields", response_model=list[FieldDefinitionOut])
def list_contact_fields(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ContactFieldDefinition]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ContactFieldDefinition).where(ContactFieldDefinition.workspace_id == workspace_id)
        .order_by(ContactFieldDefinition.key)
    ).scalars().all()


@router.patch("/contact-fields/{definition_id}", response_model=FieldDefinitionOut)
def update_contact_field(
    workspace_id: str,
    definition_id: str,
    body: FieldDefinitionPatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> ContactFieldDefinition:
    verify_workspace(principal, workspace_id)
    definition = _definition_or_404(db, workspace_id, definition_id)
    updates = body.model_dump(exclude_unset=True)
    if "options" in updates and updates["options"] is not None:
        if any(not isinstance(item, str) or not item.strip() for item in updates["options"]):
            raise HTTPException(status_code=422, detail="invalid options")
    if definition.field_type != "select" and updates.get("options"):
        raise HTTPException(status_code=422, detail="only select fields take options")
    for key, value in updates.items():
        setattr(definition, key, value)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_FIELD_UPDATED,
        entity_id=definition.id, payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return definition


@router.get("/contact-fields/public-token")
def contact_field_public_token(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """Signed capability that lets a contact update only public_update fields."""
    verify_workspace(principal, workspace_id)
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return {"token": _public_field_token(workspace_id, contact.id), "contact_id": contact.id}


@router.post("/contact-fields/public-update")
def public_update_contact_fields(
    workspace_id: str,
    body: PublicFieldUpdate,
    db: Session = Depends(get_db),
) -> dict:
    if not _verify_public_field_token(body.token, workspace_id, body.token.split(":")[2] if body.token.count(":") == 4 else ""):
        raise HTTPException(status_code=400, detail="invalid or expired field token")
    contact_id = body.token.split(":")[2]
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    values = _validate_field_values(db, workspace_id, body.values, public_only=True)
    custom = dict(contact.custom_fields or {})
    custom.update(values)
    contact.custom_fields = custom
    contact.updated_at = now()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_PUBLIC_FIELD_UPDATED,
        entity_id=contact.id, payload={"fields": sorted(values)},
        actor_id=None,
    )
    db.commit()
    return {"updated": True, "contact_id": contact.id, "fields": sorted(values)}


# ---------------------------------------------------------------------------
# MT-007 — documented contact profile, lifecycle and search behaviours
# ---------------------------------------------------------------------------


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    tags: list[str] | None = None
    custom_fields: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 20 or any(not isinstance(tag, str) or not tag.strip() for tag in value):
            raise ValueError("invalid tags")
        return [tag.strip() for tag in value]


def _contact_or_404(db: Session, workspace_id: str, contact_id: str) -> Contact:
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact


def _profile(contact: Contact) -> dict:
    return {
        "id": contact.id, "workspace_id": contact.workspace_id, "email": contact.email,
        "full_name": contact.full_name, "phone": contact.phone,
        "company_name": contact.company_name, "source": contact.source,
        "lifecycle_stage": contact.lifecycle_stage, "tags": contact.tags or [],
        "custom_fields": contact.custom_fields or {}, "archived": contact.archived,
        "created_at": contact.created_at, "updated_at": contact.updated_at,
    }


@router.get("/contact-profiles/search")
def search_contact_profiles(
    workspace_id: str,
    query: str | None = Query(None),
    field_key: str | None = Query(None),
    field_value: str | None = Query(None),
    tag: str | None = Query(None),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    statement = select(Contact).where(Contact.workspace_id == workspace_id)
    if query is not None:
        term = f"%{query.strip()}%" if query.strip() else "%"
        statement = statement.where(or_(
            Contact.email.like(term), Contact.full_name.like(term), Contact.phone.like(term)
        ))
    if field_key is not None:
        definition = db.execute(
            select(ContactFieldDefinition.id).where(
                ContactFieldDefinition.workspace_id == workspace_id,
                ContactFieldDefinition.key == field_key,
                ContactFieldDefinition.active.is_(True),
            )
        ).scalar_one_or_none()
        if definition is None:
            raise HTTPException(status_code=422, detail="unknown custom field")
        if field_value is None:
            statement = statement.where(Contact.custom_fields[field_key].isnot(None))
        else:
            # SQLAlchemy 2 removed the 1.x ``.astext`` comparator. ``as_string()``
            # is the portable equivalent: on SQLite it compiles to
            # CAST(JSON_EXTRACT(custom_fields, '$.key') AS VARCHAR), and on
            # PostgreSQL to CAST(custom_fields ->> 'key' AS VARCHAR). The ->>
            # operator returns unquoted text for JSON strings on PostgreSQL, so
            # string values compare identically on both backends; JSON numbers
            # and booleans compare via their scalar text representation.
            statement = statement.where(
                Contact.custom_fields[field_key].as_string() == field_value
            )
    if tag is not None:
        rows = db.execute(statement.order_by(Contact.email)).scalars().all()
        return [_profile(row) for row in rows if tag in (row.tags or [])]
    return [_profile(row) for row in db.execute(statement.order_by(Contact.email)).scalars().all()]


@router.get("/contact-profiles/{contact_id}")
def get_contact_profile(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    return _profile(_contact_or_404(db, workspace_id, contact_id))


@router.patch("/contact-profiles/{contact_id}")
def update_contact_profile(
    workspace_id: str,
    contact_id: str,
    body: ProfileUpdate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    updates = body.model_dump(exclude_unset=True)
    if "custom_fields" in updates:
        updates["custom_fields"] = _validate_field_values(db, workspace_id, updates["custom_fields"] or {})
        custom = dict(contact.custom_fields or {})
        custom.update(updates["custom_fields"])
        updates["custom_fields"] = custom
    for key, value in updates.items():
        setattr(contact, key, value)
    contact.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_PROFILE_UPDATED,
        entity_id=contact.id, payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return _profile(contact)


# ---------------------------------------------------------------------------
# MT-033 — configurable scoring rules with point-change history
# ---------------------------------------------------------------------------

SCORING_FIELDS = ("email_present", "company_present", "phone_present", "tag", "lifecycle_stage", "custom_field")


class ScoringRule(Base):
    __tablename__ = "scoring_rules"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_scoring_rule_ws_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str | None] = mapped_column(String(200))
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ScoreChange(Base):
    __tablename__ = "score_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    rule_id: Mapped[str | None] = mapped_column(String(36))
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    score_before: Mapped[int] = mapped_column(Integer, nullable=False)
    score_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ScoringRuleCreate(BaseModel):
    name: str
    field: str
    operator: str = "equals"
    value: str | None = None
    points: int

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rule name is required")
        return value

    @field_validator("points")
    @classmethod
    def bounded(cls, value: int) -> int:
        if value == 0 or abs(value) > 100:
            raise ValueError("points must be between -100 and 100 and non-zero")
        return value


class ScoringRulePatch(BaseModel):
    points: int | None = None
    active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("points")
    @classmethod
    def bounded(cls, value: int | None) -> int | None:
        if value is not None and (value == 0 or abs(value) > 100):
            raise ValueError("points must be between -100 and 100 and non-zero")
        return value


class ApplyScoreRequest(BaseModel):
    contact_id: str

    model_config = ConfigDict(extra="forbid")


def _validate_rule_fields(values: dict) -> None:
    field, operator, value = values.get("field"), values.get("operator"), values.get("value")
    if field not in SCORING_FIELDS:
        raise HTTPException(status_code=422, detail="unsupported scoring field")
    if operator not in FIELD_OPERATORS:
        raise HTTPException(status_code=422, detail="unsupported scoring operator")
    if field in ("email_present", "company_present", "phone_present"):
        if operator != "present" or value:
            raise HTTPException(status_code=422, detail="presence fields use the present operator")
    elif operator == "present":
        if value:
            raise HTTPException(status_code=422, detail="present operator takes no value")
    elif not value or not value.strip():
        raise HTTPException(status_code=422, detail="rule value is required")


def _rule_matches(rule: ScoringRule, contact: Contact) -> bool:
    if rule.field == "email_present":
        return bool(contact.email)
    if rule.field == "company_present":
        return bool(contact.company_name or contact.company_id)
    if rule.field == "phone_present":
        return bool(contact.phone)
    if rule.field == "tag":
        actual = " ".join(contact.tags or [])
    elif rule.field == "lifecycle_stage":
        actual = contact.lifecycle_stage or ""
    else:
        key, _, expected = (rule.value or "").partition("=")
        if not key:
            return False
        actual = str((contact.custom_fields or {}).get(key, ""))
        if rule.operator == "present":
            return bool(actual)
        if rule.operator == "contains":
            return expected in actual
        return actual == expected
    if rule.operator == "present":
        return bool(actual)
    if rule.operator == "contains":
        return (rule.value or "") in actual
    return actual == rule.value


@router.post("/scoring-rules", status_code=status.HTTP_201_CREATED)
def create_scoring_rule(
    workspace_id: str,
    body: ScoringRuleCreate,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    payload = body.model_dump()
    _validate_rule_fields(payload)
    exists = db.execute(
        select(ScoringRule.id).where(
            ScoringRule.workspace_id == workspace_id, ScoringRule.name == body.name
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="scoring rule name already exists")
    rule = ScoringRule(
        id=new_id(), workspace_id=workspace_id, name=body.name, field=body.field,
        operator=body.operator, value=body.value, points=body.points,
        active=True, created_by=principal.user.id, created_at=now(),
    )
    db.add(rule)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=SCORING_RULE_CREATED,
        entity_id=rule.id,
        payload={"field": rule.field, "points": rule.points, "operator": rule.operator},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": rule.id, "name": rule.name, "field": rule.field, "operator": rule.operator,
            "value": rule.value, "points": rule.points, "active": rule.active}


@router.get("/scoring-rules")
def list_scoring_rules(
    workspace_id: str,
    principal: Principal = Depends(require(LEAD_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rules = db.execute(
        select(ScoringRule).where(ScoringRule.workspace_id == workspace_id)
        .order_by(ScoringRule.name)
    ).scalars().all()
    return [{"id": r.id, "name": r.name, "field": r.field, "operator": r.operator,
             "value": r.value, "points": r.points, "active": r.active} for r in rules]


@router.patch("/scoring-rules/{rule_id}")
def update_scoring_rule(
    workspace_id: str,
    rule_id: str,
    body: ScoringRulePatch,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rule = db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id, ScoringRule.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="scoring rule not found")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=SCORING_RULE_UPDATED,
        entity_id=rule.id, payload={"fields": sorted(updates.keys())},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"id": rule.id, "points": rule.points, "active": rule.active}


@router.post("/scoring/apply")
def apply_scoring_rules(
    workspace_id: str,
    body: ApplyScoreRequest,
    principal: Principal = Depends(require(LEAD_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, body.contact_id)
    lead = db.execute(
        select(Lead).where(Lead.workspace_id == workspace_id, Lead.contact_id == contact.id)
    ).scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="lead not found for contact")
    # Apply rules in definition order, not alphabetical order: the audit trail
    # must show a cumulative running score in the order the rules were created.
    rules = db.execute(
        select(ScoringRule).where(
            ScoringRule.workspace_id == workspace_id, ScoringRule.active.is_(True)
        ).order_by(ScoringRule.created_at, ScoringRule.id)
    ).scalars().all()
    before = int(lead.score or 0)
    score = before
    matched: list[dict] = []
    for rule in rules:
        if not _rule_matches(rule, contact):
            continue
        previous = score
        score += rule.points
        db.add(ScoreChange(
            id=new_id(), workspace_id=workspace_id, contact_id=contact.id, lead_id=lead.id,
            rule_id=rule.id, points=rule.points, score_before=previous, score_after=score,
            reason=rule.name, actor_id=principal.user.id, created_at=now(),
        ))
        matched.append({"rule_id": rule.id, "name": rule.name, "points": rule.points})
    lead.score = score
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=LEAD_SCORED,
        entity_id=lead.id,
        payload={"contact_id": contact.id, "score_before": before, "score_after": score,
                 "matched": matched},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"lead_id": lead.id, "score_before": before, "score": score, "matched": matched}


@router.get("/scoring/history")
def list_score_history(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(LEAD_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    rows = db.execute(
        select(ScoreChange).where(
            ScoreChange.workspace_id == workspace_id, ScoreChange.contact_id == contact.id
        ).order_by(ScoreChange.created_at, ScoreChange.score_before)
    ).scalars().all()
    return [
        {"id": row.id, "rule_id": row.rule_id, "points": row.points,
         "score_before": row.score_before, "score_after": row.score_after,
         "reason": row.reason, "actor_id": row.actor_id, "created_at": row.created_at}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# MT-035 — defined lifecycle stages with guarded transitions and history
# ---------------------------------------------------------------------------


class StageDefinition(Base):
    __tablename__ = "stage_definitions"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_stage_definition_ws_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allowed_next: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class StageHistory(Base):
    __tablename__ = "stage_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    from_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class StageCreate(BaseModel):
    key: str
    label: str
    position: int = Field(default=0, ge=0, le=1000)
    allowed_next: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", value or ""):
            raise ValueError("stage key must be snake_case")
        return value

    @field_validator("label")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("stage label is required")
        return value


class StagesDefineRequest(BaseModel):
    stages: list[StageCreate]

    model_config = ConfigDict(extra="forbid")

    @field_validator("stages")
    @classmethod
    def not_empty(cls, value: list[StageCreate]) -> list[StageCreate]:
        if not value or len({stage.key for stage in value}) != len(value):
            raise ValueError("stages must be unique and non-empty")
        return value


class StageTransitionRequest(BaseModel):
    contact_id: str
    to_stage: str
    reason: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("to_stage", "reason")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


@router.post("/stages")
def define_stages(
    workspace_id: str,
    body: StagesDefineRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    declared = {stage.key for stage in body.stages}
    existing = set(db.execute(
        select(StageDefinition.key).where(StageDefinition.workspace_id == workspace_id)
    ).scalars().all())
    known = declared | existing
    for stage in body.stages:
        if set(stage.allowed_next) - known:
            raise HTTPException(status_code=422, detail="transition target is not a defined stage")
    result = []
    for stage in body.stages:
        definition = db.execute(
            select(StageDefinition).where(
                StageDefinition.workspace_id == workspace_id, StageDefinition.key == stage.key
            )
        ).scalar_one_or_none()
        if definition is None:
            definition = StageDefinition(
                id=new_id(), workspace_id=workspace_id, key=stage.key,
                label=stage.label, position=stage.position, allowed_next=stage.allowed_next,
                created_by=principal.user.id, created_at=now(),
            )
            db.add(definition)
        else:
            definition.label = stage.label
            definition.position = stage.position
            definition.allowed_next = stage.allowed_next
        db.flush()
        publish_event(
            db, workspace_id=workspace_id, event_type=STAGE_DEFINED,
            entity_id=definition.id,
            payload={"key": definition.key, "allowed_next": definition.allowed_next},
            actor_id=principal.user.id,
        )
        result.append({"id": definition.id, "key": definition.key, "label": definition.label,
                       "position": definition.position, "allowed_next": definition.allowed_next})
    db.commit()
    return result


@router.get("/stages")
def list_stages(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(StageDefinition).where(StageDefinition.workspace_id == workspace_id)
        .order_by(StageDefinition.position, StageDefinition.key)
    ).scalars().all()
    return [{"id": row.id, "key": row.key, "label": row.label, "position": row.position,
             "allowed_next": row.allowed_next} for row in rows]


@router.post("/stages/transition")
def transition_stage(
    workspace_id: str,
    body: StageTransitionRequest,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, body.contact_id)
    source = contact.lifecycle_stage or "lead"
    definition = db.execute(
        select(StageDefinition).where(
            StageDefinition.workspace_id == workspace_id, StageDefinition.key == source
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=422, detail="current stage is not configured")
    target = db.execute(
        select(StageDefinition.id).where(
            StageDefinition.workspace_id == workspace_id, StageDefinition.key == body.to_stage
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=422, detail="unknown target stage")
    if body.to_stage not in definition.allowed_next:
        raise HTTPException(status_code=409, detail="transition is not allowed")
    history = StageHistory(
        id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
        from_stage=source, to_stage=body.to_stage, reason=body.reason,
        actor_id=principal.user.id, created_at=now(),
    )
    db.add(history)
    contact.lifecycle_stage = body.to_stage
    contact.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=LIFECYCLE_CHANGED,
        entity_id=contact.id,
        payload={"from": source, "to": body.to_stage, "reason": body.reason},
        actor_id=principal.user.id,
    )
    publish_event(
        db, workspace_id=workspace_id, event_type=STAGE_TRANSITION_RECORDED,
        entity_id=history.id,
        payload={"contact_id": contact.id, "from": source, "to": body.to_stage},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"contact_id": contact.id, "from": source, "stage": body.to_stage, "history_id": history.id}


@router.get("/stages/history")
def list_stage_history(
    workspace_id: str,
    contact_id: str = Query(...),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    rows = db.execute(
        select(StageHistory).where(
            StageHistory.workspace_id == workspace_id, StageHistory.contact_id == contact.id
        ).order_by(StageHistory.created_at)
    ).scalars().all()
    return [
        {"id": row.id, "from": row.from_stage, "to": row.to_stage,
         "reason": row.reason, "actor_id": row.actor_id, "created_at": row.created_at}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# MT-122 — contact anonymization that keeps the audit trail intact
# ---------------------------------------------------------------------------


class ContactAnonymization(Base):
    __tablename__ = "contact_anonymizations"
    __table_args__ = (UniqueConstraint("workspace_id", "contact_id", name="uq_anonymization_contact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fields_masked: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class AnonymizeRequest(BaseModel):
    reason: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5 or len(value) > 500:
            raise ValueError("a meaningful reason is required")
        return value


@router.post("/contacts/{contact_id}/anonymize")
def anonymize_contact(
    workspace_id: str,
    contact_id: str,
    body: AnonymizeRequest,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    existing = db.execute(
        select(ContactAnonymization.id).where(
            ContactAnonymization.workspace_id == workspace_id,
            ContactAnonymization.contact_id == contact.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="contact is already anonymized")
    fields = ["email", "full_name", "phone", "company_name", "custom_fields", "tags"]
    email_hash = hashlib.sha256(f"{workspace_id}:{contact.email}".encode("utf-8")).hexdigest()
    event_count = db.execute(
        select(func.count(Event.id)).where(
            Event.workspace_id == workspace_id, Event.entity_id == contact.id
        )
    ).scalar() or 0
    anonymization = ContactAnonymization(
        id=new_id(), workspace_id=workspace_id, contact_id=contact.id,
        email_hash=email_hash, fields_masked=fields, reason=body.reason,
        actor_id=principal.user.id, created_at=now(),
    )
    db.add(anonymization)
    contact.email = f"anon+{contact.id}@invalid.local"
    contact.full_name = "Anonymized contact"
    contact.phone = None
    contact.company_name = None
    contact.custom_fields = {}
    contact.tags = []
    contact.archived = True
    contact.updated_at = now()
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=CONTACT_ANONYMIZED,
        entity_id=contact.id,
        payload={"fields_masked": fields, "reason": body.reason,
                 "email_hash_prefix": email_hash[:12], "events_preserved": int(event_count)},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "contact_id": contact.id, "anonymized": True, "fields_masked": fields,
        "events_preserved": int(event_count), "record_id": anonymization.id,
    }


@router.get("/contacts/{contact_id}/anonymization")
def get_contact_anonymization(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    contact = _contact_or_404(db, workspace_id, contact_id)
    record = db.execute(
        select(ContactAnonymization).where(
            ContactAnonymization.workspace_id == workspace_id,
            ContactAnonymization.contact_id == contact.id,
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="contact has not been anonymized")
    return {
        "id": record.id, "contact_id": record.contact_id, "fields_masked": record.fields_masked,
        "reason": record.reason, "actor_id": record.actor_id, "created_at": record.created_at,
    }
