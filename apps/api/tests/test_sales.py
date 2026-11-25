"""Workspace-scoped sales pipeline tests."""

from __future__ import annotations

import pytest

from novara_core.main import app
from novara_core.modules.sales import router as sales_router

from .conftest import auth, bootstrap


@pytest.fixture(autouse=True)
def _register_sales_router():
    """Attach our router when the core app has not wired capability modules yet.

    The app is shared across the suite, so restore its route table afterwards.
    """
    prefix = "/api/v1/workspaces/{workspace_id}/deals"
    if any(getattr(route, "path", "").startswith(prefix) for route in app.routes):
        yield
        return
    original_routes = list(app.routes)
    app.include_router(sales_router)
    try:
        yield
    finally:
        app.routes[:] = original_routes
        mark_changed = getattr(app.router, "_mark_routes_changed", None)
        if mark_changed is not None:
            mark_changed()


def _create_contact(client, wid: str, headers: dict, email: str) -> str:
    response = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": email, "full_name": "Jane Doe", "company_name": "Acme Co"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_deal_lifecycle_filters_summary_activities_and_events(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]
    contact_id = _create_contact(client, wid, headers, "jane@example.com")

    created = client.post(
        f"/api/v1/workspaces/{wid}/deals",
        headers=headers,
        json={
            "title": "Enterprise renewal",
            "company": "Acme Co",
            "contact_id": contact_id,
            "value": 12500.50,
            "stage": "qualified",
            "probability": 60,
            "expected_close_at": "2026-12-31T10:00:00Z",
        },
    )
    assert created.status_code == 201, created.text
    deal = created.json()
    assert deal["workspace_id"] == wid
    assert deal["owner_id"] == user_id
    assert float(deal["value"]) == pytest.approx(12500.50)

    second = client.post(
        f"/api/v1/workspaces/{wid}/deals",
        headers=headers,
        json={"title": "New logo", "company": "Globex", "value": 500, "stage": "new"},
    )
    assert second.status_code == 201, second.text

    listed = client.get(f"/api/v1/workspaces/{wid}/deals", headers=headers)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()} == {deal["id"], second.json()["id"]}

    filtered = client.get(f"/api/v1/workspaces/{wid}/deals?stage=qualified", headers=headers)
    assert [row["id"] for row in filtered.json()] == [deal["id"]]

    searched = client.get(f"/api/v1/workspaces/{wid}/deals?search=renewal", headers=headers)
    assert [row["id"] for row in searched.json()] == [deal["id"]]

    fetched = client.get(f"/api/v1/workspaces/{wid}/deals/{deal['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Enterprise renewal"

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/deals/{deal['id']}",
        headers=headers,
        json={"stage": "won", "value": 15000, "probability": 100},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["stage"] == "won"
    assert float(patched.json()["value"]) == pytest.approx(15000)

    summary = client.get(f"/api/v1/workspaces/{wid}/deals/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["total_deals"] == 2
    assert float(body["total_value"]) == pytest.approx(15500)
    by_stage = {row["stage"]: row for row in body["by_stage"]}
    assert by_stage["won"]["deal_count"] == 1
    assert float(by_stage["won"]["total_value"]) == pytest.approx(15000)
    assert by_stage["new"]["deal_count"] == 1

    activity = client.post(
        f"/api/v1/workspaces/{wid}/deals/{deal['id']}/activities",
        headers=headers,
        json={"activity_type": "call", "note": "Signed the order"},
    )
    assert activity.status_code == 201, activity.text
    assert activity.json()["actor_id"] == user_id
    activities = client.get(f"/api/v1/workspaces/{wid}/deals/{deal['id']}/activities", headers=headers)
    assert activities.status_code == 200
    assert [row["note"] for row in activities.json()] == ["Signed the order"]

    events = client.get(f"/api/v1/workspaces/{wid}/events?limit=500", headers=headers)
    assert events.status_code == 200
    emitted = [row for row in events.json() if row["event_type"].startswith("deal.")]
    types = {row["event_type"] for row in emitted}
    assert {"deal.created", "deal.stage_changed", "deal.activity_added"} <= types
    assert all(row["payload"]["actor_id"] == user_id for row in emitted)


def test_duplicate_deals_are_rejected(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact_id = _create_contact(client, wid, headers, "dup@example.com")
    url = f"/api/v1/workspaces/{wid}/deals"
    payload = {"title": "Same deal", "contact_id": contact_id, "value": 100}

    first = client.post(url, headers=headers, json=payload)
    assert first.status_code == 201, first.text
    duplicate = client.post(url, headers=headers, json=payload)
    assert duplicate.status_code == 409, duplicate.text

    no_contact_a = client.post(url, headers=headers, json={"title": "No contact deal"})
    assert no_contact_a.status_code == 201
    no_contact_b = client.post(url, headers=headers, json={"title": "No contact deal"})
    assert no_contact_b.status_code == 409


def test_invalid_deal_payloads_are_rejected(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = f"/api/v1/workspaces/{wid}/deals"

    bad_stage = client.post(url, headers=headers, json={"title": "Bad stage", "stage": "unknown"})
    assert bad_stage.status_code == 422
    bad_probability = client.post(url, headers=headers, json={"title": "Bad odds", "probability": 101})
    assert bad_probability.status_code == 422
    extra = client.post(url, headers=headers, json={"title": "Extra", "workspace_id": "other"})
    assert extra.status_code == 422
    blank = client.post(url, headers=headers, json={"title": "   "})
    assert blank.status_code == 422

    deal = client.post(url, headers=headers, json={"title": "Valid"}).json()
    bad_patch = client.patch(
        f"{url}/{deal['id']}", headers=headers, json={"value": -1}
    )
    assert bad_patch.status_code == 422
    bad_activity = client.post(
        f"{url}/{deal['id']}/activities", headers=headers, json={"activity_type": "  "}
    )
    assert bad_activity.status_code == 422


def test_deals_are_isolated_by_workspace(client):
    tokens = bootstrap(client)
    wid_a, headers_a = tokens["workspace_id"], auth(tokens["access_token"])
    contact_id = _create_contact(client, wid_a, headers_a, "isolated@example.com")
    deal = client.post(
        f"/api/v1/workspaces/{wid_a}/deals",
        headers=headers_a,
        json={"title": "Private deal", "contact_id": contact_id},
    ).json()

    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "Password123!",
            "display_name": "Other Owner",
        },
    )
    assert other.status_code == 200, other.text
    wid_b, headers_b = other.json()["workspace_id"], auth(other.json()["access_token"])

    cross = client.get(f"/api/v1/workspaces/{wid_a}/deals", headers=headers_b)
    assert cross.status_code == 403

    hidden = client.get(f"/api/v1/workspaces/{wid_b}/deals/{deal['id']}", headers=headers_b)
    assert hidden.status_code == 404

    hidden_activity = client.post(
        f"/api/v1/workspaces/{wid_b}/deals/{deal['id']}/activities",
        headers=headers_b,
        json={"activity_type": "call"},
    )
    assert hidden_activity.status_code == 404

    empty = client.get(f"/api/v1/workspaces/{wid_b}/deals", headers=headers_b)
    assert empty.status_code == 200
    assert empty.json() == []
