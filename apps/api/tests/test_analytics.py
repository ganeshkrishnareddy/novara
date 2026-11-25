from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Contact, Event, Lead, Task, User, new_id, now
from novara_core.modules import analytics

from .conftest import auth, bootstrap

PREFIX = "/api/v1/workspaces/{workspace_id}/analytics"


def _ensure_routes() -> None:
    already = any(
        (getattr(route, "path", "") or "").startswith(PREFIX)
        or getattr(route, "original_router", None) is analytics.router
        for route in app.routes
    )
    if not already:
        app.include_router(analytics.router)
    # FastAPI 0.139 wraps included routers without a .path attribute; add one so
    # generic route-introspection helpers keep working during the test run.
    for route in app.routes:
        if getattr(route, "original_router", None) is analytics.router and not hasattr(route, "path"):
            route.path = PREFIX


@pytest.fixture(autouse=True)
def _module_router() -> None:
    _ensure_routes()


def _second_workspace(client, headers):
    response = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other Workspace"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def test_experiment_crud_results_and_events(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/analytics"

    created = client.post(
        base,
        headers=headers,
        json={
            "name": "Onboarding A/B",
            "metric_name": "activation_rate",
            "hypothesis": "Shorter form converts better",
            "baseline": 0.2,
            "target": 0.3,
        },
    )
    assert created.status_code == 201, created.text
    experiment = created.json()
    assert experiment["status"] == "draft"
    assert experiment["owner_id"]

    listed = client.get(base, headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [experiment["id"]]

    fetched = client.get(f"{base}/{experiment['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Onboarding A/B"

    updated = client.patch(
        f"{base}/{experiment['id']}", headers=headers, json={"target": 0.35}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["target"] == 0.35

    status = client.post(
        f"{base}/{experiment['id']}/status", headers=headers, json={"status": "running"}
    )
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "running"

    recorded_at = now().replace(microsecond=0).isoformat()
    result = client.post(
        f"{base}/{experiment['id']}/results",
        headers=headers,
        json={"variant": "control", "impressions": 100, "conversions": 20, "recorded_at": recorded_at},
    )
    assert result.status_code == 200, result.text
    result_id = result.json()["id"]

    # Same experiment/variant/recorded_at is an upsert, not a duplicate.
    again = client.post(
        f"{base}/{experiment['id']}/results",
        headers=headers,
        json={"variant": "control", "impressions": 120, "conversions": 24, "recorded_at": recorded_at},
    )
    assert again.status_code == 200, again.text
    assert again.json()["id"] == result_id
    results = client.get(f"{base}/{experiment['id']}/results", headers=headers)
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["conversions"] == 24

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()
    types = [event.event_type for event in events]
    for expected in (
        "experiment.created",
        "experiment.result_recorded",
        "experiment.status_changed",
    ):
        assert expected in types, types
    owner_id = db_session.execute(
        select(User).where(User.email == "owner@example.com")
    ).scalar_one().id
    module_events = [event for event in events if event.event_type.startswith("experiment.")]
    assert module_events
    assert all(event.payload.get("actor_id") == owner_id for event in module_events)

    deleted = client.delete(f"{base}/{experiment['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"{base}/{experiment['id']}", headers=headers).status_code == 404


def test_funnel_summary_counts_workspace_shared_tables(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    contact_one = Contact(id=new_id(), workspace_id=wid, email="funnel@example.com", full_name="Funnel")
    contact_two = Contact(id=new_id(), workspace_id=wid, email="funnel2@example.com", full_name="Funnel Two")
    lead_one = Lead(id=new_id(), workspace_id=wid, contact_id=contact_one.id, status="converted")
    lead_two = Lead(id=new_id(), workspace_id=wid, contact_id=contact_two.id, status="new")
    task_one = Task(id=new_id(), workspace_id=wid, title="Call funnel lead")
    task_two = Task(id=new_id(), workspace_id=wid, title="Send proposal")
    db_session.add_all([contact_one, contact_two, lead_one, lead_two, task_one, task_two])
    db_session.commit()

    response = client.get(
        f"/api/v1/workspaces/{wid}/analytics/funnel", headers=auth(tokens["access_token"])
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"contacts": 2, "leads": 2, "converted_leads": 1, "tasks": 2}


def test_event_volume_with_date_range(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    headers = auth(tokens["access_token"])
    old = now() - timedelta(days=10)
    recent = now() - timedelta(hours=1)
    db_session.add_all(
        [
            Event(
                id=new_id(), event_type="volume.test", occurred_at=old,
                workspace_id=wid, correlation_id=new_id(), payload={},
            ),
            Event(
                id=new_id(), event_type="volume.test", occurred_at=recent,
                workspace_id=wid, correlation_id=new_id(), payload={},
            ),
            Event(
                id=new_id(), event_type="volume.test", occurred_at=recent,
                workspace_id=wid, correlation_id=new_id(), payload={},
            ),
        ]
    )
    db_session.commit()

    all_time = client.get(f"/api/v1/workspaces/{wid}/analytics/events/volume", headers=headers)
    assert all_time.status_code == 200, all_time.text
    counts = {row["event_type"]: row["count"] for row in all_time.json()}
    assert counts["volume.test"] == 3

    date_from = (now() - timedelta(days=1)).isoformat()
    date_to = (now() + timedelta(days=1)).isoformat()
    ranged = client.get(
        f"/api/v1/workspaces/{wid}/analytics/events/volume",
        headers=headers,
        params={"date_from": date_from, "date_to": date_to},
    )
    assert ranged.status_code == 200, ranged.text
    ranged_counts = {row["event_type"]: row["count"] for row in ranged.json()}
    assert ranged_counts["volume.test"] == 2

    invalid = client.get(
        f"/api/v1/workspaces/{wid}/analytics/events/volume",
        headers=headers,
        params={"date_from": date_to, "date_to": date_from},
    )
    assert invalid.status_code == 422


def test_workspace_isolation(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)

    foreign = client.post(
        f"/api/v1/workspaces/{other_wid}/analytics",
        headers=other_headers,
        json={"name": "Foreign experiment", "metric_name": "rate"},
    )
    assert foreign.status_code == 201, foreign.text
    foreign_id = foreign.json()["id"]

    own = client.post(
        f"/api/v1/workspaces/{wid}/analytics",
        headers=headers,
        json={"name": "Own experiment", "metric_name": "rate"},
    )
    assert own.status_code == 201, own.text

    assert client.get(
        f"/api/v1/workspaces/{wid}/analytics/{foreign_id}", headers=headers
    ).status_code == 404
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/analytics", headers=headers
    ).status_code == 403
    assert client.post(
        f"/api/v1/workspaces/{other_wid}/analytics", headers=headers,
        json={"name": "Intruder", "metric_name": "rate"},
    ).status_code == 403

    db_session.add(Contact(id=new_id(), workspace_id=wid, email="own@example.com"))
    db_session.commit()
    own_funnel = client.get(f"/api/v1/workspaces/{wid}/analytics/funnel", headers=headers).json()
    other_funnel = client.get(
        f"/api/v1/workspaces/{other_wid}/analytics/funnel", headers=other_headers
    ).json()
    assert own_funnel["contacts"] == 1
    assert other_funnel["contacts"] == 0

    own_events = client.get(
        f"/api/v1/workspaces/{wid}/analytics/events/volume", headers=headers
    ).json()
    other_events = client.get(
        f"/api/v1/workspaces/{other_wid}/analytics/events/volume", headers=other_headers
    ).json()
    assert {row["event_type"] for row in own_events} == {"experiment.created"}
    assert {row["event_type"] for row in other_events} == {"experiment.created"}


def test_invalid_payloads(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/analytics"

    assert client.post(
        base, headers=headers, json={"name": "   ", "metric_name": "rate"}
    ).status_code == 422
    assert client.post(
        base, headers=headers, json={"name": "x", "metric_name": "rate", "workspace_id": "other"}
    ).status_code == 422
    assert client.post(
        base, headers=headers, json={"name": "x", "metric_name": "rate", "status": "unknown"}
    ).status_code == 422

    created = client.post(
        base, headers=headers, json={"name": "Valid", "metric_name": "rate"}
    ).json()
    results = f"{base}/{created['id']}/results"
    assert client.post(
        results, headers=headers,
        json={"variant": "a", "impressions": -1, "conversions": 0},
    ).status_code == 422
    assert client.post(
        results, headers=headers,
        json={"variant": "a", "impressions": 10, "conversions": 11},
    ).status_code == 422
    assert client.post(
        results, headers=headers,
        json={"variant": "a", "impressions": 1, "conversions": 0, "recorded_at": "not-a-date"},
    ).status_code == 422
