"""Named acceptance tests for the clean-room sales engagement cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No Sellbird source, broker, outbound email or external AI provider is
used; the outbox's only terminal send state is an explicitly simulated dry run.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/sales-engagement"


def _ctx(client):
    tokens = bootstrap(client, "SalesEng", "saleseng@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _lead(client, wid, h, email, status="new", priority="normal", score=0):
    contact = client.post(f"/api/v1/workspaces/{wid}/contacts", headers=h,
                          json={"email": email, "full_name": email.split("@")[0]})
    assert contact.status_code == 201, contact.text
    lead = client.post(f"/api/v1/workspaces/{wid}/leads", headers=h, json={
        "contact_id": contact.json()["id"], "source": "website_form",
        "status": status, "priority": priority, "score": score,
    })
    assert lead.status_code == 201, lead.text
    return lead.json()


def _draft(client, wid, h, campaign="spring-outreach"):
    result = client.post(_base(wid) + "/drafts/generate", headers=h,
                         json={"campaign_key": campaign, "steps": 1})
    assert result.status_code == 201, result.text
    return result.json()["drafts"][0]


def test_sb008_sb012_governed_signal_catalog_is_seeded_once(client):
    """The governed vocabulary exposes 29 signals with stable codes and tiers."""
    wid, h = _ctx(client)
    result = client.get(_base(wid) + "/signals", headers=h)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["total"] == 29 and body["free"] == 26 and body["paid"] == 3
    codes = [s["code"] for s in body["signals"]]
    assert len(set(codes)) == 29
    assert all(s["active"] is False for s in body["signals"])
    again = client.get(_base(wid) + "/signals", headers=h).json()
    assert again["total"] == 29  # seeded once, not duplicated


def test_sb009_free_signals_activate_only_with_confirmation(client):
    """The 26 free signals activate through an explicit confirmed action."""
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/signals/activate-free", headers=h,
                       json={"confirm": False}).status_code == 422
    result = client.post(_base(wid) + "/signals/activate-free", headers=h,
                         json={"confirm": True})
    assert result.status_code == 200, result.text
    assert result.json()["activated"] == 26
    signals = client.get(_base(wid) + "/signals", headers=h).json()["signals"]
    assert all(s["active"] for s in signals if s["tier"] == "free")
    assert all(not s["active"] for s in signals if s["tier"] == "paid")


def test_sb010_paid_signals_require_explicit_operator_confirmation(client):
    """Paid signals stay gated until an operator explicitly confirms them."""
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/signals/intent_data_burst/activate", headers=h,
                       json={"confirm": False}).status_code == 403
    result = client.post(_base(wid) + "/signals/intent_data_burst/activate", headers=h,
                         json={"confirm": True})
    assert result.status_code == 200, result.text
    assert result.json()["active"] is True and result.json()["tier"] == "paid"
    assert client.post(_base(wid) + "/signals/no_such_signal/activate", headers=h,
                       json={"confirm": True}).status_code == 404
    assert client.post(_base(wid) + "/signals/website_visit/activate", headers=h,
                       json={"confirm": False}).status_code == 422


def test_sb015_cohort_builder_evaluates_real_workspace_leads(client):
    """Cohorts filter persisted leads by status, priority, source and score."""
    wid, h = _ctx(client)
    _lead(client, wid, h, "hot@a.test", status="qualified", priority="high", score=90)
    _lead(client, wid, h, "warm@a.test", status="qualified", priority="normal", score=60)
    _lead(client, wid, h, "cold@a.test", status="new", priority="low", score=10)
    created = client.post(_base(wid) + "/cohorts", headers=h, json={
        "name": "Qualified high score", "filters": {"status": "qualified", "min_score": 70},
    })
    assert created.status_code == 201, created.text
    result = client.post(_base(wid) + f"/cohorts/{created.json()['id']}/evaluate", headers=h)
    assert result.status_code == 200, result.text
    assert result.json()["matched"] == 1 and result.json()["external_calls"] is False
    assert client.post(_base(wid) + "/cohorts", headers=h, json={
        "name": "bad", "filters": {"unknown_field": 1},
    }).status_code == 422
    assert client.post(_base(wid) + "/cohorts", headers=h, json={
        "name": "Qualified high score", "filters": {},
    }).status_code == 409


def test_sb017_campaign_sequences_are_drafted_locally(client):
    """Sequence drafts are generated by local templates with cohort/offer context."""
    wid, h = _ctx(client)
    cohort = client.post(_base(wid) + "/cohorts", headers=h,
                         json={"name": "All leads", "filters": {}}).json()
    offer = client.post(_base(wid) + "/offers/suggest", headers=h,
                        json={"pain": "manual reporting"}).json()
    result = client.post(_base(wid) + "/drafts/generate", headers=h, json={
        "campaign_key": "q1-push", "steps": 3,
        "cohort_id": cohort["id"], "offer_id": offer["id"],
    })
    assert result.status_code == 201, result.text
    assert result.json()["created"] == 3
    assert result.json()["external_model_calls"] is False
    drafts = client.get(_base(wid) + "/drafts", headers=h).json()
    assert [d["sequence_step"] for d in drafts] == [1, 2, 3]
    assert client.post(_base(wid) + "/drafts/generate", headers=h,
                       json={"campaign_key": "x", "steps": 6}).status_code == 422
    assert client.post(_base(wid) + "/drafts/generate", headers=h,
                       json={"campaign_key": "x", "cohort_id": "missing"}).status_code == 404


def test_sb019_offer_suggestion_is_deterministic_and_local(client):
    """Offer suggestions come from local rules over researched context."""
    wid, h = _ctx(client)
    result = client.post(_base(wid) + "/offers/suggest", headers=h,
                         json={"industry": "logistics", "pain": "manual work everywhere", "budget": "low"})
    assert result.status_code == 201, result.text
    assert "automation" in result.json()["offer"].lower()
    assert result.json()["external_model_calls"] is False
    again = client.post(_base(wid) + "/offers/suggest", headers=h,
                        json={"industry": "logistics", "pain": "manual work everywhere", "budget": "low"})
    assert again.json()["offer"] == result.json()["offer"]
    empty = client.post(_base(wid) + "/offers/suggest", headers=h, json={})
    assert "discovery call" in empty.json()["offer"].lower()


def test_sb022_outbox_is_durable_with_a_status_ladder(client):
    """Outbox messages move through approval, pause, dry-run and cancel states."""
    wid, h = _ctx(client)
    draft = _draft(client, wid, h)
    enqueued = client.post(_base(wid) + "/local-queue/enqueue", headers=h, json={
        "draft_id": draft["id"], "recipient": "buyer@corp.test",
    })
    assert enqueued.status_code == 201, enqueued.text
    mid = enqueued.json()["id"]
    assert enqueued.json()["status"] == "awaiting_approval"
    assert enqueued.json()["external_delivery"] is False
    assert client.post(_base(wid) + f"/local-queue/{mid}/dry-run", headers=h).status_code == 409
    assert client.post(_base(wid) + f"/local-queue/{mid}/approve", headers=h).json()["status"] == "approved"
    assert client.post(_base(wid) + f"/local-queue/{mid}/pause", headers=h).json()["status"] == "paused"
    assert client.post(_base(wid) + f"/local-queue/{mid}/resume", headers=h).json()["status"] == "approved"
    dry = client.post(_base(wid) + f"/local-queue/{mid}/dry-run", headers=h)
    assert dry.json()["status"] == "simulated" and dry.json()["external_delivery"] is False
    assert client.post(_base(wid) + f"/local-queue/{mid}/cancel", headers=h).status_code == 409
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                       json={"draft_id": draft["id"], "recipient": "not-an-email"}).status_code == 422


def test_sb023_autopilot_is_opt_in_and_approval_is_default(client):
    """Every email needs approval unless autopilot was explicitly opted into."""
    wid, h = _ctx(client)
    draft = _draft(client, wid, h)
    first = client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                        json={"draft_id": draft["id"], "recipient": "a@corp.test"})
    assert first.json()["approval_required"] is True
    assert client.put(_base(wid) + "/delivery-mode", headers=h,
                      json={"mode": "autopilot"}).status_code == 422
    assert client.post(_base(wid) + "/autopilot/opt-in", headers=h,
                       json={"opt_in": True, "confirm": False}).status_code == 422
    opt = client.post(_base(wid) + "/autopilot/opt-in", headers=h,
                      json={"opt_in": True, "confirm": True})
    assert opt.status_code == 200, opt.text
    assert client.put(_base(wid) + "/delivery-mode", headers=h,
                      json={"mode": "autopilot"}).json()["mode"] == "autopilot"
    second = client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                         json={"draft_id": draft["id"], "recipient": "b@corp.test"})
    assert second.json()["status"] == "approved" and second.json()["approval_required"] is False
    revoke = client.post(_base(wid) + "/autopilot/opt-in", headers=h,
                         json={"opt_in": False, "confirm": False})
    assert revoke.json()["mode"] == "approval"


def test_sb026_sending_status_and_pause_controls(client):
    """Global and per-inbox pauses block enqueue and show in sending status."""
    wid, h = _ctx(client)
    draft = _draft(client, wid, h)
    assert client.post(_base(wid) + "/delivery-pause", headers=h,
                       json={"scope": "global", "paused": True}).json()["paused"] is True
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                       json={"draft_id": draft["id"], "recipient": "a@corp.test"}).status_code == 409
    client.post(_base(wid) + "/delivery-pause", headers=h, json={"scope": "global", "paused": False})
    client.post(_base(wid) + "/delivery-pause", headers=h,
                json={"scope": "inbox", "inbox_key": "sales", "paused": True})
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h, json={
        "draft_id": draft["id"], "recipient": "a@corp.test", "inbox_key": "sales",
    }).status_code == 409
    ok = client.post(_base(wid) + "/local-queue/enqueue", headers=h, json={
        "draft_id": draft["id"], "recipient": "a@corp.test", "inbox_key": "support",
    })
    assert ok.status_code == 201
    status_body = client.get(_base(wid) + "/delivery-status", headers=h).json()
    assert status_body["paused_inboxes"] == ["sales"]
    assert status_body["outbox_counts"]["awaiting_approval"] == 1
    assert status_body["external_delivery"] is False
    assert client.post(_base(wid) + "/delivery-pause", headers=h,
                       json={"scope": "inbox", "paused": True}).status_code == 422


def test_sb028_send_rules_and_header_extension_points(client):
    """Local rule/header extensions gate enqueue and attach headers."""
    wid, h = _ctx(client)
    draft = _draft(client, wid, h)
    header = client.post(_base(wid) + "/delivery-rules", headers=h, json={
        "name": "campaign-header", "kind": "header",
        "config": {"name": "X-Campaign", "value": "q1-push"},
    })
    assert header.status_code == 201, header.text
    cap = client.post(_base(wid) + "/delivery-rules", headers=h, json={
        "name": "daily-cap", "kind": "rule", "config": {"max_per_day": 1},
    })
    assert cap.status_code == 201
    first = client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                        json={"draft_id": draft["id"], "recipient": "a@corp.test"})
    assert first.json()["headers"] == {"X-Campaign": "q1-push"}
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                       json={"draft_id": draft["id"], "recipient": "b@corp.test"}).status_code == 422
    assert client.post(_base(wid) + "/delivery-rules", headers=h, json={
        "name": "bad-rule", "kind": "rule", "config": {"execute": "rm -rf"},
    }).status_code == 422
    assert client.post(_base(wid) + "/delivery-rules", headers=h, json={
        "name": "bad-header", "kind": "header", "config": {"name": "X-Only"},
    }).status_code == 422
    signal_rule = client.post(_base(wid) + "/delivery-rules", headers=h, json={
        "name": "needs-signal", "kind": "rule", "config": {"require_signal": "demo_request"},
    })
    assert signal_rule.status_code == 201
    client.delete(_base(wid) + f"/delivery-rules/{cap.json()['id']}", headers=h)
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                       json={"draft_id": draft["id"], "recipient": "b@corp.test"}).status_code == 422
    client.post(_base(wid) + "/signals/demo_request/activate", headers=h, json={"confirm": True})
    assert client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                       json={"draft_id": draft["id"], "recipient": "b@corp.test"}).status_code == 201


def test_sb055_sending_mode_selection_is_validated(client):
    """The sending mode endpoint selects approval/autopilot and rejects others."""
    wid, h = _ctx(client)
    assert client.get(_base(wid) + "/delivery-status", headers=h).json()["mode"] == "approval"
    assert client.put(_base(wid) + "/delivery-mode", headers=h,
                      json={"mode": "yolo"}).status_code == 422
    assert client.put(_base(wid) + "/delivery-mode", headers=h,
                      json={"mode": "approval"}).json()["mode"] == "approval"


def test_sales_engagement_workspace_isolation(client):
    """A second workspace cannot address this workspace's engagement rows."""
    wid, h = _ctx(client)
    cohort = client.post(_base(wid) + "/cohorts", headers=h,
                         json={"name": "Private", "filters": {}}).json()
    draft = _draft(client, wid, h)
    enqueued = client.post(_base(wid) + "/local-queue/enqueue", headers=h,
                           json={"draft_id": draft["id"], "recipient": "a@corp.test"}).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other sales"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/cohorts", headers=other_h).json() == []
    assert client.post(_base(other_wid) + f"/cohorts/{cohort['id']}/evaluate",
                       headers=other_h).status_code == 404
    assert client.post(_base(other_wid) + f"/local-queue/{enqueued['id']}/approve",
                       headers=other_h).status_code == 404
    assert client.get(_base(other_wid) + "/local-queue", headers=other_h).json() == []
    assert client.get(_base(other_wid) + "/signals", headers=h).status_code == 403