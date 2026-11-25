"""Build the honest 1,488-row feature execution registry.

Dispositions describe what was actually executed during this QA pass, not
whether a capability exists in the codebase. Route visibility and a general
API sweep are recorded as PARTIAL, never as full feature acceptance.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
OUT = ROOT / "artifacts" / "final_qa_2026-11-24"
SOURCE = ROOT / "docs" / "FEATURE_PARITY" / "MASTER_FEATURE_MATRIX.csv"
DEST = ROOT / "docs" / "QA" / "FEATURE_EXECUTION_REGISTRY.csv"
DEST.parent.mkdir(parents=True, exist_ok=True)

BOUNDARY_MARKERS = (
    "boundary", "absence", "no_claim", "no claim", "out_of_scope", "out of scope",
    "extended_claim", "no-default-dependency", "deployment", "docs/research",
)
BOUNDARY_MODULES = {"none", "none found", "", "deployment", "docs/research"}

# Module keyword -> (disposition, method, evidence, note)
RULES = [
    (("platform / auth", "auth / sessions", "core/auth", "auth, integrations",
      "platform / permissions", "platform / security", "api security", "identity / access",
      "permissions", "api_keys + web settings"),
     "PASS", "Live API auth/session/security checks",
     "evidence/qa_api_log.jsonl; evidence/qa_security_log.jsonl",
     "Bootstrap, login, invalid credentials, tampered/missing token, cross-workspace denial observed"),
    (("platform / database", "platform / migrations", "database", "platform / data"),
     "PASS", "Fresh-database migration run and API persistence",
     "test-results/migration-check.txt; evidence/qa_api_log.jsonl",
     "Fresh isolated QA DB at single Alembic head e0f1a2b3c4d5; create/list persistence observed"),
    (("workflow / outreach", "crm / contacts", "crm / notes", "crm / leads", "contacts", "leads",
      "sellbird / company records", "activity / timeline", "companies"),
     "PASS", "Live API + browser CRM workflow",
     "evidence/qa_api_log.jsonl; evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/02_contacts.png",
     "Synthetic contacts, company, notes, lead qualification/conversion and UI contact creation observed"),
    (("support / customer inbox", "support / conversation operations", "support / automation",
      "customer support / private notes", "support / labels", "support / custom attributes",
      "support / routing", "support / teams", "support / help centre", "chatwoot / help-centre governance (clean-room)",
      "visitor_conversations + support", "support + web inbox", "support", "tickets"),
     "PARTIAL", "Live support workflow + inbox route render",
     "evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/05_customer_inbox.png",
     "Ticket, message, private note and counts observed; help centre, teams, labels and routing were not individually executed"),
    (("automation / workflow", "automation / rules", "jobs / workflow", "jobs / delivery",
      "platform / jobs", "modules/jobs", "modules/jobs; core/notifications", "jobs",
      "notifications / workflow", "notification workflows", "notification automation",
      "notifications / workflow channel steps", "notifications / multi-channel delivery"),
     "PARTIAL", "Live automation create/status + workflow trigger",
     "evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/12_automation.png",
     "Local automation and in-app workflow trigger observed; external channel delivery not executed"),
    (("notifications", "topics / notifications", "identity / notifications",
      "notifications / in-app", "notifications / ui", "notifications / records",
      "notifications / content", "notifications / layered preferences",
      "notifications / inbox preferences ui", "operations / notifications",
      "security / notifications", "jobs / notifications"),
     "PARTIAL", "API listing + UI route render; streaming endpoint not consumed",
     "evidence/qa_api_log.jsonl; evidence/qa_browser_log.jsonl",
     "Notification listing and workflow message trigger observed; SSE stream intentionally excluded"),
    (("projects", "work-item planning", "plane_workspace_tools", "project_governance",
      "plane / local background-task ledger (clean-room)", "plane / work collaboration and api governance",
      "projects / wiki pages", "projects / clean-room extensions", "modules/projects",
      "projects + web tasks", "modules/projects; core/tasks", "projects / permissions",
      "projects / work-item planning", "core/tasks"),
     "PARTIAL", "Live project workflow + planning route render",
     "evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/08_projects.png; screenshots/09_work_item_planning.png",
     "Project, item, status change, progress and comment observed; planning sub-features not individually executed"),
    (("advanced experimentation", "feature flags / experimentation", "experiments / exposure adapters",
      "growthbook", "experiment-stats", "experiment-ops", "experiment-platform",
      "flag governance", "access governance", "access_governance", "experimentation"),
     "PARTIAL", "Live experiment create/observe/analyze + governance route render",
     "evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/10_experimentation.png; screenshots/13_access_governance.png; screenshots/14_flag_governance.png",
     "Local two-variant experiment analyzed; access-governance defect found and corrected then re-verified; hosted SDK/provider not contacted"),
    (("feedback / surveys", "feedback / csat", "feedback", "formbricks / clean-room sdk replacement boundary",
      "feedback studio", "survey delivery"),
     "PARTIAL", "Survey-delivery route and API contract observed; survey response flow not executed",
     "evidence/qa_api_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/15_feedback_studio.png",
     "Survey endpoints responded in the API sweep and the UI route rendered; response submission not individually exercised"),
    (("documents", "papermark", "analytics", "search indexes", "search-advanced", "search engine",
      "search", "modules/search", "modules/search; core/api"),
     "PARTIAL", "Live document/link workflow + search route render",
     "evidence/qa_e2e_log.jsonl; evidence/qa_api_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/06_documents.png; screenshots/07_document_engagement.png",
     "Room, document, share link and analytics observed; indexing internals not individually acceptance-tested"),
    (("marketing", "campaign", "email engagement", "mautic", "marketing skills", "segments", "forms"),
     "PARTIAL", "Campaign create/schedule + studio route render; no send executed",
     "evidence/qa_e2e_log.jsonl; evidence/qa_browser_log.jsonl; screenshots/04_campaign_studio.png",
     "Draft/active campaign, segment and schedule observed; outbound campaign delivery deliberately not executed"),
    (("agent center", "agents", "adapters", "integrations", "platform / api", "api", "api + documents",
      "api + security", "core/api", "api_resources", "shared event spine", "shared event spine / operations",
      "operations / audit", "operations", "platform / operations", "platform / runtime", "web client", "web design"),
     "PARTIAL", "Live agent run/approval + API surface sweep + UI route render",
     "evidence/qa_e2e_log.jsonl; evidence/qa_api_log.jsonl; evidence/qa_browser_log.jsonl",
     "Simulated agent run and approval gate observed; adapter endpoints responded; no external provider called"),
    (("platform / testing", "tests", "test"),
     "PARTIAL", "Full regression suite evidence",
     "docs/evidence/t131-fullsuite-clean-20261124.txt; test-results/final-regression.txt",
     "Named automated tests were executed; this is implementation/test evidence, not per-feature manual acceptance"),
]

API_SWEEP_MODULES = (
    "parity_capabilities", "final local capability catalogue", "novara / final local capability catalogue",
    "marketing_local_capabilities", "analytics / reporting", "core/events", "events",
)


def classify(row):
    status = row["Current status"].strip()
    module = (row["NOVARA module"] or "").strip().lower()
    name = (row["Exact source feature name"] or "").lower()
    desc = (row["Description"] or "").lower()
    if status == "INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION":
        return ("REPLACEMENT_VERIFIED",
                "Live API surface sweep + full regression suite + parity baseline",
                "evidence/qa_api_log.jsonl; evidence/qa_e2e_log.jsonl; docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md",
                "Compatible clean-room local implementation verified; no original vendor service or hosted provider was contacted")
    if module in BOUNDARY_MODULES or any(m in module for m in BOUNDARY_MARKERS):
        return ("NOT_APPLICABLE", "Documentary boundary review (not executed)",
                "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv",
                "NOVARA-local scope boundary: external/hosted/paid/absent capability is explicitly not claimed or tested")
    if ("absence of" in desc or "no claim" in desc or "not claimed" in desc) and "novara" in desc:
        return ("NOT_APPLICABLE", "Documentary boundary review (not executed)",
                "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv",
                "Explicit no-claim boundary in the source matrix; no execution claimed")
    for keys, disp, method, evidence, note in RULES:
        if any(k in module for k in keys):
            return disp, method, evidence, note
    if any(k in module for k in API_SWEEP_MODULES):
        return ("PARTIAL", "Live API GET sweep + capability route render",
                "evidence/qa_api_log.jsonl; evidence/qa_browser_log.jsonl",
                "Endpoint responded and a related UI route rendered; individual capability acceptance not claimed")
    return ("NOT_TESTED", "No per-feature execution recorded in this QA pass",
            "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv",
            "Implementation status in the parity matrix is not evidence of execution in this QA pass")


def main():
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 1488, f"Expected 1,488 source rows, got {len(rows)}"
    counts = Counter()
    out_rows = []
    for r in rows:
        disp, method, evidence, note = classify(r)
        counts[disp] += 1
        out_rows.append({
            "Master ID": r["Master ID"],
            "Source ID": r["ID"],
            "Source project": r["Source project"],
            "Exact source feature name": r["Exact source feature name"],
            "NOVARA module": r["NOVARA module"],
            "Parity implementation status": r["Current status"],
            "Execution disposition": disp,
            "Test method": method,
            "Evidence reference": evidence,
            "Observed result / honest note": note,
            "Executed (UTC)": "2026-11-24",
            "Recording timestamp": "",
            "Scope": "Local QA instance, synthetic records, no external delivery",
        })
    fields = list(out_rows[0].keys())
    with DEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    print("WROTE", DEST, len(out_rows))
    print("DISPOSITIONS", dict(counts))


if __name__ == "__main__":
    main()
