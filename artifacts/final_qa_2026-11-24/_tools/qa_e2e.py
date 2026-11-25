"""Eight local end-to-end workflows against the running NOVARA QA instance.

Every step is an observed HTTP request. No real provider, email, SMS,
payment or external integration is contacted. Campaign delivery is
deliberately NOT executed; drafts stay local.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from schema_payload import body_for

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
LOG = OUT / "evidence" / "qa_e2e_log.jsonl"
c = httpx.Client(base_url=BASE, timeout=30.0)
_seq = 0
_wf = ""


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def emit(row):
    global _seq
    _seq += 1
    row.update(seq=_seq, ts=ts(), workflow=_wf)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{_seq:03d} {row['outcome']:7s} [{_wf}] {row['method']} {row['path'][:78]} -> {row['status']}")


def step(method, path, token, expected=(200, 201), body=None, note="", override=None):
    payload = body_for(path, method) if body is None else dict(body)
    payload = payload or {}
    if override:
        payload.update(override)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = c.request(method, path, headers=headers, json=payload if method in ("POST", "PATCH", "PUT") else None)
        status = r.status_code
        try:
            data = r.json()
        except Exception:
            data = r.text[:400]
        observed = json.dumps(data, ensure_ascii=False)[:700]
    except Exception as exc:
        status, data, observed = "ERR", None, f"{type(exc).__name__}: {exc}"
    emit(dict(method=method, path=path, expected=f"status in {expected}", status=status,
              observed=observed, payload=payload, note=note,
              outcome="PASS" if status in expected else "FAIL"))
    return status, data


def workflow(name):
    global _wf
    _wf = name
    emit(dict(method="-", path="-", expected="-", status="-", observed="WORKFLOW START",
              payload=None, note="", outcome="INFO"))


def main():
    LOG.write_text("", encoding="utf-8")
    _, auth = step("POST", "/api/v1/auth/login", None, expected=(200,),
                   body={"email": "qa.owner@novara.invalid", "password": "QaSynthetic!2026"},
                   note="Synthetic QA identity")
    token = auth["access_token"]
    wid = auth["workspace_id"]
    prefix = f"/api/v1/workspaces/{wid}"

    # 1 ---------------------------------------------------------------- Lead to customer
    workflow("W1-Lead-to-customer")
    email = f"e2e.lead.{int(time.time())}@novara.invalid"
    _, intake = step("POST", prefix + "/intake/website-form", token,
                     body={"email": email, "full_name": "E2EQA Lead", "company": "Synthetic Intake Co",
                           "message": "Synthetic QA website form submission.", "source": "qa-e2e-form"})
    _, contacts = step("GET", prefix + "/contacts?search=" + email, token)
    contact_id = None
    if isinstance(contacts, list) and contacts:
        contact_id = contacts[0].get("id")
    if contact_id:
        lead_body = {"contact_id": contact_id, "source": "qa-e2e", "status": "new",
                     "priority": "high", "score": 80}
        st_lead, lead = step("POST", prefix + "/leads", token, body=lead_body,
                             expected=(200, 201, 409),
                             note="Create lead from website-form contact; 409 on a repeated QA run means it already exists")
        lead_id = lead.get("id") if isinstance(lead, dict) else None
        if st_lead == 409:
            # Idempotent rerun: the lead from an earlier QA pass already exists.
            _, leads = step("GET", prefix + "/leads", token,
                            note="Reuse the existing lead on a repeated QA run")
            if isinstance(leads, list):
                lead_id = next((x.get("id") for x in leads
                                if x.get("contact_id") == contact_id), None)
        if not lead_id:
            emit(dict(method="-", path="lead id", expected="created or existing lead", status="SKIP",
                      observed="No lead id available", payload=lead_body, note="", outcome="FAIL"))
        if lead_id:
            step("POST", prefix + f"/leads/{lead_id}/qualify", token)
            step("POST", prefix + f"/leads/{lead_id}/convert", token,
                 note="Lead becomes customer; no outbound communication")
        step("GET", prefix + "/events?limit=20", token, note="Conversion event on audit spine")
    else:
        emit(dict(method="-", path="lead conversion", expected="contact from intake", status="SKIP",
                  observed="No contact returned by contact search", payload=None, note="", outcome="FAIL"))

    # 2 ---------------------------------------------------------------- Campaign lifecycle
    workflow("W2-Campaign-lifecycle")
    camp_name = f"QA E2E Campaign {int(time.time() * 1000)}"
    _, camp = step("POST", prefix + "/campaigns", token,
                   override={"name": camp_name, "channel": "email", "status": "draft"},
                   note="Draft campaign only; no send is executed")
    cid = camp.get("id") if isinstance(camp, dict) else None
    step("GET", prefix + "/campaigns", token)
    step("POST", prefix + "/campaigns/segments", token, expected=(201, 409),
         override={"name": "QA Synthetic Segment", "description": "Local QA only"},
         note="409 on rerun means the local segment already exists")
    if cid:
        step("PATCH", prefix + f"/campaigns/{cid}", token, expected=(200,),
             override={"name": camp_name, "status": "active"})
        step("POST", prefix + f"/campaigns/{cid}/schedule", token,
             override={"start_at": "2026-11-25T09:00:00Z", "end_at": "2026-11-30T17:00:00Z"},
             note="Schedule recorded locally; no dispatch")
        step("GET", prefix + "/campaigns/analytics/lifecycle", token)
    emit(dict(method="-", path="campaign delivery", expected="not executed", status="NOT_EXECUTED",
              observed="No send/dispatch API was called: outbound email is out of scope for QA",
              payload=None, note="", outcome="INFO"))

    # 3 ---------------------------------------------------------------- Customer support
    workflow("W3-Customer-support")
    _, ticket = step("POST", prefix + "/tickets", token,
                     override={"subject": "QA E2E support ticket", "body": "Synthetic QA support request.",
                               "priority": "normal"})
    tid = ticket.get("id") if isinstance(ticket, dict) else None
    if tid:
        step("POST", prefix + f"/tickets/{tid}/messages", token,
             override={"body": "Synthetic agent reply. No notification delivered externally."})
        step("POST", prefix + f"/tickets/{tid}/notes", token,
             override={"body": "Synthetic private note - not visible to customer."})
        step("GET", prefix + f"/tickets/{tid}", token)
    step("GET", prefix + "/tickets/counts", token)

    # 4 ---------------------------------------------------------------- Document engagement
    workflow("W4-Document-engagement")
    step("POST", prefix + "/documents/rooms", token, expected=(201, 409),
         override={"name": "QA E2E Data Room"},
         note="409 on rerun means the local data room already exists")
    _, doc = step("POST", prefix + "/documents", token,
                  override={"title": "QA Synthetic Brief", "storage_path": "qa/e2e-brief.txt"})
    did = doc.get("id") if isinstance(doc, dict) else None
    if did:
        _, link = step("POST", prefix + f"/documents/{did}/links", token,
                       note="Local share link; no public notification is sent")
        lid = link.get("id") if isinstance(link, dict) else None
        step("GET", prefix + f"/documents/{did}/analytics", token)
        if lid:
            step("GET", prefix + f"/documents/links/{lid}/visits", token)
    step("GET", prefix + "/documents/rooms", token)

    # 5 ---------------------------------------------------------------- Experimentation
    workflow("W5-Experimentation")
    _, metric = step("POST", prefix + "/experiment-stats/metrics", token, expected=(201, 409),
                     override={"key": "qa_e2e_metric", "name": "QA E2E Metric", "type": "proportion"})
    mid = metric.get("id") if isinstance(metric, dict) else None
    if not mid:
        _, metrics = step("GET", prefix + "/experiment-stats/metrics", token)
        if isinstance(metrics, list) and metrics:
            mid = metrics[0].get("id")
    exp_key = f"qa-e2e-experiment-{int(time.time())}"
    _, exp = step("POST", prefix + "/experiment-stats/experiments", token, expected=(201,),
                  override={"key": exp_key, "name": "QA E2E Experiment",
                            "variants": [{"key": "control", "traffic_share": 0.5},
                                         {"key": "variant_a", "traffic_share": 0.5}]},
                  note="Two local variants so the analyzer has a control and a treatment")
    eid = exp.get("id") if isinstance(exp, dict) else None
    if eid and mid:
        for variant, sessions, conversions in (("control", 20, 4), ("variant_a", 20, 6)):
            step("POST", prefix + f"/experiment-stats/experiments/{eid}/observations", token,
                 override={"metric_id": mid, "variant": variant,
                           "sessions": sessions, "conversions": conversions})
        step("POST", prefix + f"/experiment-stats/experiments/{eid}/analyze", token,
             override={"metric_id": mid},
             note="Local statistical analysis only")
    step("GET", prefix + "/experiment-stats/experiments", token)
    step("GET", prefix + "/advanced-experiments/api-contract", token)

    # 6 ---------------------------------------------------------------- Project execution
    workflow("W6-Project-execution")
    _, proj = step("POST", prefix + "/projects", token, override={"name": "QA E2E Delivery Project"})
    pid = proj.get("id") if isinstance(proj, dict) else None
    if pid:
        _, item = step("POST", prefix + f"/projects/{pid}/items", token,
                       override={"title": "QA E2E work item", "status": "todo"})
        iid = item.get("id") if isinstance(item, dict) else None
        if iid:
            step("PATCH", prefix + f"/projects/{pid}/items/{iid}", token,
                 override={"status": "done"})
        step("GET", prefix + f"/projects/{pid}/progress", token)
        step("POST", prefix + f"/projects/{pid}/comments", token,
             override={"body": "Synthetic QA project comment."})
    step("GET", prefix + "/projects", token)

    # 7 ---------------------------------------------------------------- Automation
    workflow("W7-Automation")
    _, auto = step("POST", prefix + "/automations", token,
                   override={"name": f"QA E2E Automation {int(time.time() * 1000)}", "trigger_type": "form_submission",
                             "definition": [{"id": "qa-step-1", "type": "notify",
                                             "config": {"channel": "in_app"}}]},
                   note="Local automation definition; in-app step only")
    aid = auto.get("id") if isinstance(auto, dict) else None
    if aid:
        step("POST", prefix + f"/automations/{aid}/status", token, override={"status": "active"})
        step("GET", prefix + f"/automations/{aid}", token)
    _, templates = step("GET", prefix + "/notification-workflows/templates", token)
    key = None
    if isinstance(templates, list) and templates:
        key = templates[0].get("key")
    elif isinstance(templates, dict):
        arr = templates.get("items") or templates.get("templates") or []
        if arr:
            key = arr[0].get("key")
    if key:
        _, wf = step("POST", prefix + f"/notification-workflows/templates/{key}/instantiate", token,
                     override={"name": "QA E2E workflow"})
        wfid = wf.get("id") if isinstance(wf, dict) else None
        if wfid:
            step("POST", prefix + f"/notification-workflows/workflows/{wfid}/trigger", token,
                 note="Trigger writes to local in-app notification outbox only")
    else:
        emit(dict(method="-", path="notification workflow template", expected="template key",
                  status="SKIP", observed="No template key returned", payload=None, note="", outcome="FAIL"))

    # 8 ---------------------------------------------------------------- AI-assisted operation
    workflow("W8-AI-assisted-operation")
    _, agent = step("POST", prefix + "/agents", token,
                    override={"name": f"QA E2E Agent {int(time.time() * 1000)}", "purpose": "draft_review",
                              "model_provider": "local", "model_name": "qa-simulated",
                              "boundary": "drafts only; no external calls", "requires_approval": True})
    agid = agent.get("id") if isinstance(agent, dict) else None
    if agid:
        _, run = step("POST", prefix + f"/agents/{agid}/runs", token,
                      override={"task": "Synthetic QA task: summarise the synthetic contact."},
                      note="Simulated local agent run; no model provider called")
        rid = run.get("id") if isinstance(run, dict) else None
        if rid:
            step("GET", prefix + f"/agents/runs/{rid}", token)
            step("POST", prefix + f"/agents/{agid}/runs/{rid}/progress", token,
                 override={"status": "awaiting_approval", "steps_taken": 1},
                 note="Simulated run reaches the human approval gate")
            step("POST", prefix + f"/agents/{agid}/runs/{rid}/approve", token,
                 note="Human approval gate on simulated agent output")
    step("POST", prefix + "/outreach-drafts", token,
         override={"contact_id": contact_id, "subject_template": "QA draft for {{contact.full_name}}",
                   "body_template": "Synthetic local draft; never sent."},
         note="AI-assisted draft stored locally, not delivered")
    step("GET", prefix + "/outreach-drafts", token)

    print("\nDONE", _seq, "records")


if __name__ == "__main__":
    main()
