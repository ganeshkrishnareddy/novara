"""Phase 2 P2-5: local adapter architecture tests.

Every adapter is a local mock. These tests assert that invocation is gated by
integration status, that no response claims delivery or fabricated AI output,
and that all activity is audited and workspace-scoped.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from novara_core.database import get_db
from novara_core.errors import install_safe_validation_errors
from novara_core.models import Event, Workspace
from novara_core.modules import adapters as adapters_mod
from novara_core.modules.adapters import ADAPTER_REJECTED, AdapterCall, router
from novara_core.modules import integrations
from novara_core.modules.integrations import router as integrations_router

from .conftest import auth, bootstrap

ADAPTERS = "/api/v1/workspaces/{wid}/adapters"
INTEGRATIONS = "/api/v1/workspaces/{wid}/integrations"


@pytest.fixture()
def adapter_api(db_session):
    app = FastAPI()
    install_safe_validation_errors(app)
    app.include_router(router)
    app.include_router(integrations_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _configure(adapter_api, wid, headers, provider="gmail", status="configured", config=None):
    response = adapter_api.put(
        INTEGRATIONS.format(wid=wid),
        headers=headers,
        json={
            "provider": provider,
            "display_name": None,
            "status": status,
            "config": config or {"region": "local-test"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_capabilities_distinguish_configured_disabled_and_not_configured(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = ADAPTERS.format(wid=wid)

    listing = adapter_api.get(base, headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["workspace_id"] == wid
    assert len(payload["providers"]) == len(integrations.SUPPORTED_PROVIDERS)
    plane = next(p for p in payload["providers"] if p["provider"] == "plane")
    assert plane["kind"] == "project_management"
    assert plane["local_mock_available"] is True
    gmail = next(p for p in payload["providers"] if p["provider"] == "gmail")
    assert gmail["status"] == "not_configured"
    assert gmail["kind"] == "email"
    assert gmail["local_mock_available"] is True

    _configure(adapter_api, wid, headers)
    assert next(
        p for p in adapter_api.get(base, headers=headers).json()["providers"]
        if p["provider"] == "gmail"
    )["status"] == "configured"

    _configure(adapter_api, wid, headers, status="disabled")
    assert next(
        p for p in adapter_api.get(base, headers=headers).json()["providers"]
        if p["provider"] == "gmail"
    )["status"] == "disabled"


def test_invoke_rejected_when_not_configured(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = adapter_api.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke",
        headers=headers,
        json={"operation": "send", "request": {"to": "nobody@example.test"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "rejected"
    assert body["response"]["delivered"] is False
    assert body["response"]["status"] == "not_configured"
    assert "no outbound call" in body["response"]["note"]

    calls = db_session.execute(
        select(AdapterCall).where(AdapterCall.workspace_id == wid)
    ).scalars().all()
    assert len(calls) == 1
    assert calls[0].status == "rejected" and calls[0].kind == "email"
    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == ADAPTER_REJECTED)
    ).scalars().all()
    assert len(events) == 1


def test_local_mock_invocation_never_claims_delivery(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    _configure(adapter_api, wid, headers)

    response = adapter_api.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke",
        headers=headers,
        json={
            "operation": "send",
            "request": {"to": "recipient@example.test", "subject": "Local test only"},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "recorded"
    assert body["response"]["mode"] == "local_mock"
    assert body["response"]["delivered"] is False
    assert body["response"]["message_id"].startswith("mock-gmail-")
    assert body["response"]["recipient"] == "recipient@example.test"
    assert "nothing was sent externally" in body["response"]["note"]

    call = db_session.execute(select(AdapterCall)).scalar_one()
    assert call.status == "recorded"
    assert call.response_summary["delivered"] is False
    assert call.request_summary == {"to": "recipient@example.test", "subject": "Local test only"}
    assert db_session.execute(
        select(Event).where(Event.event_type == "adapter.invoked")
    ).scalars().one() is not None


def test_ai_adapter_does_not_fabricate_output(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    _configure(adapter_api, wid, headers, provider="local_llm")
    response = adapter_api.post(
        ADAPTERS.format(wid=wid) + "/local_llm/invoke",
        headers=headers,
        json={"operation": "generate", "request": {"prompt": "Summarise internal notes"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()["response"]
    assert body["kind"] == "ai"
    assert body["output"] is None
    assert body["tokens"] == 0
    assert body["delivered"] is False


def test_no_local_adapter_is_blocked(adapter_api, client, db_session, monkeypatch):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    _configure(adapter_api, wid, headers)
    monkeypatch.delitem(adapters_mod.PROVIDER_KINDS, "gmail")
    response = adapter_api.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke",
        headers=headers,
        json={"operation": "send", "request": {}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["kind"] == "unknown"
    assert body["response"]["delivered"] is False


def test_secrets_are_rejected_before_adapter_can_record_them(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = adapter_api.put(
        INTEGRATIONS.format(wid=wid),
        headers=headers,
        json={"provider": "gmail", "status": "configured", "config": {"api_key": "do-not-store"}},
    )
    assert response.status_code == 422
    assert "secret field is not accepted" in response.text
    assert "do-not-store" not in response.text
    assert db_session.execute(select(AdapterCall)).scalars().all() == []


def test_adapter_calls_are_workspace_scoped(adapter_api, client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    _configure(adapter_api, wid, headers)
    adapter_api.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke",
        headers=headers,
        json={"operation": "test", "request": {}},
    )
    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": "adapter-other@example.com",
            "display_name": "Other",
            "password": "Password123!",
        },
    )
    assert other.status_code == 200
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])

    assert adapter_api.get(ADAPTERS.format(wid=other_wid), headers=other_headers).json()["providers"][0]["status"] == "not_configured"
    assert adapter_api.get(ADAPTERS.format(wid=other_wid) + "/calls", headers=other_headers).json() == []
    assert adapter_api.get(ADAPTERS.format(wid=wid), headers=other_headers).status_code == 403
    assert db_session.execute(
        select(Workspace).where(Workspace.id == other_wid)
    ).scalar_one() is not None
