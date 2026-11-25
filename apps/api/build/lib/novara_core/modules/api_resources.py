"""Documented NOVARA API resource contexts (MT-072, clean-room).

Mautic's API library names three contexts — contacts, forms and pages — with
get, getList, create, edit and delete verbs. This module provides the same
*resource semantics* on NOVARA's one native, workspace-scoped API surface:
validation, permission checks, real persistence, named events and cross-workspace
denial. It does not copy Mautic code, does not expose a second API host and does
not count a bare 200 response as a feature.

There is no delivery client here. Forms and pages are local records; submitting
or visiting them is recorded on the shared event spine by the marketing module.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import Contact, new_id, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

RESOURCE_CREATED = "api_resource.created"
RESOURCE_UPDATED = "api_resource.updated"
RESOURCE_DELETED = "api_resource.deleted"
register_event_types(RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED)

API_NOTES = (
    "Native NOVARA API contexts. All resources are workspace-scoped and local; "
    "no external product source is embedded and no outbound call is made."
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/api",
    tags=["api-resources"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Form(Base):
    """A local form definition. Submissions are analytics events, not sends."""

    __tablename__ = "api_forms"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_api_form_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Page(Base):
    """A local landing-page definition. Visits are analytics events."""

    __tablename__ = "api_pages"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_api_page_workspace_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ContactCreate(BaseModel):
    email: str
    full_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    source: str = "api"
    custom_fields: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("a valid email is required")
        return value


class ContactEdit(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    lifecycle_stage: str | None = None
    custom_fields: dict | None = None

    model_config = ConfigDict(extra="forbid")


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    fields: list[dict] = Field(default_factory=list)
    status: str = "draft"

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str) -> str:
        if value not in {"draft", "published"}:
            raise ValueError("status must be draft or published")
        return value


class FormEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    fields: list[dict] | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str | None) -> str | None:
        if value is not None and value not in {"draft", "published"}:
            raise ValueError("status must be draft or published")
        return value


class PageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    content: str | None = None
    status: str = "draft"

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug")
    @classmethod
    def slug_allowed(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("slug may contain letters, numbers, hyphens and underscores")
        return value

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str) -> str:
        if value not in {"draft", "published"}:
            raise ValueError("status must be draft or published")
        return value


class PageEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = None
    content: str | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug")
    @classmethod
    def slug_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().lower()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("slug may contain letters, numbers, hyphens and underscores")
        return value

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str | None) -> str | None:
        if value is not None and value not in {"draft", "published"}:
            raise ValueError("status must be draft or published")
        return value


class ContactOut(BaseModel):
    id: str
    workspace_id: str
    email: str
    full_name: str | None
    phone: str | None
    source: str
    lifecycle_stage: str
    custom_fields: dict
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class FormOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    fields: list
    status: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class PageOut(BaseModel):
    id: str
    workspace_id: str
    title: str
    slug: str
    content: str | None
    status: str
    created_at: object
    updated_at: object

    model_config = ConfigDict(from_attributes=True)


class DeletedOut(BaseModel):
    deleted: bool
    context: str
    id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one_or_404(db: Session, model, workspace_id: str, resource_id: str):
    row = db.execute(
        select(model).where(model.id == resource_id, model.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return row


def _audit(db, *, workspace_id, context, verb, entity_id, actor_id):
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type={
            "create": RESOURCE_CREATED,
            "edit": RESOURCE_UPDATED,
            "delete": RESOURCE_DELETED,
        }[verb],
        entity_id=entity_id,
        payload={"context": context, "verb": verb},
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Contacts context — get, getList, create, edit, delete
# ---------------------------------------------------------------------------


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(
    workspace_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Contact]:
    """getList — a real workspace-scoped page of contacts."""
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Contact)
        .where(Contact.workspace_id == workspace_id)
        .order_by(Contact.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    workspace_id: str,
    body: ContactCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Contact:
    """create — validates input and persists one contact in this workspace."""
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == body.email)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="contact email already exists")
    contact = Contact(
        id=new_id(),
        workspace_id=workspace_id,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        company_name=body.company_name,
        source=body.source,
        custom_fields=body.custom_fields,
        created_at=now(),
        updated_at=now(),
    )
    db.add(contact)
    db.flush()
    _audit(db, workspace_id=workspace_id, context="contacts", verb="create",
           entity_id=contact.id, actor_id=principal.user.id)
    db.commit()
    return contact


@router.get("/contacts/{contact_id}", response_model=ContactOut)
def get_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Contact:
    verify_workspace(principal, workspace_id)
    return _one_or_404(db, Contact, workspace_id, contact_id)


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def edit_contact(
    workspace_id: str,
    contact_id: str,
    body: ContactEdit,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Contact:
    """edit — only the supplied fields change; identity fields stay immutable."""
    verify_workspace(principal, workspace_id)
    contact = _one_or_404(db, Contact, workspace_id, contact_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    contact.updated_at = now()
    _audit(db, workspace_id=workspace_id, context="contacts", verb="edit",
           entity_id=contact.id, actor_id=principal.user.id)
    db.commit()
    return contact


@router.delete("/contacts/{contact_id}", response_model=DeletedOut)
def delete_contact(
    workspace_id: str,
    contact_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DeletedOut:
    verify_workspace(principal, workspace_id)
    contact = _one_or_404(db, Contact, workspace_id, contact_id)
    db.delete(contact)
    _audit(db, workspace_id=workspace_id, context="contacts", verb="delete",
           entity_id=contact.id, actor_id=principal.user.id)
    db.commit()
    return DeletedOut(deleted=True, context="contacts", id=contact_id)


# ---------------------------------------------------------------------------
# Forms context
# ---------------------------------------------------------------------------


@router.get("/forms", response_model=list[FormOut])
def list_forms(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Form]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Form).where(Form.workspace_id == workspace_id).order_by(Form.created_at.desc())
    ).scalars().all()


@router.post("/forms", response_model=FormOut, status_code=status.HTTP_201_CREATED)
def create_form(
    workspace_id: str,
    body: FormCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Form:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Form).where(Form.workspace_id == workspace_id, Form.name == body.name)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="form name already exists")
    form = Form(
        id=new_id(), workspace_id=workspace_id, name=body.name.strip(),
        description=body.description, fields=body.fields, status=body.status,
        created_at=now(), updated_at=now(),
    )
    db.add(form)
    db.flush()
    _audit(db, workspace_id=workspace_id, context="forms", verb="create",
           entity_id=form.id, actor_id=principal.user.id)
    db.commit()
    return form


@router.get("/forms/{form_id}", response_model=FormOut)
def get_form(
    workspace_id: str,
    form_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Form:
    verify_workspace(principal, workspace_id)
    return _one_or_404(db, Form, workspace_id, form_id)


@router.patch("/forms/{form_id}", response_model=FormOut)
def edit_form(
    workspace_id: str,
    form_id: str,
    body: FormEdit,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Form:
    verify_workspace(principal, workspace_id)
    form = _one_or_404(db, Form, workspace_id, form_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(form, key, value)
    form.updated_at = now()
    _audit(db, workspace_id=workspace_id, context="forms", verb="edit",
           entity_id=form.id, actor_id=principal.user.id)
    db.commit()
    return form


@router.delete("/forms/{form_id}", response_model=DeletedOut)
def delete_form(
    workspace_id: str,
    form_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DeletedOut:
    verify_workspace(principal, workspace_id)
    form = _one_or_404(db, Form, workspace_id, form_id)
    db.delete(form)
    _audit(db, workspace_id=workspace_id, context="forms", verb="delete",
           entity_id=form.id, actor_id=principal.user.id)
    db.commit()
    return DeletedOut(deleted=True, context="forms", id=form_id)


# ---------------------------------------------------------------------------
# Pages context
# ---------------------------------------------------------------------------


@router.get("/pages", response_model=list[PageOut])
def list_pages(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[Page]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(Page).where(Page.workspace_id == workspace_id).order_by(Page.created_at.desc())
    ).scalars().all()


@router.post("/pages", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_page(
    workspace_id: str,
    body: PageCreate,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Page:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(Page).where(Page.workspace_id == workspace_id, Page.slug == body.slug)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="page slug already exists")
    page = Page(
        id=new_id(), workspace_id=workspace_id, title=body.title.strip(),
        slug=body.slug, content=body.content, status=body.status,
        created_at=now(), updated_at=now(),
    )
    db.add(page)
    db.flush()
    _audit(db, workspace_id=workspace_id, context="pages", verb="create",
           entity_id=page.id, actor_id=principal.user.id)
    db.commit()
    return page


@router.get("/pages/{page_id}", response_model=PageOut)
def get_page(
    workspace_id: str,
    page_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> Page:
    verify_workspace(principal, workspace_id)
    return _one_or_404(db, Page, workspace_id, page_id)


@router.patch("/pages/{page_id}", response_model=PageOut)
def edit_page(
    workspace_id: str,
    page_id: str,
    body: PageEdit,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> Page:
    verify_workspace(principal, workspace_id)
    page = _one_or_404(db, Page, workspace_id, page_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(page, key, value)
    page.updated_at = now()
    _audit(db, workspace_id=workspace_id, context="pages", verb="edit",
           entity_id=page.id, actor_id=principal.user.id)
    db.commit()
    return page


@router.delete("/pages/{page_id}", response_model=DeletedOut)
def delete_page(
    workspace_id: str,
    page_id: str,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db: Session = Depends(get_db),
) -> DeletedOut:
    verify_workspace(principal, workspace_id)
    page = _one_or_404(db, Page, workspace_id, page_id)
    db.delete(page)
    _audit(db, workspace_id=workspace_id, context="pages", verb="delete",
           entity_id=page.id, actor_id=principal.user.id)
    db.commit()
    return DeletedOut(deleted=True, context="pages", id=page_id)
