"""Cycle 1 Batch 3 smoke tests."""

from __future__ import annotations


def _bootstrap(client):
    from tests.conftest import bootstrap, auth

    tokens = bootstrap(client)
    return tokens["access_token"], auth(tokens["access_token"])


def test_feature_flags(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    f = client.post(
        f"/api/v1/workspaces/{ws}/flags",
        json={"key": "new-ui", "enabled": True, "rollout_percent": 100, "variants": ["on", "off"]},
        headers=headers,
    )
    assert f.status_code == 201

    ev = client.post(
        f"/api/v1/workspaces/{ws}/flags/new-ui/evaluate",
        json={"user_key": "u1", "attributes": {}},
        headers=headers,
    )
    assert ev.status_code == 200
    assert ev.json()["enabled"] is True

    allf = client.post(
        f"/api/v1/workspaces/{ws}/flags/evaluate-all",
        json={"user_key": "u2"},
        headers=headers,
    )
    assert allf.status_code == 200
    assert "new-ui" in allf.json()["flags"]


def test_analytics_reports_conversions(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    r = client.post(
        f"/api/v1/workspaces/{ws}/analytics/reports",
        json={"name": "Conv", "report_type": "conversion", "filters": {}},
        headers=headers,
    )
    assert r.status_code == 201

    c = client.get(f"/api/v1/workspaces/{ws}/analytics/conversions", headers=headers)
    assert c.status_code == 200

    co = client.get(f"/api/v1/workspaces/{ws}/analytics/cohorts", headers=headers)
    assert co.status_code == 200

    cmp = client.get(
        f"/api/v1/workspaces/{ws}/analytics/compare/contacts",
        params={
            "current_from": "2020-01-01T00:00:00Z",
            "current_to": "2030-01-01T00:00:00Z",
            "previous_from": "2019-01-01T00:00:00Z",
            "previous_to": "2020-01-01T00:00:00Z",
        },
        headers=headers,
    )
    assert cmp.status_code == 200


def test_crm_intelligence(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    c = client.post(
        f"/api/v1/workspaces/{ws}/contacts",
        json={"email": "dup@example.com", "full_name": "Dup"},
        headers=headers,
    ).json()
    c2 = client.post(
        f"/api/v1/workspaces/{ws}/contacts",
        json={"email": "dup@example.com", "full_name": "Dup2"},
        headers=headers,
    )
    # duplicate email should be rejected (409) — that's correct behavior
    assert c2.status_code == 409

    dups = client.get(f"/api/v1/workspaces/{ws}/crm/duplicates", headers=headers)
    assert dups.status_code == 200

    model = client.get(f"/api/v1/workspaces/{ws}/crm/lead-scoring-model", headers=headers)
    assert model.status_code == 200

    # lifecycle
    lc = client.post(
        f"/api/v1/workspaces/{ws}/crm/lifecycle",
        json={"contact_id": c["id"], "stage": "customer"},
        headers=headers,
    )
    assert lc.status_code == 200


def test_search_facets_suggest(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    client.post(
        f"/api/v1/workspaces/{ws}/contacts",
        json={"email": "zed@example.com", "full_name": "Zeddy"},
        headers=headers,
    )

    f = client.get(f"/api/v1/workspaces/{ws}/search/facets", headers=headers)
    assert f.status_code == 200
    assert "contact" in f.json()["counts"]

    s = client.get(f"/api/v1/workspaces/{ws}/search/suggest", params={"q": "Zed"}, headers=headers)
    assert s.status_code == 200


def test_support_saved_replies_macros_sla(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    sr = client.post(
        f"/api/v1/workspaces/{ws}/tickets/saved-replies",
        json={"name": "greet", "body": "Hello!"},
        headers=headers,
    )
    assert sr.status_code == 201

    mc = client.post(
        f"/api/v1/workspaces/{ws}/tickets/macros",
        json={"name": "close", "actions": "[\"set_status:resolved\"]"},
        headers=headers,
    )
    assert mc.status_code == 201

    sla = client.post(
        f"/api/v1/workspaces/{ws}/tickets/sla-policies",
        json={"name": "default", "first_response_minutes": 30},
        headers=headers,
    )
    assert sla.status_code == 201


def test_projects_subitems_deps_cycles(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    proj = client.post(
        f"/api/v1/workspaces/{ws}/projects",
        json={"name": "P2"},
        headers=headers,
    ).json()
    pid = proj["id"]

    item = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items",
        json={"title": "Parent"},
        headers=headers,
    ).json()
    iid = item["id"]

    sub = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items/{iid}/sub-items",
        json={"title": "Child"},
        headers=headers,
    )
    assert sub.status_code == 201

    subs = client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/items/{iid}/sub-items", headers=headers)
    assert subs.status_code == 200
    assert len(subs.json()) == 1

    dep_item = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items",
        json={"title": "Dep"},
        headers=headers,
    ).json()
    dep = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items/{dep_item['id']}/dependencies",
        json={"depends_on_id": iid},
        headers=headers,
    )
    assert dep.status_code == 201

    cyc = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/cycles",
        json={"name": "Sprint 1"},
        headers=headers,
    )
    assert cyc.status_code == 201