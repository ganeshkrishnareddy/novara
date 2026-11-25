"""Named acceptance tests for the local experimentation delivery cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No outbound webhook, Slack call, CDN API, proxy fetch or external
scheduler is used.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/experiment-delivery"
STATS = "/api/v1/workspaces/{wid}/experiment-stats"
OPS = "/api/v1/workspaces/{wid}/experiment-ops"


def _ctx(client):
    tokens = bootstrap(client, "Delivery", "delivery@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _webhook(client, wid, h, scope="event", key=None, event_types=None):
    body = {"key": key or scope + "-hook", "name": scope.title() + " hook",
            "scope": scope, "target_label": "local-" + scope,
            "event_types": event_types or []}
    response = client.post(_base(wid) + "/webhooks", headers=h, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_stats(client, wid, h):
    metric = client.post(STATS.format(wid=wid) + "/metrics", headers=h,
                         json={"key": "conversion", "name": "Conversion", "type": "proportion"})
    assert metric.status_code == 201, metric.text
    experiment = client.post(STATS.format(wid=wid) + "/experiments", headers=h, json={
        "key": "checkout", "name": "Checkout",
        "variants": [{"key": "control", "traffic_share": 0.5},
                     {"key": "variant", "traffic_share": 0.5}],
    })
    assert experiment.status_code == 201, experiment.text
    for variant, sessions, conversions in (("control", 100, 10), ("variant", 100, 16)):
        observation = client.post(
            STATS.format(wid=wid) + f"/experiments/{experiment.json()['id']}/observations",
            headers=h, json={"metric_id": metric.json()["id"], "variant": variant,
                             "sessions": sessions, "conversions": conversions},
        )
        assert observation.status_code == 201, observation.text


def test_gb071_event_webhooks_record_local_deliveries(client):
    """Event webhooks subscribe to a type and record deliveries locally."""
    wid, h = _ctx(client)
    hook = _webhook(client, wid, h, "event", event_types=["flag.updated"])
    assert client.post(_base(wid) + "/webhooks", headers=h, json={
        "key": "event-hook", "name": "dup", "scope": "event", "target_label": "local",
    }).status_code == 409
    assert client.post(_base(wid) + "/webhooks", headers=h, json={
        "key": "bad-scope", "name": "bad", "scope": "warehouse", "target_label": "local",
    }).status_code == 422
    assert client.post(_base(wid) + f"/webhooks/{hook['id']}/emit", headers=h,
                       json={"event_type": "flag.deleted", "payload": {}}).status_code == 422
    emitted = client.post(_base(wid) + f"/webhooks/{hook['id']}/emit", headers=h,
                          json={"event_type": "flag.updated", "payload": {"key": "checkout"}})
    assert emitted.status_code == 200, emitted.text
    assert emitted.json()["status"] == "recorded_local"
    deliveries = client.get(_base(wid) + f"/webhooks/{hook['id']}/deliveries", headers=h).json()
    assert len(deliveries) == 1 and deliveries[0]["event_type"] == "flag.updated"


def test_gb072_sdk_webhooks_record_payload_change(client):
    """SDK webhooks record one local delivery for a changed SDK payload."""
    wid, h = _ctx(client)
    hook = _webhook(client, wid, h, "sdk", event_types=["payload.changed"])
    emitted = client.post(_base(wid) + f"/webhooks/{hook['id']}/emit", headers=h,
                          json={"event_type": "payload.changed", "payload": {"sdk_key": "web"}})
    assert emitted.status_code == 200 and emitted.json()["scope"] == "sdk"
    deliveries = client.get(_base(wid) + f"/webhooks/{hook['id']}/deliveries", headers=h).json()
    assert len(deliveries) == 1 and deliveries[0]["scope"] == "sdk"


def test_gb073_global_sdk_webhooks_record_any_payload_change(client):
    """A global SDK webhook records each payload change in the workspace."""
    wid, h = _ctx(client)
    hook = _webhook(client, wid, h, "global_sdk")
    for event_type in ("payload.changed", "payload.revised"):
        response = client.post(_base(wid) + f"/webhooks/{hook['id']}/emit", headers=h,
                               json={"event_type": event_type, "payload": {}})
        assert response.status_code == 200 and response.json()["scope"] == "global_sdk"
    deliveries = client.get(_base(wid) + f"/webhooks/{hook['id']}/deliveries", headers=h).json()
    assert len(deliveries) == 2


def test_gb074_slack_compatible_notifier_records_without_sending(client):
    """Slack-style messages are local drafts/records; no URL is accepted."""
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/notifier", headers=h, json={
        "key": "experiment-alert", "channel": "#experiments",
        "subject": "Checkout result", "body": "Variant won locally.",
        "experiment_key": "checkout",
    })
    assert created.status_code == 201, created.text
    assert client.post(_base(wid) + "/notifier", headers=h, json={
        "key": "with-url", "channel": "#x", "subject": "s", "body": "b",
        "url": "https://example.invalid/hook",
    }).status_code == 422
    recorded = client.post(_base(wid) + f"/notifier/{created.json()['id']}/record", headers=h)
    assert recorded.status_code == 200
    assert recorded.json()["status"] == "recorded_local"
    assert recorded.json()["external_delivery"] is False
    messages = client.get(_base(wid) + "/notifier", headers=h).json()
    assert messages[0]["channel"] == "#experiments" and messages[0]["status"] == "recorded_local"


def test_gb075_cdn_cache_purge_records_local_invalidation(client):
    """Cache entries can be stored, versioned and purged by local prefix."""
    wid, h = _ctx(client)
    for key in ("sdk:payload:v1", "sdk:payload:v2", "report:summary"):
        response = client.post(_base(wid) + "/cache", headers=h,
                               json={"cache_key": key, "payload": {"key": key}})
        assert response.status_code == 201, response.text
    updated = client.post(_base(wid) + "/cache", headers=h,
                          json={"cache_key": "sdk:payload:v1", "payload": {"key": "new"}})
    assert updated.json()["version"] == 2
    purged = client.post(_base(wid) + "/cache/purge", headers=h,
                         json={"prefix": "sdk:payload:", "reason": "local flag change"})
    assert purged.status_code == 200 and purged.json()["purged_count"] == 2
    assert purged.json()["external_cdn_call"] is False
    entries = {e["cache_key"]: e for e in client.get(_base(wid) + "/cache", headers=h).json()}
    assert entries["sdk:payload:v1"]["purged"] is True
    assert entries["report:summary"]["purged"] is False


def test_gb076_self_hosted_proxy_serves_local_and_stale_snapshots(client):
    """The proxy serves stored payloads and stale-if-error without a fetch."""
    wid, h = _ctx(client)
    snapshot = client.post(_base(wid) + "/proxy", headers=h, json={
        "key": "web-payload", "name": "Web payload",
        "payload": {"flags": {"checkout": True}}, "stale_if_error": True,
    })
    assert snapshot.status_code == 201, snapshot.text
    served = client.post(_base(wid) + f"/proxy/{snapshot.json()['id']}/serve", headers=h,
                         json={"simulate_error": False})
    assert served.json()["source"] == "local_snapshot"
    assert served.json()["external_fetch"] is False
    stale = client.post(_base(wid) + f"/proxy/{snapshot.json()['id']}/serve", headers=h,
                        json={"simulate_error": True})
    assert stale.json()["source"] == "local_stale_if_error"
    assert stale.json()["payload"] == {"flags": {"checkout": True}}

    strict = client.post(_base(wid) + "/proxy", headers=h, json={
        "key": "strict-payload", "name": "Strict", "payload": {}, "stale_if_error": False,
    }).json()
    assert client.post(_base(wid) + f"/proxy/{strict['id']}/serve", headers=h,
                       json={"simulate_error": True}).status_code == 503


def test_gb081_agenda_style_local_refresh_queue(client):
    """Refresh jobs are durable, validated and workspace-scoped."""
    wid, h = _ctx(client)
    job = client.post(_base(wid) + "/refresh-jobs", headers=h, json={
        "key": "nightly-results", "job_type": "experiment_results", "target_key": "checkout",
    })
    assert job.status_code == 201, job.text
    assert job.json()["status"] == "scheduled"
    assert client.post(_base(wid) + "/refresh-jobs", headers=h, json={
        "key": "nightly-results", "job_type": "metric", "target_key": "checkout",
    }).status_code == 409
    assert client.post(_base(wid) + "/refresh-jobs", headers=h, json={
        "key": "bad-job", "job_type": "warehouse_sync", "target_key": "checkout",
    }).status_code == 422
    jobs = client.get(_base(wid) + "/refresh-jobs", headers=h).json()
    assert [j["key"] for j in jobs] == ["nightly-results"]


def test_gb082_experiment_result_refresh_uses_local_observations(client):
    """An experiment refresh recomputes from NOVARA's own statistics rows."""
    wid, h = _ctx(client)
    _seed_stats(client, wid, h)
    job = client.post(_base(wid) + "/refresh-jobs", headers=h, json={
        "key": "result-refresh", "job_type": "experiment_results", "target_key": "checkout",
    }).json()
    run = client.post(_base(wid) + f"/refresh-jobs/{job['id']}/run", headers=h)
    assert run.status_code == 200, run.text
    result = run.json()
    assert result["status"] == "succeeded"
    assert result["definition_count"] == 1
    assert result["observation_count"] == 2
    assert result["variants"] == ["control", "variant"]


def test_gb083_metric_refresh_uses_local_time_series(client):
    """A metric refresh recomputes from stored local time-series points."""
    wid, h = _ctx(client)
    point = client.post(OPS.format(wid=wid) + "/timeseries", headers=h, json={
        "experiment_key": "checkout", "metric_key": "conversion",
        "day": "2026-11-23", "sessions": 100, "conversions": 12,
    })
    assert point.status_code == 201 or point.status_code == 200, point.text
    job = client.post(_base(wid) + "/refresh-jobs", headers=h, json={
        "key": "metric-refresh", "job_type": "metric", "target_key": "checkout",
    }).json()
    run = client.post(_base(wid) + f"/refresh-jobs/{job['id']}/run", headers=h)
    assert run.status_code == 200, run.text
    result = run.json()
    assert result["point_count"] == 1
    assert result["metric_keys"] == ["conversion"]
    assert result["total_sessions"] == 100


def test_experiment_delivery_workspace_isolation(client):
    """A second workspace cannot see or use another workspace's delivery rows."""
    wid, h = _ctx(client)
    hook = _webhook(client, wid, h, "event")
    client.post(_base(wid) + "/cache", headers=h,
                json={"cache_key": "secret:local", "payload": {}})
    proxy = client.post(_base(wid) + "/proxy", headers=h, json={
        "key": "only-here", "name": "Only here", "payload": {},
    }).json()

    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other delivery"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/webhooks", headers=h).status_code == 403
    for path in ("/webhooks", "/cache", "/proxy", "/refresh-jobs", "/notifier"):
        assert client.get(_base(other_wid) + path, headers=other_h).json() == []
    assert client.post(_base(other_wid) + f"/webhooks/{hook['id']}/emit",
                       headers=other_h, json={"event_type": "x", "payload": {}}).status_code == 404
    assert client.post(_base(other_wid) + f"/proxy/{proxy['id']}/serve",
                       headers=other_h, json={}).status_code == 404
    # The other workspace's cache purge cannot touch this workspace's entries.
    other_purge = client.post(_base(other_wid) + "/cache/purge", headers=other_h,
                              json={"prefix": "secret:", "reason": "x"})
    assert other_purge.status_code == 200 and other_purge.json()["purged_count"] == 0
