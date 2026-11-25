"""One-off integration: close the eight clean-room project-governance P2 rows.

Source of truth is MASTER_FEATURE_MATRIX.csv, matching the established practice
for prior batches (the narrative deliverables are regenerated from that CSV).
"""
from pathlib import Path
import csv

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"

ROWS = {
    "PL-034": (
        "complete: persisted project status posts carry health, title and body with reactions and comments",
        "complete: create/list updates, add reaction, add comment under /project-governance/updates",
    ),
    "PL-095": (
        "complete: workspace-scoped wiki pages with create/read/patch and owner/member visibility rules",
        "complete: create/read/patch wiki routes under /project-governance/wiki",
    ),
    "PL-106": (
        "complete: teamspaces group workspace members and linked projects without changing project ownership",
        "complete: teamspace create, member add, project link and list routes",
    ),
    "PL-119": (
        "complete: multiple per-project workflows with states and rule-checked transitions; illegal reverse transition rejected",
        "complete: workflow create and transition routes under /project-governance/workflows",
    ),
    "PL-120": (
        "complete: approval requests restricted to the assigned approver; owner cannot decide for someone else; decision audited",
        "complete: approval create/decide/list routes under /project-governance/approvals",
    ),
    "PL-128": (
        "complete: private dashboards invisible to other workspace members; owner-only visibility enforced",
        "complete: dashboard create/list routes under /project-governance/dashboards",
    ),
    "PL-129": (
        "complete: dashboard release creates a read-only token; invalidate removes access immediately",
        "complete: local release/invalidate/shared-token routes (no external publish surface)",
    ),
    "PL-140": (
        "complete: epics group child work items through a local parent/child model without importing Plane type configuration",
        "complete: epic create, child attach and list routes under /project-governance/epics",
    ),
}

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    backend, api = ROWS[rid]
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "project_governance"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/project_governance.py"
    row["Backend status"] = backend
    row["Frontend status"] = "n/a: API-level acceptance criteria; no dedicated SPA view claimed for this row"
    row["Database status"] = "complete: workspace-scoped additive tables created by migration d5e6f7a8b9c0"
    row["API status"] = api
    row["Permissions / security status"] = (
        "complete: verify_workspace with require(TASK_READ/TASK_WRITE/WORKSPACE_MANAGE); "
        "workspace isolation; private dashboards owner-only; approvals limited to the assigned approver"
    )
    row["Integration status"] = (
        "complete: local project_governance.* events on NOVARA's audit bus; "
        "no Plane source, hosted API, paid configuration or external service contacted"
    )
    row["Tests / evidence"] = (
        "apps/api/tests/test_project_governance_p2.py (8 named tests); "
        "docs/evidence/project-governance-p2-20261124.md; "
        "full suite docs/evidence/t108-fullsuite-clean-20261124.txt EXIT=0, 823 passed"
    )
    row["Licensing constraint"] = (
        "Clean-room implementation from documented public behaviour; no paid Plane source or type configuration copied"
    )
    changed.append(rid)

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("closed:", ", ".join(changed))
