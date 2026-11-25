"""Named acceptance tests for the clean-room survey delivery cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No Formbricks source, hosted widget, survey email, tracking pixel or
external SDK is used.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/survey-delivery"
SURVEYS = "/api/v1/workspaces/{wid}/surveys"


def _ctx(client):
    tokens = bootstrap(client, "Surveys", "surveys@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _survey(client, wid, h, name="Checkout pulse"):
    response = client.post(SURVEYS.format(wid=wid), headers=h, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _config(client, wid, h, channels=None, **extra):
    survey = _survey(client, wid, h, extra.pop("survey_name", "Delivery survey"))
    body = {"survey_id": survey["id"], "channels": channels or ["link"]}
    body.update(extra)
    response = client.post(_base(wid) + "/configs", headers=h, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_fb002_in_app_survey_delivery_is_a_persisted_channel(client):
    """In-app surveys are a real, workspace-scoped delivery channel."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["in_app"])
    assert "in_app" in cfg["channels"]
    detail = client.get(_base(wid) + "/configs/" + cfg["id"], headers=h).json()
    assert detail["channels"] == ["in_app"]


def test_fb003_website_survey_targets_are_recorded(client):
    """Website survey delivery stores its channel for anonymous visitors."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    assert client.get(_base(wid) + "/configs", headers=h).json()[0]["channels"] == ["website"]


def test_fb004_link_survey_is_shareable_by_survey_identifier(client):
    """Link surveys expose a local share URL rooted at the survey identifier."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["link"])
    snippets = client.get(_base(wid) + f"/configs/{cfg['id']}/embed-snippets", headers=h).json()
    assert "/s/" + cfg["survey_id"] in snippets["iframe"]
    assert snippets["external_service"] is False


def test_fb005_email_survey_channel_is_recorded(client):
    """Email survey distribution is an explicit channel selection."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["email"])
    assert cfg["channels"] == ["email"]
    assert client.post(_base(wid) + "/configs", headers=h, json={
        "survey_id": cfg["survey_id"], "channels": ["carrier_pigeon"],
    }).status_code == 422


def test_fb006_embedded_surveys_generate_local_iframe_and_email_snippets(client):
    """Embed mode produces iframe and email snippets with no external service."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["embed"], embed_mode="iframe")
    snippets = client.get(_base(wid) + f"/configs/{cfg['id']}/embed-snippets", headers=h).json()
    assert snippets["embed_mode"] == "iframe"
    assert "<iframe" in snippets["iframe"] and snippets["iframe"].endswith("</iframe>")
    assert "/s/" in snippets["email_snippet"]
    assert client.post(_base(wid) + "/configs", headers=h, json={
        "survey_id": cfg["survey_id"], "channels": ["link"], "embed_mode": "remote",
    }).status_code == 422


def test_fb010_no_code_survey_editor_creates_question_pages(client):
    """The no-code editor persists editable pages and their questions."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["link"])
    page = client.post(_base(wid) + f"/configs/{cfg['id']}/pages", headers=h, json={
        "key": "intro", "title": "Introduction",
        "questions": [{"type": "text", "label": "How are you?"}], "position": 0,
    })
    assert page.status_code == 201, page.text
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/pages", headers=h, json={
        "key": "intro", "title": "Duplicate", "questions": [],
    }).status_code == 409
    pages = client.get(_base(wid) + f"/configs/{cfg['id']}/pages", headers=h).json()
    assert len(pages) == 1 and pages[0]["questions"][0]["type"] == "text"


def test_fb015_multi_page_flow_has_rules_fallbacks_and_endings(client):
    """Flow outline exposes pages, post-block rules, fallbacks and endings."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    for key, position, ending in (("intro", 0, False), ("detail", 1, False), ("thanks", 2, True)):
        response = client.post(_base(wid) + f"/configs/{cfg['id']}/pages", headers=h,
                               json={"key": key, "title": key.title(), "position": position,
                                     "ending": ending})
        assert response.status_code == 201, response.text
    for kind, target in (("post_block", "detail"), ("fallback", "thanks"), ("ending", "thanks")):
        response = client.post(_base(wid) + f"/configs/{cfg['id']}/rules", headers=h,
                               json={"from_page": "intro", "kind": kind,
                                     "condition": {"score_gte": 7}, "target_page": target})
        assert response.status_code == 201, response.text
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/rules", headers=h,
                       json={"from_page": "intro", "kind": "teleport",
                             "target_page": "thanks"}).status_code == 422
    outline = client.get(_base(wid) + f"/configs/{cfg['id']}/flow", headers=h).json()
    assert [p["key"] for p in outline["pages"]] == ["intro", "detail", "thanks"]
    assert outline["pages"][2]["ending"] is True
    assert {r["kind"] for r in outline["rules"]} == {"post_block", "fallback", "ending"}


def test_fb036_email_branding_is_workspace_scoped(client):
    """Respondent email branding is stored per config, never sent."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["email"])
    assert client.get(_base(wid) + f"/configs/{cfg['id']}/email-branding", headers=h).json() is None
    response = client.put(_base(wid) + f"/configs/{cfg['id']}/email-branding", headers=h, json={
        "from_name": "NOVARA Research", "from_address": "research@novara.local",
        "subject_template": "Tell us about {{product}}",
        "footer_text": "Sent locally", "reply_to": None,
    })
    assert response.status_code == 200 and response.json()["external_send"] is False
    branding = client.get(_base(wid) + f"/configs/{cfg['id']}/email-branding", headers=h).json()
    assert branding["from_name"] == "NOVARA Research"
    assert "{{product}}" in branding["subject_template"]


def test_fb038_hide_back_button_is_a_configurable_flag(client):
    """Hiding the back button is a persisted, togglable config option."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["link"], hide_back_button=True)
    assert client.get(_base(wid) + f"/configs/{cfg['id']}", headers=h).json()["hide_back_button"] is True
    updated = client.patch(_base(wid) + f"/configs/{cfg['id']}", headers=h,
                           json={"hide_back_button": False})
    assert updated.status_code == 200
    assert client.get(_base(wid) + f"/configs/{cfg['id']}", headers=h).json()["hide_back_button"] is False


def test_fb074_pin_protected_surveys_verify_without_exposing_the_pin(client):
    """A four-digit PIN is hashed at rest and verified without disclosure."""
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/configs", headers=h, json={
        "survey_id": _survey(client, wid, h, "Bad PIN")["id"],
        "channels": ["link"], "pin": "12",
    }).status_code == 422
    cfg = _config(client, wid, h, ["link"], pin="4321")
    detail = client.get(_base(wid) + f"/configs/{cfg['id']}", headers=h).json()
    assert detail["pin_protected"] is True and "pin" not in detail
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/verify-pin", headers=h,
                       json={"pin": "0000"}).json()["valid"] is False
    valid = client.post(_base(wid) + f"/configs/{cfg['id']}/verify-pin", headers=h,
                        json={"pin": "4321"}).json()
    assert valid["valid"] is True and valid["stored_pin_exposed"] is False
    client.patch(_base(wid) + f"/configs/{cfg['id']}", headers=h, json={"remove_pin": True})
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/verify-pin", headers=h,
                       json={"pin": "0000"}).json() == {
        "required": False, "valid": True, "stored_pin_exposed": False,
    }


def test_fb075_custom_head_scripts_are_scoped_to_one_config(client):
    """Custom head scripts are stored, toggleable and appear in the embed head."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["link"])
    script = client.post(_base(wid) + f"/configs/{cfg['id']}/head-scripts", headers=h, json={
        "key": "analytics", "label": "Analytics pixel",
        "script": "<meta name=\"local\" content=\"1\">", "enabled": True,
    })
    assert script.status_code == 201, script.text
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/head-scripts", headers=h, json={
        "key": "analytics", "label": "dup", "script": "x",
    }).status_code == 409
    scripts = client.get(_base(wid) + f"/configs/{cfg['id']}/head-scripts", headers=h).json()
    assert scripts[0]["enabled"] is True and "script" not in scripts[0]
    head = client.get(_base(wid) + f"/configs/{cfg['id']}/embed-snippets", headers=h).json()["head_scripts"]
    assert "local" in head


def test_fb079_host_page_css_interaction_is_isolated_by_style_scope(client):
    """Host CSS interaction mode keeps survey styling scoped."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"], host_css_mode="scoped", style_scope="my-survey")
    assert client.post(_base(wid) + "/configs", headers=h, json={
        "survey_id": cfg["survey_id"], "channels": ["link"], "host_css_mode": "global",
    }).status_code == 422
    snippets = client.get(_base(wid) + f"/configs/{cfg['id']}/embed-snippets", headers=h).json()
    assert snippets["host_css_mode"] == "scoped"
    assert snippets["style_scope"] == "my-survey"
    assert snippets["style_scope"] in snippets["iframe"]


def test_fb080_email_followups_are_triggered_by_answers_or_endings(client):
    """Follow-ups are local records keyed to answer or ending triggers."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["email"])
    response = client.post(_base(wid) + f"/configs/{cfg['id']}/followups", headers=h, json={
        "key": "low-score", "trigger_type": "answer", "trigger_value": "score<=4",
        "subject": "Sorry to hear that", "body": "Tell us more locally.",
    })
    assert response.status_code == 201 and response.json()["external_send"] is False
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/followups", headers=h, json={
        "key": "done", "trigger_type": "ending", "trigger_value": "thanks",
        "subject": "Done", "body": "Thanks.",
    }).status_code == 201
    assert client.post(_base(wid) + f"/configs/{cfg['id']}/followups", headers=h, json={
        "key": "bad", "trigger_type": "calendar", "trigger_value": "x",
        "subject": "s", "body": "b",
    }).status_code == 422
    followups = client.get(_base(wid) + f"/configs/{cfg['id']}/followups", headers=h).json()
    assert {f["trigger_type"] for f in followups} == {"answer", "ending"}


def test_fb183_accessibility_settings_are_persisted_and_validated(client):
    """Accessibility options are stored as a structured config object."""
    wid, h = _ctx(client)
    a11y = {
        "aria_labels": True, "keyboard_navigation": True, "high_contrast": True,
        "focus_indicator": True, "reduced_motion": True,
        "screen_reader_announcements": True, "wcag_version": "2.2",
    }
    cfg = _config(client, wid, h, ["website"], accessibility=a11y)
    detail = client.get(_base(wid) + f"/configs/{cfg['id']}", headers=h).json()
    assert detail["accessibility"]["wcag_version"] == "2.2"
    assert detail["accessibility"]["keyboard_navigation"] is True


def test_fb184_creatives_package_registers_local_creatives(client):
    """The creatives package registers workspace-scoped creative records."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    response = client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "general", "type": "feedback_button",
        "label": "General feedback",
    })
    assert response.status_code == 201, response.text
    assert client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "general", "type": "banner", "label": "dup",
    }).status_code == 409
    assert client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "bad", "type": "popup", "label": "bad",
    }).status_code == 422
    assert client.get(_base(wid) + "/creatives", headers=h).json()[0]["key"] == "general"


def test_fb185_feedback_button_creative_has_label_icon_colour_and_position(client):
    """The edge feedback button stores label, icon, colours, size and position."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    creative = client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "edge-tab", "type": "feedback_button",
        "label": "Feedback", "icon": "message", "colors": {"background": "#101827"},
        "size": "small", "position": "bottom-left",
    }).json()
    assert client.patch(_base(wid) + f"/creatives/{creative['id']}", headers=h,
                        json={"status": "active"}).status_code == 200
    result = client.post(_base(wid) + f"/creatives/{creative['id']}/evaluate", headers=h,
                         json={"page": "/pricing", "device": "desktop"}).json()
    assert result["show"] is True and result["type"] == "feedback_button"
    assert result["local_evaluation"] is True


def test_fb186_banner_creative_stores_message_button_and_schedule(client):
    """The top/bottom banner stores its message, button and minute schedule."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    creative = client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "notice", "type": "banner",
        "label": "Notice", "message": "Help us improve", "button_label": "Open",
        "position": "top",
        "schedule": {"start": "2026-01-01T00:00:00", "end": "2099-01-01T00:00:00"},
    }).json()
    assert creative["type"] == "banner"
    assert client.patch(_base(wid) + f"/creatives/{creative['id']}", headers=h,
                        json={"status": "active"}).status_code == 200
    result = client.post(_base(wid) + f"/creatives/{creative['id']}/evaluate", headers=h,
                         json={"page": "/"}).json()
    assert result["show"] is True and result["reasons"] == []


def test_fb187_creative_show_conditions_gate_page_device_views_and_share(client):
    """Scheduling and targeting determine where and when a creative appears."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["website"])
    creative = client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "gated", "type": "banner", "label": "Gated",
        "schedule": {"start": "2099-01-01T00:00:00"},
        "targeting": {"pages": ["/pricing"], "devices": ["desktop"],
                      "min_views": 3, "share": 50},
    }).json()
    assert client.patch(_base(wid) + f"/creatives/{creative['id']}", headers=h,
                        json={"status": "active"}).status_code == 200
    hidden = client.post(_base(wid) + f"/creatives/{creative['id']}/evaluate", headers=h,
                         json={"page": "/about", "device": "mobile", "views": 1, "share": 80}).json()
    assert hidden["show"] is False
    assert {"before_start", "page_not_targeted", "device_not_targeted",
            "below_min_views", "outside_share"}.issubset(set(hidden["reasons"]))
    assert client.post(_base(wid) + f"/creatives/{creative['id']}/evaluate", headers=h,
                       json={"page": "/about", "device": "smartwatch"}).status_code == 422


def test_survey_delivery_workspace_isolation(client):
    """Configs, scripts, creatives and evaluations are confined to a workspace."""
    wid, h = _ctx(client)
    cfg = _config(client, wid, h, ["link"], pin="1111")
    script = client.post(_base(wid) + f"/configs/{cfg['id']}/head-scripts", headers=h,
                         json={"key": "only-here", "label": "Only", "script": "x"}).json()
    creative = client.post(_base(wid) + "/creatives", headers=h, json={
        "config_id": cfg["id"], "key": "only-here", "type": "banner", "label": "Only",
    }).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other surveys"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/configs", headers=h).status_code == 403
    for path in ("/configs", "/creatives"):
        assert client.get(_base(other_wid) + path, headers=other_h).json() == []
    assert client.get(_base(other_wid) + f"/configs/{cfg['id']}", headers=other_h).status_code == 404
    assert client.post(_base(other_wid) + f"/configs/{cfg['id']}/verify-pin",
                       headers=other_h, json={"pin": "1111"}).status_code == 404
    assert client.get(_base(other_wid) + f"/configs/{script['id']}/head-scripts",
                      headers=other_h).status_code == 404
    assert client.post(_base(other_wid) + f"/creatives/{creative['id']}/evaluate",
                       headers=other_h, json={}).status_code == 404
