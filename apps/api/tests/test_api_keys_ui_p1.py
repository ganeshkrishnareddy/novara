"""Named acceptance test for the API-key settings UI (PL-045, PL-070).

Real API calls issue, rotate and revoke a key; source assertions prove the
settings view binds those operations to real handlers and never displays a
stored secret. No external call is made.
"""

from __future__ import annotations

from pathlib import Path

from .conftest import auth, bootstrap

API = "/api/v1"
KEYS = API + "/workspaces/{wid}/api-keys"
APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def test_pl045_pl070_settings_ui_issue_rotate_revoke(client):
    tokens = bootstrap(client, "KeyUI", "key-ui-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = KEYS.format(wid=wid)

    issued = client.post(
        base, headers=headers,
        json={"name": "Reporting client", "scopes": ["contact:read"]},
    )
    assert issued.status_code == 201, issued.text
    first = issued.json()
    assert first["secret"].startswith(first["prefix"])
    assert "secret" not in client.get(base, headers=headers).json()[0]

    rotated = client.post(base + f"/{first['id']}/rotate", headers=headers, json={})
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()
    assert second["secret"] != first["secret"]
    assert client.get(API + "/workspaces/" + wid + "/contacts", headers={"X-API-Key": first["secret"]}).status_code == 401
    assert client.get(API + "/workspaces/" + wid + "/contacts", headers={"X-API-Key": second["secret"]}).status_code == 200

    revoked = client.delete(base + f"/{first['id']}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked_at"]
    assert client.get(API + "/workspaces/" + wid + "/contacts", headers={"X-API-Key": second["secret"]}).status_code == 401

    source = APP_JS.read_text(encoding="utf-8")
    for marker in (
        "data-form=\"api-key-create\"",
        "case 'api-key-rotate':",
        "case 'api-key-revoke':",
        "api(apiW('/api-keys'))",
        "api(apiW('/api-keys'), {",
        "showApiKeySecret(issued, 'API key issued'",
        "readonly data-api-key-secret",
        "field('scopes', 'Scopes (comma-separated)'",
    ):
        assert source.count(marker) == 1, f"UI marker {marker!r} count={source.count(marker)}"
