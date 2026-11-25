"""Named acceptance tests for the documented survey-template presets.

Each template must create a real workspace-scoped survey with persisted typed
questions, and those questions must accept real answers. No template is claimed
on name alone (FB-192, FB-194..FB-204).
"""

from __future__ import annotations

from .conftest import auth, bootstrap

TEMPLATE_IDS = {
    "contact_form": "FB-192", "docs_feedback": "FB-194", "feature_chaser": "FB-195",
    "feedback_box": "FB-196", "improve_email_content": "FB-197",
    "app_interview_prompt": "FB-198", "churn_survey": "FB-199",
    "product_market_fit": "FB-200", "quiz_time": "FB-201",
    "improve_trial_conversion": "FB-202", "panel_management": "FB-203",
    "collect_google_reviews": "FB-204",
}


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def test_all_documented_template_presets_create_real_surveys(client):
    wid, h = _ctx(client)
    keys = client.get(f"/api/v1/workspaces/{wid}/feedback/templates", headers=h).json()
    present = {k["key"] for k in keys}
    for key in TEMPLATE_IDS:
        assert key in present, f"missing template preset: {key}"
        created = client.post(f"/api/v1/workspaces/{wid}/feedback/surveys/from-template",
                              headers=h, json={"name": key, "template": key})
        assert created.status_code == 201, (key, created.text)
        sid = created.json()["survey_id"]
        questions = client.get(f"/api/v1/workspaces/{wid}/feedback/surveys/{sid}/questions",
                               headers=h).json()
        assert len(questions) >= 2, f"{key} has no persisted questions"
        assert all(q["type"] and q["code"] and q["label"] for q in questions)


def test_template_questions_are_answerable_and_isolated(client):
    wid, h = _ctx(client)
    created = client.post(f"/api/v1/workspaces/{wid}/feedback/surveys/from-template",
                          headers=h, json={"name": "Contact form", "template": "contact_form"})
    sid = created.json()["survey_id"]
    questions = client.get(f"/api/v1/workspaces/{wid}/feedback/surveys/{sid}/questions",
                           headers=h).json()
    for q in questions:
        answer = client.post(f"/api/v1/workspaces/{wid}/feedback/surveys/{sid}/answers",
                             headers=h, json={"code": q["code"], "value": "test", "embedded": {"src": "template"}})
        assert answer.status_code == 201, answer.text
        assert answer.json()["code"] == q["code"]
    answers = client.get(f"/api/v1/workspaces/{wid}/feedback/surveys/{sid}/answers", headers=h).json()
    assert len(answers) == len(questions)
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    assert client.get(f"/api/v1/workspaces/{other['workspace_id']}/feedback/surveys/{sid}/questions",
                      headers=auth(other["access_token"])).status_code == 404


def test_unknown_template_is_rejected(client):
    wid, h = _ctx(client)
    r = client.post(f"/api/v1/workspaces/{wid}/feedback/surveys/from-template",
                    headers=h, json={"name": "bad", "template": "not_a_template"})
    assert r.status_code == 422
