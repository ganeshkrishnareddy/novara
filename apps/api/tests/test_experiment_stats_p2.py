"""Named acceptance tests for the GrowthBook experimentation-statistics cluster.

Every test drives the real FastAPI app against real persisted, workspace-scoped
rows. Statistics are computed locally by ``experiment_stats`` from stored
observations; no GrowthBook source, external service or statistics package is
used. Promoted rows: GB-020, GB-021, GB-022, GB-023, GB-029, GB-030, GB-031,
GB-032, GB-038 and GB-042.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/experiment-stats"


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _metric(client, wid, h, key="conversion", mtype="proportion"):
    r = client.post(_base(wid) + "/metrics", headers=h,
                    json={"key": key, "name": key.replace("-", " ").title(), "type": mtype})
    assert r.status_code == 201, r.text
    return r.json()


def _experiment(client, wid, h, key="checkout"):
    r = client.post(_base(wid) + "/experiments", headers=h, json={
        "key": key, "name": key.title(),
        "variants": [{"key": "control", "traffic_share": 0.5},
                     {"key": "variant", "traffic_share": 0.5}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _observe(client, wid, h, experiment, metric, variant, **values):
    body = {"metric_id": metric["id"], "variant": variant, **values}
    r = client.post(f"{_base(wid)}/experiments/{experiment['id']}/observations", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _proportion_pair(client, wid, h, c_conv=10, v_conv=30, sessions=100):
    metric = _metric(client, wid, h)
    experiment = _experiment(client, wid, h)
    _observe(client, wid, h, experiment, metric, "control", sessions=sessions, conversions=c_conv)
    _observe(client, wid, h, experiment, metric, "variant", sessions=sessions, conversions=v_conv)
    return experiment, metric


def test_api_contract_declares_local_engines_and_metric_types(client):
    wid, h = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert set(contract["engines"]) == {"frequentist", "bayesian"}
    assert set(contract["metric_types"]) == {"proportion", "mean", "ratio"}
    assert contract["delivery"] == "local-only"


def test_gb029_030_031_032_metric_definitions_are_typed_and_validated(client):
    wid, h = _ctx(client)
    for key, mtype in (("conversion", "proportion"), ("revenue", "mean"), ("ctr", "ratio")):
        metric = _metric(client, wid, h, key, mtype)
        assert metric["type"] == mtype
    assert any(m["key"] == "revenue" for m in
               client.get(_base(wid) + "/metrics", headers=h).json())
    assert client.post(_base(wid) + "/metrics", headers=h,
                       json={"key": "conversion", "name": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/metrics", headers=h,
                       json={"key": "bad", "name": "x", "type": "carrier-pigeon"}).status_code == 422


def test_experiment_variants_and_observations_are_validated(client):
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/experiments", headers=h, json={
        "key": "bad-split", "name": "Bad",
        "variants": [{"key": "control", "traffic_share": 0.9},
                     {"key": "variant", "traffic_share": 0.2}],
    }).status_code == 422
    assert client.post(_base(wid) + "/experiments", headers=h, json={
        "key": "one", "name": "One", "variants": [{"key": "control", "traffic_share": 1.0}],
    }).status_code == 422
    experiment = _experiment(client, wid, h)
    metric = _metric(client, wid, h)
    assert client.post(f"{_base(wid)}/experiments/{experiment['id']}/observations", headers=h,
                       json={"metric_id": metric["id"], "variant": "carrier-pigeon"}).status_code == 422
    assert client.post(f"{_base(wid)}/experiments/{experiment['id']}/observations", headers=h,
                       json={"metric_id": metric["id"], "variant": "control",
                             "sessions": 10, "conversions": 11}).status_code == 422
    first = _observe(client, wid, h, experiment, metric, "control", sessions=100, conversions=10)
    second = _observe(client, wid, h, experiment, metric, "control", sessions=200, conversions=25)
    assert second["id"] == first["id"] and second["sessions"] == 200  # upsert, not duplicate
    rows = client.get(f"{_base(wid)}/experiments/{experiment['id']}/observations", headers=h,
                      params={"metric_id": metric["id"]}).json()
    assert len(rows) == 1


def test_gb021_frequentist_engine_returns_p_value_and_confidence_interval(client):
    wid, h = _ctx(client)
    experiment, metric = _proportion_pair(client, wid, h)
    result = client.post(f"{_base(wid)}/experiments/{experiment['id']}/analyze", headers=h,
                         json={"metric_id": metric["id"], "engine": "frequentist"}).json()
    assert result["engine"] == "frequentist"
    assert result["z_statistic"] > 3.0
    assert result["p_value"] < 0.01
    assert result["confidence_interval_95"][0] > 0
    assert result["insufficient_data"] is False
    bad = client.post(f"{_base(wid)}/experiments/{experiment['id']}/analyze", headers=h,
                      json={"metric_id": metric["id"], "engine": "carrier-pigeon"})
    assert bad.status_code == 422


def test_gb020_bayesian_engine_returns_probability_and_expected_loss(client):
    wid, h = _ctx(client)
    experiment, metric = _proportion_pair(client, wid, h)
    result = client.post(f"{_base(wid)}/experiments/{experiment['id']}/analyze", headers=h,
                         json={"metric_id": metric["id"], "engine": "bayesian"}).json()
    assert result["engine"] == "bayesian"
    assert result["probability_variant_beats_control"] > 0.99
    assert 0 <= result["expected_loss"] < 0.01
    assert result["credible_interval"][0] < result["variant_mean"] < result["credible_interval"][1]


def test_gb031_mean_metric_analysis_uses_stored_variance(client):
    wid, h = _ctx(client)
    metric = _metric(client, wid, h, "revenue", "mean")
    experiment = _experiment(client, wid, h)
    _observe(client, wid, h, experiment, metric, "control", sessions=1000,
             value_sum=5000.0, value_sq_sum=26000.0)   # mean 5.0, variance 1.0
    _observe(client, wid, h, experiment, metric, "variant", sessions=1000,
             value_sum=5300.0, value_sq_sum=29090.0)   # mean 5.3, variance 1.0
    result = client.post(f"{_base(wid)}/experiments/{experiment['id']}/analyze", headers=h,
                         json={"metric_id": metric["id"], "engine": "frequentist"}).json()
    assert 0.29 < result["absolute_difference"] < 0.31
    assert result["p_value"] < 0.05


def test_gb032_ratio_metric_analysis_uses_delta_method(client):
    wid, h = _ctx(client)
    metric = _metric(client, wid, h, "ctr", "ratio")
    experiment = _experiment(client, wid, h)
    _observe(client, wid, h, experiment, metric, "control", sessions=100,
             numerator_sum=50.0, numerator_sq_sum=100.0,
             denominator_sum=100.0, denominator_sq_sum=200.0)
    _observe(client, wid, h, experiment, metric, "variant", sessions=100,
             numerator_sum=80.0, numerator_sq_sum=160.0,
             denominator_sum=100.0, denominator_sq_sum=200.0)
    result = client.post(f"{_base(wid)}/experiments/{experiment['id']}/analyze", headers=h,
                         json={"metric_id": metric["id"], "engine": "frequentist"}).json()
    assert result["metric_type"] == "ratio"
    assert 0.29 < result["absolute_difference"] < 0.31
    assert 0 <= result["p_value"] <= 1


def test_gb022_srm_detects_skewed_traffic_and_accepts_balanced(client):
    wid, h = _ctx(client)
    experiment, metric = _proportion_pair(client, wid, h, c_conv=10, v_conv=12)
    good = client.post(f"{_base(wid)}/experiments/{experiment['id']}/srm", headers=h).json()
    assert good["srm_detected"] is False and good["p_value"] > 0.9
    skewed = _experiment(client, wid, h, "skewed")
    _observe(client, wid, h, skewed, metric, "control", sessions=100, conversions=10)
    _observe(client, wid, h, skewed, metric, "variant", sessions=160, conversions=16)
    bad = client.post(f"{_base(wid)}/experiments/{skewed['id']}/srm", headers=h).json()
    assert bad["srm_detected"] is True and bad["p_value"] < 0.001
    assert bad["chi_square"] > 13
    assert abs(sum(bad["expected"].values()) - sum(bad["observed"].values())) < 1e-6


def test_gb023_health_reports_low_sample_missing_variant_and_healthy(client):
    wid, h = _ctx(client)
    metric = _metric(client, wid, h)
    healthy = _experiment(client, wid, h, "healthy")
    _observe(client, wid, h, healthy, metric, "control", sessions=500, conversions=50)
    _observe(client, wid, h, healthy, metric, "variant", sessions=500, conversions=60)
    result = client.post(f"{_base(wid)}/experiments/{healthy['id']}/health", headers=h).json()
    assert result["healthy"] is True
    assert result["diagnostics"][0]["code"] == "healthy"

    low = _experiment(client, wid, h, "low")
    _observe(client, wid, h, low, metric, "control", sessions=10, conversions=1)
    codes = [d["code"] for d in client.post(
        f"{_base(wid)}/experiments/{low['id']}/health", headers=h).json()["diagnostics"]]
    assert "low_sample" in codes and "no_exposure" in codes


def test_gb038_power_analysis_computes_sample_size_and_mde(client):
    wid, h = _ctx(client)
    result = client.post(_base(wid) + "/analysis/power", headers=h,
                         json={"baseline_rate": 0.1, "mde": 0.02}).json()
    assert 3000 < result["required_sample_size_per_variant"] < 4000
    assert round(result["z_alpha"], 2) == 1.96
    reverse = client.post(_base(wid) + "/analysis/power", headers=h,
                          json={"baseline_rate": 0.1, "sample_size": 1000}).json()
    assert 0.03 < reverse["detectable_mde"] < 0.05
    assert client.post(_base(wid) + "/analysis/power", headers=h,
                       json={"baseline_rate": 1.5, "mde": 0.02}).status_code == 422


def test_gb042_multiple_testing_corrections(client):
    wid, h = _ctx(client)
    result = client.post(_base(wid) + "/analysis/correct", headers=h,
                         json={"p_values": [0.01, 0.04, 0.03, 0.2]}).json()
    bonf = result["bonferroni"]
    bh = result["benjamini_hochberg"]
    assert [round(item["adjusted"], 4) for item in bonf] == [0.04, 0.16, 0.12, 0.8]
    assert round(bh[0]["adjusted"], 4) == 0.04
    assert round(bh[1]["adjusted"], 4) == 0.0533
    assert bonf[0]["significant"] is True and bonf[1]["significant"] is False
    assert client.post(_base(wid) + "/analysis/correct", headers=h,
                       json={"p_values": [1.4]}).status_code == 422


def test_experiment_stats_workspace_isolation(client):
    wid, h = _ctx(client)
    metric = _metric(client, wid, h)
    experiment = _experiment(client, wid, h)
    _observe(client, wid, h, experiment, metric, "control", sessions=100, conversions=10)
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    for path in ("/metrics", "/experiments"):
        assert client.get(_base(owid) + path, headers=oh).json() == []
    assert client.post(f"{_base(owid)}/experiments/{experiment['id']}/analyze", headers=oh,
                       json={"metric_id": metric["id"]}).status_code == 404
    assert client.post(f"{_base(owid)}/experiments/{experiment['id']}/srm", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/experiments/{experiment['id']}/observations", headers=oh,
                       json={"metric_id": metric["id"], "variant": "control"}).status_code == 404
