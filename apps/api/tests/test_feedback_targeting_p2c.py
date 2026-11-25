"""Named acceptance tests for the targeting/trigger/controls P2 cluster.

Every behaviour is computed from workspace-scoped local state, persisted and
audited. No survey is injected into a host page and no external SDK is called.
"""

from __future__ import annotations

from .conftest import auth, bootstrap


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return f"/api/v1/workspaces/{wid}/feedback/targeting"


def _ext(wid):
    return f"/api/v1/workspaces/{wid}/feedback"


def _survey(client, wid, headers, name="Targeted survey"):
    r = client.post(f"/api/v1/workspaces/{wid}/surveys", headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _action(client, wid, headers, name="purchase"):
    r = client.post(f"{_base(wid)}/action-classes", headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _trigger(client, wid, headers, sid, aid, **overrides):
    body = {"survey_id": sid, "action_class_id": aid, "name": "On purchase"}
    body.update(overrides)
    r = client.post(f"{_base(wid)}/triggers", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_fb056_user_identification_and_attribute_merge(client):
    wid, h = _ctx(client)
    first = client.post(f"{_base(wid)}/users", headers=h,
                        json={"user_id": "u-1", "attributes": {"plan": "free", "locale": "en"}})
    assert first.status_code == 201
    assert first.json()["attributes"] == {"plan": "free", "locale": "en"}
    second = client.post(f"{_base(wid)}/users", headers=h,
                         json={"user_id": "u-1", "attributes": {"plan": "gold"}})
    assert second.status_code == 201
    assert second.json()["attributes"] == {"plan": "gold", "locale": "en"}
    assert client.get(f"{_base(wid)}/users/u-1", headers=h).json()["attributes"]["plan"] == "gold"
    assert client.post(f"{_base(wid)}/users", headers=h,
                       json={"user_id": "  "}).status_code == 422


def test_fb058_action_class_creation_and_dedup(client):
    wid, h = _ctx(client)
    aid = _action(client, wid, h, "checkout")
    assert aid
    assert client.post(f"{_base(wid)}/action-classes", headers=h,
                       json={"name": "checkout"}).status_code == 409
    names = [a["name"] for a in client.get(f"{_base(wid)}/action-classes", headers=h).json()]
    assert names == ["checkout"]


def test_fb059_trigger_creation_and_lifecycle(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid)
    listed = client.get(f"{_base(wid)}/triggers", headers=h).json()
    assert listed[0]["id"] == tid and listed[0]["enabled"] is True
    patched = client.patch(f"{_base(wid)}/triggers/{tid}", headers=h,
                           json={"enabled": False, "percentage": 25})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False and patched.json()["percentage"] == 25
    assert client.patch(f"{_base(wid)}/triggers/{tid}", headers=h,
                        json={"percentage": 101}).status_code == 422
    # Validate cross-references are enforced.
    assert client.post(f"{_base(wid)}/triggers", headers=h, json={
        "survey_id": sid, "action_class_id": "missing", "name": "bad",
    }).status_code == 404


def test_fb057_fb060_attribute_based_show_conditions(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid, show_conditions={
        "plan": "gold", "visits": {"op": "gte", "value": 3},
        "country": {"op": "in", "value": ["IN", "US"]},
    })
    client.post(f"{_base(wid)}/users", headers=h,
                json={"user_id": "u-2", "attributes": {"plan": "gold", "visits": 5, "country": "IN"}})
    ev = client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                     json={"user_id": "u-2", "action": "purchase"})
    assert ev.status_code == 200
    assert ev.json()["shown"] is True and ev.json()["reason"] == "shown"
    # Per-call context overrides stored attributes; a mismatch blocks the survey.
    ev2 = client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                      json={"user_id": "u-2", "action": "purchase",
                            "attributes": {"plan": "free"}})
    assert ev2.json()["shown"] is False
    assert ev2.json()["reason"] == "show_condition_mismatch"


def test_fb061_display_logic_requires_attributes(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid,
                   display_logic={"require_attributes": ["email"]})
    blocked = client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                          json={"user_id": "u-3", "action": "purchase"})
    assert blocked.json()["shown"] is False
    assert blocked.json()["reason"] == "display_logic_unmet"
    allowed = client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                          json={"user_id": "u-3", "action": "purchase",
                                "attributes": {"email": "u@example.com"}})
    assert allowed.json()["shown"] is True


def test_fb064_percentage_rollout_is_stable(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid, percentage=50)
    outcomes = [
        client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                    json={"user_id": "u-4", "action": "purchase"}).json()["shown"]
        for _ in range(4)
    ]
    assert len(set(outcomes)) == 1  # deterministic bucket for the same user
    zero = _trigger(client, wid, h, sid, aid, percentage=0, name="Zero percent")
    assert client.post(f"{_base(wid)}/triggers/{zero}/evaluate", headers=h,
                       json={"user_id": "u-4", "action": "purchase"}).json()["reason"] == "percentage_excluded"


def test_fb062_recontact_options(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    once = _trigger(client, wid, h, sid, aid, recontact={"mode": "once"}, name="Once")
    req = {"user_id": "u-5", "action": "purchase"}
    assert client.post(f"{_base(wid)}/triggers/{once}/evaluate", headers=h,
                       json=req).json()["shown"] is True
    assert client.post(f"{_base(wid)}/triggers/{once}/evaluate", headers=h,
                       json=req).json()["reason"] == "recontact_once"
    limited = _trigger(client, wid, h, sid, aid,
                       recontact={"mode": "limited", "max_times": 2}, name="Limited")
    results = [client.post(f"{_base(wid)}/triggers/{limited}/evaluate", headers=h,
                           json=req).json() for _ in range(3)]
    assert [r["shown"] for r in results] == [True, True, False]
    assert results[2]["reason"] == "recontact_limit"


def test_fb063_cooldown_period(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid, cooldown_seconds=3600)
    req = {"user_id": "u-6", "action": "purchase"}
    assert client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                       json=req).json()["shown"] is True
    second = client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h, json=req).json()
    assert second["shown"] is False and second["reason"] == "cooldown_active"
    decisions = client.get(f"{_base(wid)}/triggers/{tid}/decisions", headers=h).json()
    assert [d["reason"] for d in decisions] == ["shown", "cooldown_active"]


def test_fb055_inapp_targeting_without_code_changes(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid)
    # Wrong action and disabled triggers are rejected without any injected code.
    assert client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                       json={"user_id": "u-7", "action": "signup"}).json()["reason"] == "action_mismatch"
    client.patch(f"{_base(wid)}/triggers/{tid}", headers=h, json={"enabled": False})
    assert client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                       json={"user_id": "u-7", "action": "purchase"}).json()["reason"] == "trigger_disabled"
    client.patch(f"{_base(wid)}/triggers/{tid}", headers=h, json={"enabled": True})
    assert client.post(f"{_base(wid)}/triggers/{tid}/evaluate", headers=h,
                       json={"user_id": "u-7", "action": "purchase"}).json()["shown"] is True
    # A successful decision also creates a real display-tracking record.
    displays = client.get(f"{_ext(wid)}/surveys/{sid}/displays", headers=h).json()
    assert any(d["subject"] == "u-7" for d in displays)


def test_fb081_limit_submissions(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    r = client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h, json={"max_responses": 2})
    assert r.status_code == 201
    for _ in range(2):
        assert client.post(f"{_ext(wid)}/surveys/{sid}/answers", headers=h,
                           json={"value": 5}).status_code == 201
    ev = client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h, json={})
    assert ev.json()["eligible"] is False
    assert ev.json()["reason"] == "response_limit_reached"
    assert ev.json()["response_count"] == 2


def test_fb082_schedule_a_survey(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    future = "2099-01-01T00:00:00+00:00"
    past = "2000-01-01T00:00:00+00:00"
    assert client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h,
                       json={"schedule_start": future, "schedule_end": "2099-12-31T00:00:00+00:00"}).status_code == 201
    assert client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h,
                       json={}).json()["reason"] == "before_schedule"
    assert client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h,
                       json={"schedule_start": past, "schedule_end": "2001-01-01T00:00:00+00:00"}).status_code == 201
    assert client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h,
                       json={}).json()["reason"] == "after_schedule"
    assert client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h,
                       json={"schedule_start": "2099-01-01T00:00:00+00:00",
                             "schedule_end": "2000-01-01T00:00:00+00:00"}).status_code == 422


def test_fb083_segment_targeting(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h,
                json={"segment": {"country": "IN", "plan": {"op": "in", "value": ["gold", "pro"]}}})
    blocked = client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h,
                          json={"attributes": {"country": "US", "plan": "gold"}})
    assert blocked.json()["eligible"] is False
    assert blocked.json()["reason"] == "segment_mismatch"
    allowed = client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h,
                          json={"attributes": {"country": "IN", "plan": "pro"}})
    assert allowed.json()["eligible"] is True


def test_fb084_quota_management(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    client.post(f"{_base(wid)}/surveys/{sid}/controls", headers=h,
                json={"quotas": {"plan": {"value": "gold", "limit": 2}}})
    for _ in range(2):
        assert client.post(f"{_ext(wid)}/surveys/{sid}/answers", headers=h,
                           json={"value": 5, "embedded": {"plan": "gold"}}).status_code == 201
    ev = client.post(f"{_base(wid)}/surveys/{sid}/controls/evaluate", headers=h, json={})
    assert ev.json()["eligible"] is False
    assert ev.json()["reason"] == "quota_full:plan"


def test_p2c_workspace_isolation(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    aid = _action(client, wid, h)
    tid = _trigger(client, wid, h, sid, aid)
    client.post(f"{_base(wid)}/users", headers=h,
                json={"user_id": "iso-user", "attributes": {"plan": "gold"}})

    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    assert client.get(f"{_base(owid)}/users/iso-user", headers=oh).status_code == 404
    assert client.get(f"{_base(owid)}/action-classes", headers=oh).json() == []
    assert client.post(f"{_base(owid)}/triggers/{tid}/evaluate", headers=oh,
                       json={"user_id": "iso-user", "action": "purchase"}).status_code == 404
    assert client.post(f"{_base(owid)}/surveys/{sid}/controls/evaluate", headers=oh,
                       json={}).status_code == 404
