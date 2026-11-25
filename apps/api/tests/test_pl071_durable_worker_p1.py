"""Named acceptance test for PL-071 (durable asynchronous job worker).

Proves a job enqueued through the HTTP API is processed by the background
``JobWorker`` without any request calling ``POST /jobs/run``, that the side
effect is a real database row, that the durable state and audit events survive,
and that a workspace-scoped worker cannot claim another workspace's job.

No Celery broker, external service or network call is involved: the worker polls
the same durable job table the API writes.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from novara_core.database import Base, get_db
from novara_core.main import API, app
from novara_core.models import Event, Notification, new_id, now
from novara_core.modules import import_all
from novara_core.modules.jobs import (
    JOB_COMPLETED,
    JOB_STARTED,
    Job,
    JobWorker,
    enqueue_job,
)

from .conftest import auth, bootstrap

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture()
def worker_app(tmp_path):
    import_all()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'worker.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _wait_for_job(client, tickets: str, headers, job_id: str, status: str, seconds: float = 10.0):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        response = client.get(f"{tickets}/{job_id}", headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] == status:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never reached {status}; last={last}")


def test_pl071_background_worker_processes_jobs_asynchronously(worker_app):
    client, factory = worker_app
    tokens = bootstrap(client, "PL071", "pl071-owner@example.com")
    wid, token = tokens["workspace_id"], tokens["access_token"]
    headers = auth(token)
    jobs = f"{API}/workspaces/{wid}/jobs"

    created = client.post(
        jobs,
        headers=headers,
        json={
            "job_type": "notification.create",
            "payload": {
                "workspace_id": wid,
                "message": "Processed by the background worker",
            },
            "idempotency_key": "pl071-async",
        },
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "queued"
    assert job["locked_by"] is None

    # Nobody calls POST /jobs/run. The background worker must do the work.
    worker = JobWorker(
        factory,
        worker_id="pl071-worker",
        workspace_id=wid,
        poll_seconds=0.05,
        recover_after_seconds=1,
    )
    thread = worker.start()
    try:
        finished = _wait_for_job(client, jobs, headers, job["id"], "succeeded")
    finally:
        worker.stop()

    assert not thread.is_alive()
    assert set(finished["result"]) == {"notification_id"}
    assert finished["attempts"] == 0
    assert finished["finished_at"] is not None

    # The side effect is a real notification row, not a fabricated response.
    db = factory()
    try:
        notification = db.execute(
            select(Notification).where(Notification.workspace_id == wid)
        ).scalar_one()
        assert notification.message == "Processed by the background worker"
        assert notification.id == finished["result"]["notification_id"]
        event_types = set(
            db.execute(select(Event.event_type).where(Event.workspace_id == wid))
            .scalars()
            .all()
        )
        assert {JOB_STARTED, JOB_COMPLETED} <= event_types
        # Durable state: the finished job is still there with its outcome.
        stored = db.execute(select(Job).where(Job.id == job["id"])).scalar_one()
        assert stored.status == "succeeded"
        assert stored.locked_by is None and stored.locked_at is None
    finally:
        db.close()

    # A restarted worker does not re-run a completed job.
    restarted = JobWorker(factory, worker_id="pl071-worker-2", poll_seconds=0.05)
    summary = restarted.tick()
    assert summary["claimed"] == 0
    db = factory()
    try:
        assert db.execute(select(Notification).where(Notification.workspace_id == wid)).scalars().all()
        assert db.execute(select(Event).where(Event.event_type == JOB_COMPLETED)).scalars().all()
    finally:
        db.close()


def test_pl071_worker_is_workspace_scoped(worker_app):
    client, factory = worker_app
    tokens = bootstrap(client, "PL071S", "pl071s-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    jobs = f"{API}/workspaces/{wid}/jobs"

    mine = client.post(
        jobs,
        headers=headers,
        json={"job_type": "noop", "payload": {}},
    )
    assert mine.status_code == 201, mine.text

    # A job owned by another workspace must never be claimed by this worker.
    other_workspace = new_id()
    db = factory()
    try:
        foreign = enqueue_job(
            db,
            workspace_id=other_workspace,
            job_type="noop",
            payload={},
            created_by="foreign-owner",
        )
        foreign_id = foreign.id
        db.commit()
    finally:
        db.close()

    worker = JobWorker(
        factory,
        worker_id="pl071-scoped",
        workspace_id=wid,
        poll_seconds=0.05,
    )
    summary = worker.tick()
    assert summary["claimed"] == 1
    assert summary["succeeded"] == 1

    db = factory()
    try:
        assert db.execute(select(Job).where(Job.id == mine.json()["id"])).scalar_one().status == "succeeded"
        untouched = db.execute(select(Job).where(Job.id == foreign_id)).scalar_one()
        assert untouched.status == "queued"
        assert untouched.attempts == 0
    finally:
        db.close()


def test_pl071_worker_script_exists_and_reports_one_cycle():
    source = (SCRIPTS / "job_worker.py").read_text(encoding="utf-8")
    assert "JobWorker" in source
    assert "--once" in source
    assert "session_factory" not in source  # script uses the configured database
