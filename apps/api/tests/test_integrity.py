"""Phase 2 P2-3: CRM transaction integrity tests.

Checks intake idempotency, shared correlation ids, database rollback on
constraint violations, and SAVEPOINT rollback when a job handler fails after a
partial write.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from novara_core.models import Contact, Event, Lead, Notification, OutreachDraft, Task, now
from novara_core.modules import jobs as jobs_mod
from novara_core.modules.jobs import enqueue_job, run_one_job

from .conftest import auth, bootstrap


INTAKE = "/api/v1/workspaces/{wid}/intake/website-form"


def test_repeated_submission_creates_one_workflow_run(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    payload = {
        "submission_id": "crm-integrity-001",
        "email": "integrity.one@example.test",
        "full_name": "Integrity One",
        "company": "Test Co",
        "message": "Please get in touch",
    }
    first = client.post(INTAKE.format(wid=wid), headers=headers, json=payload)
    second = client.post(INTAKE.format(wid=wid), headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json() == second.json()
    result = first.json()

    assert len(db_session.execute(
        select(Contact).where(Contact.workspace_id == wid, Contact.email == payload["email"])
    ).scalars().all()) == 1
    for model in (Lead, Task, Notification, OutreachDraft):
        rows = db_session.execute(
            select(model).where(model.workspace_id == wid)
        ).scalars().all()
        assert len(rows) == 1, model.__name__

    events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid,
            Event.correlation_id == result["correlation_id"],
        )
    ).scalars().all()
    assert len(events) >= 5
    assert len({event.event_type for event in events}) >= 5
    assert all(event.correlation_id == result["correlation_id"] for event in events)


def test_distinct_submission_ids_create_distinct_runs(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = {"email": "integrity.two@example.test", "full_name": "Integrity Two"}
    first = client.post(
        INTAKE.format(wid=wid), headers=headers, json={**base, "submission_id": "run-a"}
    )
    second = client.post(
        INTAKE.format(wid=wid), headers=headers, json={**base, "submission_id": "run-b"}
    )
    assert first.json()["correlation_id"] != second.json()["correlation_id"]
    # One contact, but two qualified workflows and drafts.
    assert len(db_session.execute(select(Contact)).scalars().all()) == 1
    assert len(db_session.execute(select(Lead)).scalars().all()) == 1
    assert len(db_session.execute(select(Task)).scalars().all()) == 2
    assert len(db_session.execute(select(OutreachDraft)).scalars().all()) == 2


def test_constraint_failure_rolls_back_without_partial_contact(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    db_session.add(
        Contact(
            workspace_id=wid,
            email="rollback@example.test",
            full_name="First",
            created_at=now(),
            updated_at=now(),
        )
    )
    db_session.commit()  # the first row is persisted before the failing write
    db_session.add(
        Contact(
            workspace_id=wid,
            email="rollback@example.test",
            full_name="Duplicate",
            created_at=now(),
            updated_at=now(),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
    rows = db_session.execute(
        select(Contact).where(Contact.email == "rollback@example.test")
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].full_name == "First"
    # Session remains usable after the rollback.
    assert db_session.execute(select(Contact)).scalars().all()


def test_failed_handler_discards_partial_writes(client, db_session, monkeypatch):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]

    def partial_writer(db, payload):
        db.add(
            Notification(
                workspace_id=payload["workspace_id"],
                message="partial write must not survive",
                created_at=now(),
            )
        )
        db.flush()
        raise RuntimeError("failed after writing")

    monkeypatch.setitem(jobs_mod._HANDLERS, "test.partial_write", partial_writer)
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="test.partial_write",
        payload={"workspace_id": wid},
        created_by="test-actor",
        max_attempts=1,
    )
    run_one_job(db_session, worker_id="integrity-worker")
    assert job.status == "dead_letter"
    assert "failed after writing" in job.last_error
    leftovers = db_session.execute(
        select(Notification).where(Notification.message == "partial write must not survive")
    ).scalars().all()
    assert leftovers == []


def test_approval_never_sends_external_message(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    intake = client.post(
        INTAKE.format(wid=wid),
        headers=headers,
        json={"submission_id": "approval-001", "email": "approval@example.test"},
    )
    draft_id = intake.json()["draft_id"]
    approved = client.post(
        f"/api/v1/workspaces/{wid}/outreach-drafts/{draft_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_by"]
    approval_event = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid,
            Event.entity_id == draft_id,
            Event.event_type == "outreach.approved",
        )
    ).scalar_one()
    assert "nothing was sent" in approval_event.payload["note"].lower()
