"""Workspace-scoped marketing campaign and metric tests."""

from __future__ import annotations

import pytest

from novara_core.main import app
from novara_core.modules.marketing import router as marketing_router

from .conftest import auth, bootstrap


@pytest.fixture(autouse=True)
def _register_marketing_router():
    """Attach our router when the core app has not wired capability modules yet.

    The app is shared across the suite, so restore its route table afterwards.
    """
    prefix = "/api/v1/workspaces/{workspace_id}/campaigns"
    if any(getattr(route, "path", "").startswith(prefix) for route in app.routes):
        yield
        return
    original_routes = list(app.routes)
    app.include_router(marketing_router)
    try:
        yield
    finally:
        app.routes[:] = original_routes
        mark_changed = getattr(app.router, "_mark_routes_changed", None)
        if mark_changed is not None:
            mark_changed()


def test_campaign_metrics_rollups_summary_and_events(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]
    base = f"/api/v1/workspaces/{wid}/campaigns"

    created = client.post(
        base,
        headers=headers,
        json={
            "name": "Spring launch",
            "channel": "email",
            "status": "draft",
            "goal": "Generate qualified leads",
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-03-31T00:00:00Z",
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["workspace_id"] == wid
    assert campaign["owner_id"] == user_id

    listed = client.get(base, headers=headers)
    assert [row["id"] for row in listed.json()] == [campaign["id"]]
    active_only = client.get(f"{base}?status=active", headers=headers)
    assert active_only.json() == []

    first_metric = client.put(
        f"{base}/{campaign['id']}/metrics",
        headers=headers,
        json={"date": "2026-01-02", "impressions": 1000, "clicks": 100, "leads": 10, "spend": 250.25},
    )
    assert first_metric.status_code == 200, first_metric.text
    updated_metric = client.put(
        f"{base}/{campaign['id']}/metrics",
        headers=headers,
        json={"date": "2026-01-02", "impressions": 1200, "clicks": 150, "leads": 12, "spend": 300.50},
    )
    assert updated_metric.status_code == 200, updated_metric.text
    assert updated_metric.json()["id"] == first_metric.json()["id"]

    second_metric = client.post(
        f"{base}/{campaign['id']}/metrics",
        headers=headers,
        json={"date": "2026-01-03", "impressions": 400, "clicks": 40, "leads": 4, "spend": 75},
    )
    assert second_metric.status_code == 201, second_metric.text

    metrics = client.get(f"{base}/{campaign['id']}/metrics", headers=headers)
    assert metrics.status_code == 200
    assert [row["date"] for row in metrics.json()] == ["2026-01-02", "2026-01-03"]
    assert float(metrics.json()[0]["spend"]) == pytest.approx(300.50)

    detail = client.get(f"{base}/{campaign['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["campaign"]["name"] == "Spring launch"
    assert body["metric_days"] == 2
    assert body["total_impressions"] == 1600
    assert body["total_clicks"] == 190
    assert body["total_leads"] == 16
    assert float(body["total_spend"]) == pytest.approx(375.50)

    patched = client.patch(
        f"{base}/{campaign['id']}", headers=headers, json={"status": "active", "goal": "Scale"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "active"
    assert patched.json()["goal"] == "Scale"

    performance = client.get(f"{base}/performance", headers=headers)
    assert performance.status_code == 200, performance.text
    row = performance.json()[0]
    assert row["campaign_id"] == campaign["id"]
    assert row["status"] == "active"
    assert row["total_impressions"] == 1600
    assert float(row["total_spend"]) == pytest.approx(375.50)

    events = client.get(f"/api/v1/workspaces/{wid}/events?limit=500", headers=headers)
    assert events.status_code == 200
    emitted = [row for row in events.json() if row["event_type"].startswith("campaign.")]
    types = {row["event_type"] for row in emitted}
    assert {
        "campaign.created",
        "campaign.status_changed",
        "campaign.metric_recorded",
    } <= types
    assert all(row["payload"]["actor_id"] == user_id for row in emitted)


def test_duplicate_campaign_names_are_rejected(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = f"/api/v1/workspaces/{wid}/campaigns"
    payload = {"name": "Duplicate campaign", "channel": "ads"}

    assert client.post(url, headers=headers, json=payload).status_code == 201
    duplicate = client.post(url, headers=headers, json=payload)
    assert duplicate.status_code == 409, duplicate.text


def test_invalid_campaign_payloads_are_rejected(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = f"/api/v1/workspaces/{wid}/campaigns"

    bad_channel = client.post(url, headers=headers, json={"name": "Bad channel", "channel": "carrier-pigeon"})
    assert bad_channel.status_code == 422
    missing_channel = client.post(url, headers=headers, json={"name": "No channel"})
    assert missing_channel.status_code == 422
    extra = client.post(url, headers=headers, json={"name": "Extra", "channel": "ads", "workspace_id": "x"})
    assert extra.status_code == 422
    blank = client.post(url, headers=headers, json={"name": "  ", "channel": "ads"})
    assert blank.status_code == 422
    bad_dates = client.post(
        url,
        headers=headers,
        json={
            "name": "Bad dates",
            "channel": "ads",
            "start_at": "2026-05-01T00:00:00Z",
            "end_at": "2026-04-01T00:00:00Z",
        },
    )
    assert bad_dates.status_code == 422

    campaign = client.post(url, headers=headers, json={"name": "Valid", "channel": "social"}).json()
    bad_status = client.patch(f"{url}/{campaign['id']}", headers=headers, json={"status": "archived"})
    assert bad_status.status_code == 422
    negative_spend = client.put(
        f"{url}/{campaign['id']}/metrics",
        headers=headers,
        json={"date": "2026-02-01", "spend": -5},
    )
    assert negative_spend.status_code == 422
    bad_metric_date = client.put(
        f"{url}/{campaign['id']}/metrics",
        headers=headers,
        json={"date": "not-a-date"},
    )
    assert bad_metric_date.status_code == 422


def test_campaigns_are_isolated_by_workspace(client):
    tokens = bootstrap(client)
    wid_a, headers_a = tokens["workspace_id"], auth(tokens["access_token"])
    campaign = client.post(
        f"/api/v1/workspaces/{wid_a}/campaigns",
        headers=headers_a,
        json={"name": "Private campaign", "channel": "email"},
    ).json()

    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": "marketer@example.com",
            "password": "Password123!",
            "display_name": "Other Marketer",
        },
    )
    assert other.status_code == 200, other.text
    wid_b, headers_b = other.json()["workspace_id"], auth(other.json()["access_token"])

    cross = client.get(f"/api/v1/workspaces/{wid_a}/campaigns", headers=headers_b)
    assert cross.status_code == 403

    hidden = client.get(f"/api/v1/workspaces/{wid_b}/campaigns/{campaign['id']}", headers=headers_b)
    assert hidden.status_code == 404

    hidden_metric = client.put(
        f"/api/v1/workspaces/{wid_b}/campaigns/{campaign['id']}/metrics",
        headers=headers_b,
        json={"date": "2026-01-01", "impressions": 10},
    )
    assert hidden_metric.status_code == 404

    empty = client.get(f"/api/v1/workspaces/{wid_b}/campaigns", headers=headers_b)
    assert empty.status_code == 200
    assert empty.json() == []
