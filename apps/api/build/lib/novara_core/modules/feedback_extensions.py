"""Clean-room survey extensions (Formbricks P2 feature cluster).

This module adds survey configuration, question types, logic, presets and
partial submissions on top of the existing Feedback Studio (``feedback.py``).
It owns its tables and a single APIRouter and is registered through
``modules/__init__.py``. All behaviour is local: no survey is distributed,
no email is sent and no external Formbricks service is contacted.

Feature IDs closed here (evidence: apps/api/tests/test_feedback_extensions_p2.py):
FB-008, FB-009, FB-011, FB-012, FB-013, FB-014, FB-016, FB-017, FB-018,
FB-019, FB-021, FB-022, FB-023, FB-026, FB-027, FB-028, FB-030, FB-032,
FB-033, FB-034, FB-035, FB-037, FB-040, FB-041, FB-042, FB-044.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, delete, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from pydantic import BaseModel, ConfigDict, field_validator

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE
from .feedback import Survey, _survey_or_404

CONFIG_UPSERTED = "survey.config_upserted"
QUESTION_CHANGED = "survey.question_changed"
ANSWER_SUBMITTED = "survey.answer_submitted"
LINK_CHANGED = "survey.link_changed"
DISPLAY_RECORDED = "survey.display_recorded"
TAGS_CHANGED = "survey.tags_changed"
register_event_types(CONFIG_UPSERTED, QUESTION_CHANGED, ANSWER_SUBMITTED,
                     LINK_CHANGED, DISPLAY_RECORDED, TAGS_CHANGED)

DISPLAY_OPTIONS = ("displayOnce", "displayMultiple", "displaySome", "respondMultiple")
VISIBILITIES = ("workspace", "restricted")
THEMES = ("default", "forest", "gold", "minimal")
QUESTION_TYPES = (
    "nps", "csat", "ces", "consent", "contact_info", "date", "free_text",
    "single_choice", "multi_choice", "rating", "image", "video", "address",
    # Extended question types (FB-039, FB-043, FB-045..FB-054)
    "file_upload", "matrix", "ranking", "schedule_meeting", "picture_selection",
    "signature", "statement", "thank_you",
)

# Built-in presets. These are original definitions, not copied Formbricks assets.
TEMPLATES: dict[str, dict] = {
    "nps": {
        "name": "Net Promoter Score",
        "questions": [
            {"type": "nps", "code": "nps_score", "label": "How likely are you to recommend us?", "required": True},
            {"type": "free_text", "code": "nps_why", "label": "Why did you give that score?", "required": False},
        ],
    },
    "csat": {
        "name": "Customer Satisfaction",
        "questions": [
            {"type": "csat", "code": "csat_score", "label": "How satisfied are you?", "required": True},
            {"type": "free_text", "code": "csat_note", "label": "Anything we can improve?", "required": False},
        ],
    },
    "ces": {
        "name": "Customer Effort Score",
        "questions": [
            {"type": "ces", "code": "ces_score", "label": "How easy was it to get help?", "required": True},
        ],
    },
    "best_practice": {
        "name": "Best-practice feedback",
        "questions": [
            {"type": "consent", "code": "consent", "label": "I agree to the processing of my response.", "required": True},
            {"type": "rating", "code": "rating", "label": "Rate your experience", "required": True},
            {"type": "free_text", "code": "comment", "label": "Tell us more", "required": False},
        ],
    },
    # Original NOVARA templates, one per documented source preset. Each is a
    # real, local question set exercised by a named test in test_feedback_templates_p2c.py.
    "contact_form": {
        "name": "Contact Form",
        "questions": [
            {"type": "free_text", "code": "full_name", "label": "Your name", "required": True},
            {"type": "free_text", "code": "email", "label": "Your email", "required": True},
            {"type": "free_text", "code": "message", "label": "Your message", "required": True},
        ],
    },
    "docs_feedback": {
        "name": "Docs Feedback",
        "questions": [
            {"type": "single_choice", "code": "helpful", "label": "Was this page helpful?", "required": True},
            {"type": "free_text", "code": "docs_note", "label": "How could we improve it?"},
        ],
    },
    "feature_chaser": {
        "name": "Feature Chaser",
        "questions": [
            {"type": "single_choice", "code": "feature", "label": "Which feature do you need most?"},
            {"type": "free_text", "code": "feature_detail", "label": "Tell us more"},
        ],
    },
    "feedback_box": {
        "name": "Feedback Box",
        "questions": [
            {"type": "rating", "code": "rating", "label": "Rate your experience", "required": True},
            {"type": "free_text", "code": "comment", "label": "Your feedback"},
        ],
    },
    "improve_email_content": {
        "name": "Improve Email Content",
        "questions": [
            {"type": "single_choice", "code": "clear", "label": "Was the email clear?"},
            {"type": "free_text", "code": "email_note", "label": "What would you change?"},
        ],
    },
    "app_interview_prompt": {
        "name": "App Interview Prompt",
        "questions": [
            {"type": "free_text", "code": "goal", "label": "What are you trying to achieve?"},
            {"type": "rating", "code": "ease", "label": "How easy is the app?"},
        ],
    },
    "churn_survey": {
        "name": "Churn Survey",
        "questions": [
            {"type": "single_choice", "code": "reason", "label": "Why are you leaving?"},
            {"type": "free_text", "code": "win_back", "label": "What would bring you back?"},
        ],
    },
    "product_market_fit": {
        "name": "Product-Market Fit Survey",
        "questions": [
            {"type": "single_choice", "code": "disappointment", "label": "How would you feel if the product disappeared?"},
            {"type": "free_text", "code": "pmf_benefit", "label": "What is the main benefit to you?"},
        ],
    },
    "quiz_time": {
        "name": "Quiz Time",
        "questions": [
            {"type": "single_choice", "code": "q1", "label": "Quiz question one", "required": True},
            {"type": "single_choice", "code": "q2", "label": "Quiz question two", "required": True},
        ],
    },
    "improve_trial_conversion": {
        "name": "Improve Trial Conversion",
        "questions": [
            {"type": "single_choice", "code": "blocker", "label": "What stopped you upgrading?"},
            {"type": "free_text", "code": "trial_note", "label": "What would have helped?"},
        ],
    },
    "panel_management": {
        "name": "Panel Management",
        "questions": [
            {"type": "free_text", "code": "panel_name", "label": "Panel name", "required": True},
            {"type": "date", "code": "availability", "label": "Availability date"},
        ],
    },
    "collect_google_reviews": {
        "name": "Collect Google Reviews",
        "questions": [
            {"type": "rating", "code": "experience", "label": "How was your experience?", "required": True},
            {"type": "consent", "code": "review_consent", "label": "May we quote your review?"},
        ],
    },
}

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/feedback",
    tags=["feedback-extensions"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

class SurveyConfig(Base):
    __tablename__ = "survey_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True, unique=True)
    display_option: Mapped[str] = mapped_column(String(30), default="displayOnce")
    visibility: Mapped[str] = mapped_column(String(30), default="workspace")
    allowed_roles: Mapped[dict] = mapped_column(JSON, default=dict)
    theme: Mapped[str] = mapped_column(String(30), default="default")
    custom_css: Mapped[str | None] = mapped_column(Text)
    style: Mapped[dict] = mapped_column(JSON, default=dict)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    hidden_fields: Mapped[list] = mapped_column(JSON, default=list)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    logic: Mapped[dict] = mapped_column(JSON, default=dict)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)  # language -> text


class SurveyEmbeddedData(Base):
    """FB-026: settable/clearable embedded data, keyed by a caller subject."""

    __tablename__ = "survey_embedded_data"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class SurveyLink(Base):
    """FB-066..FB-073: shareable survey links with settings and controls."""

    __tablename__ = "survey_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="personal")
    slug: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    preview_image: Mapped[str | None] = mapped_column(Text)
    prefill: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str | None] = mapped_column(String(80))
    start_block: Mapped[str | None] = mapped_column(String(64))
    require_identified: Mapped[bool] = mapped_column(default=False)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyDisplay(Base):
    """FB-091: a recorded impression of a survey/link to a subject."""

    __tablename__ = "survey_displays"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    link_id: Mapped[str | None] = mapped_column(ForeignKey("survey_links.id"))
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyTag(Base):
    """FB-092: workspace/survey-scoped tags for responses."""

    __tablename__ = "survey_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class SurveyAnswerTag(Base):
    __tablename__ = "survey_answer_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("survey_answers.id"), nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("survey_tags.id"), nullable=False, index=True)


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    question_id: Mapped[str | None] = mapped_column(ForeignKey("survey_questions.id"))
    code: Mapped[str | None] = mapped_column(String(64))
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    embedded: Mapped[dict] = mapped_column(JSON, default=dict)
    partial: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class ConfigUpsert(BaseModel):
    display_option: str = "displayOnce"
    visibility: str = "workspace"
    allowed_roles: list[str] | None = None
    theme: str = "default"
    custom_css: str | None = None
    style: dict | None = None
    languages: list[str] | None = None
    hidden_fields: list[dict] | None = None
    variables: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("display_option")
    @classmethod
    def _display(cls, v):
        if v not in DISPLAY_OPTIONS:
            raise ValueError("invalid display option")
        return v

    @field_validator("visibility")
    @classmethod
    def _visibility(cls, v):
        if v not in VISIBILITIES:
            raise ValueError("invalid visibility mode")
        return v

    @field_validator("theme")
    @classmethod
    def _theme(cls, v):
        if v not in THEMES:
            raise ValueError("invalid theme")
        return v


class ConfigOut(BaseModel):
    id: str
    survey_id: str
    display_option: str
    visibility: str
    allowed_roles: dict
    theme: str
    custom_css: str | None
    style: dict
    languages: list
    hidden_fields: list
    variables: dict

    model_config = ConfigDict(from_attributes=True)


class QuestionCreate(BaseModel):
    type: str
    code: str
    label: str
    required: bool = False
    position: int = 0
    config: dict | None = None
    logic: dict | None = None
    labels: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        if v not in QUESTION_TYPES:
            raise ValueError("invalid question type")
        return v


class QuestionUpdate(BaseModel):
    label: str | None = None
    required: bool | None = None
    position: int | None = None
    config: dict | None = None
    logic: dict | None = None
    labels: dict | None = None

    model_config = ConfigDict(extra="forbid")


class QuestionOut(BaseModel):
    id: str
    survey_id: str
    type: str
    code: str
    label: str
    required: bool
    position: int
    config: dict
    logic: dict
    labels: dict

    model_config = ConfigDict(from_attributes=True)


class AnswerCreate(BaseModel):
    contact_id: str | None = None
    question_id: str | None = None
    code: str | None = None
    value: object = None
    embedded: dict | None = None
    partial: bool = False
    link_token: str | None = None

    model_config = ConfigDict(extra="forbid")


class AnswerOut(BaseModel):
    id: str
    survey_id: str
    contact_id: str | None
    question_id: str | None
    code: str | None
    value: object
    embedded: dict
    partial: bool

    model_config = ConfigDict(from_attributes=True)


class FromTemplate(BaseModel):
    name: str
    template: str

    model_config = ConfigDict(extra="forbid")


class EmbeddedSet(BaseModel):
    subject: str
    data: dict

    model_config = ConfigDict(extra="forbid")


class EmbeddedClear(BaseModel):
    subject: str

    model_config = ConfigDict(extra="forbid")


class LinkCreate(BaseModel):
    kind: str = "personal"
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    preview_image: str | None = None
    prefill: dict | None = None
    source: str | None = None
    start_block: str | None = None
    require_identified: bool = False
    contact_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        if v not in ("personal", "single_use"):
            raise ValueError("invalid link kind")
        return v


class LinkOut(BaseModel):
    id: str
    survey_id: str
    token: str
    kind: str
    slug: str | None
    title: str | None
    description: str | None
    preview_image: str | None
    prefill: dict
    source: str | None
    start_block: str | None
    require_identified: bool
    contact_id: str | None
    used: bool

    model_config = ConfigDict(from_attributes=True)


class DisplayCreate(BaseModel):
    subject: str
    link_token: str | None = None

    model_config = ConfigDict(extra="forbid")


class TagCreate(BaseModel):
    name: str

    model_config = ConfigDict(extra="forbid")


class TagOut(BaseModel):
    id: str
    survey_id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class AnswerUpdate(BaseModel):
    value: object = None
    partial: bool | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _config_or_404(db: Session, workspace_id: str, survey_id: str) -> SurveyConfig:
    cfg = db.execute(
        select(SurveyConfig).where(
            SurveyConfig.workspace_id == workspace_id,
            SurveyConfig.survey_id == survey_id,
        )
    ).scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="survey config not found")
    return cfg


def _question_or_404(db: Session, workspace_id: str, question_id: str) -> SurveyQuestion:
    q = db.execute(
        select(SurveyQuestion).where(
            SurveyQuestion.workspace_id == workspace_id,
            SurveyQuestion.id == question_id,
        )
    ).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="question not found")
    return q


def _answer_or_404(db: Session, workspace_id: str, answer_id: str) -> SurveyAnswer:
    a = db.execute(
        select(SurveyAnswer).where(
            SurveyAnswer.workspace_id == workspace_id,
            SurveyAnswer.id == answer_id,
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail="answer not found")
    return a


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.get("/templates")
def list_templates(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    return [{"key": key, **value} for key, value in TEMPLATES.items()]


@router.post("/surveys/from-template", status_code=status.HTTP_201_CREATED)
def create_from_template(
    workspace_id: str,
    body: FromTemplate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    preset = TEMPLATES.get(body.template)
    if preset is None:
        raise HTTPException(status_code=422, detail="unknown template")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="survey name is required")
    if db.execute(select(Survey.id).where(Survey.workspace_id == workspace_id, Survey.name == name)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="a survey with this name already exists")
    survey = Survey(id=new_id(), workspace_id=workspace_id, name=name,
                    description=f"Created from {body.template} preset", status="draft",
                    created_by=principal.user.id, created_at=now())
    db.add(survey)
    db.flush()
    cfg = SurveyConfig(id=new_id(), workspace_id=workspace_id, survey_id=survey.id,
                       display_option="displayOnce", visibility="workspace",
                       allowed_roles={}, theme="default", style={}, languages=[],
                       hidden_fields=[], variables={})
    db.add(cfg)
    questions = []
    for idx, q in enumerate(preset["questions"]):
        row = SurveyQuestion(id=new_id(), workspace_id=workspace_id, survey_id=survey.id,
                             type=q["type"], code=q["code"], label=q["label"],
                             required=q.get("required", False), position=idx,
                             config={}, logic={}, labels={})
        db.add(row)
        questions.append(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=CONFIG_UPSERTED,
                  entity_id=survey.id, payload={"template": body.template},
                  actor_id=principal.user.id)
    db.commit()
    return {"survey_id": survey.id, "config": ConfigOut.model_validate(cfg),
            "questions": [QuestionOut.model_validate(q) for q in questions]}


@router.post("/surveys/{survey_id}/config", response_model=ConfigOut)
def upsert_config(
    workspace_id: str,
    survey_id: str,
    body: ConfigUpsert,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    cfg = db.execute(
        select(SurveyConfig).where(SurveyConfig.workspace_id == workspace_id,
                                   SurveyConfig.survey_id == survey_id)
    ).scalar_one_or_none()
    if cfg is None:
        cfg = SurveyConfig(id=new_id(), workspace_id=workspace_id, survey_id=survey_id)
        db.add(cfg)
    cfg.display_option = body.display_option
    cfg.visibility = body.visibility
    cfg.allowed_roles = {"roles": body.allowed_roles or []}
    cfg.theme = body.theme
    cfg.custom_css = body.custom_css
    cfg.style = body.style or {}
    cfg.languages = body.languages or []
    cfg.hidden_fields = body.hidden_fields or []
    cfg.variables = body.variables or {}
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=CONFIG_UPSERTED,
                  entity_id=survey_id, payload={"display_option": cfg.display_option,
                                                "visibility": cfg.visibility},
                  actor_id=principal.user.id)
    db.commit()
    return cfg


@router.get("/surveys/{survey_id}/config", response_model=ConfigOut)
def get_config(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return _config_or_404(db, workspace_id, survey_id)


@router.post("/surveys/{survey_id}/questions", response_model=QuestionOut,
             status_code=status.HTTP_201_CREATED)
def add_question(
    workspace_id: str,
    survey_id: str,
    body: QuestionCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    code = body.code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="question code is required")
    if db.execute(select(SurveyQuestion.id).where(
        SurveyQuestion.workspace_id == workspace_id,
        SurveyQuestion.survey_id == survey_id,
        SurveyQuestion.code == code,
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="duplicate question code")
    logic = body.logic or {}
    if set(logic) - {"show_if", "jump_to", "set_value"}:
        raise HTTPException(status_code=422, detail="unsupported logic field")
    q = SurveyQuestion(id=new_id(), workspace_id=workspace_id, survey_id=survey_id,
                       type=body.type, code=code, label=body.label,
                       required=body.required, position=body.position,
                       config=body.config or {}, logic=logic, labels=body.labels or {})
    db.add(q)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=QUESTION_CHANGED,
                  entity_id=q.id, payload={"survey_id": survey_id, "action": "add"},
                  actor_id=principal.user.id)
    db.commit()
    return q


@router.get("/surveys/{survey_id}/questions", response_model=list[QuestionOut])
def list_questions(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return db.execute(
        select(SurveyQuestion).where(
            SurveyQuestion.workspace_id == workspace_id,
            SurveyQuestion.survey_id == survey_id,
        ).order_by(SurveyQuestion.position, SurveyQuestion.code)
    ).scalars().all()


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(
    workspace_id: str,
    question_id: str,
    body: QuestionUpdate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = _question_or_404(db, workspace_id, question_id)
    for field in ("label", "required", "position", "config", "logic", "labels"):
        value = getattr(body, field)
        if value is not None:
            setattr(q, field, value)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=QUESTION_CHANGED,
                  entity_id=q.id, payload={"survey_id": q.survey_id, "action": "update"},
                  actor_id=principal.user.id)
    db.commit()
    return q


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    workspace_id: str,
    question_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    q = _question_or_404(db, workspace_id, question_id)
    survey_id = q.survey_id
    db.delete(q)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=QUESTION_CHANGED,
                  entity_id=question_id, payload={"survey_id": survey_id, "action": "delete"},
                  actor_id=principal.user.id)
    db.commit()
    return None


@router.post("/surveys/{survey_id}/answers", response_model=AnswerOut,
             status_code=status.HTTP_201_CREATED)
def submit_answer(
    workspace_id: str,
    survey_id: str,
    body: AnswerCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    survey = _survey_or_404(db, workspace_id, survey_id)
    if survey.status == "closed":
        raise HTTPException(status_code=409, detail="survey is closed")
    if body.contact_id is not None and db.execute(
        select(Contact.id).where(Contact.id == body.contact_id,
                                 Contact.workspace_id == workspace_id)
    ).scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="contact not found in this workspace")
    question = None
    if body.question_id is not None:
        question = _question_or_404(db, workspace_id, body.question_id)
        if question.survey_id != survey_id:
            raise HTTPException(status_code=422, detail="question belongs to another survey")
    code = body.code or (question.code if question else None)
    if question is not None and question.required and not body.partial and body.value in (None, "", {}, []):
        raise HTTPException(status_code=422, detail="required question needs a value")
    embedded = dict(body.embedded or {})
    link = None
    if body.link_token is not None:
        link = db.execute(
            select(SurveyLink).where(
                SurveyLink.workspace_id == workspace_id,
                SurveyLink.survey_id == survey_id,
                SurveyLink.token == body.link_token,
            )
        ).scalar_one_or_none()
        if link is None:
            raise HTTPException(status_code=422, detail="link not found for this survey")
        if link.kind == "single_use" and link.used:
            raise HTTPException(status_code=409, detail="single-use link already consumed")
        if link.require_identified and body.contact_id is None and link.contact_id is None:
            raise HTTPException(status_code=422, detail="this link requires an identified respondent")
        embedded.update(link.prefill or {})
        if link.source is not None:
            embedded["source"] = link.source
    contact_id = body.contact_id or (link.contact_id if link is not None else None)
    answer = SurveyAnswer(id=new_id(), workspace_id=workspace_id, survey_id=survey_id,
                          contact_id=contact_id,
                          question_id=question.id if question else None,
                          code=code, value=body.value, embedded=embedded,
                          partial=body.partial, created_at=now())
    db.add(answer)
    db.flush()
    if link is not None and link.kind == "single_use":
        link.used = True
    publish_event(db, workspace_id=workspace_id, event_type=ANSWER_SUBMITTED,
                  entity_id=answer.id, payload={"survey_id": survey_id,
                                                "partial": body.partial,
                                                "link_token": body.link_token},
                  actor_id=principal.user.id)
    db.commit()
    return answer


@router.get("/surveys/{survey_id}/answers", response_model=list[AnswerOut])
def list_answers(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return db.execute(
        select(SurveyAnswer).where(
            SurveyAnswer.workspace_id == workspace_id,
            SurveyAnswer.survey_id == survey_id,
        ).order_by(SurveyAnswer.created_at)
    ).scalars().all()


@router.post("/surveys/{survey_id}/embedded/set")
def set_embedded(
    workspace_id: str,
    survey_id: str,
    body: EmbeddedSet,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status_code=422, detail="subject is required")
    row = db.execute(
        select(SurveyEmbeddedData).where(
            SurveyEmbeddedData.workspace_id == workspace_id,
            SurveyEmbeddedData.survey_id == survey_id,
            SurveyEmbeddedData.subject == subject,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SurveyEmbeddedData(id=new_id(), workspace_id=workspace_id,
                                 survey_id=survey_id, subject=subject)
        db.add(row)
    row.data = body.data
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=CONFIG_UPSERTED,
                  entity_id=survey_id, payload={"embedded": "set", "subject": subject},
                  actor_id=principal.user.id)
    db.commit()
    return {"subject": subject, "data": row.data}


@router.post("/surveys/{survey_id}/embedded/clear")
def clear_embedded(
    workspace_id: str,
    survey_id: str,
    body: EmbeddedClear,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    row = db.execute(
        select(SurveyEmbeddedData).where(
            SurveyEmbeddedData.workspace_id == workspace_id,
            SurveyEmbeddedData.survey_id == survey_id,
            SurveyEmbeddedData.subject == body.subject,
        )
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=CONFIG_UPSERTED,
                  entity_id=survey_id, payload={"embedded": "clear", "subject": body.subject},
                  actor_id=principal.user.id)
    db.commit()
    return {"subject": body.subject, "cleared": True}


@router.get("/surveys/{survey_id}/recall")
def recall(
    workspace_id: str,
    survey_id: str,
    contact_id: str | None = None,
    subject: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    cfg = _config_or_404(db, workspace_id, survey_id)
    embedded: dict = {}
    key = subject or contact_id
    if key is not None:
        stored = db.execute(
            select(SurveyEmbeddedData).where(
                SurveyEmbeddedData.workspace_id == workspace_id,
                SurveyEmbeddedData.survey_id == survey_id,
                SurveyEmbeddedData.subject == key,
            )
        ).scalar_one_or_none()
        if stored is not None:
            embedded.update(stored.data or {})
    if contact_id is not None:
        answers = db.execute(
            select(SurveyAnswer).where(
                SurveyAnswer.workspace_id == workspace_id,
                SurveyAnswer.survey_id == survey_id,
                SurveyAnswer.contact_id == contact_id,
            ).order_by(SurveyAnswer.created_at)
        ).scalars().all()
        for answer in answers:
            embedded.update(answer.embedded or {})
    return {"hidden_fields": cfg.hidden_fields, "variables": cfg.variables,
            "embedded": embedded}


# --------------------------------------------------------------------------
# Shareable links, display tracking, tags and response management
# --------------------------------------------------------------------------

@router.post("/surveys/{survey_id}/links", response_model=LinkOut,
             status_code=status.HTTP_201_CREATED)
def create_link(
    workspace_id: str,
    survey_id: str,
    body: LinkCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    if body.contact_id is not None and db.execute(
        select(Contact.id).where(Contact.id == body.contact_id,
                                 Contact.workspace_id == workspace_id)
    ).scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="contact not found in this workspace")
    if body.slug:
        if db.execute(select(SurveyLink.id).where(
            SurveyLink.workspace_id == workspace_id, SurveyLink.slug == body.slug
        )).scalar_one_or_none():
            raise HTTPException(status_code=409, detail="slug already in use")
    link = SurveyLink(id=new_id(), workspace_id=workspace_id, survey_id=survey_id,
                      token=new_id().replace("-", "")[:32], kind=body.kind,
                      slug=body.slug, title=body.title, description=body.description,
                      preview_image=body.preview_image, prefill=body.prefill or {},
                      source=body.source, start_block=body.start_block,
                      require_identified=body.require_identified,
                      contact_id=body.contact_id, used=False, created_at=now())
    db.add(link)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=LINK_CHANGED,
                  entity_id=link.id, payload={"survey_id": survey_id, "kind": link.kind},
                  actor_id=principal.user.id)
    db.commit()
    return link


@router.get("/surveys/{survey_id}/links", response_model=list[LinkOut])
def list_links(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return db.execute(
        select(SurveyLink).where(SurveyLink.workspace_id == workspace_id,
                                 SurveyLink.survey_id == survey_id)
        .order_by(SurveyLink.created_at)
    ).scalars().all()


@router.get("/links/resolve")
def resolve_link(
    workspace_id: str,
    token: str | None = None,
    slug: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if not token and not slug:
        raise HTTPException(status_code=422, detail="token or slug is required")
    query = select(SurveyLink).where(SurveyLink.workspace_id == workspace_id)
    link = None
    if token is not None:
        link = db.execute(query.where(SurveyLink.token == token)).scalar_one_or_none()
    if link is None and slug is not None:
        link = db.execute(query.where(SurveyLink.slug == slug)).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    survey = _survey_or_404(db, workspace_id, link.survey_id)
    return {
        "token": link.token, "survey_id": link.survey_id, "survey_name": survey.name,
        "title": link.title, "description": link.description,
        "preview_image": link.preview_image, "prefill": link.prefill,
        "start_block": link.start_block, "source": link.source,
        "require_identified": link.require_identified, "kind": link.kind,
        "used": link.used,
    }


@router.post("/links/{token}/displays", status_code=status.HTTP_201_CREATED)
def record_display(
    workspace_id: str,
    token: str,
    body: DisplayCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    link = db.execute(
        select(SurveyLink).where(SurveyLink.workspace_id == workspace_id,
                                 SurveyLink.token == token)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status_code=422, detail="subject is required")
    display = SurveyDisplay(id=new_id(), workspace_id=workspace_id,
                            survey_id=link.survey_id, link_id=link.id,
                            subject=subject, created_at=now())
    db.add(display)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DISPLAY_RECORDED,
                  entity_id=display.id, payload={"survey_id": link.survey_id,
                                                 "subject": subject},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": display.id, "survey_id": link.survey_id, "subject": subject}


@router.get("/surveys/{survey_id}/displays")
def list_displays(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    rows = db.execute(
        select(SurveyDisplay).where(SurveyDisplay.workspace_id == workspace_id,
                                    SurveyDisplay.survey_id == survey_id)
        .order_by(SurveyDisplay.created_at)
    ).scalars().all()
    return [{"id": r.id, "subject": r.subject, "link_id": r.link_id,
             "created_at": r.created_at} for r in rows]


@router.post("/surveys/{survey_id}/tags", response_model=TagOut,
             status_code=status.HTTP_201_CREATED)
def create_tag(
    workspace_id: str,
    survey_id: str,
    body: TagCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="tag name is required")
    if db.execute(select(SurveyTag.id).where(
        SurveyTag.workspace_id == workspace_id, SurveyTag.survey_id == survey_id,
        SurveyTag.name == name
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="tag already exists")
    tag = SurveyTag(id=new_id(), workspace_id=workspace_id, survey_id=survey_id, name=name)
    db.add(tag)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TAGS_CHANGED,
                  entity_id=tag.id, payload={"survey_id": survey_id, "name": name},
                  actor_id=principal.user.id)
    db.commit()
    return tag


@router.get("/surveys/{survey_id}/tags", response_model=list[TagOut])
def list_tags(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    return db.execute(
        select(SurveyTag).where(SurveyTag.workspace_id == workspace_id,
                                SurveyTag.survey_id == survey_id).order_by(SurveyTag.name)
    ).scalars().all()


@router.post("/answers/{answer_id}/tags", status_code=status.HTTP_201_CREATED)
def assign_tag(
    workspace_id: str,
    answer_id: str,
    tag_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    answer = _answer_or_404(db, workspace_id, answer_id)
    tag = db.execute(
        select(SurveyTag).where(SurveyTag.workspace_id == workspace_id,
                                SurveyTag.id == tag_id,
                                SurveyTag.survey_id == answer.survey_id)
    ).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=422, detail="tag not found for this survey")
    if db.execute(select(SurveyAnswerTag.id).where(
        SurveyAnswerTag.workspace_id == workspace_id,
        SurveyAnswerTag.answer_id == answer_id, SurveyAnswerTag.tag_id == tag_id
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="tag already assigned")
    row = SurveyAnswerTag(id=new_id(), workspace_id=workspace_id,
                          answer_id=answer_id, tag_id=tag_id)
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=TAGS_CHANGED,
                  entity_id=row.id, payload={"answer_id": answer_id, "tag_id": tag_id},
                  actor_id=principal.user.id)
    db.commit()
    return {"answer_id": answer_id, "tag_id": tag_id}


@router.get("/answers/{answer_id}/tags")
def answer_tags(
    workspace_id: str,
    answer_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _answer_or_404(db, workspace_id, answer_id)
    rows = db.execute(
        select(SurveyTag.id, SurveyTag.name).join(
            SurveyAnswerTag, SurveyAnswerTag.tag_id == SurveyTag.id
        ).where(SurveyAnswerTag.workspace_id == workspace_id,
                SurveyAnswerTag.answer_id == answer_id)
    ).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.patch("/answers/{answer_id}", response_model=AnswerOut)
def update_answer(
    workspace_id: str,
    answer_id: str,
    body: AnswerUpdate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    answer = _answer_or_404(db, workspace_id, answer_id)
    if body.value is not None:
        answer.value = body.value
    if body.partial is not None:
        answer.partial = body.partial
    if body.note is not None:
        embedded = dict(answer.embedded or {})
        embedded["review_note"] = body.note
        answer.embedded = embedded
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=ANSWER_SUBMITTED,
                  entity_id=answer.id, payload={"survey_id": answer.survey_id,
                                                "action": "update"},
                  actor_id=principal.user.id)
    db.commit()
    return answer


@router.delete("/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer(
    workspace_id: str,
    answer_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    answer = _answer_or_404(db, workspace_id, answer_id)
    survey_id = answer.survey_id
    db.execute(
        delete(SurveyAnswerTag).where(
            SurveyAnswerTag.workspace_id == workspace_id,
            SurveyAnswerTag.answer_id == answer_id,
        )
    )
    db.delete(answer)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=ANSWER_SUBMITTED,
                  entity_id=answer_id, payload={"survey_id": survey_id, "action": "delete"},
                  actor_id=principal.user.id)
    db.commit()
    return None


@router.get("/surveys/{survey_id}/answers/export")
def export_answers(
    workspace_id: str,
    survey_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    _survey_or_404(db, workspace_id, survey_id)
    import csv
    import io

    answers = db.execute(
        select(SurveyAnswer).where(SurveyAnswer.workspace_id == workspace_id,
                                   SurveyAnswer.survey_id == survey_id)
        .order_by(SurveyAnswer.created_at)
    ).scalars().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "contact_id", "question_code", "value", "partial", "created_at"])
    for a in answers:
        writer.writerow([a.id, a.contact_id or "", a.code or "", str(a.value),
                         "true" if a.partial else "false", str(a.created_at)])
    return {"content_type": "text/csv", "filename": f"survey-{survey_id}-answers.csv",
            "rows": len(answers), "csv": buffer.getvalue()}
