"""The shared event envelope and append-only publish function.

Every module writes through this function, so the audit log and all cross-module
automation consume one shape. Events are never updated or deleted.
"""

from __future__ import annotations

from sqlalchemy import select

from .models import Event, new_id, now

CONTACT_IDENTIFIED = "contact.identified"
CONTACT_UPDATED = "contact.updated"
CONTACT_EXTERNAL_ID_UPDATED = "contact.external_id_updated"
CONTACT_ARCHIVED = "contact.archived"
CONTACT_RESTORED = "contact.restored"
CONTACT_DELETED = "contact.deleted"
LEAD_CREATED = "lead.created"
LEAD_QUALIFIED = "lead.qualified"
LEAD_CONVERTED = "lead.converted"
COMPANY_CREATED = "company.created"
COMPANY_UPDATED = "company.updated"
COMPANY_ARCHIVED = "company.archived"
COMPANY_RESTORED = "company.restored"
NOTE_CREATED = "note.created"
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
NOTIFICATION_CREATED = "notification.created"
NOTIFICATION_SEEN = "notification.seen"
NOTIFICATION_READ = "notification.read"
NOTIFICATION_READ_ALL = "notification.read_all"
NOTIFICATION_SETTINGS_UPDATED = "notification.settings_updated"
OUTREACH_DRAFT_CREATED = "outreach.draft_created"
OUTREACH_APPROVED = "outreach.approved"
MEMBER_INVITED = "member.invited"
MEMBER_JOINED = "member.joined"
MEMBER_UPDATED = "member.updated"

EVENT_TYPES = {
        CONTACT_IDENTIFIED,
        CONTACT_UPDATED,
        CONTACT_EXTERNAL_ID_UPDATED,
        CONTACT_ARCHIVED,
        CONTACT_RESTORED,
        CONTACT_DELETED,
        LEAD_CREATED,
        LEAD_QUALIFIED,
        LEAD_CONVERTED,
        COMPANY_CREATED,
        COMPANY_UPDATED,
        COMPANY_ARCHIVED,
        COMPANY_RESTORED,
        NOTE_CREATED,
        TASK_CREATED,
        TASK_UPDATED,
        NOTIFICATION_CREATED,
        NOTIFICATION_SEEN,
        NOTIFICATION_READ,
        NOTIFICATION_READ_ALL,
        NOTIFICATION_SETTINGS_UPDATED,
        OUTREACH_DRAFT_CREATED,
        OUTREACH_APPROVED,
        MEMBER_INVITED,
        MEMBER_JOINED,
        MEMBER_UPDATED,
}


def register_event_types(*names: str) -> None:
    """Modules register their event names at import time. The registry stays
    central without any module needing to edit this shared file."""
    EVENT_TYPES.update(names)


def publish_event(
    db,
    *,
    workspace_id: str,
    event_type: str,
    entity_id: str | None = None,
    payload: dict | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    actor_id: str | None = None,
) -> Event:
    """Append one event. A repeated idempotency key within a workspace returns
    the original event instead of creating a duplicate."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type}")

    if idempotency_key:
        existing = db.execute(
            select(Event).where(
                Event.workspace_id == workspace_id,
                Event.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    event_payload = dict(payload or {})
    if actor_id:
        event_payload["actor_id"] = actor_id

    event = Event(
        id=new_id(),
        event_type=event_type,
        occurred_at=now(),
        workspace_id=workspace_id,
        entity_id=entity_id,
        schema_version=1,
        correlation_id=correlation_id or new_id(),
        idempotency_key=idempotency_key,
        payload=event_payload,
    )
    db.add(event)
    db.flush()
    return event
