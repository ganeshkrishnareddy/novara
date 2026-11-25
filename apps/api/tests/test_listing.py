"""Phase 3 P3-2/P3-4: validated listing options and BI aggregates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .conftest import auth, bootstrap


def _contact(client, wid, headers, email, name):
    response = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": email, "full_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _lead(client, wid, headers, contact_id, status="new", priority="normal", score=0):
    response = client.post(
        f"/api/v1/workspaces/{wid}/leads",
        headers=headers,
        json={
            "contact_id": contact_id,
            "source": "website_form",
            "status": status,
            "priority": priority,
            "score": score,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _task(client, wid, headers, title, priority="normal"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/tasks",
        headers=headers,
        json={"title": title, "priority": priority},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_leads_support_search_filter_sort_and_pagination(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    a = _contact(client, wid, headers, "listing.a@example.test", "Ada Lovelace")
    b = _contact(client, wid, headers, "listing.b@example.test", "Grace Hopper")
    _lead(client, wid, headers, a, status="new", priority="low", score=10)
    _lead(client, wid, headers, b, status="qualified", priority="high", score=90)

    assert len(client.get(f"/api/v1/workspaces/{wid}/leads", headers=headers).json()) == 2

    filtered = client.get(f"/api/v1/workspaces/{wid}/leads?status=qualified", headers=headers)
    assert [row["status"] for row in filtered.json()] == ["qualified"]

    by_contact_name = client.get(
        f"/api/v1/workspaces/{wid}/leads", params={"search": "Grace"}, headers=headers
    ).json()
    assert len(by_contact_name) == 1
    assert by_contact_name[0]["contact_id"] == b

    by_email = client.get(
        f"/api/v1/workspaces/{wid}/leads",
        params={"search": "listing.a@example.test"},
        headers=headers,
    ).json()
    assert len(by_email) == 1
    assert by_email[0]["contact_id"] == a

    sorted_rows = client.get(
        f"/api/v1/workspaces/{wid}/leads",
        params={"sort": "score", "order": "desc"},
        headers=headers,
    ).json()
    assert [row["score"] for row in sorted_rows] == [90, 10]

    page = client.get(
        f"/api/v1/workspaces/{wid}/leads",
        params={"sort": "score", "order": "desc", "skip": 1, "limit": 1},
        headers=headers,
    ).json()
    assert len(page) == 1
    assert page[0]["score"] == 10

    assert client.get(
        f"/api/v1/workspaces/{wid}/leads", params={"sort": "password_hash"}, headers=headers
    ).status_code == 422
    assert client.get(
        f"/api/v1/workspaces/{wid}/leads", params={"order": "sideways"}, headers=headers
    ).status_code == 422


def test_tasks_support_search_filter_sort_and_pagination(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    _task(client, wid, headers, "Call Ada about pricing", priority="high")
    _task(client, wid, headers, "Send proposal to Grace", priority="low")
    _task(client, wid, headers, "Archive old notes", priority="normal")

    assert len(client.get(f"/api/v1/workspaces/{wid}/tasks", headers=headers).json()) == 3

    searched = client.get(
        f"/api/v1/workspaces/{wid}/tasks", params={"search": "Grace"}, headers=headers
    ).json()
    assert len(searched) == 1
    assert searched[0]["title"] == "Send proposal to Grace"

    titles = client.get(
        f"/api/v1/workspaces/{wid}/tasks",
        params={"sort": "title", "order": "asc"},
        headers=headers,
    ).json()
    assert [row["title"] for row in titles] == sorted(row["title"] for row in titles)

    paged = client.get(
        f"/api/v1/workspaces/{wid}/tasks",
        params={"sort": "title", "order": "asc", "skip": 1, "limit": 1},
        headers=headers,
    ).json()
    assert len(paged) == 1
    assert paged[0]["title"] == titles[1]["title"]

    # The default status filter still works for existing callers.
    open_rows = client.get(
        f"/api/v1/workspaces/{wid}/tasks", params={"status": "open"}, headers=headers
    ).json()
    assert len(open_rows) == 3

    assert client.get(
        f"/api/v1/workspaces/{wid}/tasks", params={"skip": -1}, headers=headers
    ).status_code == 422
    assert client.get(
        f"/api/v1/workspaces/{wid}/tasks", params={"limit": 500}, headers=headers
    ).status_code == 422


def test_analytics_funnel_uses_real_rows_and_is_workspace_scoped(client):
    first = bootstrap(client, workspace_name="BI first")
    wid, headers = first["workspace_id"], auth(first["access_token"])
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bi.second@example.test",
            "display_name": "BI second",
            "password": "Password123!",
        },
    )
    other = registered.json()
    other_headers = auth(other["access_token"])

    contact_id = _contact(client, wid, headers, "bi.first@example.test", "BI Contact")
    lead = _lead(client, wid, headers, contact_id, status="new")
    _task(client, wid, headers, "BI task")

    funnel = client.get(f"/api/v1/workspaces/{wid}/analytics/funnel", headers=headers)
    assert funnel.status_code == 200, funnel.text
    assert funnel.json() == {"contacts": 1, "leads": 1, "converted_leads": 0, "tasks": 1}

    client.post(
        f"/api/v1/workspaces/{wid}/leads/{lead['id']}/qualify", headers=headers
    )
    client.post(
        f"/api/v1/workspaces/{wid}/leads/{lead['id']}/convert", headers=headers
    )
    assert client.get(
        f"/api/v1/workspaces/{wid}/analytics/funnel", headers=headers
    ).json()["converted_leads"] == 1

    other_funnel = client.get(
        f"/api/v1/workspaces/{other['workspace_id']}/analytics/funnel", headers=other_headers
    ).json()
    assert other_funnel == {"contacts": 0, "leads": 0, "converted_leads": 0, "tasks": 0}
    assert client.get(
        f"/api/v1/workspaces/{wid}/analytics/funnel", headers=other_headers
    ).status_code == 403


def test_event_volume_supports_date_window(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={"submission_id": "volume-001", "email": "volume@example.test"},
    )
    base = f"/api/v1/workspaces/{wid}/analytics/events/volume"

    all_rows = client.get(base, headers=headers).json()
    assert all_rows
    assert all(row["count"] > 0 for row in all_rows)
    assert [row["count"] for row in all_rows] == sorted(
        [row["count"] for row in all_rows], reverse=True
    )

    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    assert client.get(base, params={"date_from": future}, headers=headers).json() == []

    invalid = client.get(
        base,
        params={"date_from": future, "date_to": "2020-01-01T00:00:00Z"},
        headers=headers,
    )
    assert invalid.status_code == 422
