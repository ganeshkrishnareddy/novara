"""Named acceptance tests for the API-key P1 cluster (PL-045, PL-070).

Every test drives the real FastAPI app through the ``client`` fixture and
inspects real persisted rows and audit events. No app code is mocked and no
secret material is printed in assertion messages.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from novara_core.models import Event, User, now
from novara_core.modules.api_keys import ApiKey
from novara_core.security import hash_token

from .conftest import auth, bootstrap

API_KEYS = "/api/v1/workspaces/{wid}/api-keys"
CONTACTS = "/api/v1/workspaces/{wid}/contacts"


def _issue(client, wid, headers, name, scopes, expires_at=None):
    body = {"name": name, "scopes": scopes}
    if expires_at is not None:
        body["expires_at"] = expires_at
    response = client.post(API_KEYS.format(wid=wid), headers=headers, json=body)
    assert response.status_code == 201
    return response.json()


def _key_headers(secret):
    return {"X-API-Key": secret}


def test_pl045_api_key_authenticates_and_secret_is_not_stored(client, db_session):
    """A scoped key authenticates; only its hash is persisted or returned."""
    tokens = bootstrap(client, "KeyAuth", "keyauth@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    issued = _issue(client, wid, headers, "reader", ["contact:read"])

    listed = client.get(CONTACTS.format(wid=wid), headers=_key_headers(issued["secret"]))
    assert listed.status_code == 200

    row = db_session.execute(
        select(ApiKey).where(ApiKey.id == issued["id"])
    ).scalar_one()
    assert row.secret_hash == hash_token(issued["secret"])
    assert row.secret_hash != issued["secret"]
    assert issued["secret"] not in row.secret_hash
    assert issued["secret"] not in row.prefix
    assert row.scopes == ["contact:read"]
    assert row.last_used_at is not None

    for response in (
        client.get(API_KEYS.format(wid=wid), headers=headers),
        client.get(API_KEYS.format(wid=wid) + f"/{row.id}", headers=headers),
    ):
        assert response.status_code == 200
        body = response.json()
        items = body if isinstance(body, list) else [body]
        assert items
        for item in items:
            assert "secret_hash" not in item
            assert "secret" not in item
            assert issued["secret"] not in response.text


def test_pl070_read_scoped_key_is_denied_write_and_allows_read(client, db_session):
    """A read key cannot write; a write key can. Management is bearer-only."""
    tokens = bootstrap(client, "KeyScopes", "keyscopes@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    reader = _issue(client, wid, headers, "reader", ["contact:read"])

    assert client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(reader["secret"])
    ).status_code == 200
    denied = client.post(
        CONTACTS.format(wid=wid),
        headers=_key_headers(reader["secret"]),
        json={"email": "blocked@example.com", "full_name": "Blocked"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "permission required: contact:write"

    writer = _issue(client, wid, headers, "writer", ["contact:write"])
    created = client.post(
        CONTACTS.format(wid=wid),
        headers=_key_headers(writer["secret"]),
        json={"email": "allowed@example.com", "full_name": "Allowed"},
    )
    assert created.status_code == 201
    assert client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(writer["secret"])
    ).json()["detail"] == "permission required: contact:read"

    manager = _issue(client, wid, headers, "manager", ["workspace:manage", "contact:read"])
    manager_headers = _key_headers(manager["secret"])
    assert client.get(
        API_KEYS.format(wid=wid), headers=manager_headers
    ).status_code == 200
    assert client.post(
        API_KEYS.format(wid=wid), headers=manager_headers,
        json={"name": "child", "scopes": ["contact:read"]},
    ).status_code == 403
    assert client.post(
        API_KEYS.format(wid=wid) + f"/{reader['id']}/rotate",
        headers=manager_headers, json={},
    ).status_code == 403
    assert client.delete(
        API_KEYS.format(wid=wid) + f"/{reader['id']}", headers=manager_headers
    ).status_code == 403


def test_pl045_expired_and_revoked_keys_fail_closed(client, db_session):
    """Expired, revoked and unknown keys all receive a clean 401."""
    tokens = bootstrap(client, "KeyStates", "keystates@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    past = (now() - timedelta(hours=1)).isoformat()
    expired = _issue(client, wid, headers, "expired", ["contact:read"], expires_at=past)
    expired_response = client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(expired["secret"])
    )
    assert expired_response.status_code == 401
    assert expired_response.json()["detail"] == "invalid or expired API key"

    revoked = _issue(client, wid, headers, "revoked", ["contact:read"])
    removal = client.delete(API_KEYS.format(wid=wid) + f"/{revoked['id']}", headers=headers)
    assert removal.status_code == 200
    row = db_session.execute(
        select(ApiKey).where(ApiKey.id == revoked["id"])
    ).scalar_one()
    assert row.revoked_at is not None
    denied = client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(revoked["secret"])
    )
    assert denied.status_code == 401
    assert denied.json()["detail"] == "invalid or expired API key"

    unknown = client.get(
        CONTACTS.format(wid=wid),
        headers=_key_headers("nvk_notarealprefix_definitely-not-a-key"),
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "invalid or expired API key"
    assert "secret" not in unknown.json()["detail"]


def test_pl045_rotation_invalidates_old_secret(client, db_session):
    """Rotation issues a fresh secret, retires the old one and is audited."""
    tokens = bootstrap(client, "KeyRotate", "keyrotate@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner_id = db_session.execute(
        select(User.id).where(User.email == "keyrotate@example.com")
    ).scalar_one()
    issued = _issue(client, wid, headers, "rotating", ["contact:read"])
    assert client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(issued["secret"])
    ).status_code == 200

    rotated = client.post(
        API_KEYS.format(wid=wid) + f"/{issued['id']}/rotate",
        headers=headers, json={},
    )
    assert rotated.status_code == 200
    fresh = rotated.json()
    assert fresh["secret"] != issued["secret"]
    assert client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(issued["secret"])
    ).status_code == 401
    assert client.get(
        CONTACTS.format(wid=wid), headers=_key_headers(fresh["secret"])
    ).status_code == 200

    row = db_session.execute(
        select(ApiKey).where(ApiKey.id == issued["id"])
    ).scalar_one()
    assert row.secret_hash == hash_token(fresh["secret"])
    events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid,
            Event.entity_id == issued["id"],
            Event.event_type.in_(["api_key.created", "api_key.rotated"]),
        )
    ).scalars().all()
    assert {event.event_type for event in events} == {"api_key.created", "api_key.rotated"}
    assert all(event.payload.get("actor_id") == owner_id for event in events)


def test_pl045_key_cannot_escalate_or_cross_workspace(client, db_session):
    """No wildcard/duplicated scopes, no member key minting, no tenant hopping."""
    tokens = bootstrap(client, "KeyLimitA", "keylimit-a@example.com")
    wid_a, headers_a = tokens["workspace_id"], auth(tokens["access_token"])

    for scopes in (["*"], ["contact:read", "*"], ["contact:read", "contact:read"], ["nope:scope"]):
        rejected = client.post(
            API_KEYS.format(wid=wid_a), headers=headers_a,
            json={"name": "bad", "scopes": scopes},
        )
        assert rejected.status_code == 422

    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": "keylimit-member@example.com",
            "display_name": "Limited member",
            "password": "Password123!",
        },
    )
    assert other.status_code == 200
    member_tokens = other.json()
    wid_b = member_tokens["workspace_id"]
    invite = client.post(
        f"/api/v1/workspaces/{wid_a}/invitations",
        headers=headers_a,
        json={"email": "keylimit-member@example.com", "role": "read_only"},
    )
    assert invite.status_code == 200
    accepted = client.post(
        "/api/v1/invitations/accept",
        headers=auth(member_tokens["access_token"]),
        json={"token": invite.json()["invite_token"]},
    )
    assert accepted.status_code == 200
    denied_member = client.post(
        API_KEYS.format(wid=wid_a),
        headers=auth(accepted.json()["access_token"]),
        json={"name": "escalation", "scopes": ["contact:read"]},
    )
    assert denied_member.status_code == 403
    assert denied_member.json()["detail"] == "permission required: workspace:manage"

    scoped = _issue(client, wid_a, headers_a, "tenant-bound", ["contact:read"])
    cross = client.get(
        CONTACTS.format(wid=wid_b), headers=_key_headers(scoped["secret"])
    )
    assert cross.status_code == 403
    assert cross.json()["detail"] == "cross-workspace access is denied"
    assert client.get(
        API_KEYS.format(wid=wid_b), headers=_key_headers(scoped["secret"])
    ).status_code == 403
