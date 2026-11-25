"""Integration checks against the real production app object.

Unlike the module unit tests, these exercise the routes that `main.py` actually
serves, with `include_all(app)` already applied. They prove the modules are part
of the one NOVARA application and that the same auth / workspace / event rules
apply to every capability area.
"""

from __future__ import annotations

from .conftest import auth, bootstrap


def test_every_module_is_registered_on_the_production_app():
    from novara_core.main import app

    paths = set(app.openapi()["paths"])
    expected = {
        "/api/v1/workspaces/{workspace_id}/surveys",
        "/api/v1/workspaces/{workspace_id}/deals",
        "/api/v1/workspaces/{workspace_id}/campaigns",
        "/api/v1/workspaces/{workspace_id}/tickets",
        "/api/v1/workspaces/{workspace_id}/projects",
        "/api/v1/workspaces/{workspace_id}/documents",
        "/api/v1/workspaces/{workspace_id}/analytics/funnel",
        "/api/v1/workspaces/{workspace_id}/search",
        "/api/v1/workspaces/{workspace_id}/automations",
        "/api/v1/workspaces/{workspace_id}/agents",
        "/api/v1/workspaces/{workspace_id}/integrations",
    }
    assert expected <= paths, f"missing routes: {sorted(expected - paths)}"


def test_module_endpoints_work_through_the_real_app(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    checks = [
        ("/surveys", {}),
        ("/deals", {}),
        ("/campaigns", {}),
        ("/tickets", {}),
        ("/projects", {}),
        ("/documents/rooms", {}),
        ("/analytics/funnel", {}),
        ("/search", {"q": "nothing"}),
        ("/automations", {}),
        ("/agents", {}),
        ("/integrations/capabilities", {}),
    ]
    for path, params in checks:
        response = client.get(
            f"/api/v1/workspaces/{wid}{path}", headers=headers, params=params
        )
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"


def test_module_event_appears_in_shared_audit_log(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    created = client.post(
        f"/api/v1/workspaces/{wid}/surveys",
        headers=headers,
        json={"name": "Customer satisfaction"},
    )
    assert created.status_code == 201, created.text

    events = client.get(f"/api/v1/workspaces/{wid}/events", headers=headers).json()
    assert any(event["event_type"] == "survey.created" for event in events)
    assert all(event["workspace_id"] == wid for event in events)


def test_module_routes_enforce_workspace_isolation(client):
    first = bootstrap(client, "First", "first@example.com")
    first_headers = auth(first["access_token"])
    second = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second"}
    )
    assert second.status_code == 200
    other_wid = second.json()["workspace_id"]

    for path in ("/surveys", "/deals", "/tickets", "/projects", "/agents"):
        response = client.get(
            f"/api/v1/workspaces/{other_wid}{path}", headers=first_headers
        )
        assert response.status_code == 403, f"{path}: {response.status_code}"


def test_web_client_is_served_by_the_api_process(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "NOVARA" in response.text
    assert "text/html" in response.headers.get("content-type", "")
