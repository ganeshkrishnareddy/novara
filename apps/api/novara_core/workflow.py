"""Connected workflows built on the shared contracts.

Website submission -> one contact -> lead qualification record -> follow-up task
-> in-app notification -> outreach DRAFT requiring human approval.

This service never sends an external message. Delivery belongs to a separately
authorised adapter.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select

from .events import (
    CONTACT_IDENTIFIED,
    CONTACT_UPDATED,
    LEAD_CREATED,
    NOTIFICATION_CREATED,
    OUTREACH_APPROVED,
    OUTREACH_DRAFT_CREATED,
    TASK_CREATED,
    publish_event,
)
from .models import (
    Company,
    Contact,
    Event,
    Lead,
    Notification,
    OutreachDraft,
    Task,
    Workspace,
    WorkspaceMember,
    new_id,
    now,
)
from .modules.outreach_safety import compliance_footer, evaluate_presend_gate
from .permissions import OUTREACH_APPROVE, has_permission
from .schemas import IntakeResult, WebsiteSubmission

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class UnresolvedTemplateVariables(ValueError):
    """A template referenced data that is not present in this workspace."""

    def __init__(self, variables: list[str]) -> None:
        self.variables = variables
        super().__init__("unresolved template variables: " + ", ".join(sorted(set(variables))))


class DraftCreateRequest(BaseModel):
    """Clean-room, deterministic personalisation input. No AI provider is used."""

    contact_id: str
    subject_template: str
    body_template: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("contact_id")
    @classmethod
    def contact_valid(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("contact_id is required")
        return value

    @field_validator("subject_template", "body_template")
    @classmethod
    def template_valid(cls, value: str, info) -> str:
        value = value.strip()
        if not value:
            raise ValueError("a template must not be blank")
        limit = 200 if info.field_name == "subject_template" else 5000
        if len(value) > limit:
            raise ValueError("template is too long")
        return value


def _workspace(db, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise LookupError("workspace not found")
    return workspace


def _active_member(db, workspace_id: str, user_id: str) -> WorkspaceMember | None:
    return db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()


def _assignee_id(db, workspace_id: str, preferred_user_id: str | None) -> str | None:
    """Pick an assignment inside this workspace. A user id from outside is
    rejected rather than silently trusted."""
    if preferred_user_id:
        member = _active_member(db, workspace_id, preferred_user_id)
        if member is None:
            raise LookupError("assigned user is not an active member of this workspace")
        return member.user_id
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active",
        ).order_by(WorkspaceMember.created_at)
    ).scalars().first()
    return member.user_id if member else None


def _template_variables(db, workspace_id: str, contact: Contact) -> dict[str, str | None]:
    """Read every supported variable from rows owned by this workspace."""
    workspace = _workspace(db, workspace_id)
    company = None
    if contact.company_id:
        company = db.get(Company, contact.company_id)
        if company is not None and company.workspace_id != workspace_id:
            company = None
    if company is None and contact.company_name:
        company = db.execute(
            select(Company).where(
                Company.workspace_id == workspace_id,
                Company.name == contact.company_name,
            )
        ).scalar_one_or_none()
    display_name = contact.full_name or contact.email.split("@")[0]
    return {
        "first_name": display_name.split()[0] if display_name else None,
        "full_name": display_name,
        "email": contact.email,
        "company_name": company.name if company else contact.company_name,
        "company_industry": company.industry if company else None,
        "company_location": company.location if company else None,
        "workspace_name": workspace.name,
    }


def render_personalised_template(template: str, variables: dict[str, str | None]) -> str:
    """Resolve only known variables. Missing values are rejected, never invented."""
    unresolved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            unresolved.append(key)
            return match.group(0)
        value = variables[key]
        if value is None or not str(value).strip():
            unresolved.append(key)
            return match.group(0)
        return str(value)

    rendered = _PLACEHOLDER.sub(replace, template)
    if unresolved or _PLACEHOLDER.search(rendered):
        raise UnresolvedTemplateVariables(unresolved or ["unknown"])
    return rendered


def create_personalised_draft(
    db,
    *,
    workspace_id: str,
    contact_id: str,
    subject_template: str,
    body_template: str,
    actor_user_id: str | None = None,
    publish: bool = True,
) -> OutreachDraft:
    """Create a DRAFT from workspace-owned fields plus the configured footer.

    The result always stops at ``outreach_drafts``. There is deliberately no
    delivery call, and unresolved variables fail closed before a row is added.
    """
    contact = db.execute(
        select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if contact is None:
        raise LookupError("contact not found")
    variables = _template_variables(db, workspace_id, contact)
    subject = render_personalised_template(subject_template, variables)
    body = render_personalised_template(body_template, variables)
    if len(subject) > 300:
        raise ValueError("rendered subject is too long")

    draft = OutreachDraft(
        workspace_id=workspace_id,
        contact_id=contact.id,
        subject=subject,
        body=body.rstrip() + "\n\n" + compliance_footer(db, workspace_id),
        status="draft",
        created_at=now(),
    )
    db.add(draft)
    db.flush()
    if publish:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=OUTREACH_DRAFT_CREATED,
            entity_id=draft.id,
            payload={
                "contact_id": contact.id,
                "status": draft.status,
                "source": "workspace_template",
                "compliance_footer_included": True,
            },
            actor_id=actor_user_id,
        )
    return draft


def handle_website_form(
    db,
    *,
    workspace_id: str,
    submission: WebsiteSubmission,
    actor_user_id: str | None = None,
) -> IntakeResult:
    """Capture a submission once and fan it out to the shared records.

    A submission_id makes retries safe: a second call with the same id returns
    the original result and creates no new rows or events.
    """
    _workspace(db, workspace_id)

    idempotency_key = f"intake:{submission.submission_id}" if submission.submission_id else None
    if idempotency_key:
        prior = db.execute(
            select(Event).where(
                Event.workspace_id == workspace_id,
                Event.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if prior is not None:
            return IntakeResult(**prior.payload["result"])

    contact = db.execute(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == submission.email)
    ).scalar_one_or_none()
    created_contact = contact is None

    if created_contact:
        contact = Contact(
            workspace_id=workspace_id,
            email=submission.email,
            full_name=submission.full_name,
            company_name=submission.company,
            source=submission.source,
            lifecycle_stage="lead",
            tags=[],
            custom_fields={},
        )
        db.add(contact)
        db.flush()
    else:
        contact.updated_at = now()
        if submission.full_name and not contact.full_name:
            contact.full_name = submission.full_name
        if submission.company and not contact.company_name:
            contact.company_name = submission.company

    assignee_id = _assignee_id(db, workspace_id, actor_user_id)

    lead = db.execute(
        select(Lead).where(Lead.workspace_id == workspace_id, Lead.contact_id == contact.id)
    ).scalar_one_or_none()
    if lead is None:
        lead = Lead(
            workspace_id=workspace_id,
            contact_id=contact.id,
            source=submission.source,
            status="new",
            priority="normal",
            score=10 if submission.message else 0,
            owner_id=assignee_id,
        )
        db.add(lead)
        db.flush()

    task = Task(
        workspace_id=workspace_id,
        contact_id=contact.id,
        title=f"Qualify lead: {contact.full_name or contact.email}",
        status="open",
        priority="normal",
        owner_id=assignee_id,
    )
    db.add(task)

    display_name = contact.full_name or contact.email.split("@")[0]
    draft = create_personalised_draft(
        db,
        workspace_id=workspace_id,
        contact_id=contact.id,
        subject_template="Following up, {{full_name}}",
        body_template=(
            "Hi {{first_name}},\n\nThank you for getting in touch with {{workspace_name}}. "
            "We have received your message and will follow up shortly.\n\n— The team"
        ),
        publish=False,
    )

    notification = Notification(
        workspace_id=workspace_id,
        contact_id=contact.id,
        user_id=assignee_id,
        message=f"New lead captured: {display_name} ({contact.email})",
        read=False,
    )
    db.add(notification)
    db.flush()

    correlation_id = new_id()
    result = IntakeResult(
        workspace_id=workspace_id,
        contact_id=contact.id,
        lead_id=lead.id,
        task_id=task.id,
        notification_id=notification.id,
        draft_id=draft.id,
        created_contact=created_contact,
        correlation_id=correlation_id,
    )

    event_kwargs = dict(workspace_id=workspace_id, correlation_id=correlation_id)
    publish_event(
        db,
        event_type=CONTACT_IDENTIFIED if created_contact else CONTACT_UPDATED,
        entity_id=contact.id,
        idempotency_key=idempotency_key,
        payload={"result": result.model_dump(), "email": contact.email, "created": created_contact},
        actor_id=actor_user_id,
        **event_kwargs,
    )
    publish_event(
        db,
        event_type=LEAD_CREATED,
        entity_id=lead.id,
        payload={"contact_id": contact.id, "source": lead.source},
        actor_id=actor_user_id,
        **event_kwargs,
    )
    publish_event(
        db,
        event_type=TASK_CREATED,
        entity_id=task.id,
        payload={"contact_id": contact.id, "title": task.title},
        actor_id=actor_user_id,
        **event_kwargs,
    )
    publish_event(
        db,
        event_type=NOTIFICATION_CREATED,
        entity_id=notification.id,
        payload={"contact_id": contact.id, "user_id": notification.user_id},
        **event_kwargs,
    )
    publish_event(
        db,
        event_type=OUTREACH_DRAFT_CREATED,
        entity_id=draft.id,
        payload={"contact_id": contact.id, "status": draft.status},
        **event_kwargs,
    )

    db.commit()
    return result


def approve_outreach_draft(
    db,
    *,
    workspace_id: str,
    draft_id: str,
    actor_user_id: str,
) -> OutreachDraft:
    """Human approval gate. The actor must be an active member of this workspace
    whose role grants the outreach:approve permission. Approval sends nothing."""
    _workspace(db, workspace_id)

    member = _active_member(db, workspace_id, actor_user_id)
    if member is None:
        raise PermissionError("the approving user is not an active member of this workspace")
    if not has_permission(member.role, OUTREACH_APPROVE):
        raise PermissionError("this role cannot approve external outreach")

    draft = db.execute(
        select(OutreachDraft).where(
            OutreachDraft.id == draft_id, OutreachDraft.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if draft is None:
        raise LookupError("outreach draft not found")

    # Approval is the human gate; the deterministic pre-send gate must also pass
    # (required fields, compliance footer and suppression/opt-out) before a
    # draft may advance. Passing still sends nothing in this build.
    decision = evaluate_presend_gate(
        db,
        workspace_id=workspace_id,
        draft_id=draft_id,
        actor_id=actor_user_id,
        require_approval=False,
    )
    if not decision["allowed"]:
        db.commit()  # persist the rejection audit event
        raise PermissionError("presend gate rejected: " + "; ".join(decision["failures"]))

    if draft.status != "approved":
        draft.status = "approved"
        draft.approved_at = now()
        draft.approved_by = actor_user_id
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=OUTREACH_APPROVED,
            entity_id=draft.id,
            payload={
                "contact_id": draft.contact_id,
                "actor_user_id": actor_user_id,
                "actor_role": member.role,
                "note": "approved for a future authorised delivery adapter; nothing was sent",
            },
            actor_id=actor_user_id,
        )
        db.commit()
    return draft
