"""Named acceptance tests for the experimentation-operations P2 cluster.

Every test drives the real FastAPI app against real persisted, workspace-scoped
rows. The module builds on NOVARA's existing feature-flag tables; no GrowthBook
source, hosted platform, warehouse or external service is used. Promoted rows:
GB-007, GB-012, GB-013, GB-014, GB-025, GB-026, GB-039, GB-041, GB-048, GB-049.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/experiment-ops"
FLAGS = "/api/v1/workspaces/{wid}/flags"


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _project(client, wid, h, key="web-app"):
    r = client.post(_base(wid) + "/projects", headers=h,
                    json={"key": key, "name": key.replace("-", " ").title()})
    assert r.status_code == 201, r.text
    return r.json()


def _flag(client, wid, h, key="new-checkout", **extra):
    body = {"key": key, "enabled": True, "rollout_percent": 0, "default_value": "off"}
    body.update(extra)
    r = client.post(FLAGS.format(wid=wid), headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_gb007_projects_namespace_flags_experiments_and_settings(client):
    wid, h = _ctx(client)
    first = _project(client, wid, h, "web-app")
    second = _project(client, wid, h, "mobile-app")
    assert first["archived"] is False
    keys = [p["key"] for p in client.get(_base(wid) + "/projects", headers=h).json()]
    assert set(keys) == {"web-app", "mobile-app"}
    assert client.post(_base(wid) + "/projects", headers=h,
                       json={"key": "web-app", "name": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/projects", headers=h,
                       json={"key": "Bad Key", "name": "bad"}).status_code == 422
    archived = client.post(f"{_base(wid)}/projects/{first['id']}/archive", headers=h).json()
    assert archived["archived"] is True
    assert [p["archived"] for p in client.get(_base(wid) + "/projects", headers=h).json()
            if p["id"] == first["id"]] == [True]


def test_gb012_saved_groups_evaluate_local_targeting_lists(client):
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    group = client.post(f"{_base(wid)}/projects/{project['id']}/saved-groups", headers=h, json={
        "key": "pro-users", "name": "Pro users", "group_type": "attribute",
        "conditions": [{"attribute": "plan", "op": "eq", "value": "pro"},
                       {"attribute": "score", "op": "gte", "value": 7}],
    })
    assert group.status_code == 201, group.text
    group = group.json()
    assert client.post(f"{_base(wid)}/projects/{project['id']}/saved-groups", headers=h, json={
        "key": "pro-users", "name": "dup"}).status_code == 409
    assert client.post(f"{_base(wid)}/projects/{project['id']}/saved-groups", headers=h, json={
        "key": "bad", "name": "x",
        "conditions": [{"attribute": "plan", "op": "carrier-pigeon"}]}).status_code == 422
    listed = client.get(f"{_base(wid)}/projects/{project['id']}/saved-groups", headers=h).json()
    assert [g["key"] for g in listed] == ["pro-users"]
    hit = client.post(f"{_base(wid)}/saved-groups/{group['id']}/evaluate", headers=h,
                      json={"user_key": "alice", "attributes": {"plan": "pro", "score": 9}}).json()
    miss = client.post(f"{_base(wid)}/saved-groups/{group['id']}/evaluate", headers=h,
                       json={"user_key": "bob", "attributes": {"plan": "free", "score": 9}}).json()
    assert hit["matched"] is True and miss["matched"] is False
    assert hit["user_key"] == "alice" and len(hit["conditions"]) == 2


def test_gb013_flag_archive_and_history_keeps_full_change_record(client):
    wid, h = _ctx(client)
    flag = _flag(client, wid, h)
    for n in (1, 2):
        revision = client.post(f"{_base(wid)}/flags/{flag['id']}/revisions", headers=h,
                               json={"definition": {"enabled": True, "rollout_percent": n * 25}})
        assert revision.status_code == 201, revision.text
        assert client.post(f"{_base(wid)}/revisions/{revision.json()['id']}/activate",
                           headers=h).status_code == 200
    archived = client.post(f"{_base(wid)}/flags/{flag['id']}/archive", headers=h,
                           json={"reason": "superseded"})
    assert archived.status_code == 200, archived.text
    assert archived.json()["reason"] == "superseded"
    history = client.get(f"{_base(wid)}/flags/{flag['id']}/history", headers=h).json()
    assert history["archive"]["archived"] is True
    assert history["archive"]["reason"] == "superseded"
    assert [r["version"] for r in history["revisions"]] == [1, 2]
    assert all(r["status"] == "published" for r in history["revisions"])
    restored = client.post(f"{_base(wid)}/flags/{flag['id']}/restore", headers=h).json()
    assert restored["archived"] is False
    assert client.get(f"{_base(wid)}/flags/{flag['id']}/history", headers=h).json()[
        "archive"]["restored_at"]
    assert client.post(f"{_base(wid)}/flags/{flag['id']}/restore", headers=h).status_code == 422


def test_gb014_draft_revisions_do_not_affect_evaluation_until_published(client):
    wid, h = _ctx(client)
    flag = _flag(client, wid, h, "draft-checkout", enabled=False, rollout_percent=0)
    draft = client.post(f"{_base(wid)}/flags/{flag['id']}/revisions", headers=h, json={
        "definition": {"enabled": True, "rollout_percent": 75, "description": "launched"},
    })
    assert draft.status_code == 201, draft.text
    revision = draft.json()
    assert revision["version"] == 1 and revision["status"] == "draft"
    unchanged = client.get(FLAGS.format(wid=wid), headers=h).json()
    live = [f for f in unchanged if f["id"] == flag["id"]][0]
    assert live["enabled"] is False and live["rollout_percent"] == 0
    assert client.post(f"{_base(wid)}/flags/{flag['id']}/revisions", headers=h,
                       json={"definition": {"enabled": True}}).status_code == 409
    assert client.post(f"{_base(wid)}/flags/{flag['id']}/revisions", headers=h, json={
        "definition": {"rollout_percent": 140},
    }).status_code == 422
    published = client.post(f"{_base(wid)}/revisions/{revision['id']}/activate", headers=h).json()
    assert published["status"] == "published"
    assert published["flag"]["enabled"] is True
    assert published["flag"]["rollout_percent"] == 75
    assert client.post(f"{_base(wid)}/revisions/{revision['id']}/activate",
                       headers=h).status_code == 422


def test_gb025_dimensions_breakdown_validates_declared_values(client):
    wid, h = _ctx(client)
    dimension = client.post(_base(wid) + "/dimensions", headers=h, json={
        "key": "browser", "name": "Browser", "attribute": "browser",
        "values": ["chrome", "firefox"],
    })
    assert dimension.status_code == 201, dimension.text
    dimension = dimension.json()
    assert client.post(_base(wid) + "/dimensions", headers=h,
                       json={"key": "browser", "name": "dup", "attribute": "browser"}).status_code == 409
    assert client.post(_base(wid) + "/dimensions", headers=h,
                       json={"key": "BAD", "name": "x"}).status_code == 422
    assert [d["key"] for d in client.get(_base(wid) + "/dimensions", headers=h).json()] == ["browser"]
    good = client.post(f"{_base(wid)}/dimensions/{dimension['id']}/breakdown", headers=h,
                       json={"dimension_value": "chrome", "sessions": 120}).json()
    assert good["attribute"] == "browser" and good["sessions"] == 120
    assert client.post(f"{_base(wid)}/dimensions/{dimension['id']}/breakdown", headers=h,
                       json={"dimension_value": "carrier-pigeon", "sessions": 1}).status_code == 422
    assert client.post(f"{_base(wid)}/dimensions/{dimension['id']}/breakdown", headers=h,
                       json={"dimension_value": "chrome", "sessions": -1}).status_code == 422


def test_gb026_segments_are_reusable_attribute_slices(client):
    wid, h = _ctx(client)
    segment = client.post(_base(wid) + "/segments", headers=h, json={
        "key": "power-users", "name": "Power users",
        "rules": [{"attribute": "plan", "op": "eq", "value": "pro"},
                  {"attribute": "sessions", "op": "gt", "value": 10}],
    })
    assert segment.status_code == 201, segment.text
    segment = segment.json()
    assert client.post(_base(wid) + "/segments", headers=h,
                       json={"key": "power-users", "name": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/segments", headers=h, json={
        "key": "bad", "name": "x",
        "rules": [{"attribute": "plan", "op": "carrier-pigeon"}],
    }).status_code == 422
    assert [s["key"] for s in client.get(_base(wid) + "/segments", headers=h).json()] == ["power-users"]
    yes = client.post(f"{_base(wid)}/segments/{segment['id']}/evaluate", headers=h,
                      json={"user_key": "alice", "attributes": {"plan": "pro", "sessions": 42}}).json()
    no = client.post(f"{_base(wid)}/segments/{segment['id']}/evaluate", headers=h,
                     json={"user_key": "bob", "attributes": {"plan": "pro", "sessions": 3}}).json()
    assert yes["matched"] is True and no["matched"] is False


def test_gb039_aa_tests_validate_assignment_and_metric_plumbing(client):
    wid, h = _ctx(client)
    project = _project(client, wid, h, "qa")
    test = client.post(_base(wid) + "/aa-tests", headers=h, json={
        "project_id": project["id"], "key": "aa-checkout", "name": "A/A checkout",
    })
    assert test.status_code == 201, test.text
    test = test.json()
    assert client.post(_base(wid) + "/aa-tests", headers=h, json={
        "project_id": project["id"], "key": "aa-checkout", "name": "dup"}).status_code == 409
    assert client.post(f"{_base(wid)}/aa-tests/{test['id']}/observe", headers=h, json={
        "variant": "a", "sessions": 1000, "conversions": 100,
    }).status_code == 201
    assert client.post(f"{_base(wid)}/aa-tests/{test['id']}/observe", headers=h, json={
        "variant": "b", "sessions": 1000, "conversions": 101,
    }).status_code == 201
    assert client.post(f"{_base(wid)}/aa-tests/{test['id']}/observe", headers=h, json={
        "variant": "a", "sessions": 10, "conversions": 11,
    }).status_code == 422
    result = client.get(f"{_base(wid)}/aa-tests/{test['id']}/result", headers=h).json()
    assert result["passed"] is True and result["rate_spread"] < 0.01
    assert len(result["observations"]) == 2
    skewed = client.post(_base(wid) + "/aa-tests", headers=h, json={
        "project_id": project["id"], "key": "aa-skewed", "name": "Skewed",
    }).json()
    for variant, conv in (("a", 100), ("b", 300)):
        client.post(f"{_base(wid)}/aa-tests/{skewed['id']}/observe", headers=h,
                    json={"variant": variant, "sessions": 1000, "conversions": conv})
    bad = client.get(f"{_base(wid)}/aa-tests/{skewed['id']}/result", headers=h).json()
    assert bad["passed"] is False and bad["rate_spread"] > 0.1


def test_gb041_timeseries_gives_cumulative_impact_by_day(client):
    wid, h = _ctx(client)
    for day, sessions, conversions in (("2026-11-21", 100, 10),
                                       ("2026-11-22", 200, 30),
                                       ("2026-11-23", 300, 60)):
        r = client.post(_base(wid) + "/timeseries", headers=h, json={
            "experiment_key": "checkout", "metric_key": "conversion", "day": day,
            "sessions": sessions, "conversions": conversions, "value_sum": sessions / 10,
        })
        assert r.status_code == 201, r.text
    assert client.post(_base(wid) + "/timeseries", headers=h, json={
        "experiment_key": "checkout", "metric_key": "conversion", "day": "23-11-2026",
        "sessions": 1,
    }).status_code == 422
    listed = client.get(_base(wid) + "/timeseries", headers=h,
                        params={"experiment_key": "checkout"}).json()
    assert listed["count"] == 3
    summary = client.get(_base(wid) + "/timeseries/summary", headers=h,
                         params={"experiment_key": "checkout"}).json()
    assert [p["cumulative_sessions"] for p in summary["series"]] == [100, 300, 600]
    assert [p["cumulative_conversions"] for p in summary["series"]] == [10, 40, 100]
    assert summary["total_sessions"] == 600 and summary["total_conversions"] == 100
    # Upsert the same day instead of duplicating it.
    again = client.post(_base(wid) + "/timeseries", headers=h, json={
        "experiment_key": "checkout", "metric_key": "conversion", "day": "2026-11-23",
        "sessions": 400, "conversions": 80,
    })
    assert again.status_code == 201
    assert client.get(_base(wid) + "/timeseries", headers=h,
                      params={"experiment_key": "checkout"}).json()["count"] == 3


def test_gb048_stale_flags_detection(client):
    wid, h = _ctx(client)
    stale = _flag(client, wid, h, "stale-flag", enabled=False, rollout_percent=100)
    active = _flag(client, wid, h, "active-flag", enabled=True, rollout_percent=50)
    result = client.get(_base(wid) + "/stale-flags", headers=h).json()
    by_key = {item["key"]: item["reasons"] for item in result["flags"]}
    assert "disabled" in by_key["stale-flag"]
    assert "fully_rolled_out" in by_key["stale-flag"]
    assert "never_exposed" in by_key["stale-flag"]
    assert "active-flag" in by_key  # never exposed yet
    evaluated = client.post(f"{FLAGS.format(wid=wid)}/active-flag/evaluate", headers=h,
                            json={"user_key": "alice", "attributes": {}})
    assert evaluated.status_code == 200, evaluated.text
    result = client.get(_base(wid) + "/stale-flags", headers=h).json()
    by_key = {item["key"]: item["reasons"] for item in result["flags"]}
    assert "active-flag" not in by_key  # a delivered flag is no longer stale
    # Archived flags are also surfaced.
    client.post(f"{_base(wid)}/flags/{active['id']}/archive", headers=h, json={"reason": "done"})
    result = client.get(_base(wid) + "/stale-flags", headers=h).json()
    by_key = {item["key"]: item["reasons"] for item in result["flags"]}
    assert "archived" in by_key["active-flag"]


def test_gb049_diagnostics_explain_why_a_user_received_a_value(client):
    wid, h = _ctx(client)
    flag = _flag(client, wid, h, "plan-upgrade", enabled=True, rollout_percent=0,
                 default_value="off", variants=["on"])
    rule = client.post(f"{FLAGS.format(wid=wid)}/plan-upgrade/rules", headers=h, json={
        "position": 1,
        "conditions": [{"attribute": "plan", "op": "eq", "value": "pro"}],
        "rollout_percent": 100, "value": "upgrade-banner",
    })
    assert rule.status_code == 201, rule.text
    project = _project(client, wid, h, "diag")
    group = client.post(f"{_base(wid)}/projects/{project['id']}/saved-groups", headers=h, json={
        "key": "pro-list", "name": "Pro list",
        "conditions": [{"attribute": "plan", "op": "eq", "value": "pro"}],
    })
    assert group.status_code == 201, group.text
    hit = client.post(f"{_base(wid)}/flags/{flag['id']}/diagnose", headers=h, json={
        "user_key": "alice", "attributes": {"plan": "pro"},
    })
    assert hit.status_code == 200, hit.text
    result = hit.json()
    assert result["enabled"] is True
    assert result["variant"] == "upgrade-banner"
    assert result["reason"] == "rule_match"
    steps = {step["step"]: step for step in result["steps"]}
    assert set(steps) == {"flag_state", "environment", "prerequisites", "rules", "saved_groups"}
    assert steps["rules"]["evaluated"][0]["conditions_match"] is True
    assert steps["saved_groups"]["matching"] == ["pro-list"]
    miss = client.post(f"{_base(wid)}/flags/{flag['id']}/diagnose", headers=h, json={
        "user_key": "bob", "attributes": {"plan": "free"},
    }).json()
    assert miss["enabled"] is False and miss["reason"] in ("rollout", "attribute_mismatch")
    assert miss["steps"][3]["evaluated"][0]["conditions_match"] is False


def test_experiment_ops_workspace_isolation(client):
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    flag = _flag(client, wid, h)
    segment = client.post(_base(wid) + "/segments", headers=h,
                          json={"key": "all", "name": "All"}).json()
    client.post(_base(wid) + "/timeseries", headers=h, json={
        "experiment_key": "checkout", "metric_key": "conversion", "day": "2026-11-23",
        "sessions": 10,
    })
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    for path in ("/projects", "/dimensions", "/segments", "/aa-tests", "/stale-flags"):
        result = client.get(_base(owid) + path, headers=oh)
        assert result.status_code == 200, result.text
        payload = result.json()
        assert (payload == [] if isinstance(payload, list) else payload["count"] == 0)
    assert client.get(_base(owid) + "/timeseries", headers=oh,
                      params={"experiment_key": "checkout"}).json()["count"] == 0
    assert client.get(f"{_base(owid)}/flags/{flag['id']}/history", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/flags/{flag['id']}/archive", headers=oh,
                       json={}).status_code == 404
    assert client.post(f"{_base(owid)}/segments/{segment['id']}/evaluate", headers=oh,
                       json={}).status_code == 404
    assert client.get(f"{_base(owid)}/projects/{project['id']}/saved-groups",
                      headers=oh).status_code == 404
