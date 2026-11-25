"""Named acceptance tests for clean-room advanced feature-flag governance.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. GB-183/196/206/209/210/211/224/225/231/232/233/247/248/249 are proven end
to end. No GrowthBook source, SDK, hosted endpoint, licence server, warehouse or
external service is used; socket.socket.connect is patched to raise.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"
BASE = API.format(wid="{wid}") + "/flag-governance"


def _ctx(client, name="FlagGov", email="flaggov-owner@example.com"):
    tokens = bootstrap(client, name, email)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("a flag-governance endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _post(client, wid, h, path, body):
    return client.post(_base(wid) + path, headers=h, json=body)


def _other(client, h):
    response = client.post("/api/v1/workspaces", headers=h, json={"name": "Other flag gov"})
    assert response.status_code == 200, response.text
    return response.json()["workspace_id"], auth(response.json()["access_token"])


def test_gb183_scheduled_flag_state(client, monkeypatch):
    """GB-183: scheduled state resolves to the latest started schedule."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    for starts, state in (("2026-01-01T00:00:00Z", {"state": "on", "value": "first"}),
                          ("2026-06-01T00:00:00Z", {"state": "variant", "value": "b"})):
        response = _post(client, wid, h, "/schedules", {
            "flag_key": "checkout", "starts_at": starts, "state": state})
        assert response.status_code == 201, response.text
    result = _post(client, wid, h, "/schedules/resolve", {
        "flag_values": {"checkout": "off"},
        "attrs": {"at": "2026-03-01T00:00:00Z"}}).json()
    assert result["states"]["checkout"]["value"] == "first"
    result = _post(client, wid, h, "/schedules/resolve", {
        "flag_values": {"checkout": "off"},
        "attrs": {"at": "2026-09-01T00:00:00Z"}}).json()
    assert result["states"]["checkout"]["value"] == "b"
    assert _post(client, wid, h, "/schedules", {
        "flag_key": "bad", "starts_at": "not-a-date", "state": {"state": "on"}}).status_code == 422


def test_gb196_hash_secure_attributes(client, monkeypatch):
    """GB-196: sensitive attribute values are salted-hashed before matching."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    saved = _post(client, wid, h, "/secure-attributes", {
        "flag_key": "checkout", "attribute": "email", "salt": "pepper-42",
        "value": "user@example.com"})
    assert saved.status_code == 201, saved.text
    digest = saved.json()["digest"]
    assert "user@example.com" not in digest
    assert len(digest) == 64
    assert _post(client, wid, h, "/secure-attributes/match", {
        "flag_key": "checkout", "attribute": "email", "salt": "pepper-42",
        "value": "user@example.com"}).json()["matched"] is True
    assert _post(client, wid, h, "/secure-attributes/match", {
        "flag_key": "checkout", "attribute": "email", "salt": "pepper-42",
        "value": "other@example.com"}).json()["matched"] is False


def test_gb206_sticky_bucketing_stable(client, monkeypatch):
    """GB-206: a user's bucketed variant stays stable across rollout changes."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    first = _post(client, wid, h, "/sticky", {
        "flag_key": "onboarding", "user_key": "user-1", "percent": 10}).json()
    second = _post(client, wid, h, "/sticky", {
        "flag_key": "onboarding", "user_key": "user-1", "percent": 90}).json()
    assert first["sticky"] is True
    assert first["variant"] == second["variant"]
    repeat = _post(client, wid, h, "/sticky", {
        "flag_key": "onboarding", "user_key": "user-1", "percent": 50}).json()
    assert repeat["variant"] == first["variant"]
    assert _post(client, wid, h, "/sticky", {
        "flag_key": "onboarding", "user_key": "user-1", "percent": 150}).status_code == 422


def test_gb209_prerequisites_value_check(client, monkeypatch):
    """GB-209: prerequisites require the named flag to hold a value."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/prerequisites", {
        "flag_key": "checkout", "prerequisite_key": "account_ready",
        "required_value": "on"})
    assert created.status_code == 201, created.text
    ok = _post(client, wid, h, "/prerequisites/check", {
        "flag_values": {"account_ready": "on"}, "attrs": {"flag_key": "checkout"}}).json()
    assert ok["met"] is True and ok["reason"] == "prerequisites_met"
    bad = _post(client, wid, h, "/prerequisites/check", {
        "flag_values": {"account_ready": "off"}, "attrs": {"flag_key": "checkout"}}).json()
    assert bad["met"] is False and bad["reason"] == "prerequisite_value:account_ready"


def test_gb210_prerequisite_targeting_conditions(client, monkeypatch):
    """GB-210: a prerequisite can carry a saved targeting condition."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    _post(client, wid, h, "/prerequisites", {
        "flag_key": "premium", "prerequisite_key": "account_ready",
        "target_condition": {"all": [{"attr": "plan", "op": "eq", "value": "pro"}]}})
    matching = _post(client, wid, h, "/prerequisites/check", {
        "flag_values": {"account_ready": "on"},
        "attrs": {"flag_key": "premium", "plan": "pro"}}).json()
    assert matching["met"] is True
    failing = _post(client, wid, h, "/prerequisites/check", {
        "flag_values": {"account_ready": "on"},
        "attrs": {"flag_key": "premium", "plan": "free"}}).json()
    assert failing["met"] is False
    assert failing["reason"] == "prerequisite_targeting:account_ready"


def test_gb211_redirect_rule_result(client, monkeypatch):
    """GB-211: a rule can return a local redirect target without external calls."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/redirects", {
        "flag_key": "checkout", "rule_id": "new-flow",
        "target_url": "/checkout/v2"})
    assert created.status_code == 201, created.text
    resolved = _post(client, wid, h, "/redirects/resolve", {
        "attrs": {"flag_key": "checkout", "rule_id": "new-flow"}}).json()
    assert resolved["redirect"]["target_url"] == "/checkout/v2"
    missing = _post(client, wid, h, "/redirects/resolve", {
        "attrs": {"flag_key": "checkout", "rule_id": "missing"}}).json()
    assert missing["redirect"] is None
    assert _post(client, wid, h, "/redirects", {
        "flag_key": "checkout", "rule_id": "bad", "target_url": "ftp://unsafe"}).status_code == 422


def test_gb224_environment_inheritance(client, monkeypatch):
    """GB-224: environments inherit parent settings with local overrides."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    _post(client, wid, h, "/environments", {
        "environment": "production", "overrides": {"rollout": 100, "color": "blue"}})
    _post(client, wid, h, "/environments", {
        "environment": "staging", "parent_environment": "production",
        "overrides": {"rollout": 10}})
    resolved = _post(client, wid, h, "/environments/resolve", {
        "attrs": {"environment": "staging"}}).json()
    assert resolved["chain"] == ["staging", "production"]
    assert resolved["effective"]["rollout"] == 10
    assert resolved["effective"]["color"] == "blue"


def test_gb225_template_instantiation(client, monkeypatch):
    """GB-225: a reusable template instantiates a named flag definition."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/templates", {
        "key": "kill-switch", "definition": {"enabled": True, "default_value": "off"}})
    assert created.status_code == 201, created.text
    instantiated = _post(client, wid, h, "/templates/instantiate", {
        "template_key": "kill-switch", "flag_key": "checkout-kill"}).json()
    assert instantiated["key"] == "checkout-kill"
    assert instantiated["template_key"] == "kill-switch"
    assert instantiated["enabled"] is True
    assert len(client.get(_base(wid) + "/templates", headers=h).json()) == 1


def test_gb231_safe_rollout_guardrail(client, monkeypatch):
    """GB-231: a guardrail regression holds or rolls back a safe rollout."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/safe-rollouts", {
        "flag_key": "checkout", "guardrail_metric": "error_rate",
        "threshold": 0.05, "current_percent": 20})
    assert created.status_code == 201, created.text
    rollback = _post(client, wid, h, "/safe-rollouts/evaluate", {
        "flag_key": "checkout", "observed_rate": 0.01, "baseline_rate": 0.10}).json()
    assert rollback["action"] == "rollback" and rollback["next_percent"] == 0
    hold = _post(client, wid, h, "/safe-rollouts/evaluate", {
        "flag_key": "checkout", "observed_rate": 0.20, "baseline_rate": 0.10}).json()
    assert hold["action"] == "hold" and hold["next_percent"] == 20
    promote = _post(client, wid, h, "/safe-rollouts/evaluate", {
        "flag_key": "checkout", "observed_rate": 0.10, "baseline_rate": 0.10}).json()
    assert promote["action"] == "promote" and promote["next_percent"] == 30


def test_gb232_gb233_workspace_settings(client, monkeypatch):
    """GB-232/233: require-project settings are persisted per workspace."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    assert client.get(_base(wid) + "/settings", headers=h).json() == {
        "require_project_for_features": False, "require_project_for_sdk": False}
    updated = client.put(_base(wid) + "/settings", headers=h, json={
        "require_project_for_features": True, "require_project_for_sdk": True}).json()
    assert updated["require_project_for_features"] is True
    assert updated["require_project_for_sdk"] is True
    assert client.get(_base(wid) + "/settings", headers=h).json() == updated
    assert client.put(_base(wid) + "/settings", headers=h, json={}).status_code == 200


def test_gb247_ramp_schedule(client, monkeypatch):
    """GB-247: a ramp schedule interpolates traffic over a time window."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/ramps", {
        "flag_key": "checkout", "start_percent": 0, "end_percent": 100,
        "starts_at": "2026-01-01T00:00:00Z", "ends_at": "2026-01-11T00:00:00Z"})
    assert created.status_code == 201, created.text
    assert _post(client, wid, h, "/ramps/percent-at", {
        "attrs": {"flag_key": "checkout", "at": "2025-12-01T00:00:00Z"}}).json()["percent"] == 0
    assert _post(client, wid, h, "/ramps/percent-at", {
        "attrs": {"flag_key": "checkout", "at": "2026-01-06T00:00:00Z"}}).json()["percent"] == 50
    assert _post(client, wid, h, "/ramps/percent-at", {
        "attrs": {"flag_key": "checkout", "at": "2026-02-01T00:00:00Z"}}).json()["percent"] == 100
    assert _post(client, wid, h, "/ramps", {
        "flag_key": "bad", "start_percent": 0, "end_percent": 100,
        "starts_at": "2026-02-01T00:00:00Z", "ends_at": "2026-01-01T00:00:00Z"}).status_code == 422


def test_gb248_scheduled_revisions(client, monkeypatch):
    """GB-248: scheduled revisions apply and resolve by effective time."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/revisions", {
        "flag_key": "checkout", "effective_at": "2026-06-01T00:00:00Z",
        "config": {"enabled": True, "value": "v2"}})
    assert created.status_code == 201, created.text
    before = _post(client, wid, h, "/revisions/resolve", {
        "attrs": {"flag_key": "checkout", "at": "2026-01-01T00:00:00Z"}}).json()
    assert before["revision"] is None
    pending = _post(client, wid, h, "/revisions/resolve", {
        "attrs": {"flag_key": "checkout", "at": "2026-09-01T00:00:00Z"}}).json()
    assert pending["revision"] is None
    applied = _post(client, wid, h, "/revisions/apply", {
        "flag_key": "checkout", "revision_id": created.json()["id"]}).json()
    assert applied["status"] == "applied"
    after = _post(client, wid, h, "/revisions/resolve", {
        "attrs": {"flag_key": "checkout", "at": "2026-09-01T00:00:00Z"}}).json()
    assert after["revision"]["config"]["value"] == "v2"


def test_gb249_feature_configs_isolation(client, monkeypatch):
    """GB-249: typed feature configurations persist and are tenant-scoped."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = _post(client, wid, h, "/configs", {
        "flag_key": "checkout", "environment": "production",
        "value_type": "json", "value": {"timeout": 30, "retries": 2}})
    assert created.status_code == 201, created.text
    rows = client.get(_base(wid) + "/configs", headers=h).json()
    assert len(rows) == 1 and rows[0]["value"]["timeout"] == 30
    assert _post(client, wid, h, "/configs", {
        "flag_key": "bad", "value_type": "xml", "value": {}}).status_code == 422
    owid, oh = _other(client, h)
    assert client.get(_base(owid) + "/configs", headers=oh).json() == []
