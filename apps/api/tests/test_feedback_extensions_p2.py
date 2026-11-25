"""Named acceptance tests for the Formbricks P2 survey-extension cluster.

Every closed row has a test that exercises real local behaviour against the
FastAPI app. No survey is distributed and no external service is contacted.
"""

from __future__ import annotations

from novara_core.modules import feedback_extensions as fe

from .conftest import auth, bootstrap


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _survey(client, wid, headers, name="Survey"):
    r = client.post(f"/api/v1/workspaces/{wid}/surveys",
                    headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _base(wid):
    return f"/api/v1/workspaces/{wid}/feedback"


def test_fb008_display_options_validated(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    for option in fe.DISPLAY_OPTIONS:
        r = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                        json={"display_option": option})
        assert r.status_code == 200 and r.json()["display_option"] == option
    bad = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                      json={"display_option": "displayForever"})
    assert bad.status_code == 422


def test_fb009_visibility_modes(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    r = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                    json={"visibility": "restricted", "allowed_roles": ["admin", "manager"]})
    assert r.status_code == 200
    assert r.json()["visibility"] == "restricted"
    assert r.json()["allowed_roles"]["roles"] == ["admin", "manager"]
    assert client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                       json={"visibility": "private"}).status_code == 422


def test_fb011_012_013_templates_and_presets(client):
    wid, h = _ctx(client)
    templates = client.get(f"{_base(wid)}/templates", headers=h)
    assert templates.status_code == 200
    keys = {t["key"] for t in templates.json()}
    assert {"nps", "csat", "ces", "best_practice"} <= keys
    for key, code in (("nps", "nps_score"), ("csat", "csat_score"), ("ces", "ces_score")):
        r = client.post(f"{_base(wid)}/surveys/from-template", headers=h,
                        json={"name": f"{key} survey", "template": key})
        assert r.status_code == 201, r.text
        codes = [q["code"] for q in r.json()["questions"]]
        assert code in codes
    assert client.post(f"{_base(wid)}/surveys/from-template", headers=h,
                       json={"name": "x", "template": "missing"}).status_code == 422


def test_fb014_ces_and_question_types(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    for qtype in ("ces", "consent", "contact_info", "date", "free_text",
                  "image", "video", "address"):
        r = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                        json={"type": qtype, "code": f"q_{qtype}", "label": qtype})
        assert r.status_code == 201 and r.json()["type"] == qtype, r.text
    bad = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                      json={"type": "telepathy", "code": "q_bad", "label": "bad"})
    assert bad.status_code == 422


def test_fb021_question_codes_unique(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    first = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                        json={"type": "free_text", "code": "Q1", "label": "One"})
    assert first.status_code == 201
    dup = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                      json={"type": "free_text", "code": "Q1", "label": "Two"})
    assert dup.status_code == 409
    assert client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                       json={"type": "free_text", "code": "  ", "label": "x"}).status_code == 422


def test_fb022_023_hidden_fields_and_embedded_data(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    cfg = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h, json={
        "hidden_fields": [{"code": "source", "value": "website"}],
    })
    assert cfg.status_code == 200 and cfg.json()["hidden_fields"][0]["code"] == "source"
    ans = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                      json={"value": 5, "embedded": {"source": "website", "camp": "c1"}})
    assert ans.status_code == 201 and ans.json()["embedded"]["camp"] == "c1"


def test_fb016_017_018_logic_and_branching(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    r = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h, json={
        "type": "single_choice", "code": "Q1", "label": "Continue?",
        "logic": {"show_if": {"code": "Q0", "equals": "yes"}, "jump_to": "__end__"},
    })
    assert r.status_code == 201
    assert r.json()["logic"]["jump_to"] == "__end__"
    bad = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h, json={
        "type": "free_text", "code": "Q2", "label": "x", "logic": {"steal_secrets": True},
    })
    assert bad.status_code == 422


def test_fb019_set_value_and_fb028_variables(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    cfg = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                      json={"variables": {"score_band": "expression"}})
    assert cfg.status_code == 200 and cfg.json()["variables"]["score_band"] == "expression"
    q = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h, json={
        "type": "rating", "code": "Q1", "label": "Rate",
        "logic": {"set_value": {"var": "score_band", "expression": "value >= 8"}},
    })
    assert q.status_code == 201


def test_fb026_027_028_recall_and_variables(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h, json={
        "hidden_fields": [{"code": "locale", "value": "en"}],
        "variables": {"v": 1},
    })
    # Answers may be anonymous; recall still exposes config variables and hidden fields.
    # FB-026: set embedded data for a subject and recall it.
    assert client.post(f"{_base(wid)}/surveys/{sid}/embedded/set", headers=h,
                       json={"subject": "visitor-1", "data": {"plan": "gold"}}).status_code == 200
    recall = client.get(f"{_base(wid)}/surveys/{sid}/recall?subject=visitor-1", headers=h)
    assert recall.status_code == 200
    assert recall.json()["embedded"]["plan"] == "gold"
    assert recall.json()["hidden_fields"][0]["code"] == "locale"
    assert recall.json()["variables"] == {"v": 1}
    # FB-026: clearing removes it from recall.
    assert client.post(f"{_base(wid)}/surveys/{sid}/embedded/clear", headers=h,
                       json={"subject": "visitor-1"}).status_code == 200
    assert client.get(f"{_base(wid)}/surveys/{sid}/recall?subject=visitor-1",
                      headers=h).json()["embedded"] == {}


def test_fb030_partial_submissions(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    q = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                    json={"type": "free_text", "code": "Q1", "label": "Required", "required": True})
    qid = q.json()["id"]
    blocked = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                          json={"question_id": qid, "value": ""})
    assert blocked.status_code == 422
    partial = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                          json={"question_id": qid, "value": "", "partial": True})
    assert partial.status_code == 201 and partial.json()["partial"] is True
    answers = client.get(f"{_base(wid)}/surveys/{sid}/answers", headers=h)
    assert answers.status_code == 200 and len(answers.json()) == 1


def test_fb032_033_034_035_language_and_styling(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    cfg = client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h, json={
        "languages": ["en", "te"], "theme": "forest", "custom_css": ".x{color:green}",
        "style": {"accent": "#176B55"},
    })
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["languages"] == ["en", "te"]
    assert body["theme"] == "forest" and body["custom_css"] == ".x{color:green}"
    assert client.post(f"{_base(wid)}/surveys/{sid}/config", headers=h,
                       json={"theme": "neon"}).status_code == 422
    q = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h, json={
        "type": "free_text", "code": "Q1", "label": "Hello",
        "labels": {"en": "Hello", "te": "నమస్తే"},
    })
    assert q.status_code == 201 and q.json()["labels"]["te"] == "నమస్తే"


def test_fb040_041_042_044_contact_and_closure(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    for qtype in ("consent", "contact_info", "date", "free_text"):
        assert client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                           json={"type": qtype, "code": f"q_{qtype}", "label": qtype}).status_code == 201
    # close the survey through the existing lifecycle and confirm no new answers
    assert client.patch(f"/api/v1/workspaces/{wid}/surveys/{sid}", headers=h,
                        json={"status": "closed"}).status_code == 200
    assert client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                       json={"value": 1}).status_code == 409


def test_feedback_extensions_workspace_isolation(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh = auth(other["access_token"])
    assert client.get(f"{_base(other['workspace_id'])}/surveys/{sid}/config", headers=oh).status_code == 404
    q = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                    json={"type": "free_text", "code": "Q1", "label": "x"}).json()
    assert client.patch(f"{_base(other['workspace_id'])}/questions/{q['id']}", headers=oh,
                        json={"label": "hijack"}).status_code == 404
