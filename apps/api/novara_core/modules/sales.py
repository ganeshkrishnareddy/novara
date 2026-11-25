"""Sales pipeline module.

Real workspace-scoped deals and deal activities. All reads and writes are
filtered by workspace_id, all mutations publish an event with the authenticated
actor id, and no external message is ever sent.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, WorkspaceMember, new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

Stage = Literal["new", "qualified", "proposal", "won", "lost"]

DEAL_CREATED = "deal.created"
DEAL_UPDATED = "deal.updated"
DEAL_STAGE_CHANGED = "deal.stage_changed"
DEAL_ACTIVITY_ADDED = "deal.activity_added"
register_event_types(DEAL_CREATED, DEAL_UPDATED, DEAL_STAGE_CHANGED, DEAL_ACTIVITY_ADDED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/deals",
    tags=["sales"],
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "title", "contact_id", name="uq_deal_workspace_title_contact"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"), index=True)
    company: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    expected_close_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class DealActivity(Base):
    __tablename__ = "deal_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class DealCreate(BaseModel):
    title: str
    company: str | None = None
    contact_id: str | None = None
    value: Decimal = Field(default=Decimal("0"), ge=0)
    stage: Stage = "new"
    probability: int = Field(default=0, ge=0, le=100)
    owner_id: str | None = None
    expected_close_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("deal title is required")
        return value

    @field_validator("company")
    @classmethod
    def company_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DealUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    contact_id: str | None = None
    value: Decimal | None = Field(default=None, ge=0)
    stage: Stage | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    owner_id: str | None = None
    expected_close_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("deal title is required")
        return value


class ActivityCreate(BaseModel):
    activity_type: str
    note: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("activity_type")
    @classmethod
    def activity_type_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("activity_type is required")
        return value


class DealOut(BaseModel):
    id: str
    workspace_id: str
    contact_id: str | None
    company: str | None
    title: str
    value: float
    stage: str
    probability: int
    owner_id: str | None
    expected_close_at: object
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class ActivityOut(BaseModel):
    id: str
    workspace_id: str
    deal_id: str
    activity_type: str
    note: str | None
    actor_id: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class StageSummary(BaseModel):
    stage: str
    deal_count: int
    total_value: float


class DealSummary(BaseModel):
    by_stage: list[StageSummary]
    total_deals: int
    total_value: float


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _deal_or_404(db: Session, workspace_id: str, deal_id: str) -> Deal:
    deal = db.execute(
        select(Deal).where(Deal.id == deal_id, Deal.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=404, detail="deal not found")
    return deal


def _validate_contact(db: Session, workspace_id: str, contact_id: str | None) -> None:
    if contact_id is None:
        return
    contact = db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")


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
    title: str,
    contact_id: str | None,
    exclude_deal_id: str | None = None,
) -> None:
    query = select(Deal).where(Deal.workspace_id == workspace_id, Deal.title == title)
    if contact_id is None:
        query = query.where(Deal.contact_id.is_(None))
    else:
        query = query.where(Deal.contact_id == contact_id)
    if exclude_deal_id is not None:
        query = query.where(Deal.id != exclude_deal_id)
    if db.execute(query).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="a deal with this title already exists for this contact")


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=list[DealOut])
def list_deals(
    workspace_id: str,
    stage: Stage | None = None,
    search: str | None = None,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Deal]:
    verify_workspace(principal, workspace_id)
    query = select(Deal).where(Deal.workspace_id == workspace_id)
    if stage is not None:
        query = query.where(Deal.stage == stage)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Deal.title.ilike(pattern), Deal.company.ilike(pattern)))
    return db.execute(query.order_by(Deal.created_at.desc())).scalars().all()


@router.get("/summary", response_model=DealSummary)
def deal_summary(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> DealSummary:
    verify_workspace(principal, workspace_id)
    grouped = db.execute(
        select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.value), Decimal("0")))
        .where(Deal.workspace_id == workspace_id)
        .group_by(Deal.stage)
        .order_by(Deal.stage)
    ).all()
    overall = db.execute(
        select(func.count(Deal.id), func.coalesce(func.sum(Deal.value), Decimal("0"))).where(
            Deal.workspace_id == workspace_id
        )
    ).one()
    return DealSummary(
        by_stage=[
            StageSummary(stage=row[0], deal_count=row[1], total_value=float(row[2])) for row in grouped
        ],
        total_deals=overall[0],
        total_value=float(overall[1]),
    )


@router.post("", response_model=DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(
    workspace_id: str,
    body: DealCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Deal:
    verify_workspace(principal, workspace_id)
    _validate_contact(db, workspace_id, body.contact_id)
    _validate_owner(db, workspace_id, body.owner_id)
    _reject_duplicate(db, workspace_id, body.title, body.contact_id)
    deal = Deal(
        id=new_id(),
        workspace_id=workspace_id,
        contact_id=body.contact_id,
        company=body.company,
        title=body.title,
        value=Decimal(str(body.value)),
        stage=body.stage,
        probability=body.probability,
        owner_id=body.owner_id or principal.user.id,
        expected_close_at=body.expected_close_at,
        created_at=now(),
        updated_at=now(),
    )
    db.add(deal)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DEAL_CREATED,
        entity_id=deal.id,
        payload={"title": deal.title, "stage": deal.stage, "contact_id": deal.contact_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return deal


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    workspace_id: str,
    deal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Deal:
    verify_workspace(principal, workspace_id)
    return _deal_or_404(db, workspace_id, deal_id)


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(
    workspace_id: str,
    deal_id: str,
    body: DealUpdate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Deal:
    verify_workspace(principal, workspace_id)
    deal = _deal_or_404(db, workspace_id, deal_id)
    updates = body.model_dump(exclude_unset=True)
    old_stage = deal.stage
    if "title" in updates and updates["title"] is not None:
        _reject_duplicate(
            db,
            workspace_id,
            updates["title"],
            updates.get("contact_id", deal.contact_id),
            exclude_deal_id=deal.id,
        )
    if "contact_id" in updates:
        _validate_contact(db, workspace_id, updates["contact_id"])
        if "title" not in updates:
            _reject_duplicate(db, workspace_id, deal.title, updates["contact_id"], exclude_deal_id=deal.id)
    if "owner_id" in updates:
        _validate_owner(db, workspace_id, updates["owner_id"])
    if "value" in updates and updates["value"] is not None:
        updates["value"] = Decimal(str(updates["value"]))
    for key, value in updates.items():
        setattr(deal, key, value)
    deal.updated_at = now()
    stage_changed = "stage" in updates and updates["stage"] != old_stage
    event_type = DEAL_STAGE_CHANGED if stage_changed else DEAL_UPDATED
    payload = {
        "fields": sorted(updates.keys()),
        "from_stage": old_stage if stage_changed else None,
        "to_stage": deal.stage if stage_changed else None,
    }
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=event_type,
        entity_id=deal.id,
        payload=payload,
        actor_id=principal.user.id,
    )
    db.commit()
    return deal


@router.get("/{deal_id}/activities", response_model=list[ActivityOut])
def list_activities(
    workspace_id: str,
    deal_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[DealActivity]:
    verify_workspace(principal, workspace_id)
    _deal_or_404(db, workspace_id, deal_id)
    return db.execute(
        select(DealActivity)
        .where(DealActivity.workspace_id == workspace_id, DealActivity.deal_id == deal_id)
        .order_by(DealActivity.created_at)
    ).scalars().all()


@router.post("/{deal_id}/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def add_activity(
    workspace_id: str,
    deal_id: str,
    body: ActivityCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DealActivity:
    verify_workspace(principal, workspace_id)
    deal = _deal_or_404(db, workspace_id, deal_id)
    activity = DealActivity(
        id=new_id(),
        workspace_id=workspace_id,
        deal_id=deal.id,
        activity_type=body.activity_type,
        note=body.note,
        actor_id=principal.user.id,
        created_at=now(),
    )
    db.add(activity)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DEAL_ACTIVITY_ADDED,
        entity_id=activity.id,
        payload={
            "deal_id": deal.id,
            "activity_type": activity.activity_type,
            "actor_id": principal.user.id,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return activity
