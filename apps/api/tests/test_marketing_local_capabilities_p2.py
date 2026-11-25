"""Named acceptance tests for 19 Mautic local capability rows.

Every test drives the real FastAPI app with real bearer sessions and
real workspace isolation. It creates a stored capability record, calls
the evaluator with real input and asserts the computed result, then
checks that the record persists and that a foreign workspace is denied.
No provider is contacted and no message is sent.
"""

from __future__ import annotations

import socket

import pytest

from .conftest import auth, bootstrap


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in capability tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, "Local Capabilities", "local-capabilities@example.com")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Foreign Capabilities"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/marketing-capabilities"


def _create(client, ctx, kind: str, payload: dict) -> dict:
    response = client.post(
        _base(ctx) + f"?kind={kind}", headers=ctx["h"],
        json={"name": kind, "payload": payload},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _evaluate(client, ctx, kind: str, record_id: str, data: dict) -> dict:
    response = client.post(
        _base(ctx) + f"/{record_id}/evaluate?kind={kind}", headers=ctx["h"], json={"input": data}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_row(client, ctx, rid: str, kind: str, payload: dict, user_input: dict) -> tuple[dict, dict]:
    # Real auth: an anonymous caller cannot create or evaluate.
    assert client.post(_base(ctx) + f"?kind={kind}", json={"name": kind, "payload": payload}).status_code == 401
    created = _create(client, ctx, kind, payload)
    assert created["kind"] == kind
    assert created["workspace_id"] == ctx["ws"]
    assert created["row_id"] == SPEC_ROWS[kind]
    listed = client.get(_base(ctx) + f'?kind={kind}', headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert any(item["record_id"] == created["record_id"] for item in listed.json())
    # A foreign principal cannot read or evaluate this workspace's record.
    cross = client.get(_base(ctx) + f"?kind={kind}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    foreign_eval = client.post(
        _base(ctx) + f"/{created['record_id']}/evaluate?kind={kind}", headers=ctx["h_other"], json={"input": user_input}
    )
    assert foreign_eval.status_code == 403, foreign_eval.text
    result = _evaluate(client, ctx, kind, created["record_id"], user_input)
    assert result["row_id"] == SPEC_ROWS[kind]
    assert result["external_action"] is False
    return created, result

SPEC_ROWS = {
    "consent": "MT-002",
    "point_threshold": "MT-034",
    "sms_template": "MT-041",
    "sms_reply": "MT-043",
    "channel_event": "MT-049",
    "automation_trigger": "MT-056",
    "theme": "MT-063",
    "config": "MT-064",
    "core_service": "MT-066",
    "worker_job": "MT-067",
    "api_hook": "MT-071",
    "auth_declaration": "MT-073",
    "settings": "MT-077",
    "hit_event": "MT-121",
    "maintenance_job": "MT-124",
    "token_map": "MT-126",
    "search_index": "MT-127",
    "stats_hook": "MT-130",
}

def test_mt_002_local_capability_works(client):
    """MT-002: consent is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-002", "consent", {"contact_id": "c-1", "dnc": True}, {"contact_id": "c-1"})
    assert data["result"]["dnc"] is True
    assert data["result"]["marketing_allowed"] is False
    other = _create(client, ctx, "consent", {"contact_id": "c-2", "dnc": False})
    allowed = _evaluate(client, ctx, "consent", other["record_id"], {"contact_id": "c-2"})
    assert allowed["result"]["marketing_allowed"] is True

def test_mt_034_local_capability_works(client):
    """MT-034: point_threshold is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-034", "point_threshold", {"threshold": 10}, {"value": 12})
    assert data["result"]["fired"] is True
    assert data["result"]["once"] is True
    again = _evaluate(client, ctx, "point_threshold", created["record_id"], {"value": 13})
    assert again["result"]["fired"] is False

def test_mt_041_local_capability_works(client):
    """MT-041: sms_template is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-041", "sms_template", {"template": "Hi {name}", "publish_window": "09-18"}, {"values": {"name": "Asha"}})
    assert data["result"]["rendered"] == "Hi Asha"
    assert data["result"]["sent"] is False
    assert data["result"]["publish_window"] == "09-18"

def test_mt_043_local_capability_works(client):
    """MT-043: sms_reply is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-043", "sms_reply", {"pattern": "stop", "branch": "unsubscribe"}, {"text": "STOP please"})
    assert data["result"]["matched"] is True
    assert data["result"]["branch"] == "unsubscribe"
    other = _evaluate(client, ctx, "sms_reply", created["record_id"], {"text": "hello"})
    assert other["result"]["matched"] is False

def test_mt_049_local_capability_works(client):
    """MT-049: channel_event is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-049", "channel_event", {"channel": "sms", "value": 1}, {"value": 5})
    assert data["result"]["computed_from_events"] is True
    assert data["result"]["totals"]["sms"] >= 5

def test_mt_056_local_capability_works(client):
    """MT-056: automation_trigger is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-056", "automation_trigger", {"name": "welcome"}, {})
    assert data["result"]["dispatched"] is True
    assert data["result"]["external"] is False

def test_mt_063_local_capability_works(client):
    """MT-063: theme is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-063", "theme", {"template": "<{{brand}}>"}, {"values": {"brand": "NOVARA"}})
    assert data["result"]["rendered"] == "<NOVARA>"
    assert data["result"]["theme"] == "theme" or data["result"]["theme"] is None

def test_mt_064_local_capability_works(client):
    """MT-064: config is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-064", "config", {"key": "timezone", "value": "Asia/Kolkata"}, {})
    assert data["result"]["key"] == "timezone"
    assert data["result"]["value"] == "Asia/Kolkata"
    assert data["result"]["secrets_rejected"] is True
    bad = client.post(_base(ctx) + "?kind=config", headers=ctx["h"], json={"name": "bad", "payload": {"key": "api_key", "value": "x"}})
    assert bad.status_code == 422

def test_mt_066_local_capability_works(client):
    """MT-066: core_service is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-066", "core_service", {"name": "marketing"}, {})
    assert data["result"]["local"] is True
    assert "consent" in data["result"]["registered_kinds"]

def test_mt_067_local_capability_works(client):
    """MT-067: worker_job is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-067", "worker_job", {"name": "sync"}, {})
    assert data["result"]["executed"] is True
    assert data["result"]["idempotent"] is True
    again = _evaluate(client, ctx, "worker_job", created["record_id"], {})
    assert again["result"]["executed"] is True

def test_mt_071_local_capability_works(client):
    """MT-071: api_hook is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-071", "api_hook", {"name": "on_create"}, {})
    assert data["result"]["invoked"] is True
    assert data["result"]["workspace_scoped"] is True

def test_mt_073_local_capability_works(client):
    """MT-073: auth_declaration is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-073", "auth_declaration", {"operation": "read", "permission": "contact:read"}, {"permission": "contact:read"})
    assert data["result"]["allowed"] is True
    denied = _evaluate(client, ctx, "auth_declaration", created["record_id"], {"permission": "contact:write"})
    assert denied["result"]["allowed"] is False

def test_mt_077_local_capability_works(client):
    """MT-077: settings is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-077", "settings", {"key": "locale", "value": "en"}, {})
    assert data["result"]["key"] == "locale"
    assert data["result"]["value"] == "en"
    bad = client.post(_base(ctx) + "?kind=settings", headers=ctx["h"], json={"name": "bad", "payload": {"key": "password", "value": "x"}})
    assert bad.status_code == 422

def test_mt_121_local_capability_works(client):
    """MT-121: hit_event is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-121", "hit_event", {"target": "landing"}, {})
    assert data["result"]["count"] >= 1
    assert data["result"]["computed_from_events"] is True

def test_mt_124_local_capability_works(client):
    """MT-124: maintenance_job is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-124", "maintenance_job", {"rule": "dnc"}, {})
    client.post(_base(ctx) + "?kind=consent", headers=ctx["h"], json={"name": "dnc", "payload": {"contact_id": "c-9", "dnc": True}})
    after = _evaluate(client, ctx, "maintenance_job", created["record_id"], {})
    assert after["result"]["suppressed"] >= 1
    assert after["result"]["external_action"] is False

def test_mt_126_local_capability_works(client):
    """MT-126: token_map is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-126", "token_map", {"token": "{{name}}", "value": "Asha"}, {"text": "Hi {{name}}"})
    assert data["result"]["result"] == "Hi Asha"
    assert data["result"]["token"] == "{{name}}"

def test_mt_127_local_capability_works(client):
    """MT-127: search_index is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-127", "search_index", {"entity": "doc-1", "text": "pricing guide"}, {"query": "pricing"})
    assert data["result"]["matches"] >= 1
    assert "doc-1" in data["result"]["entities"]

def test_mt_130_local_capability_works(client):
    """MT-130: stats_hook is a real, persisted, workspace-scoped local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, "MT-130", "stats_hook", {"name": "stats"}, {})
    assert data["result"]["calls_before"] == 0
    assert data["result"]["invoked"] is True
    again = _evaluate(client, ctx, "stats_hook", created["record_id"], {})
    assert again["result"]["calls_before"] == 1


def test_mt123_import_export_round_trip_works(client):
    """MT-123: export and import preserve real stored records in one workspace."""
    ctx = _setup(client)
    created = _create(client, ctx, "consent", {"contact_id": "c-1", "dnc": False})
    exported = client.get(_base(ctx) + "/export", headers=ctx["h"])
    assert exported.status_code == 200, exported.text
    records = exported.json()["records"]
    assert any(item["record_id"] == created["record_id"] for item in records)
    cross = client.get(_base(ctx) + "/export", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    imported = client.post(_base(ctx) + "/import", headers=ctx["h"], json={"records": records})
    assert imported.status_code == 200, imported.text
    assert len(imported.json()) == len(records)
