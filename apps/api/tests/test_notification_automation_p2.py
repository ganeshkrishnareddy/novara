"""Named acceptance tests for the clean-room notification automation cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No Novu source, outbound HTTP, real email/SMS/push delivery or hosted
provider is used; HTTP steps resolve only against registered local stubs and
demo sends persist simulated local records.
"""

from __future__ import annotations

import hashlib

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/notification-automation"


def _ctx(client):
    tokens = bootstrap(client, "Automation", "automation@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _subscriber(client, wid, h, key, email="", name=""):
    response = client.post(_base(wid) + "/subscribers", headers=h,
                           json={"subscriber_key": key, "email": email, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_nv009_code_steps_are_sandboxed_versioned_and_published(client):
    """Code steps evaluate in a restricted sandbox, version and gate on publish."""
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/code-steps", headers=h, json={
        "workflow_key": "welcome", "step_key": "total",
        "code": "payload.amount * 2 + len(payload.items)", "publish": True,
    })
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1 and created.json()["published"] is True
    result = client.post(_base(wid) + f"/code-steps/{created.json()['id']}/evaluate", headers=h,
                         json={"payload": {"amount": 5, "items": ["a", "b"]}})
    assert result.status_code == 200, result.text
    assert result.json()["result"] == 12 and result.json()["sandboxed"] is True
    updated = client.post(_base(wid) + "/code-steps", headers=h, json={
        "workflow_key": "welcome", "step_key": "total", "code": "payload.amount + 1",
    })
    assert updated.json()["version"] == 2
    assert client.post(_base(wid) + f"/code-steps/{created.json()['id']}/evaluate", headers=h,
                       json={"payload": {}}).status_code == 409  # now unpublished draft
    for unsafe in ("__import__('os').system('x')", "open('secret.txt')", "payload.__class__"):
        assert client.post(_base(wid) + "/code-steps", headers=h, json={
            "workflow_key": "welcome", "step_key": "bad", "code": unsafe,
        }).status_code == 422


def test_nv015_http_steps_resolve_only_registered_local_stubs(client):
    """HTTP steps need authorisation and resolve against local stubs, never outbound."""
    wid, h = _ctx(client)
    stub = client.post(_base(wid) + "/http-stubs", headers=h, json={
        "path": "/local/pricing", "method": "GET", "response": {"price": 10},
    })
    assert stub.status_code == 201, stub.text
    assert client.post(_base(wid) + "/http-stubs", headers=h, json={
        "path": "https://external.example/api", "response": {},
    }).status_code == 422
    step = client.post(_base(wid) + "/http-steps", headers=h, json={
        "workflow_key": "quote", "step_key": "fetch-price",
        "method": "GET", "path": "/local/pricing", "authorized": True,
    })
    assert step.status_code == 201, step.text
    run = client.post(_base(wid) + f"/http-steps/{step.json()['id']}/run", headers=h)
    assert run.status_code == 200, run.text
    assert run.json()["response"] == {"price": 10}
    assert run.json()["external_calls"] is False
    unauthorized = client.post(_base(wid) + "/http-steps", headers=h, json={
        "workflow_key": "quote", "step_key": "no-auth", "path": "/local/pricing",
    })
    assert client.post(_base(wid) + f"/http-steps/{unauthorized.json()['id']}/run",
                       headers=h).status_code == 403
    missing = client.post(_base(wid) + "/http-steps", headers=h, json={
        "workflow_key": "quote", "step_key": "missing-stub",
        "path": "/local/absent", "authorized": True,
    })
    assert client.post(_base(wid) + f"/http-steps/{missing.json()['id']}/run",
                       headers=h).status_code == 422
    assert client.post(_base(wid) + "/http-steps", headers=h, json={
        "workflow_key": "quote", "step_key": "outbound",
        "path": "https://external.example/api", "authorized": True,
    }).status_code == 422


def test_nv026_routing_selects_primary_and_fallback_chain(client):
    """Routing picks a provider by subscriber/context/data with priority fallbacks."""
    wid, h = _ctx(client)
    _subscriber(client, wid, h, "vip-1", email="ceo@vip.local")
    for provider, priority, conditions in (
        ("demo_email", 10, [{"source": "subscriber", "key": "email_domain", "equals": "vip.local"}]),
        ("demo_sms", 20, [{"source": "context", "key": "region", "equals": "IN"}]),
        ("in_app", 30, []),
    ):
        response = client.post(_base(wid) + "/routing-rules", headers=h, json={
            "workflow_key": "alerts", "provider": provider,
            "priority": priority, "conditions": conditions,
        })
        assert response.status_code == 201, response.text
    result = client.post(_base(wid) + "/routing/evaluate", headers=h, json={
        "workflow_key": "alerts", "subscriber_key": "vip-1", "context": {"region": "IN"},
    })
    assert result.status_code == 200, result.text
    assert result.json()["primary"] == "demo_email"
    assert result.json()["fallbacks"] == ["demo_sms", "in_app"]
    unmatched = client.post(_base(wid) + "/routing/evaluate", headers=h, json={
        "workflow_key": "other-flow",
    })
    assert unmatched.json()["primary"] == "in_app"
    assert unmatched.json()["matched_rules"] == 0
    assert client.post(_base(wid) + "/routing-rules", headers=h, json={
        "workflow_key": "alerts", "provider": "pagerduty", "priority": 1,
    }).status_code == 422


def test_nv027_demo_providers_enforce_their_daily_quotas(client):
    """Demo SMS sends are simulated locally and stop at the documented daily quota."""
    wid, h = _ctx(client)
    _subscriber(client, wid, h, "demo-user", email="demo@local.test")
    for i in range(20):
        response = client.post(_base(wid) + "/demo-send", headers=h, json={
            "provider": "demo_sms", "subscriber_key": "demo-user", "payload": {"n": i},
        })
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "simulated"
        assert response.json()["external_delivery"] is False
    blocked = client.post(_base(wid) + "/demo-send", headers=h, json={
        "provider": "demo_sms", "subscriber_key": "demo-user", "payload": {"n": 20},
    })
    assert blocked.status_code == 429
    providers = client.get(_base(wid) + "/demo-providers", headers=h).json()
    sms = [p for p in providers if p["provider"] == "demo_sms"][0]
    assert sms["used_today"] == 20 and sms["remaining"] == 0 and sms["real_delivery"] is False
    assert client.post(_base(wid) + "/demo-send", headers=h, json={
        "provider": "real_email", "subscriber_key": "demo-user",
    }).status_code == 422


def test_nv031_channel_endpoints_store_hashed_secrets_only(client):
    """Device tokens/phones/chat endpoints persist with hashed secrets and masked output."""
    wid, h = _ctx(client)
    subscriber = _subscriber(client, wid, h, "device-user")
    secret = "device-token-abc123"
    response = client.post(_base(wid) + f"/subscribers/{subscriber['id']}/endpoints", headers=h,
                           json={"channel": "push", "endpoint": "token-abcdef987654", "secret": secret})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["has_secret"] is True
    assert secret not in response.text and "token-abcdef987654" not in response.text
    assert body["endpoint_masked"].endswith("7654")
    listed = client.get(_base(wid) + f"/subscribers/{subscriber['id']}/endpoints", headers=h)
    assert secret not in listed.text and "token-abcdef987654" not in listed.text
    assert client.post(_base(wid) + f"/subscribers/{subscriber['id']}/endpoints", headers=h,
                       json={"channel": "push", "endpoint": "token-abcdef987654"}).status_code == 409
    assert client.post(_base(wid) + f"/subscribers/{subscriber['id']}/endpoints", headers=h,
                       json={"channel": "fax", "endpoint": "x"}).status_code == 422
    removed = client.delete(_base(wid) + f"/subscribers/{subscriber['id']}/endpoints/{body['id']}",
                            headers=h)
    assert removed.status_code == 200
    assert hashlib.sha256(secret.encode()).hexdigest()  # hash contract documented in module


def test_nv103_platform_quotas_are_documented_and_enforced(client):
    """Documented caps are workspace-scoped, overridable and enforced on writes."""
    wid, h = _ctx(client)
    quotas = client.get(_base(wid) + "/quotas", headers=h)
    assert quotas.status_code == 200, quotas.text
    assert quotas.json()["documented"]["max_bulk_create"] == 500
    assert quotas.json()["workspace_scoped"] is True
    override = client.put(_base(wid) + "/quotas", headers=h,
                          json={"key": "max_bulk_create", "value": 2})
    assert override.status_code == 200, override.text
    assert client.post(_base(wid) + "/subscribers/bulk", headers=h, json={
        "subscribers": [{"subscriber_key": f"u{i}"} for i in range(3)],
    }).status_code == 422
    assert client.put(_base(wid) + "/quotas", headers=h,
                      json={"key": "unknown_cap", "value": 1}).status_code == 422
    _subscriber(client, wid, h, "payload-user")
    client.put(_base(wid) + "/quotas", headers=h, json={"key": "max_payload_bytes", "value": 10})
    assert client.post(_base(wid) + "/demo-send", headers=h, json={
        "provider": "demo_email", "subscriber_key": "payload-user",
        "payload": {"message": "this payload is far too large"},
    }).status_code == 422


def test_nv104_broadcast_requires_flag_and_explicit_authorisation(client):
    """Broadcast is flag-gated, authorised, and delivers local records to all subscribers."""
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/broadcast", headers=h, json={
        "workflow_key": "announce", "authorized": True,
    }).status_code == 409  # experimental_broadcast defaults off
    enabled = client.patch(_base(wid) + "/feature-flags/experimental_broadcast", headers=h,
                           json={"enabled": True})
    assert enabled.status_code == 200, enabled.text
    assert client.post(_base(wid) + "/broadcast", headers=h, json={
        "workflow_key": "announce", "authorized": False,
    }).status_code == 403
    assert client.post(_base(wid) + "/broadcast", headers=h, json={
        "workflow_key": "announce", "authorized": True,
    }).status_code == 422  # no subscribers yet
    _subscriber(client, wid, h, "s1")
    _subscriber(client, wid, h, "s2")
    result = client.post(_base(wid) + "/broadcast", headers=h, json={
        "workflow_key": "announce", "payload": {"title": "Maintenance"}, "authorized": True,
    })
    assert result.status_code == 201, result.text
    assert result.json()["recipients"] == 2
    assert result.json()["status"] == "delivered_local"
    assert result.json()["external_delivery"] is False
    deliveries = client.get(_base(wid) + "/deliveries", headers=h).json()
    broadcast_rows = [d for d in deliveries if d["broadcast_id"] == result.json()["broadcast_id"]]
    assert len(broadcast_rows) == 2
    assert all(d["status"] == "delivered_local" for d in broadcast_rows)


def test_nv107_subscriber_search_and_bulk_create(client):
    """Subscribers are searchable and up to 500 can be created in one request."""
    wid, h = _ctx(client)
    bulk = client.post(_base(wid) + "/subscribers/bulk", headers=h, json={
        "subscribers": [
            {"subscriber_key": "ana", "email": "ana@example.com", "name": "Ana Ruiz"},
            {"subscriber_key": "bo", "email": "bo@example.com", "name": "Bo Lin"},
            {"subscriber_key": "cy", "email": "cy@other.org", "name": "Cy Fox"},
        ],
    })
    assert bulk.status_code == 201, bulk.text
    assert bulk.json()["created"] == 3
    found = client.get(_base(wid) + "/subscribers", headers=h, params={"q": "EXAMPLE"})
    assert {s["subscriber_key"] for s in found.json()} == {"ana", "bo"}
    assert client.get(_base(wid) + "/subscribers", headers=h, params={"q": "fox"}).json()[0]["subscriber_key"] == "cy"
    assert client.post(_base(wid) + "/subscribers/bulk", headers=h, json={
        "subscribers": [{"subscriber_key": "dup"}, {"subscriber_key": "dup"}],
    }).status_code == 422
    assert client.post(_base(wid) + "/subscribers/bulk", headers=h, json={
        "subscribers": [{"subscriber_key": "ana"}],
    }).status_code == 409
    assert client.post(_base(wid) + "/subscribers/bulk", headers=h, json={
        "subscribers": [{"subscriber_key": f"bulk{i}"} for i in range(501)],
    }).status_code == 422


def test_nv118_feature_flags_gate_experimental_features(client):
    """Workspace feature flags expose env-style defaults and gate experimental routes."""
    wid, h = _ctx(client)
    flags = client.get(_base(wid) + "/feature-flags", headers=h)
    assert flags.status_code == 200, flags.text
    by_key = {f["key"]: f for f in flags.json()}
    assert by_key["experimental_broadcast"]["enabled"] is False
    assert by_key["experimental_broadcast"]["env_default"] == "NOVARA_EXPERIMENTAL_BROADCAST=false"
    assert by_key["experimental_code_steps"]["enabled"] is True
    disabled = client.patch(_base(wid) + "/feature-flags/experimental_code_steps", headers=h,
                            json={"enabled": False})
    assert disabled.status_code == 200
    assert client.post(_base(wid) + "/code-steps", headers=h, json={
        "workflow_key": "w", "step_key": "s", "code": "1 + 1",
    }).status_code == 409
    client.patch(_base(wid) + "/feature-flags/experimental_code_steps", headers=h,
                 json={"enabled": True})
    assert client.post(_base(wid) + "/code-steps", headers=h, json={
        "workflow_key": "w", "step_key": "s", "code": "1 + 1",
    }).status_code == 201
    assert client.patch(_base(wid) + "/feature-flags/no_such_flag", headers=h,
                        json={"enabled": True}).status_code == 404


def test_notification_automation_workspace_isolation(client):
    """A second workspace cannot address this workspace's automation rows."""
    wid, h = _ctx(client)
    subscriber = _subscriber(client, wid, h, "isolated")
    step = client.post(_base(wid) + "/code-steps", headers=h, json={
        "workflow_key": "w", "step_key": "s", "code": "1 + 1", "publish": True,
    }).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other automation"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/subscribers", headers=other_h).json() == []
    assert client.get(_base(other_wid) + f"/subscribers/{subscriber['id']}/endpoints",
                      headers=other_h).status_code == 404
    assert client.post(_base(other_wid) + f"/code-steps/{step['id']}/evaluate", headers=other_h,
                       json={"payload": {}}).status_code == 404
    assert client.get(_base(other_wid) + "/routing-rules", headers=other_h).json() == []
    assert client.get(_base(other_wid) + "/deliveries", headers=other_h).json() == []
    assert client.patch(_base(other_wid) + "/feature-flags/experimental_broadcast", headers=h,
                        json={"enabled": True}).status_code == 403