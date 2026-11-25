"""NOVARA QA harness — synthetic data + observed API checks.

Runs against a locally started NOVARA instance with a dedicated QA SQLite DB.
Every request and observed outcome is appended to qa_api_log.jsonl.
No real provider, email, SMS, payment or external service is contacted.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
LOG = OUT / "evidence" / "qa_api_log.jsonl"

client = httpx.Client(base_url=BASE, timeout=30.0)
_seq = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def record(phase, module, scenario, method, path, expected, status, observed, outcome, note=""):
    global _seq
    _seq += 1
    row = {
        "seq": _seq,
        "ts": now(),
        "phase": phase,
        "module": module,
        "scenario": scenario,
        "method": method,
        "path": path,
        "expected": expected,
        "status": status,
        "observed": observed[:600] if isinstance(observed, str) else observed,
        "outcome": outcome,
        "note": note,
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{_seq:03d}] {outcome:7s} {method:6s} {path[:70]:70s} -> {status}")


def call(method, path, *, token=None, json_body=None, expected=(200, 201), phase="setup",
         module="Platform", scenario="", note=""):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    started = time.monotonic()
    try:
        r = client.request(method, path, headers=headers, json=json_body)
        status = r.status_code
        try:
            payload = r.json()
        except Exception:
            payload = r.text[:400]
        observed = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    except Exception as exc:  # network/server failure is recorded, never hidden
        status = "ERR"
        observed = f"{type(exc).__name__}: {exc}"
    outcome = "PASS" if status in expected else "FAIL"
    record(phase, module, scenario, method, path, f"status in {expected}", status, observed,
           outcome, note)
    return status, (payload if 'payload' in locals() else None), token


def main():
    LOG.write_text("", encoding="utf-8")
    print("QA API harness start", now(), BASE)

    # ---------------- Phase 1: bootstrap / synthetic identities ----------------
    st, boot, _ = call(
        "POST", "/api/v1/setup/bootstrap",
        json_body={
            "workspace_name": "QA Synthetic Workspace A",
            "email": "qa.owner@novara.invalid",
            "password": "QaSynthetic!2026",
            "display_name": "QA Owner (synthetic)",
        },
        expected=(200, 201, 409), phase="bootstrap", module="Platform",
        scenario="First-run bootstrap creates QA owner and workspace",
    )
    if st in (200, 201):
        token = boot["access_token"]
        wid = boot["workspace_id"]
    else:
        # Idempotent rerun: the QA workspace already exists, sign in again.
        st, boot, _ = call(
            "POST", "/api/v1/auth/login",
            json_body={"email": "qa.owner@novara.invalid", "password": "QaSynthetic!2026"},
            expected=(200,), phase="bootstrap", module="Platform",
            scenario="Re-authenticate the existing QA owner on rerun",
        )
        if st != 200:
            print("Bootstrap/login failed; aborting seed"); return
        token = boot["access_token"]
        wid = boot["workspace_id"]
    (OUT / "evidence" / "qa_context.json").write_text(
        json.dumps({"token_prefix": token[:8] + "…(redacted)", "workspace_id": wid,
                    "email": "qa.owner@novara.invalid"}, indent=2), encoding="utf-8")

    call("GET", "/health", phase="startup", module="Platform",
         scenario="Health endpoint reports ok", expected=(200,))
    call("GET", "/api/v1/auth/me", token=token, phase="startup", module="Platform",
         scenario="Session identity and permissions resolve", expected=(200,))

    # negative: invalid login
    call("POST", "/api/v1/auth/login",
         json_body={"email": "qa.owner@novara.invalid", "password": "wrong-password"},
         expected=(401,), phase="security", module="Settings & Administration",
         scenario="Invalid password is rejected",
         note="Expected 401; response body must not reveal whether the email exists")

    # second synthetic identity / workspace for isolation tests
    st, reg2, _ = call(
        "POST", "/api/v1/auth/register",
        json_body={"email": "qa.other@novara.invalid", "password": "QaOther!2026",
                   "display_name": "QA Other (synthetic)"},
        expected=(200, 201, 409), phase="bootstrap", module="Platform",
        scenario="Second QA identity in a separate workspace",
    )
    if st == 409:
        st, reg2, _ = call(
            "POST", "/api/v1/auth/login",
            json_body={"email": "qa.other@novara.invalid", "password": "QaOther!2026"},
            expected=(200,), phase="bootstrap", module="Platform",
            scenario="Re-authenticate the second QA identity on rerun",
        )
    if st != 200:
        print("Second identity unavailable; isolation tests skipped"); return
    token2 = reg2["access_token"]
    wid2 = reg2["workspace_id"]

    # ---------------- Phase 2: CRM and Contacts ----------------
    st, comp, _ = call(
        "POST", f"/api/v1/workspaces/{wid}/companies",
        token=token, json_body={"name": "NorthwindQA Botanicals",
                                 "industry": "Synthetic retail", "website": "https://example.invalid",
                                 "location": "Test City"},
        expected=(201, 409), phase="seed", module="CRM & Contacts",
        scenario="Create a synthetic company",
    )
    company_id = comp.get("id") if isinstance(comp, dict) else None
    if not company_id:
        _, existing, _ = call("GET", f"/api/v1/workspaces/{wid}/companies", token=token,
                              expected=(200,), phase="seed", module="CRM & Contacts",
                              scenario="Reuse existing synthetic company on rerun")
        if isinstance(existing, list) and existing:
            company_id = existing[0].get("id")

    contact_ids = []
    for i, (name, email) in enumerate([
        ("AshaQA Kapoor", "asha.qa@novara.invalid"),
        ("RohanQA Mehta", "rohan.qa@novara.invalid"),
        ("MeeraQA Iyer", "meera.qa@novara.invalid"),
    ], start=1):
        st, c, _ = call(
            "POST", f"/api/v1/workspaces/{wid}/contacts", token=token,
            json_body={"email": email, "full_name": name,
                       "company_name": "NorthwindQA Botanicals" if i == 1 else None,
                       "company_id": company_id if i == 1 else None,
                       "source": "qa-synthetic-form", "tags": ["qa", "synthetic"],
                       "custom_fields": {"qa_run": "2026-11-24"}},
            expected=(201, 409), phase="seed", module="CRM & Contacts",
            scenario=f"Create synthetic contact {i}",
        )
        if isinstance(c, dict) and c.get("id"):
            contact_ids.append(c["id"])

    if len(contact_ids) < 3:
        _, existing, _ = call("GET", f"/api/v1/workspaces/{wid}/contacts", token=token,
                              expected=(200,), phase="seed", module="CRM & Contacts",
                              scenario="Reuse existing synthetic contacts on rerun")
        if isinstance(existing, list):
            for row in existing:
                if row.get("id") not in contact_ids:
                    contact_ids.append(row["id"])
                if len(contact_ids) >= 3:
                    break

    if contact_ids:
        call("GET", f"/api/v1/workspaces/{wid}/contacts", token=token,
             phase="crm", module="CRM & Contacts", scenario="List contacts (persistence)",
             expected=(200,))
        call("GET", f"/api/v1/workspaces/{wid}/contacts?search=asha.qa", token=token,
             phase="crm", module="CRM & Contacts", scenario="Search contacts by email", expected=(200,))
        call("POST", f"/api/v1/workspaces/{wid}/contacts", token=token,
             json_body={"email": "asha.qa@novara.invalid", "full_name": "DuplicateQA"},
             expected=(409,), phase="security", module="CRM & Contacts",
             scenario="Duplicate contact email is rejected")
        call("GET", f"/api/v1/workspaces/{wid}/contacts/{contact_ids[0]}", token=token2,
             expected=(403, 404), phase="security", module="CRM & Contacts",
             scenario="Cross-workspace contact read is denied",
             note="Workspace B token must not read Workspace A record")

        call("PATCH", f"/api/v1/workspaces/{wid}/contacts/{contact_ids[0]}", token=token,
             json_body={"full_name": "AshaQA Kapoor (edited)"},
             expected=(200,), phase="crm", module="CRM & Contacts", scenario="Edit contact")
        call("POST", f"/api/v1/workspaces/{wid}/contacts/{contact_ids[0]}/notes", token=token,
             json_body={"contact_id": contact_ids[0],
                        "body": "Synthetic QA note: follow-up requested."},
             expected=(201,), phase="crm", module="CRM & Contacts",
             scenario="Record a customer timeline note")
        call("GET", f"/api/v1/workspaces/{wid}/contacts/{contact_ids[0]}/notes", token=token,
             expected=(200,), phase="crm", module="CRM & Contacts",
             scenario="Customer timeline note persists")

    # ---------------- Phase 3: Lead Intelligence and Sales ----------------
    lead_id = None
    if contact_ids:
        st, lead, _ = call(
            "POST", f"/api/v1/workspaces/{wid}/leads", token=token,
            json_body={"contact_id": contact_ids[0], "source": "qa-web-form",
                       "status": "new", "priority": "high", "score": 72},
            expected=(201, 409), phase="seed", module="Lead Intelligence & Sales",
            scenario="Create a synthetic lead",
        )
        lead_id = lead.get("id") if isinstance(lead, dict) else None
        if not lead_id:
            _, existing_leads, _ = call("GET", f"/api/v1/workspaces/{wid}/leads", token=token,
                                        expected=(200,), phase="seed",
                                        module="Lead Intelligence & Sales",
                                        scenario="Reuse existing synthetic lead on rerun")
            if isinstance(existing_leads, list) and existing_leads:
                lead_id = existing_leads[0].get("id")
        call("GET", f"/api/v1/workspaces/{wid}/leads", token=token,
             expected=(200,), phase="sales", module="Lead Intelligence & Sales",
             scenario="List leads")
        if lead_id:
            call("POST", f"/api/v1/workspaces/{wid}/leads/{lead_id}/qualify", token=token,
                 expected=(200,), phase="sales", module="Lead Intelligence & Sales",
                 scenario="Qualify the lead")
            call("POST", f"/api/v1/workspaces/{wid}/leads/{lead_id}/convert", token=token,
                 expected=(200,), phase="sales", module="Lead Intelligence & Sales",
                 scenario="Convert qualified lead to customer")
        call("POST", f"/api/v1/workspaces/{wid}/outreach-drafts", token=token,
             json_body={"contact_id": contact_ids[-1],
                        "subject_template": "QA draft for {{contact.full_name}}",
                        "body_template": "This is a synthetic draft. No message is sent."},
             expected=(201,), phase="sales", module="Lead Intelligence & Sales",
             scenario="Create an outreach DRAFT only (never sent)")
        call("GET", f"/api/v1/workspaces/{wid}/outreach-drafts", token=token,
             expected=(200,), phase="sales", module="Lead Intelligence & Sales",
             scenario="Review-only draft outbox")

    # ---------------- Phase 4: intake workflow ----------------
    call("POST", f"/api/v1/workspaces/{wid}/intake/website-form", token=token,
         json_body={"email": "intake.qa@novara.invalid", "full_name": "IntakeQA Tester",
                    "company": "Synthetic Intake Co", "message": "Synthetic QA submission.",
                    "source": "qa-website-form"},
         expected=(201,), phase="workflow", module="Command Center",
         scenario="Website form -> contact/lead intake (Workflow A step 1)")

    # ---------------- Phase 5: tasks / notifications ----------------
    if contact_ids:
        call("POST", f"/api/v1/workspaces/{wid}/tasks", token=token,
             json_body={"title": "QA follow-up with synthetic contact",
                        "contact_id": contact_ids[0], "priority": "medium"},
             expected=(201,), phase="workflow", module="Lead Intelligence & Sales",
             scenario="Create a sales follow-up task")
    call("GET", f"/api/v1/workspaces/{wid}/tasks", token=token,
         expected=(200,), phase="workflow", module="Lead Intelligence & Sales",
         scenario="Tasks persist and are listable")
    call("GET", f"/api/v1/workspaces/{wid}/notifications", token=token,
         expected=(200,), phase="module", module="Notifications",
         scenario="Notification listing responds")
    call("GET", f"/api/v1/workspaces/{wid}/events", token=token,
         expected=(200,), phase="module", module="Command Center",
         scenario="Activity feed persists business events")

    # ---------------- Phase 6: broad GET surface sweep ----------------
    spec = json.loads((OUT / "evidence" / "openapi.json").read_text(encoding="utf-8"))
    def synthetic_query(name: str, schema: dict):
        """Supply a deterministic harmless value for a required query parameter."""
        t = schema.get("type") or "string"
        fmt = schema.get("format", "")
        if t == "integer" or t == "number":
            return 1
        if t == "boolean":
            return False
        low = name.lower()
        if "from" in low or low.endswith("_after") or low == "start":
            return "2026-01-01T00:00:00Z"
        if "to" in low or low.endswith("_before") or low == "end":
            return "2026-12-31T23:59:59Z"
        if "date" in low:
            return "2026-11-24"
        if "email" in low:
            return "qa.owner@novara.invalid"
        if "token" in low or "key" in low:
            return "qa-synthetic-token"
        if low in ("q", "query", "search", "term", "name", "slug"):
            return "qa"
        if "id" in low:
            return "qa-synthetic-id"
        if "permission" in low:
            return "read"
        if "role" in low:
            return "owner"
        if "type" in low:
            return "contact"
        if "limit" in low:
            return 10
        return "qa"

    swept = 0
    for path, ops in spec["paths"].items():
        if "get" not in ops:
            continue
        op = ops["get"]
        if path.endswith("/stream") or "stream" in op.get("operationId", "").lower():
            continue  # server-sent-event endpoints are intentionally long-lived
        params = op.get("parameters", [])
        pnames = {p.get("name") for p in params if p.get("in") == "path"}
        if pnames and pnames != {"workspace_id"}:
            continue
        if "{workspace_id}" not in path:
            continue
        url = path.replace("{workspace_id}", wid)
        query = {}
        for p in params:
            if p.get("in") == "query" and p.get("required"):
                query[p["name"]] = synthetic_query(p["name"], p.get("schema", {}))
        started = time.monotonic()
        try:
            r = client.get(url, headers={"Authorization": f"Bearer {token}"}, params=query)
            status = r.status_code
            observed = r.text[:600]
        except Exception as exc:
            status, observed = "ERR", f"{type(exc).__name__}: {exc}"
        # The sweep feeds deliberately synthetic identifiers/tokens. A domain
        # rejection (not found / invalid / tampered / unsupported / key required)
        # is correct behavior and is recorded openly with its raw status.
        rejection_markers = (
            "not found", "invalid", "tampered", "unsupported", "required",
            "expired", "does not exist", "forbidden", "unauthorized",
        )
        domain_rejection = (
            isinstance(status, int) and 400 <= status < 500
            and any(m in observed.lower() for m in rejection_markers)
        )
        acceptable = status == 200 or domain_rejection
        note = ("Live GET sweep with synthetic params; not a feature acceptance test"
                + (" | expected domain rejection of synthetic input" if domain_rejection else ""))
        record("surface-sweep", "API surface", "Read-only module endpoint responds",
               "GET", url + (("?" + "&".join(f"{k}={v}" for k, v in query.items())) if query else ""),
               "200, or a domain rejection for synthetic input", status, observed,
               "PASS" if acceptable else "FAIL", note)
        swept += 1
        if swept >= 260:
            break

    # ---------------- Phase 7: tampered token / unauthorized ----------------
    call("GET", f"/api/v1/workspaces/{wid}/contacts", token="not-a-real-token",
         expected=(401, 403), phase="security", module="Settings & Administration",
         scenario="Unauthorized API access is rejected")
    print("\nDONE. records:", _seq)


if __name__ == "__main__":
    main()
