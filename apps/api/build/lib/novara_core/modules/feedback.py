"""Feedback and surveys module — reference implementation for all modules.

Copy this structure exactly for other modules:
  * module-owned SQLAlchemy tables importing Base from ..database
  * register_event_types(...) at import time
  * one APIRouter named `router`, prefix includes {workspace_id}
  * every endpoint: verify_workspace(...) then a `require(...)` dependency
  * every mutation: publish_event(...) with actor_id=principal.user.id
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from pydantic import BaseModel, ConfigDict, field_validator

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

SURVEY_CREATED = "survey.created"
SURVEY_UPDATED = "survey.updated"
SURVEY_STATUS_CHANGED = "survey.status_changed"
SURVEY_RESPONSE_CREATED = "survey.response_created"
SURVEY_STATUSES = ("draft", "active", "closed")
register_event_types(
    SURVEY_CREATED, SURVEY_UPDATED, SURVEY_STATUS_CHANGED, SURVEY_RESPONSE_CREATED
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/surveys",
    tags=["feedback"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_survey_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    score: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class SurveyCreate(BaseModel):
    name: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class SurveyUpdate(BaseModel):
    """Lifecycle and metadata changes for one existing survey."""

    name: str | None = None
    description: str | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class SurveyOut(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class ResponseCreate(BaseModel):
    contact_id: str | None = None
    score: int | None = None
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("score")
    @classmethod
    def score_in_range(cls, value: int | None) -> int | None:
        """FB-087: reject out-of-range scores before any row is written."""
        if value is not None and not 1 <= value <= 10:
            raise ValueError("score must be between 1 and 10")
        return value


class ResponseOut(BaseModel):
    id: str
    survey_id: str
    contact_id: str | None
    score: int | None
    comment: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SurveyDetail(BaseModel):
    survey: SurveyOut
    response_count: int
    average_score: float | None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _survey_or_404(db: Session, workspace_id: str, survey_id: str) -> Survey:
    survey = db.execute(
        select(Survey).where(Survey.id == survey_id, Survey.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if survey is None:
        raise HTTPException(status_code=404, detail="survey not found")
    return survey


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[SurveyOut])
def list_surveys(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Survey]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Survey).where(Survey.workspace_id == workspace_id).order_by(Survey.created_at.desc())
    ).scalars().all()


@router.post("", response_model=SurveyOut, status_code=status.HTTP_201_CREATED)
def create_survey(
    workspace_id: str,
    body: SurveyCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Survey:
    verify_workspace(principal, workspace_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="survey name is required")
    exists = db.execute(
        select(Survey).where(Survey.workspace_id == workspace_id, Survey.name == name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="a survey with this name already exists")
    survey = Survey(
        id=new_id(),
        workspace_id=workspace_id,
        name=name,
        description=body.description,
        status="draft",
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(survey)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=SURVEY_CREATED,
        entity_id=survey.id,
        payload={"name": survey.name},
        actor_id=principal.user.id,
    )
    db.commit()
    return survey


@router.get("/{survey_id}", response_model=SurveyDetail)
def get_survey(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> SurveyDetail:
    verify_workspace(principal, workspace_id)
    survey = _survey_or_404(db, workspace_id, survey_id)
    response_scope = (
        SurveyResponse.workspace_id == workspace_id,
        SurveyResponse.survey_id == survey.id,
    )
    result = db.execute(
        select(func.count()).select_from(SurveyResponse).where(*response_scope)
    ).scalar()
    average = db.execute(
        select(func.avg(SurveyResponse.score)).where(*response_scope)
    ).scalar()
    return SurveyDetail(
        survey=SurveyOut.model_validate(survey),
        response_count=result,
        average_score=round(float(average), 2) if average is not None else None,
    )


@router.patch("/{survey_id}", response_model=SurveyOut)
def update_survey(
    workspace_id: str,
    survey_id: str,
    body: SurveyUpdate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> Survey:
    verify_workspace(principal, workspace_id)
    survey = _survey_or_404(db, workspace_id, survey_id)
    if body.name is None and body.description is None and body.status is None:
        raise HTTPException(status_code=422, detail="name, description or status is required")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="survey name is required")
        duplicate = db.execute(
            select(Survey).where(
                Survey.workspace_id == workspace_id,
                Survey.name == name,
                Survey.id != survey.id,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="a survey with this name already exists")
        survey.name = name
    if body.description is not None:
        survey.description = body.description
    status_changed = body.status is not None and body.status != survey.status
    if status_changed:
        if body.status not in SURVEY_STATUSES:
            raise HTTPException(status_code=422, detail="invalid survey status")
        survey.status = body.status
    changes: dict[str, object] = {}
    if body.name is not None:
        changes["name"] = survey.name
    if body.description is not None:
        changes["description"] = survey.description
    if status_changed:
        changes["status"] = survey.status
    if changes:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=SURVEY_STATUS_CHANGED if status_changed else SURVEY_UPDATED,
            entity_id=survey.id,
            payload={"changes": changes},
            actor_id=principal.user.id,
        )
        db.commit()
    return survey


@router.get("/{survey_id}/responses", response_model=list[ResponseOut])
def list_responses(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[SurveyResponse]:
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return db.execute(
        select(SurveyResponse)
        .where(SurveyResponse.workspace_id == workspace_id, SurveyResponse.survey_id == survey_id)
        .order_by(SurveyResponse.created_at)
    ).scalars().all()


@router.post("/{survey_id}/responses", response_model=ResponseOut, status_code=status.HTTP_201_CREATED)
def add_response(
    workspace_id: str,
    survey_id: str,
    body: ResponseCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> SurveyResponse:
    verify_workspace(principal, workspace_id)
    survey = _survey_or_404(db, workspace_id, survey_id)
    if survey.status == "closed":
        raise HTTPException(status_code=409, detail="survey is closed to new responses")
    if body.contact_id is not None:
        valid_contact = db.execute(
            select(Contact.id).where(
                Contact.id == body.contact_id, Contact.workspace_id == workspace_id
            )
        ).scalar_one_or_none()
        if valid_contact is None:
            raise HTTPException(status_code=422, detail="contact not found in this workspace")
    score = body.score
    response = SurveyResponse(
        id=new_id(),
        workspace_id=workspace_id,
        survey_id=survey.id,
        contact_id=body.contact_id,
        score=score,
        comment=body.comment,
        created_at=now(),
    )
    db.add(response)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=SURVEY_RESPONSE_CREATED,
        entity_id=response.id,
        payload={"survey_id": survey.id, "contact_id": response.contact_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return response
