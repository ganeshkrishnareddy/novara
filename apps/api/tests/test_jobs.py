"""Phase 2 P2-4: durable job queue tests.

Covers enqueue idempotency, local handler execution, retry with backoff,
dead-lettering, manual retry, cancellation, crash recovery, workspace isolation
and role permissions. No external side effect is possible in these tests.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from novara_core.database import get_db
from novara_core.models import Event, Notification, User, WorkspaceMember, new_id, now
from novara_core.modules import jobs as jobs_mod
from novara_core.modules.jobs import (
    JOB_DEAD_LETTER,
    JOB_RECOVERED,
    JOB_RETRIED,
    Job,
    claim_job,
    enqueue_job,
    recover_stale_jobs,
    run_one_job,
    run_pending_jobs,
    router,
)
from novara_core.security import create_session, hash_password

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/jobs"


@pytest.fixture()
def jobs_api(db_session):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _owner_id(db_session) -> str:
    return db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one().id


def _member_headers(db_session, workspace_id: str, role: str, email: str):
    user = User(
        id=new_id(),
        email=email,
        display_name="Test member",
        password_hash=hash_password("Password123!"),
        created_at=now(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            status="active",
            created_at=now(),
        )
    )
    db_session.flush()
    _, access, _ = create_session(db_session, user_id=user.id, workspace_id=workspace_id)
    db_session.commit()
    return auth(access)


def _event_count(db_session, wid: str, event_type: str, entity_id: str | None = None) -> int:
    query = select(Event).where(Event.workspace_id == wid, Event.event_type == event_type)
    if entity_id:
        query = query.where(Event.entity_id == entity_id)
    return len(db_session.execute(query).scalars().all())


def test_enqueue_is_idempotent_and_audited(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    owner_id = _owner_id(db_session)

    first = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="noop",
        payload={"hello": "world"},
        created_by=owner_id,
        idempotency_key="welcome-job-1",
    )
    second = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="noop",
        payload={"different": True},
        created_by=owner_id,
        idempotency_key="welcome-job-1",
    )
    assert first.id == second.id
    assert first.correlation_id == second.correlation_id
    assert first.payload == {"hello": "world"}
    assert _event_count(db_session, wid, "job.queued", first.id) == 1
    assert first.status == "queued" and first.attempts == 0


def test_local_handler_creates_real_notification(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    owner_id = _owner_id(db_session)

    enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="notification.create",
        payload={"workspace_id": wid, "message": "Queue is healthy"},
        created_by=owner_id,
    )
    summary = run_pending_jobs(db_session, worker_id="worker-1", limit=5)
    assert summary == {"claimed": 1, "succeeded": 1, "retried": 0, "dead_lettered": 0}

    notifications = db_session.execute(
        select(Notification).where(Notification.workspace_id == wid)
    ).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].message == "Queue is healthy"
    job = db_session.execute(select(Job)).scalar_one()
    assert job.status == "succeeded"
    assert job.result["notification_id"] == notifications[0].id
    assert job.finished_at is not None and job.locked_at is None


def test_retry_backoff_then_success(client, db_session, monkeypatch):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    owner_id = _owner_id(db_session)
    calls = {"n": 0}

    def flaky(db, payload):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary failure")
        return {"ok": True}

    monkeypatch.setitem(jobs_mod._HANDLERS, "test.flaky", flaky)
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="test.flaky",
        created_by=owner_id,
        max_attempts=3,
        retry_delay_seconds=1,
    )
    first_run_at = job.run_at
    run_one_job(db_session, worker_id="w", job_types=["test.flaky"])
    assert job.status == "queued" and job.attempts == 1
    assert job.run_at > first_run_at
    assert "temporary failure" in job.last_error
    # Simulate the backoff window elapsing before the next attempt.
    job.run_at = now() - timedelta(seconds=1)
    db_session.flush()
    run_one_job(db_session, worker_id="w", job_types=["test.flaky"])
    assert job.status == "queued" and job.attempts == 2
    job.run_at = now() - timedelta(seconds=1)  # second backoff window elapsed
    db_session.flush()
    run_one_job(db_session, worker_id="w", job_types=["test.flaky"])
    assert job.status == "succeeded" and calls["n"] == 3
    assert _event_count(db_session, wid, JOB_RETRIED, job.id) == 2
    assert _event_count(db_session, wid, "job.completed", job.id) == 1


def test_dead_letter_and_manual_retry(client, db_session, monkeypatch):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    owner_id = _owner_id(db_session)

    def always_fail(db, payload):
        raise ValueError("permanent boom")

    monkeypatch.setitem(jobs_mod._HANDLERS, "test.always_fail", always_fail)
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="test.always_fail",
        created_by=owner_id,
        max_attempts=2,
        retry_delay_seconds=1,
    )
    run_one_job(db_session, worker_id="w")
    job.run_at = now() - timedelta(seconds=1)  # backoff window elapsed
    db_session.flush()
    run_one_job(db_session, worker_id="w")
    assert job.status == "dead_letter"
    assert job.attempts == 2
    assert "permanent boom" in job.last_error
    assert _event_count(db_session, wid, JOB_DEAD_LETTER, job.id) == 1

    headers = auth(tokens["access_token"])
    # Retry through the API after replacing the failing handler.
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setitem(jobs_mod._HANDLERS, "test.always_fail", lambda db, p: {"ok": True})
    with TestClient(app) as api:
        response = api.post(BASE.format(wid=wid) + f"/{job.id}/retry", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    assert response.json()["attempts"] == 0
    run_one_job(db_session, worker_id="w")
    assert job.status == "succeeded"
    app.dependency_overrides.clear()


def test_unknown_handler_dead_letters_without_consuming_retries(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="does.not.exist",
        created_by=_owner_id(db_session),
        max_attempts=3,
    )
    run_one_job(db_session, worker_id="w")
    assert job.status == "dead_letter"
    assert job.attempts == 1
    assert "no local handler" in job.last_error


def test_cancel_and_retry_lifecycle(client, db_session, jobs_api):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    headers = auth(tokens["access_token"])
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="noop",
        created_by=_owner_id(db_session),
        run_at=now() + timedelta(hours=1),
    )
    response = jobs_api.post(BASE.format(wid=wid) + f"/{job.id}/cancel", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    again = jobs_api.post(BASE.format(wid=wid) + f"/{job.id}/cancel", headers=headers)
    assert again.status_code == 409
    retried = jobs_api.post(BASE.format(wid=wid) + f"/{job.id}/retry", headers=headers)
    assert retried.status_code == 200 and retried.json()["status"] == "queued"


def test_recover_stale_jobs_after_crash(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="noop",
        created_by=_owner_id(db_session),
    )
    claimed = claim_job(db_session, worker_id="crashed-worker")
    assert claimed is not None and claimed.id == job.id
    job.locked_at = now() - timedelta(seconds=900)
    db_session.flush()
    recovered = recover_stale_jobs(db_session, stale_after_seconds=300)
    assert recovered == 1
    assert job.status == "queued" and job.locked_by is None
    assert _event_count(db_session, wid, JOB_RECOVERED, job.id) == 1
    assert claim_job(db_session, worker_id="new-worker") is not None


def test_recovery_is_scoped_to_one_workspace(client, db_session):
    tokens = bootstrap(client)
    w1 = tokens["workspace_id"]
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "second-owner@example.com",
            "display_name": "Second owner",
            "password": "Password123!",
        },
    )
    assert registered.status_code == 200, registered.text
    w2 = registered.json()["workspace_id"]

    owner1 = _owner_id(db_session)
    owner2 = db_session.execute(
        select(User).where(User.email == "second-owner@example.com")
    ).scalar_one().id
    enqueue_job(db_session, workspace_id=w1, job_type="noop", created_by=owner1)
    job2 = enqueue_job(db_session, workspace_id=w2, job_type="noop", created_by=owner2)
    claim_job(db_session, worker_id="crashed-worker")
    job2.locked_at = now() - timedelta(seconds=900)
    job2.status = "running"
    job2.locked_by = "crashed-worker"
    db_session.flush()
    assert recover_stale_jobs(db_session, stale_after_seconds=300) == 1
    assert job2.status == "queued"


def test_job_api_isolation_and_permissions(client, db_session, jobs_api):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    owner_headers = auth(tokens["access_token"])
    created = jobs_api.post(
        BASE.format(wid=wid),
        headers=owner_headers,
        json={"job_type": "noop", "payload": {"x": 1}, "idempotency_key": "api-key-1"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "queued"

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-owner@example.com",
            "display_name": "Other owner",
            "password": "Password123!",
        },
    )
    other_wid = registered.json()["workspace_id"]
    other_headers = auth(registered.json()["access_token"])
    assert jobs_api.get(BASE.format(wid=other_wid), headers=other_headers).json() == []
    assert jobs_api.get(BASE.format(wid=wid), headers=other_headers).status_code == 403
    assert jobs_api.get(
        BASE.format(wid=wid) + f"/{created.json()['id']}", headers=other_headers
    ).status_code == 403

    sales_headers = _member_headers(
        db_session, wid, "sales_rep", f"rep-{new_id()[:8]}@example.com"
    )
    denied = jobs_api.post(
        BASE.format(wid=wid), headers=sales_headers, json={"job_type": "noop"}
    )
    assert denied.status_code == 403
    read_only = jobs_api.get(BASE.format(wid=wid), headers=sales_headers)
    assert read_only.status_code == 403  # sales_rep has no EVENT_READ

    stats = jobs_api.get(BASE.format(wid=wid) + "/stats", headers=owner_headers)
    assert stats.status_code == 200
    assert stats.json()["queued"] >= 1
    assert "notification.create" in stats.json()["handlers"]
