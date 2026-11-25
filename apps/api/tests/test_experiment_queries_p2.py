"""Named acceptance tests for the local experiment-data exploration cluster.

Every test drives the real FastAPI app against real persisted, workspace-scoped
rows. GB-028/027/034/035/037/024/101 are implemented as clean-room local views
over NOVARA's own experiment, assignment, exposure and result tables. No
warehouse SQL, external data source, GrowthBook source or hosted platform is
used, and nothing is sent or published externally.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/experiment-queries"
STATS = "/api/v1/workspaces/{wid}/experiment-stats"
FLAGS = "/api/v1/workspaces/{wid}/flags"
ANALYTICS = "/api/v1/workspaces/{wid}/analytics"


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _seed_stats(client, wid, h, key="checkout"):
    metric = client.post(STATS.format(wid=wid) + "/metrics", headers=h,
                         json={"key": "conversion", "name": "Conversion", "type": "proportion"})
    assert metric.status_code == 201, metric.text
    experiment = client.post(STATS.format(wid=wid) + "/experiments", headers=h, json={
        "key": key, "name": "Checkout", "variants": [
            {"key": "control", "traffic_share": 0.5},
            {"key": "variant", "traffic_share": 0.5},
        ],
    })
    assert experiment.status_code == 201, experiment.text
    experiment = experiment.json()
    for variant, sessions, conversions in (("control", 100, 10), ("variant", 100, 16)):
        observation = client.post(
            STATS.format(wid=wid) + f"/experiments/{experiment['id']}/observations",
            headers=h, json={"metric_id": metric.json()["id"], "variant": variant,
                             "sessions": sessions, "conversions": conversions},
        )
        assert observation.status_code == 201, observation.text
    return experiment


def _seed_analytics(client, wid, h, name="checkout"):
    experiment = client.post(ANALYTICS.format(wid=wid), headers=h,
                             json={"name": name, "metric_name": "conversion"})
    assert experiment.status_code == 201, experiment.text
    experiment = experiment.json()
    result = client.post(
        ANALYTICS.format(wid=wid) + f"/{experiment['id']}/results",
        headers=h, json={"variant": "control", "impressions": 100, "conversions": 10},
    )
    assert result.status_code == 200 or result.status_code == 201, result.text
    result = client.post(
        ANALYTICS.format(wid=wid) + f"/{experiment['id']}/results",
        headers=h, json={"variant": "variant", "impressions": 100, "conversions": 16},
    )
    assert result.status_code == 200 or result.status_code == 201, result.text
    return experiment


def _seed_exposures(client, wid, h, flag_key="query-flag"):
    """Create real flag assignments plus exposures keyed to the local 'checkout' reference."""
    flag = client.post(FLAGS.format(wid=wid), headers=h, json={
        "key": flag_key, "enabled": True, "rollout_percent": 100, "default_value": "on",
    })
    assert flag.status_code == 201, flag.text
    for user, variant in (("u1", "control"), ("u2", "variant")):
        evaluated = client.post(f"{FLAGS.format(wid=wid)}/{flag_key}/evaluate", headers=h,
                                json={"user_key": user})
        assert evaluated.status_code == 200, evaluated.text
        exposure = client.post(f"{FLAGS.format(wid=wid)}/{flag_key}/exposures", headers=h,
                               json={"user_key": user, "variant": variant,
                                     "experiment_key": "checkout"})
        assert exposure.status_code == 201, exposure.text
    return flag.json()


def _fact_table(client, wid, h, source="observations", fields=None):
    body = {"key": source + "-facts", "name": source.title(), "source": source,
            "fields": fields or ["variant", "sessions", "conversions"]}
    r = client.post(_base(wid) + "/fact-tables", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_gb028_fact_tables_describe_shared_local_row_sets(client):
    wid, h = _ctx(client)
    fact = _fact_table(client, wid, h)
    assert fact["source"] == "observations" and len(fact["fields"]) == 3
    assert client.post(_base(wid) + "/fact-tables", headers=h, json={
        "key": "other-facts", "name": "Other", "source": "warehouse",
        "fields": ["a"],
    }).status_code == 422
    assert client.post(_base(wid) + "/fact-tables", headers=h, json={
        "key": "other-facts", "name": "Other", "source": "observations",
        "fields": ["not_a_column"],
    }).status_code == 422
    assert client.post(_base(wid) + "/fact-tables", headers=h, json={
        "key": "observations-facts", "name": "dup", "source": "observations",
        "fields": ["variant"],
    }).status_code == 409
    listed = client.get(_base(wid) + "/fact-tables", headers=h).json()
    assert [f["key"] for f in listed] == ["observations-facts"]
    preview = client.get(f"{_base(wid)}/fact-tables/{fact['id']}/preview", headers=h).json()
    assert preview["source"] == "observations" and preview["rows"] == []
    assert "sessions" in preview["available_fields"]


def test_gb027_discovery_queries_filter_and_project_local_facts(client):
    wid, h = _ctx(client)
    _seed_stats(client, wid, h)
    fact = _fact_table(client, wid, h)
    query = client.post(_base(wid) + "/discovery-queries", headers=h, json={
        "key": "control-facts", "name": "Control facts", "fact_table_id": fact["id"],
        "fields": ["variant", "sessions", "conversions"],
        "filters": [{"field": "variant", "op": "eq", "value": "control"}],
        "limit": 5,
    })
    assert query.status_code == 201, query.text
    query = query.json()
    assert client.post(_base(wid) + "/discovery-queries", headers=h, json={
        "key": "bad-facts", "name": "Bad", "fact_table_id": fact["id"],
        "fields": ["secret_column"],
    }).status_code == 422
    assert client.post(_base(wid) + "/discovery-queries", headers=h, json={
        "key": "bad-filter", "name": "Bad", "fact_table_id": fact["id"],
        "fields": ["variant"],
        "filters": [{"field": "variant", "op": "eq", "value": "x"},
                    {"field": "nope", "op": "eq", "value": "x"}],
    }).status_code == 422
    assert client.post(_base(wid) + "/discovery-queries", headers=h, json={
        "key": "control-facts", "name": "dup", "fact_table_id": fact["id"],
        "fields": ["variant"],
    }).status_code == 409
    result = client.post(f"{_base(wid)}/discovery-queries/{query['id']}/run", headers=h).json()
    assert result["count"] == 1
    assert result["rows"] == [{"variant": "control", "sessions": 100, "conversions": 10}]
    listed = client.get(_base(wid) + "/discovery-queries", headers=h).json()
    assert [q["key"] for q in listed] == ["control-facts"]


def test_gb034_assignment_queries_identify_exposed_units(client):
    wid, h = _ctx(client)
    _seed_analytics(client, wid, h)
    _seed_exposures(client, wid, h)
    query = client.post(_base(wid) + "/assignment-queries", headers=h, json={
        "key": "exposed-units", "name": "Exposed units",
        "experiment_key": "checkout", "source": "exposures",
    })
    assert query.status_code == 201, query.text
    query = query.json()
    assert client.post(_base(wid) + "/assignment-queries", headers=h, json={
        "key": "bad-source", "name": "Bad", "experiment_key": "checkout",
        "source": "warehouse",
    }).status_code == 422
    assert client.post(_base(wid) + "/assignment-queries", headers=h, json={
        "key": "bad-ref", "name": "Bad", "experiment_key": "not valid!",
    }).status_code == 422
    assert client.post(_base(wid) + "/assignment-queries", headers=h, json={
        "key": "exposed-units", "name": "dup", "experiment_key": "checkout",
    }).status_code == 409
    result = client.post(f"{_base(wid)}/assignment-queries/{query['id']}/run", headers=h).json()
    assert result["count"] == 2
    assert {u["user_key"] for u in result["units"]} == {"u1", "u2"}
    assert all(u["source"] == "exposure" for u in result["units"])

    filtered = client.post(_base(wid) + "/assignment-queries", headers=h, json={
        "key": "control-units", "name": "Control units",
        "experiment_key": "checkout", "source": "exposures",
        "filters": [{"field": "variant", "op": "eq", "value": "control"}],
    }).json()
    result = client.post(f"{_base(wid)}/assignment-queries/{filtered['id']}/run", headers=h).json()
    assert result["count"] == 1 and result["units"][0]["user_key"] == "u1"


def test_gb035_identifier_types_and_joins_resolve_local_ids(client):
    wid, h = _ctx(client)
    user_type = client.post(_base(wid) + "/identifier-types", headers=h, json={
        "key": "user-id", "name": "User id", "attribute": "user_id",
        "pattern": r"[a-z0-9]+", "normalization": "strip_lower",
    })
    assert user_type.status_code == 201, user_type.text
    user_type = user_type.json()
    email_type = client.post(_base(wid) + "/identifier-types", headers=h, json={
        "key": "email", "name": "Email", "attribute": "email",
        "pattern": r"[^@]+@[^@]+\.[^@]+", "normalization": "lower",
    })
    assert email_type.status_code == 201, email_type.text
    email_type = email_type.json()
    assert client.post(_base(wid) + "/identifier-types", headers=h, json={
        "key": "user-id", "name": "dup", "attribute": "x",
    }).status_code == 409
    assert client.post(_base(wid) + "/identifier-types", headers=h, json={
        "key": "bad", "name": "Bad", "attribute": "x", "pattern": "[",
    }).status_code == 422
    normalized = client.post(f"{_base(wid)}/identifier-types/{user_type['id']}/normalize",
                             headers=h, json={"value": "  U1 "}).json()
    assert normalized["normalized"] == "u1" and normalized["valid"] is True
    invalid = client.post(f"{_base(wid)}/identifier-types/{email_type['id']}/normalize",
                          headers=h, json={"value": "not-an-email"}).json()
    assert invalid["valid"] is False

    join = client.post(_base(wid) + "/identifier-joins", headers=h, json={
        "key": "user-email", "name": "User to email",
        "left_type_id": user_type["id"], "right_type_id": email_type["id"],
        "mappings": [{"left": "u1", "right": "u1@example.com"},
                     {"left": "u2", "right": "u2@example.com"}],
    })
    assert join.status_code == 201, join.text
    join = join.json()
    assert client.post(_base(wid) + "/identifier-joins", headers=h, json={
        "key": "same", "name": "Same",
        "left_type_id": user_type["id"], "right_type_id": user_type["id"],
    }).status_code == 422
    forward = client.post(f"{_base(wid)}/identifier-joins/{join['id']}/resolve",
                          headers=h, json={"value": "u1"}).json()
    backward = client.post(f"{_base(wid)}/identifier-joins/{join['id']}/resolve",
                           headers=h, json={"value": "u2@example.com",
                                            "direction": "right_to_left"}).json()
    assert forward["matches"] == ["u1@example.com"]
    assert backward["matches"] == ["u2"]
    assert client.post(f"{_base(wid)}/identifier-joins/{join['id']}/resolve",
                       headers=h, json={"value": "u1", "direction": "sideways"}).status_code == 422
    listed = client.get(_base(wid) + "/identifier-joins", headers=h).json()
    assert listed[0]["mappings"] == 2


def test_gb037_funnel_analysis_measures_ordered_steps(client):
    wid, h = _ctx(client)
    _seed_stats(client, wid, h)
    _seed_analytics(client, wid, h)
    _seed_exposures(client, wid, h)
    funnel = client.post(_base(wid) + "/funnels", headers=h, json={
        "key": "checkout-funnel", "name": "Checkout funnel", "experiment_key": "checkout",
        "steps": ["assigned", "exposed", "converted"],
    })
    assert funnel.status_code == 201, funnel.text
    assert client.post(_base(wid) + "/funnels", headers=h, json={
        "key": "bad-funnel", "name": "Bad", "experiment_key": "checkout",
        "steps": ["converted", "assigned"],
    }).status_code == 422
    result = client.get(f"{_base(wid)}/funnels/{funnel.json()['id']}/result", headers=h).json()
    assert [s["stage"] for s in result["steps"]] == ["assigned", "exposed", "converted"]
    assert result["counts"]["assigned"] == 2
    assert result["counts"]["exposed"] == 2
    assert result["counts"]["converted"] == 26
    assert result["steps"][2]["step_rate"] == 13.0
    assert result["overall_conversion"] == 13.0


def test_gb024_custom_reports_summarize_local_experiment_data(client):
    wid, h = _ctx(client)
    _seed_stats(client, wid, h)
    _seed_analytics(client, wid, h)
    _seed_exposures(client, wid, h)
    funnel = client.post(_base(wid) + "/funnels", headers=h, json={
        "key": "report-funnel", "name": "Report funnel", "experiment_key": "checkout",
        "steps": ["assigned", "exposed", "converted"],
    }).json()
    summary = client.post(_base(wid) + "/reports", headers=h, json={
        "key": "experiment-summary", "name": "Experiment summary",
        "report_type": "experiment_summary", "config": {"experiment_key": "checkout"},
    })
    assert summary.status_code == 201, summary.text
    assert client.post(_base(wid) + "/reports", headers=h, json={
        "key": "bad-report", "name": "Bad", "report_type": "experiment_summary",
        "config": {},
    }).status_code == 422
    assert client.post(_base(wid) + "/reports", headers=h, json={
        "key": "experiment-summary", "name": "dup", "report_type": "experiment_summary",
        "config": {"experiment_key": "checkout"},
    }).status_code == 409
    result = client.post(f"{_base(wid)}/reports/{summary.json()['id']}/run", headers=h).json()
    assert result["report_type"] == "experiment_summary"
    assert result["total_sessions"] == 200 and result["total_conversions"] == 26
    assert {v["variant"] for v in result["variants"]} == {"control", "variant"}

    funnel_report = client.post(_base(wid) + "/reports", headers=h, json={
        "key": "funnel-report", "name": "Funnel report", "report_type": "funnel_summary",
        "config": {"funnel_id": funnel["id"]},
    })
    assert funnel_report.status_code == 201, funnel_report.text
    result = client.post(f"{_base(wid)}/reports/{funnel_report.json()['id']}/run", headers=h).json()
    assert result["report_type"] == "funnel_summary"
    assert result["counts"]["exposed"] == 2
    assert result["overall_conversion"] == 13.0
    listed = client.get(_base(wid) + "/reports", headers=h).json()
    assert {r["key"] for r in listed} == {"experiment-summary", "funnel-report"}


def test_gb101_carryover_guidance_warns_and_requires_ack(client):
    wid, h = _ctx(client)
    risky = client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "risky-restart", "experiment_key": "checkout",
        "previous_end": "2026-11-18", "restart": "2026-11-20", "washout_days": 7,
    })
    assert risky.status_code == 201, risky.text
    risky = risky.json()
    assert risky["gap_days"] == 2 and risky["warning"] is True
    assert "Re-randomise" in risky["guidance"]
    assert client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "risky-restart", "experiment_key": "checkout",
        "previous_end": "2026-11-18", "restart": "2026-11-20",
    }).status_code == 409
    assert client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "bad-dates", "experiment_key": "checkout",
        "previous_end": "20-11-2026", "restart": "2026-11-20",
    }).status_code == 422
    assert client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "backwards", "experiment_key": "checkout",
        "previous_end": "2026-11-22", "restart": "2026-11-20",
    }).status_code == 422
    acked = client.post(f"{_base(wid)}/carryover/{risky['id']}/acknowledge", headers=h).json()
    assert acked["acknowledged"] is True
    listed = client.get(_base(wid) + "/carryover", headers=h).json()
    assert listed[0]["warning"] is True and listed[0]["acknowledged"] is True

    safe = client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "safe-restart", "experiment_key": "checkout",
        "previous_end": "2026-11-01", "restart": "2026-11-20", "washout_days": 7,
    }).json()
    assert safe["warning"] is False and safe["gap_days"] == 19
    assert "low" in safe["guidance"]


def test_experiment_queries_workspace_isolation(client):
    wid, h = _ctx(client)
    fact = _fact_table(client, wid, h)
    user_type = client.post(_base(wid) + "/identifier-types", headers=h,
                            json={"key": "user-id", "name": "User", "attribute": "user_id"}).json()
    funnel = client.post(_base(wid) + "/funnels", headers=h, json={
        "key": "iso-funnel", "name": "Iso", "experiment_key": "checkout",
        "steps": ["assigned", "exposed"],
    }).json()
    report = client.post(_base(wid) + "/reports", headers=h, json={
        "key": "iso-report", "name": "Iso", "report_type": "funnel_summary",
        "config": {"funnel_id": funnel["id"]},
    }).json()
    carryover = client.post(_base(wid) + "/carryover", headers=h, json={
        "key": "iso-carryover", "experiment_key": "checkout",
        "previous_end": "2026-11-18", "restart": "2026-11-20",
    }).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    for path in ("/fact-tables", "/discovery-queries", "/assignment-queries",
                 "/identifier-types", "/identifier-joins", "/funnels", "/reports",
                 "/carryover"):
        result = client.get(_base(owid) + path, headers=oh)
        assert result.status_code == 200 and result.json() == [], (path, result.text)
    contract = client.get(_base(owid) + "/api-contract", headers=oh).json()
    assert contract["delivery"] == "local-only"
    assert client.get(f"{_base(owid)}/fact-tables/{fact['id']}/preview", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/identifier-types/{user_type['id']}/normalize",
                       headers=oh, json={"value": "x"}).status_code == 404
    assert client.get(f"{_base(owid)}/funnels/{funnel['id']}/result", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/reports/{report['id']}/run", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/carryover/{carryover['id']}/acknowledge",
                       headers=oh).status_code == 404
