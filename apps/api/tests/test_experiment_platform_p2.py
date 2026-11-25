"""Named acceptance tests for the experimentation platform governance cluster.

GB-061/062/065/066/067 are proven against the real generated OpenAPI document,
the real scoped API-key implementation and real workspace-scoped role bindings.
No GrowthBook source, hosted platform, external provider or secret material is
used in assertions.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.models import Event, User
from novara_core.modules.api_keys import ApiKey
from novara_core.security import hash_token

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/experiment-platform"
KEYS = "/api/v1/workspaces/{wid}/api-keys"
CONTACTS = "/api/v1/workspaces/{wid}/contacts"


def _ctx(client):
    tokens = bootstrap(client, "Platform", "platform@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def test_gb061_openapi_spec_is_generated_and_clean(client):
    """The OpenAPI status reflects the real app document, not a static claim."""
    wid, h = _ctx(client)
    status = client.get(BASE.format(wid=wid) + "/openapi-status", headers=h)
    assert status.status_code == 200, status.text
    status = status.json()

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    spec = spec.json()
    assert spec["openapi"] == status["openapi_version"]
    assert status["generated_from_live_app"] is True
    assert status["clean"] is True and status["unique_operation_ids"] is True
    operation_ids = [
        operation.get("operationId")
        for methods in spec["paths"].values()
        for method, operation in methods.items()
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert "experimentPlatformContract" in operation_ids
    assert "experimentQueriesContract" in operation_ids
    assert "experimentOpsContract" in operation_ids


def test_gb062_rest_inventory_counts_real_experiment_operations(client):
    """Forty-plus real REST operations are visible across the route modules."""
    wid, h = _ctx(client)
    response = client.get(BASE.format(wid=wid) + "/rest-inventory", headers=h)
    assert response.status_code == 200, response.text
    inventory = response.json()
    assert inventory["meets_minimum"] is True
    assert inventory["operation_count"] >= 40
    assert inventory["path_count"] > 0
    for prefix in ("flags", "experiment-ops", "experiment-queries", "experiment-stats"):
        assert prefix in inventory["route_modules"]


def test_gb065_personal_access_token_is_user_owned_and_revocable(client, db_session):
    """A user-owned token is shown once, hashed at rest and fails after revoke."""
    wid, h = _ctx(client)
    issued = client.post(KEYS.format(wid=wid), headers=h, json={
        "name": "experiment-reader", "scopes": ["contact:read"],
    })
    assert issued.status_code == 201, issued.text
    issued = issued.json()
    assert issued["secret"].startswith("nvk_")

    row = db_session.execute(
        select(ApiKey).where(ApiKey.id == issued["id"])
    ).scalar_one()
    assert row.user_id is not None and row.secret_hash == hash_token(issued["secret"])
    assert row.secret_hash != issued["secret"]
    assert client.get(CONTACTS.format(wid=wid),
                      headers={"X-API-Key": issued["secret"]}).status_code == 200

    listed = client.get(KEYS.format(wid=wid), headers=h)
    assert listed.status_code == 200
    assert "secret" not in listed.json()[0]
    assert "secret_hash" not in listed.json()[0]

    revoked = client.delete(KEYS.format(wid=wid) + f"/{issued['id']}", headers=h)
    assert revoked.status_code == 200
    assert client.get(CONTACTS.format(wid=wid),
                      headers={"X-API-Key": issued["secret"]}).status_code == 401


def test_gb066_server_api_key_scopes_are_enforced(client):
    """Server keys are explicit, scoped and cannot self-manage credentials."""
    wid, h = _ctx(client)
    reader = client.post(KEYS.format(wid=wid), headers=h, json={
        "name": "server-reader", "scopes": ["contact:read"],
    }).json()
    reader_headers = {"X-API-Key": reader["secret"]}
    assert client.get(CONTACTS.format(wid=wid), headers=reader_headers).status_code == 200
    denied = client.post(CONTACTS.format(wid=wid), headers=reader_headers,
                         json={"email": "blocked@example.com"})
    assert denied.status_code == 403

    manager = client.post(KEYS.format(wid=wid), headers=h, json={
        "name": "server-manager",
        "scopes": ["workspace:manage", "contact:read"],
    }).json()
    manager_headers = {"X-API-Key": manager["secret"]}
    assert client.get(KEYS.format(wid=wid), headers=manager_headers).status_code == 200
    assert client.post(KEYS.format(wid=wid), headers=manager_headers,
                       json={"name": "child", "scopes": ["contact:read"]}).status_code == 403


def test_gb067_default_roles_and_bindings_are_workspace_scoped(client, db_session):
    """The six default roles are checkable and bound per workspace."""
    wid, h = _ctx(client)
    roles = client.get(BASE.format(wid=wid) + "/roles", headers=h)
    assert roles.status_code == 200, roles.text
    assert {r["role"] for r in roles.json()} == {
        "noaccess", "readonly", "collaborator", "engineer", "analyst", "admin",
    }

    can = client.get(BASE.format(wid=wid) + "/roles/can", headers=h,
                     params={"role": "analyst", "permission": "contact:read"})
    assert can.json()["allowed"] is True
    can = client.get(BASE.format(wid=wid) + "/roles/can", headers=h,
                     params={"role": "noaccess", "permission": "contact:read"})
    assert can.json()["allowed"] is False
    can = client.get(BASE.format(wid=wid) + "/roles/can", headers=h,
                     params={"role": "admin", "permission": "workspace:manage"})
    assert can.json()["allowed"] is True
    assert client.get(BASE.format(wid=wid) + "/roles/can", headers=h,
                      params={"role": "unknown", "permission": "contact:read"}).status_code == 422

    user = db_session.execute(
        select(User).where(User.email == "platform@example.com")
    ).scalar_one()
    bind = client.post(BASE.format(wid=wid) + "/roles/bindings", headers=h,
                       json={"user_id": user.id, "role": "analyst"})
    assert bind.status_code == 201, bind.text
    assert bind.json()["role"] == "analyst"
    rebind = client.post(BASE.format(wid=wid) + "/roles/bindings", headers=h,
                         json={"user_id": user.id, "role": "engineer"})
    assert rebind.status_code == 201 and rebind.json()["id"] == bind.json()["id"]
    listed = client.get(BASE.format(wid=wid) + "/roles/bindings", headers=h).json()
    assert len(listed) == 1 and listed[0]["role"] == "engineer"

    assert client.post(BASE.format(wid=wid) + "/roles/bindings", headers=h,
                       json={"user_id": user.id, "role": "wizard"}).status_code == 422
    assert client.post(BASE.format(wid=wid) + "/roles/bindings", headers=h,
                       json={"user_id": "missing-user", "role": "analyst"}).status_code == 404
    assert db_session.execute(
        select(Event).where(Event.event_type == "experiment.role_bound")
    ).scalars().first() is not None

    other_tokens = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"})
    assert other_tokens.status_code == 200
    other_wid, other_h = other_tokens.json()["workspace_id"], auth(other_tokens.json()["access_token"])
    assert client.get(BASE.format(wid=other_wid) + "/roles/bindings", headers=h).status_code == 403
    assert client.get(BASE.format(wid=other_wid) + "/roles/bindings", headers=other_h).json() == []
