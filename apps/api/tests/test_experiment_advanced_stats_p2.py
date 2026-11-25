"""Named acceptance tests for clean-room advanced experimentation statistics.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. GB-187, GB-188, GB-189, GB-214, GB-215, GB-217, GB-222 and GB-237 are
proven end to end. No GrowthBook source, stats package, hosted platform,
warehouse, SDK or external statistics service is used; socket.socket.connect
is patched to raise in every test.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client, name="AdvStats", email="advstats-owner@example.com"):
    tokens = bootstrap(client, name, email)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return API.format(wid=wid) + "/advanced-experiments"


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("an advanced-statistics endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _other_workspace(client, headers):
    response = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other adv"})
    assert response.status_code == 200, response.text
    return response.json()["workspace_id"], auth(response.json()["access_token"])


def _save(client, wid, headers, kind, name, inputs, experiment_key=""):
    return client.post(_base(wid) + "/analyses", headers=headers, json={
        "kind": kind, "name": name, "experiment_key": experiment_key, "inputs": inputs,
    })


def test_gb187_cuped_variance_reduction(client, monkeypatch):
    """GB-187: CUPED adjusts the effect with a pre-period covariate."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    response = _save(client, wid, h, "cuped", "Checkout CUPED", {
        "control": [1, 2, 3, 4, 5, 6, 7, 8],
        "treatment": [2, 3, 5, 5, 7, 8, 9, 10],
        "control_pre": [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4],
        "treatment_pre": [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5],
    }, experiment_key="checkout")
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["method"] == "cuped"
    assert result["theta"] > 0
    assert result["raw_effect"] > 0
    assert result["adjusted_effect"] > 0
    assert result["adjusted_variance"] < result["raw_variance"]
    assert 0 < result["variance_reduction_ratio"] < 1
    analysis_id = response.json()["id"]
    assert client.get(_base(wid) + "/analyses", headers=h).json()[0]["id"] == analysis_id
    assert client.get(_base(wid) + "/analyses/" + analysis_id, headers=h).status_code == 200
    owid, oh = _other_workspace(client, h)
    assert client.get(_base(owid) + "/analyses/" + analysis_id, headers=oh).status_code == 404
    assert _save(client, wid, h, "cuped", "Mismatch", {
        "control": [1, 2], "treatment": [2, 3], "control_pre": [1], "treatment_pre": [1],
    }).status_code == 422


def test_gb188_post_stratification_weighted_effect(client, monkeypatch):
    """GB-188: stratum effects are combined by stratum size."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    units = []
    for value in (10, 12, 14, 16):
        units.append({"stratum": "new", "variant": "control", "value": value})
    for value in (14, 16, 18, 20):
        units.append({"stratum": "new", "variant": "treatment", "value": value})
    for value in (30, 32):
        units.append({"stratum": "returning", "variant": "control", "value": value})
    for value in (35, 37):
        units.append({"stratum": "returning", "variant": "treatment", "value": value})
    response = _save(client, wid, h, "post_stratification", "Signup strata", {"units": units})
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["method"] == "post_stratification"
    assert result["units"] == 12
    assert len(result["strata"]) == 2
    assert result["effect"] > 0
    assert 3 < result["effect"] < 6
    assert _save(client, wid, h, "post_stratification", "Bad strata", {
        "units": [{"stratum": "x", "variant": "control", "value": 1}],
    }).status_code == 422


def test_gb189_sequential_testing_boundaries(client, monkeypatch):
    """GB-189: mSPRT and O'Brien-Fleming boundaries gate early stopping."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    early = _save(client, wid, h, "sequential", "Early look", {
        "z": 3.0, "information": 100, "fraction": 0.1,
    }).json()["result"]
    final = _save(client, wid, h, "sequential", "Final look", {
        "z": 3.0, "information": 100, "fraction": 1.0,
    }).json()["result"]
    assert early["method"] == "sequential"
    assert early["obf_boundary"] > final["obf_boundary"]
    assert early["obf_stop"] is False
    assert final["obf_stop"] is True
    assert final["msprt_boundary"] > 0
    assert final["msprt_stop"] is True
    assert _save(client, wid, h, "sequential", "Bad look", {
        "z": 1.0, "information": 0,
    }).status_code == 422


def test_gb214_quantile_metric_bootstrap(client, monkeypatch):
    """GB-214: quantile estimate has a deterministic bootstrap interval."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    inputs = {"values": list(range(1, 101)), "q": 0.5, "bootstrap": 200, "seed": 7}
    first = _save(client, wid, h, "quantile", "Latency p50", inputs).json()["result"]
    second = _save(client, wid, h, "quantile", "Latency p50 repeat", inputs).json()["result"]
    assert first["method"] == "quantile"
    assert first["q"] == 0.5
    assert first["value"] == 50.5
    assert first["ci_low"] <= first["value"] <= first["ci_high"]
    assert first["ci_low"] == second["ci_low"] and first["ci_high"] == second["ci_high"]
    assert _save(client, wid, h, "quantile", "Bad q", {
        "values": [1, 2, 3], "q": 1.5,
    }).status_code == 422


def test_gb215_retention_metrics_curve(client, monkeypatch):
    """GB-215: a day-N retention curve is derived from cohort counts."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    response = _save(client, wid, h, "retention", "D7/D30 retention", {"cohorts": [
        {"day": 30, "size": 100, "retained": 25},
        {"day": 0, "size": 100, "retained": 100},
        {"day": 7, "size": 100, "retained": 40},
    ]})
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["method"] == "retention"
    assert [row["day"] for row in result["curve"]] == [0, 7, 30]
    assert result["day_0"] == 1.0
    assert result["last_day"] == 30
    assert result["last_retention"] == 0.25
    assert _save(client, wid, h, "retention", "Bad retention", {"cohorts": [
        {"day": 7, "size": 10, "retained": 11},
    ]}).status_code == 422


def test_gb217_compound_metrics_weighted_score(client, monkeypatch):
    """GB-217: a compound metric combines weighted components."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    result = _save(client, wid, h, "compound", "Activation score", {"components": [
        {"name": "signup", "value": 10, "weight": 3},
        {"name": "retention", "value": 20, "weight": 1},
    ]}).json()["result"]
    assert result["method"] == "compound"
    assert result["total_weight"] == 4
    assert abs(result["score"] - 12.5) < 1e-9
    assert len(result["components"]) == 2
    assert _save(client, wid, h, "compound", "Bad weight", {"components": [
        {"name": "a", "value": 1, "weight": 0},
        {"name": "b", "value": 2, "weight": 1},
    ]}).status_code == 422


def test_gb222_bandit_recommend_and_reward(client, monkeypatch):
    """GB-222: Thompson/UCB recommendation and Bayesian reward updates persist."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    base = _base(wid) + "/bandits/onboarding"
    for arm, alpha, beta in (("a", 2.0, 8.0), ("b", 8.0, 2.0)):
        created = client.post(base + "/arms", headers=h, json={
            "arm": arm, "alpha": alpha, "beta": beta, "pulls": 5,
        })
        assert created.status_code == 201, created.text
    state = client.get(base, headers=h).json()
    assert [row["arm"] for row in state["arms"]] == ["a", "b"]
    thompson = client.post(base + "/recommend", headers=h,
                           json={"policy": "thompson", "seed": 11}).json()
    ucb = client.post(base + "/recommend", headers=h,
                      json={"policy": "ucb", "seed": 11}).json()
    assert thompson["arm"] in ("a", "b")
    assert ucb["arm"] in ("a", "b")
    repeat = client.post(base + "/recommend", headers=h,
                         json={"policy": "thompson", "seed": 11}).json()
    assert repeat["arm"] == thompson["arm"]
    updated = client.post(base + "/reward", headers=h,
                          json={"arm": "b", "reward": 1.0})
    assert updated.status_code == 200, updated.text
    assert updated.json()["alpha"] == 9.0 and updated.json()["beta"] == 2.0
    assert updated.json()["pulls"] == 6
    owid, oh = _other_workspace(client, h)
    assert client.get(_base(owid) + "/bandits/onboarding", headers=oh).json()["arms"] == []
    assert client.post(base + "/reward", headers=h,
                       json={"arm": "missing", "reward": 0.5}).status_code == 404
    assert client.post(_base(wid) + "/holdouts", headers=h, json={
        "name": "Global holdout", "fraction": 0.1, "experiment_keys": ["checkout"],
    }).status_code == 201
    holdout = client.get(_base(wid) + "/holdouts", headers=h).json()[0]
    checked = client.post(_base(wid) + "/holdouts/" + holdout["id"] + "/check",
                          headers=h, json={"user_key": "user-42"})
    assert checked.status_code == 200, checked.text
    assert isinstance(checked.json()["assigned"], bool)


def test_gb237_metric_correlation(client, monkeypatch):
    """GB-237: Pearson correlation is computed locally and rejects constants."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    result = _save(client, wid, h, "correlation", "Revenue/Sessions", {
        "xs": [1, 2, 3, 4, 5], "ys": [2, 4, 6, 8, 10],
    }).json()["result"]
    assert result["method"] == "correlation"
    assert abs(result["r"] - 1.0) < 1e-9
    assert abs(result["r_squared"] - 1.0) < 1e-9
    assert result["n"] == 5
    assert _save(client, wid, h, "correlation", "Constant", {
        "xs": [1, 1, 1], "ys": [2, 3, 4],
    }).status_code == 422
