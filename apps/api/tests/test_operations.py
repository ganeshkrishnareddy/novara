"""Phase 2 P2-6: audit and monitoring views over real workspace rows."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from novara_core.database import get_db
from novara_core.models import Event, User
from novara_core.modules.jobs import enqueue_job
from novara_core.modules.operations import router

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/operations"
INTEGRATIONS = "/api/v1/workspaces/{wid}/integrations"
ADAPTERS = "/api/v1/workspaces/{wid}/adapters"
INTAKE = "/api/v1/workspaces/{wid}/intake/website-form"


@pytest.fixture()
def ops_api(db_session):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_summary_reports_real_counts(ops_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()

    intake = client.post(
        INTAKE.format(wid=wid),
        headers=headers,
        json={"submission_id": "ops-001", "email": "ops@example.test", "full_name": "Ops Test"},
    )
    assert intake.status_code == 201
    enqueue_job(db_session, workspace_id=wid, job_type="noop", created_by=owner.id)

    summary = ops_api.get(BASE.format(wid=wid) + "/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["workspace_id"] == wid
    assert body["contacts"] == 1
    assert body["leads"] == 1
    assert body["open_tasks"] == 1
    assert body["pending_drafts"] == 1
    assert body["unread_notifications"] == 1
    assert body["jobs_queued"] == 1
    assert body["events_total"] >= 5
    assert "computed from stored workspace rows" in body["notes"]


def test_components_distinguish_local_and_blocked(ops_api, client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = ops_api.get(BASE.format(wid=wid) + "/components", headers=headers)
    assert response.status_code == 200
    states = {item["name"]: item["state"] for item in response.json()["components"]}
    assert states["database"] == "local"
    assert states["job_queue"] == "local"
    assert states["adapters"] == "local_mock"
    assert states["ai_providers"] == "blocked"
    assert states["containers"] == "blocked"


def test_audit_filters_by_correlation_and_type(ops_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    intake = client.post(
        INTAKE.format(wid=wid),
        headers=headers,
        json={"submission_id": "audit-001", "email": "audit@example.test"},
    )
    correlation_id = intake.json()["correlation_id"]
    response = ops_api.get(
        BASE.format(wid=wid) + "/audit",
        params={"correlation_id": correlation_id, "limit": 50},
        headers=headers,
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 5
    assert all(row["correlation_id"] == correlation_id for row in rows)

    filtered = ops_api.get(
        BASE.format(wid=wid) + "/audit",
        params={"event_type": "lead.created"},
        headers=headers,
    )
    assert len(filtered.json()) == 1
    assert db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()


def test_operations_are_workspace_scoped(ops_api, client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ops.other@example.test",
            "display_name": "Other",
            "password": "Password123!",
        },
    )
    other_wid, other_headers = registered.json()["workspace_id"], auth(registered.json()["access_token"])

    for suffix in ("/summary", "/components", "/audit"):
        assert ops_api.get(BASE.format(wid=wid) + suffix, headers=other_headers).status_code == 403
    other_summary = ops_api.get(BASE.format(wid=other_wid) + "/summary", headers=other_headers)
    assert other_summary.json()["contacts"] == 0
    assert other_summary.json()["events_total"] == 0
