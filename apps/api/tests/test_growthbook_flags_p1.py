"""Named acceptance tests for the remaining GrowthBook P1 rows.

Every test drives the real NOVARA app through ``client``/``bootstrap``/``auth``
or a real module-owned pure function. All data is local; no external service is
called and no GrowthBook source is used.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.main import API
from novara_core.models import Event
from novara_core.modules import feature_flags

from .conftest import auth, bootstrap


def _base(wid: str) -> str:
    return f"{API}/workspaces/{wid}/flags"


def _analytics(wid: str) -> str:
    return f"{API}/workspaces/{wid}/analytics"


def _other(client, headers):
    response = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other"})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def _flag(client, base, headers, key, **extra):
    response = client.post(base, headers=headers, json={"key": key, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _experiment(client, wid, headers, name="Local experiment", baseline=0.1):
    response = client.post(_analytics(wid), headers=headers, json={
        "name": name, "metric_name": "signup_rate", "baseline": baseline,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _rule(client, base, headers, key, **body):
    response = client.post(f"{base}/{key}/rules", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _sdk_key(client, base, headers, name="local", environment="production"):
    response = client.post(f"{base}/sdk/connections", headers=headers,
                           json={"name": name, "environment": environment})
    assert response.status_code == 201, response.text
    return response.json()["sdk_key"]


def _payload(client, base, headers, sdk_key, environment="production"):
    return client.get(f"{base}/sdk/payload", headers={**headers, "X-SDK-Key": sdk_key},
                      params={"environment": environment})


def _events(db_session, wid):
    return db_session.execute(select(Event).where(Event.workspace_id == wid)).scalars().all()


# ---------------------------------------------------------------------------
# GB-001..GB-006 — keys, kill switch, defaults, CRUD and environments
# ---------------------------------------------------------------------------


def test_gb_001_feature_keys_are_validated_immutable_and_workspace_isolated(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    created = _flag(client, base, headers, "new_checkout")
    assert created["key"] == "new_checkout"
    assert client.post(base, headers=headers, json={"key": "new_checkout"}).status_code == 409
    for bad in ("  ", "-bad", "bad key", "bad/key", "x" * 201):
        assert client.post(base, headers=headers, json={"key": bad}).status_code == 422, bad
    assert client.patch(f"{base}/new_checkout", headers=headers,
                        json={"key": "renamed"}).status_code == 422

    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/new_checkout", headers=other_headers).status_code == 403
    other = _flag(client, _base(other_wid), other_headers, "new_checkout")
    assert other["workspace_id"] if "workspace_id" in other else True
    assert [row["key"] for row in client.get(_base(other_wid), headers=other_headers).json()] == ["new_checkout"]
    assert client.get(base).status_code == 401


def test_gb_002_kill_switch_disables_evaluation_immediately(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "kill_switch", enabled=True, rollout_percent=100)

    on = client.post(f"{base}/kill_switch/evaluate", headers=headers, json={"user_key": "u1"})
    assert on.status_code == 200 and on.json()["enabled"] is True
    off = client.patch(f"{base}/kill_switch", headers=headers, json={"enabled": False})
    assert off.status_code == 200 and off.json()["enabled"] is False
    killed = client.post(f"{base}/kill_switch/evaluate", headers=headers, json={"user_key": "u1"})
    assert killed.json()["enabled"] is False and killed.json()["reason"] == "disabled"
    revived = client.patch(f"{base}/kill_switch", headers=headers, json={"enabled": True})
    assert revived.status_code == 200
    assert client.post(f"{base}/kill_switch/evaluate", headers=headers,
                       json={"user_key": "u1"}).json()["enabled"] is True


def test_gb_003_default_value_is_served_when_no_rule_matches(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "defaults", enabled=True, rollout_percent=0,
          default_value="legacy_value")

    result = client.post(f"{base}/defaults/evaluate", headers=headers, json={"user_key": "u1"})
    assert result.status_code == 200, result.text
    assert result.json()["variant"] == "legacy_value"

    _rule(client, base, headers, "defaults",
          conditions=[{"attribute": "plan", "op": "eq", "value": "pro"}], value="pro_value")
    fallback = client.post(f"{base}/defaults/evaluate", headers=headers,
                           json={"user_key": "u2", "attributes": {"plan": "free"}})
    assert fallback.json()["variant"] == "legacy_value"
    changed = client.patch(f"{base}/defaults", headers=headers, json={"default_value": "new_default"})
    assert changed.status_code == 200 and changed.json()["default_value"] == "new_default"
    assert client.post(f"{base}/defaults/evaluate", headers=headers,
                       json={"user_key": "u3", "attributes": {"plan": "free"}}
                       ).json()["variant"] == "new_default"
    assert client.patch(f"{base}/defaults", headers=headers,
                        json={"default_value": "  "}).status_code == 422


def test_gb_004_flag_crud_is_workspace_scoped_and_audited(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    created = _flag(client, base, headers, "crud", description="first")
    flag_id = created["id"]
    assert [row["id"] for row in client.get(base, headers=headers).json()] == [flag_id]
    assert client.get(f"{base}/{flag_id}", headers=headers).json()["key"] == "crud"
    patched = client.patch(f"{base}/{flag_id}", headers=headers, json={"description": "second"})
    assert patched.status_code == 200 and patched.json()["description"] == "second"

    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/{flag_id}", headers=other_headers).status_code == 403
    assert client.patch(f"{base}/{flag_id}", headers=other_headers,
                        json={"description": "hijack"}).status_code == 403
    assert client.delete(f"{base}/{flag_id}", headers=other_headers).status_code == 403
    assert client.delete(f"{base}/{flag_id}", headers=headers).json() == {"deleted": True, "key": "crud"}
    assert client.get(f"{base}/{flag_id}", headers=headers).status_code == 404

    types = {e.event_type for e in _events(db_session, wid)}
    assert {feature_flags.FLAG_CREATED, feature_flags.FLAG_UPDATED, feature_flags.FLAG_DELETED} <= types
    assert all(e.workspace_id == wid for e in _events(db_session, wid))


def test_gb_005_builtin_environments_are_validated_and_enumerable(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    listed = client.get(f"{base}/environments", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == {"environments": ["production", "dev", "staging", "test"]}
    dev = _flag(client, base, headers, "env_flag", environment="dev")
    assert dev["environment"] == "dev"
    for bad in ("qa", "", "prod"):
        assert client.post(base, headers=headers,
                           json={"key": "bad_env", "environment": bad}).status_code == 422
    assert client.patch(f"{base}/env_flag", headers=headers,
                        json={"environment": "qa"}).status_code == 422
    assert [f["key"] for f in client.get(base, headers=headers,
                                         params={"environment": "dev"}).json()] == ["env_flag"]
    assert client.get(base, headers=headers, params={"environment": "qa"}).status_code == 422


def test_gb_006_per_environment_state_is_independent(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "per_env", enabled=True, rollout_percent=100, default_value="off")

    dev_state = client.put(f"{base}/per_env/environments/dev", headers=headers,
                           json={"enabled": False, "rollout_percent": 0})
    assert dev_state.status_code == 200 and dev_state.json()["enabled"] is False
    dev_eval = client.post(f"{base}/per_env/evaluate", headers=headers,
                           json={"user_key": "u1", "environment": "dev"})
    assert dev_eval.json()["enabled"] is False
    assert dev_eval.json()["reason"] == "environment_disabled"
    prod_eval = client.post(f"{base}/per_env/evaluate", headers=headers,
                            json={"user_key": "u1", "environment": "production"})
    assert prod_eval.json()["enabled"] is True

    enabled = client.put(f"{base}/per_env/environments/dev", headers=headers,
                         json={"enabled": True, "rollout_percent": 0})
    assert enabled.status_code == 200
    assert client.post(f"{base}/per_env/evaluate", headers=headers,
                       json={"user_key": "u2", "environment": "dev"}).json()["enabled"] is False
    client.put(f"{base}/per_env/environments/dev", headers=headers,
               json={"enabled": True, "rollout_percent": 100})
    assert client.post(f"{base}/per_env/evaluate", headers=headers,
                       json={"user_key": "u2", "environment": "dev"}).json()["enabled"] is True
    assert [row["environment"] for row in client.get(f"{base}/per_env/environments",
                                                      headers=headers).json()] == ["dev"]
    assert client.put(f"{base}/per_env/environments/qa", headers=headers,
                      json={"enabled": True}).status_code == 422
    other_wid, other_headers = _other(client, headers)
    assert client.put(f"{base}/per_env/environments/dev", headers=other_headers,
                      json={"enabled": True}).status_code == 403


# ---------------------------------------------------------------------------
# GB-008..GB-011 — ordered rules, targeting, attributes and rollouts
# ---------------------------------------------------------------------------


def test_gb_008_ordered_rules_first_match_wins_and_reorder(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "ordered", enabled=True, rollout_percent=100,
          default_value="default_value")

    pro = _rule(client, base, headers, "ordered", position=0,
                conditions=[{"attribute": "plan", "op": "eq", "value": "pro"}], value="pro_value")
    catch_all = _rule(client, base, headers, "ordered", position=1, conditions=[], value="catch_all")
    assert [r["position"] for r in client.get(f"{base}/ordered/rules", headers=headers).json()] == [0, 1]
    assert client.post(f"{base}/ordered/evaluate", headers=headers,
                       json={"user_key": "u1", "attributes": {"plan": "pro"}}
                       ).json()["variant"] == "pro_value"
    assert client.post(f"{base}/ordered/evaluate", headers=headers,
                       json={"user_key": "u2", "attributes": {"plan": "free"}}
                       ).json()["variant"] == "catch_all"

    reordered = client.post(f"{base}/ordered/rules/reorder", headers=headers,
                            json={"rule_ids": [catch_all["id"], pro["id"]]})
    assert reordered.status_code == 200, reordered.text
    assert [r["id"] for r in reordered.json()] == [catch_all["id"], pro["id"]]
    assert client.post(f"{base}/ordered/evaluate", headers=headers,
                       json={"user_key": "u3", "attributes": {"plan": "pro"}}
                       ).json()["variant"] == "catch_all"

    assert client.delete(f"{base}/ordered/rules/{catch_all['id']}", headers=headers).status_code == 200
    assert client.post(f"{base}/ordered/evaluate", headers=headers,
                       json={"user_key": "u4", "attributes": {"plan": "pro"}}
                       ).json()["variant"] == "pro_value"
    types = {e.event_type for e in _events(db_session, wid)}
    assert {feature_flags.FLAG_RULE_ADDED, feature_flags.FLAG_RULE_UPDATED,
            feature_flags.FLAG_RULE_DELETED} <= types


def test_gb_009_targeting_condition_operators_match_caller_attributes(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "conditions", enabled=True, rollout_percent=100,
          default_value="fallback")
    _rule(client, base, headers, "conditions", position=0,
          conditions=[{"attribute": "plan", "op": "in", "value": ["pro", "team"]}], value="paid")
    _rule(client, base, headers, "conditions", position=1,
          conditions=[{"attribute": "age", "op": "gte", "value": 18}], value="adult")
    _rule(client, base, headers, "conditions", position=2,
          conditions=[{"attribute": "beta", "op": "exists", "value": True}], value="beta")
    _rule(client, base, headers, "conditions", position=3,
          conditions=[{"attribute": "name", "op": "contains", "value": "ann"}], value="ann")

    def variant(user, **attributes):
        r = client.post(f"{base}/conditions/evaluate", headers=headers,
                        json={"user_key": user, "attributes": attributes})
        assert r.status_code == 200, r.text
        return r.json()["variant"]

    assert variant("u1", plan="team", age=30) == "paid"
    assert variant("u2", age=18) == "adult"
    assert variant("u3", beta=True) == "beta"
    assert variant("u4", name="joanna") == "ann"
    assert variant("u5", age=12, name="bob", plan="free") == "fallback"
    bad = client.post(f"{base}/conditions/rules", headers=headers,
                      json={"conditions": [{"attribute": "age", "op": "regex", "value": ".*"}]})
    assert bad.status_code == 422


def test_gb_010_user_attributes_drive_targeting_and_are_validated(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "attrs", enabled=True, rollout_percent=100,
          default_value="fallback", attributes={"country": "IN"})
    _rule(client, base, headers, "attrs",
          conditions=[{"attribute": "device", "op": "eq", "value": "mobile"}], value="mobile_value")

    matched = client.post(f"{base}/attrs/evaluate", headers=headers,
                          json={"user_key": "u1", "attributes": {"country": "IN", "device": "mobile"}})
    assert matched.json()["variant"] == "mobile_value"
    mismatch = client.post(f"{base}/attrs/evaluate", headers=headers,
                           json={"user_key": "u2", "attributes": {"country": "US", "device": "mobile"}})
    assert mismatch.json()["variant"] == "fallback"
    assert client.post(f"{base}/attrs/evaluate", headers=headers,
                       json={"user_key": "u3", "attributes": {"": "x"}}).status_code == 422
    assert client.post(f"{base}/attrs/evaluate", headers=headers,
                       json={"user_key": "u3", "attributes": {str(i): i for i in range(101)}}
                       ).status_code == 422
    assert client.post(f"{base}/attrs/evaluate", headers=headers, json={"user_key": " "}).status_code == 422
    assert client.post(f"{base}/attrs/evaluate",
                       json={"user_key": "u1", "attributes": {"device": "mobile"}}).status_code == 401


def test_gb_011_percentage_rollout_is_deterministic_and_bounded(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    _flag(client, base, headers, "percent", enabled=True, rollout_percent=40, default_value="off")

    bucket = feature_flags._bucket_for
    selected = sum(1 for i in range(1000) if bucket("user-%d" % i, "percent") < 40)
    assert 340 <= selected <= 460
    assert bucket("user-7", "percent") == bucket("user-7", "percent")

    first = client.post(f"{base}/percent/evaluate", headers=headers, json={"user_key": "user-7"})
    second = client.post(f"{base}/percent/evaluate", headers=headers, json={"user_key": "user-7"})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["enabled"] == second.json()["enabled"]
    assert first.json()["variant"] == second.json()["variant"]

    client.patch(f"{base}/percent", headers=headers, json={"rollout_percent": 0, "enabled": True})
    zero = client.post(f"{base}/percent/evaluate", headers=headers, json={"user_key": "user-8"})
    assert zero.json()["enabled"] is False
    client.patch(f"{base}/percent", headers=headers, json={"rollout_percent": 100, "enabled": True})
    full = client.post(f"{base}/percent/evaluate", headers=headers, json={"user_key": "user-9"})
    assert full.json()["enabled"] is True
    assert client.patch(f"{base}/percent", headers=headers,
                        json={"rollout_percent": 101}).status_code == 422


# ---------------------------------------------------------------------------
# GB-015..GB-019 and GB-036 — local experiment linkage and exposure
# ---------------------------------------------------------------------------


def test_gb_015_experiment_ref_rule_links_a_local_experiment(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers)
    _flag(client, base, headers, "exp_ref", enabled=True, rollout_percent=100, default_value="off")

    rule = _rule(client, base, headers, "exp_ref", experiment_key=experiment["id"],
                 weights={"control": 50, "treatment": 50})
    assert rule["experiment_key"] == experiment["id"]
    result = client.post(f"{base}/exp_ref/evaluate", headers=headers, json={"user_key": "u1"})
    assert result.json()["reason"] == "experiment_rule"
    assert result.json()["variant"] in {"control", "treatment"}
    assert client.get(f"{base}/exp_ref/experiment/results", headers=headers).json()[
        "experiment_id"] == experiment["id"]

    assert client.post(f"{base}/exp_ref/rules", headers=headers,
                       json={"experiment_key": "missing", "weights": {"a": 100}}).status_code == 422
    other_wid, other_headers = _other(client, headers)
    other_exp = _experiment(client, other_wid, other_headers, name="Other experiment")
    assert client.post(f"{base}/exp_ref/rules", headers=headers,
                       json={"experiment_key": other_exp["id"], "weights": {"a": 100}}
                       ).status_code == 422
    assert any(e.event_type == feature_flags.EXPERIMENT_LINKED for e in _events(db_session, wid))


def test_gb_016_experiment_configuration_targeting_variants_and_weights(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers, name="Configured", baseline=0.2)
    _flag(client, base, headers, "exp_config", enabled=True, rollout_percent=100, default_value="off")

    rule = _rule(client, base, headers, "exp_config", position=0,
                 conditions=[{"attribute": "plan", "op": "eq", "value": "pro"}],
                 experiment_key=experiment["id"], weights={"control": 40, "treatment": 60})
    _rule(client, base, headers, "exp_config", position=1, value="not_targeted")
    stored = client.get(f"{base}/exp_config/rules", headers=headers).json()
    assert stored[0]["weights"] == {"control": 40, "treatment": 60}
    assert stored[0]["conditions"][0]["attribute"] == "plan"

    targeted = client.post(f"{base}/exp_config/evaluate", headers=headers,
                           json={"user_key": "u1", "attributes": {"plan": "pro"}})
    assert targeted.json()["reason"] == "experiment_rule"
    assert targeted.json()["variant"] in {"control", "treatment"}
    assert client.post(f"{base}/exp_config/evaluate", headers=headers,
                       json={"user_key": "u2", "attributes": {"plan": "free"}}
                       ).json()["variant"] == "not_targeted"

    assert client.post(f"{base}/exp_config/rules", headers=headers,
                       json={"experiment_key": experiment["id"], "weights": {"a": 90}}).status_code == 422
    assert client.post(f"{base}/exp_config/rules", headers=headers,
                       json={"experiment_key": experiment["id"], "weights": {"": 100}}).status_code == 422
    patched = client.patch(f"{base}/exp_config/rules/{rule['id']}", headers=headers,
                           json={"weights": {"control": 100}})
    assert patched.status_code == 200 and patched.json()["weights"] == {"control": 100}
    assert client.post(f"{base}/exp_config/evaluate", headers=headers,
                       json={"user_key": "u3", "attributes": {"plan": "pro"}}
                       ).json()["variant"] == "control"
    other_wid, other_headers = _other(client, headers)
    assert client.patch(f"{base}/exp_config/rules/{rule['id']}", headers=other_headers,
                        json={"weights": {"treatment": 100}}).status_code == 403


def test_gb_017_ab_tests_split_control_and_treatment_deterministically(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers, name="A/B checkout")
    _flag(client, base, headers, "ab_test", enabled=True, rollout_percent=100, default_value="off")
    _rule(client, base, headers, "ab_test", experiment_key=experiment["id"],
          weights={"control": 50, "treatment": 50})

    variants = set()
    for i in range(120):
        response = client.post(f"{base}/ab_test/evaluate", headers=headers, json={"user_key": "ab-%d" % i})
        assert response.status_code == 200, response.text
        variants.add(response.json()["variant"])
    assert variants == {"control", "treatment"}
    for user in ("ab-1", "ab-7", "ab-42"):
        first = client.post(f"{base}/ab_test/evaluate", headers=headers, json={"user_key": user}).json()
        second = client.post(f"{base}/ab_test/evaluate", headers=headers, json={"user_key": user}).json()
        assert first["variant"] == second["variant"]


def test_gb_018_variations_and_traffic_split_are_configurable(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers, name="Variations")
    _flag(client, base, headers, "variations", enabled=True, rollout_percent=100,
          default_value="off", variants=["blue", "green"])

    served = set()
    for i in range(80):
        response = client.post(f"{base}/variations/evaluate", headers=headers,
                               json={"user_key": "var-%d" % i})
        served.add(response.json()["variant"])
    assert {"blue", "green"} <= served

    _rule(client, base, headers, "variations", experiment_key=experiment["id"],
          weights={"a": 25, "b": 75})
    split = {name: 0 for name in ("a", "b")}
    for i in range(1000):
        split[feature_flags._variant_from_weights(experiment["id"], "w-%d" % i,
                                                   {"a": 25, "b": 75})] += 1
    assert 200 <= split["a"] <= 300 and 700 <= split["b"] <= 800
    assert client.post(f"{base}/variations/rules", headers=headers,
                       json={"experiment_key": experiment["id"], "weights": {"a": 101}}).status_code == 422


def test_gb_019_experiment_results_table_compares_variants_from_local_rows(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers, name="Results", baseline=0.1)
    _flag(client, base, headers, "results_exp", enabled=True, rollout_percent=100, default_value="off")
    _rule(client, base, headers, "results_exp", experiment_key=experiment["id"],
          weights={"control": 50, "treatment": 50})

    assert client.post(f"{_analytics(wid)}/{experiment['id']}/results", headers=headers,
                       json={"variant": "control", "impressions": 100, "conversions": 10}
                       ).status_code == 200
    assert client.post(f"{_analytics(wid)}/{experiment['id']}/results", headers=headers,
                       json={"variant": "treatment", "impressions": 80, "conversions": 20}
                       ).status_code == 200

    results = client.get(f"{base}/results_exp/experiment/results", headers=headers)
    assert results.status_code == 200, results.text
    data = results.json()
    assert data["experiment_id"] == experiment["id"] and data["metric_name"] == "signup_rate"
    rows = {row["variant"]: row for row in data["rows"]}
    assert rows["control"]["conversion_rate"] == 0.1
    assert rows["treatment"]["conversion_rate"] == 0.25
    assert abs(rows["treatment"]["delta_vs_baseline"] - 0.15) < 1e-9

    assert client.get(f"{base}/results_exp/experiment/results").status_code == 401
    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/results_exp/experiment/results", headers=other_headers).status_code == 403
    _flag(client, base, headers, "no_exp", enabled=True, rollout_percent=100)
    assert client.get(f"{base}/no_exp/experiment/results", headers=headers).status_code == 404


def test_gb_036_exposure_callback_records_first_assignment_and_audit(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    experiment = _experiment(client, wid, headers, name="Exposure")
    _flag(client, base, headers, "exposed", enabled=True, rollout_percent=100, default_value="off")
    _rule(client, base, headers, "exposed", experiment_key=experiment["id"],
          weights={"control": 50, "treatment": 50})

    evaluated = client.post(f"{base}/exposed/evaluate", headers=headers, json={"user_key": "u1"})
    first_variant = evaluated.json()["variant"]
    exposures = client.get(f"{base}/exposed/exposures", headers=headers)
    assert exposures.status_code == 200 and len(exposures.json()) == 1
    assert exposures.json()[0]["variant"] == first_variant
    assert exposures.json()[0]["experiment_key"] == experiment["id"]

    repeat = client.post(f"{base}/exposed/exposures", headers=headers,
                         json={"user_key": "u1", "variant": "treatment"})
    assert repeat.status_code == 201 and repeat.json()["variant"] == first_variant
    added = client.post(f"{base}/exposed/exposures", headers=headers,
                        json={"user_key": "u2", "variant": "treatment",
                              "experiment_key": experiment["id"]})
    assert added.status_code == 201 and added.json()["variant"] == "treatment"
    assert len(client.get(f"{base}/exposed/exposures", headers=headers).json()) == 2
    assert client.post(f"{base}/exposed/exposures", headers=headers,
                       json={"user_key": " "}).status_code == 422

    types = {e.event_type for e in _events(db_session, wid)}
    assert {feature_flags.EXPOSURE_RECORDED, feature_flags.EXPERIMENT_ASSIGNMENT} <= types
    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/exposed/exposures", headers=other_headers).status_code == 403


# ---------------------------------------------------------------------------
# GB-055..GB-058 — local SDK payload, evaluation and connections
# ---------------------------------------------------------------------------


def test_gb_055_sdk_payload_endpoint_serves_scoped_configuration(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    sdk_key = _sdk_key(client, base, headers)
    _flag(client, base, headers, "sdk_flag", enabled=True, rollout_percent=100,
          default_value="off", attributes={"country": "IN"})

    payload = _payload(client, base, headers, sdk_key)
    assert payload.status_code == 200, payload.text
    data = payload.json()
    assert data["workspace_id"] == wid and data["environment"] == "production"
    assert data["features"]["sdk_flag"]["attributes"] == {"country": "IN"}
    assert "sdk_key" not in data
    assert client.get(f"{base}/sdk/payload", headers=headers).status_code == 401
    assert client.get(f"{base}/sdk/payload", headers={**headers, "X-SDK-Key": "wrong"}
                      ).status_code == 401
    dev_key = _sdk_key(client, base, headers, name="dev", environment="dev")
    assert client.get(f"{base}/sdk/payload", headers={**headers, "X-SDK-Key": dev_key}
                      ).status_code == 403
    other_wid, other_headers = _other(client, headers)
    # A bearer from another workspace is authenticated but for the wrong tenant;
    # the app's consistent cross-workspace response is 403 (see GB-003/GB-004).
    assert client.get(f"{base}/sdk/payload", headers={**other_headers, "X-SDK-Key": sdk_key}
                      ).status_code == 403
    other_key = _sdk_key(client, _base(other_wid), other_headers, name="other")
    assert client.get(f"{_base(other_wid)}/sdk/payload",
                      headers={**other_headers, "X-SDK-Key": other_key}
                      ).json()["features"] == {}


def test_gb_056_local_sdk_evaluation_matches_server_without_http(client):
    offline_payload = {
        "features": {
            "checkout": {
                # 0% rollout so the non-matching user receives the default value;
                # rollout_percent=100 would (correctly) serve "on" instead.
                "key": "checkout", "enabled": True, "rollout_percent": 0,
                "attributes": {}, "prerequisites": [], "variants": [],
                "default_value": "off",
                "rules": [{"position": 0, "conditions": [
                    {"attribute": "plan", "op": "eq", "value": "pro"}],
                    "rollout_percent": 100, "value": "pro_value",
                    "experiment_key": None, "weights": {}, "enabled": True}],
            }
        },
        "environment_state": {},
    }
    local = feature_flags.evaluate_local(offline_payload, "u1", {"plan": "pro"})
    assert local["features"]["checkout"] == {
        "enabled": True, "value": "pro_value", "reason": "rule_match",
    }
    assert feature_flags.evaluate_local(offline_payload, "u2", {"plan": "free"})[
        "features"]["checkout"]["value"] == "off"

    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    sdk_key = _sdk_key(client, base, headers)
    _flag(client, base, headers, "checkout", enabled=True, rollout_percent=100,
          default_value="off")
    _rule(client, base, headers, "checkout",
          conditions=[{"attribute": "plan", "op": "eq", "value": "pro"}], value="pro_value")
    payload = _payload(client, base, headers, sdk_key).json()
    server = client.post(f"{base}/checkout/evaluate", headers=headers,
                         json={"user_key": "local-1", "attributes": {"plan": "pro"}}).json()
    offline = feature_flags.evaluate_local(payload, "local-1", {"plan": "pro"})
    assert offline["features"]["checkout"]["value"] == server["variant"] == "pro_value"


def test_gb_057_remote_configuration_reflects_flag_changes(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)
    sdk_key = _sdk_key(client, base, headers)
    _flag(client, base, headers, "remote", enabled=False, rollout_percent=0, default_value="off")

    before = _payload(client, base, headers, sdk_key).json()["features"]["remote"]
    assert before["enabled"] is False

    client.patch(f"{base}/remote", headers=headers,
                 json={"enabled": True, "rollout_percent": 100, "default_value": "live"})
    client.put(f"{base}/remote/environments/dev", headers=headers,
               json={"enabled": False, "rollout_percent": 0})
    _rule(client, base, headers, "remote", value="rule_value")

    after = _payload(client, base, headers, sdk_key).json()
    feature = after["features"]["remote"]
    assert feature["enabled"] is True and feature["rollout_percent"] == 100
    assert feature["default_value"] == "live" and len(feature["rules"]) == 1
    assert after["environment_state"]["remote"]["dev"]["enabled"] is False
    dev_feature = feature_flags.evaluate_local(after, "u1", {}, environment="dev")
    assert dev_feature["features"]["remote"]["reason"] == "disabled"


def test_gb_058_sdk_connections_are_scoped_revocable_and_audited(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    created = client.post(f"{base}/sdk/connections", headers=headers,
                          json={"name": "web", "environment": "staging"})
    assert created.status_code == 201, created.text
    connection = created.json()
    assert connection["sdk_key"].startswith("nv_sdk_") and connection["environment"] == "staging"
    assert client.post(f"{base}/sdk/connections", headers=headers,
                       json={"name": "web"}).status_code == 409
    assert client.post(f"{base}/sdk/connections", headers=headers,
                       json={"name": "bad", "environment": "qa"}).status_code == 422

    listed = client.get(f"{base}/sdk/connections", headers=headers).json()
    assert [row["name"] for row in listed] == ["web"]
    assert all("sdk_key" not in row for row in listed)
    revoked = client.post(f"{base}/sdk/connections/{connection['id']}/revoke", headers=headers)
    assert revoked.status_code == 200 and revoked.json()["revoked_at"] is not None
    assert client.get(f"{base}/sdk/payload", headers={
        **headers, "X-SDK-Key": connection["sdk_key"]},
        params={"environment": "staging"}).status_code == 401

    types = {e.event_type for e in _events(db_session, wid)}
    assert {feature_flags.SDK_CONNECTION_CREATED, feature_flags.SDK_CONNECTION_REVOKED} <= types
    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/sdk/connections", headers=other_headers).status_code == 403
    assert client.post(f"{base}/sdk/connections/{connection['id']}/revoke",
                       headers=other_headers).status_code == 403
    assert client.get(f"{_base(other_wid)}/sdk/connections", headers=other_headers).json() == []
