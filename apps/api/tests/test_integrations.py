"""Integrations and settings: catalog, secrets policy and workspace scope."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from novara_core.database import get_db
from novara_core.models import Event, User
from novara_core.modules.integrations import (
    INTEGRATION_CONFIGURED,
    INTEGRATION_DISABLED,
    Integration,
    SUPPORTED_PROVIDERS,
    router,
)

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/integrations"


@pytest.fixture()
def integration_api(db_session):
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


def _upsert(api, workspace_id, headers, provider="gmail", **overrides):
    payload = {
        "provider": provider,
        "display_name": "Gmail mailbox",
        "status": "configured",
        "config": {"default_folder": "INBOX"},
    }
    payload.update(overrides)
    return api.put(BASE.format(wid=workspace_id), headers=headers, json=payload)


def test_integration_upsert_get_disable_and_capabilities(client, db_session, integration_api):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = BASE.format(wid=wid)
    owner_id = _owner_id(db_session)

    assert integration_api.get(url, headers=headers).json() == []
    catalog = integration_api.get(f"{url}/capabilities", headers=headers)
    assert catalog.status_code == 200, catalog.text
    catalog_data = catalog.json()
    assert {entry["provider"] for entry in catalog_data["providers"]} == set(SUPPORTED_PROVIDERS)
    assert all(entry["status"] == "adapter not configured" for entry in catalog_data["providers"])
    assert all(entry["configured"] is False for entry in catalog_data["providers"])
    assert all("adapter not configured" in entry["notes"] for entry in catalog_data["providers"])

    created = _upsert(integration_api, wid, headers)
    assert created.status_code == 200, created.text
    created_data = created.json()
    assert created_data["provider"] == "gmail"
    assert created_data["config"] == {"default_folder": "INBOX"}
    assert created_data["created_by"] == owner_id
    assert "No outbound network call" in created_data["notes"]

    listed = integration_api.get(url, headers=headers).json()
    assert [row["id"] for row in listed] == [created_data["id"]]
    fetched = integration_api.get(f"{url}/gmail", headers=headers).json()
    assert fetched["status"] == "configured"

    updated = _upsert(
        integration_api, wid, headers, config={"default_folder": "Archive", "threaded": True}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["config"] == {"default_folder": "Archive", "threaded": True}

    catalog_after = integration_api.get(f"{url}/capabilities", headers=headers).json()
    gmail = next(entry for entry in catalog_after["providers"] if entry["provider"] == "gmail")
    assert gmail["configured"] is True
    assert gmail["status"] == "configured"
    other_status = next(
        entry["status"] for entry in catalog_after["providers"] if entry["provider"] == "outlook"
    )
    assert other_status == "adapter not configured"

    disabled = integration_api.post(f"{url}/gmail/disable", headers=headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "disabled"
    gmail_after = next(
        entry
        for entry in integration_api.get(f"{url}/capabilities", headers=headers).json()["providers"]
        if entry["provider"] == "gmail"
    )
    assert gmail_after["status"] == "disabled"

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()
    types = [event.event_type for event in events]
    assert types.count(INTEGRATION_CONFIGURED) == 2
    assert types.count(INTEGRATION_DISABLED) == 1
    assert all(event.payload["actor_id"] == owner_id for event in events)
    configured_event = next(event for event in events if event.event_type == INTEGRATION_CONFIGURED)
    assert configured_event.entity_id == created_data["id"]
    assert configured_event.payload["provider"] == "gmail"
    assert db_session.get(Integration, created_data["id"]).config == {
        "default_folder": "Archive",
        "threaded": True,
    }


@pytest.mark.parametrize(
    "secret_field",
    ["api_key", "token", "secret", "password", "credential", "credentials", "access_token"],
)
def test_secret_fields_are_rejected(client, db_session, integration_api, secret_field):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    rejected = _upsert(
        integration_api, wid, headers, config={"default_folder": "INBOX", secret_field: "s3cr3t"}
    )
    assert rejected.status_code == 422, rejected.text
    assert "secret field is not accepted" in rejected.text

    assert db_session.execute(select(Integration)).scalars().all() == []
    assert db_session.execute(select(Event)).scalars().all() == []


def test_secret_like_fields_are_rejected_even_when_nested_or_camel_case(
    client, db_session, integration_api
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    for payload in (
        {"provider": "gmail", "config": {"apiKey": "s3cr3t"}},
        {"provider": "gmail", "config": {"settings": {"token": "s3cr3t"}}},
        {"provider": "gmail", "config": {"items": [{"password": "s3cr3t"}]}},
        {"provider": "gmail", "token": "s3cr3t"},
        {"provider": "not_a_real_provider", "config": {"default_folder": "INBOX"}},
    ):
        response = integration_api.put(BASE.format(wid=wid), headers=headers, json=payload)
        assert response.status_code == 422, response.text

    assert db_session.execute(select(Integration)).scalars().all() == []


def test_integrations_are_workspace_scoped(client, db_session, integration_api):
    first = bootstrap(client)
    first_wid, first_headers = first["workspace_id"], auth(first["access_token"])
    first_row = _upsert(
        integration_api, first_wid, first_headers, config={"default_folder": "First"}
    ).json()

    second = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Other workspace"}
    )
    assert second.status_code == 200, second.text
    second_tokens = second.json()
    second_wid, second_headers = second_tokens["workspace_id"], auth(second_tokens["access_token"])
    second_row = _upsert(
        integration_api, second_wid, second_headers, config={"default_folder": "Second"}
    ).json()

    assert integration_api.get(BASE.format(wid=first_wid), headers=second_headers).status_code == 403
    assert integration_api.get(
        f"{BASE.format(wid=first_wid)}/capabilities", headers=second_headers
    ).status_code == 403
    assert integration_api.post(
        f"{BASE.format(wid=first_wid)}/gmail/disable", headers=second_headers
    ).status_code == 403

    first_config = integration_api.get(
        f"{BASE.format(wid=first_wid)}/gmail", headers=first_headers
    ).json()
    second_config = integration_api.get(
        f"{BASE.format(wid=second_wid)}/gmail", headers=second_headers
    ).json()
    assert first_config["config"] == {"default_folder": "First"}
    assert second_config["config"] == {"default_folder": "Second"}
    assert first_config["id"] != second_config["id"]
    assert integration_api.get(
        f"{BASE.format(wid=first_wid)}/{second_row['id']}", headers=first_headers
    ).status_code == 404

    assert db_session.get(Integration, first_row["id"]).workspace_id == first_wid
    assert db_session.get(Integration, second_row["id"]).workspace_id == second_wid


def test_integration_endpoints_require_authentication(client, db_session, integration_api):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    url = BASE.format(wid=wid)
    assert integration_api.get(url).status_code == 401
    assert integration_api.put(url, json={"provider": "gmail"}).status_code == 401
