"""Parse the ten validated inventories into one structured dataset.

Outputs:
  - MASTER_FEATURE_MATRIX.csv  (all 1,488 rows, one row per permanent feature ID)
  - _master_data.json          (structured rows + aggregate counts, used to author the
                                narrative deliverables from real numbers)
Read-only with respect to the SOURCES files.
"""
from pathlib import Path
import csv
import json
import re
import sys
from collections import Counter, defaultdict

if "--from-sources" not in sys.argv:
    raise SystemExit(
        "Refusing to rebuild MASTER_FEATURE_MATRIX.csv from the stale SOURCES inventories. "
        "The live matrix is maintained incrementally by evidence-gated closures; use "
        "generate_deliverables.py to regenerate narrative deliverables. Pass --from-sources "
        "only for an intentional full re-inventory."
    )

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
SRC = BASE / "SOURCES"
FILES = [
    ("01-formbricks.md", "FB", "Formbricks"),
    ("02-meilisearch.md", "MS", "Meilisearch"),
    ("03-growthbook.md", "GB", "GrowthBook"),
    ("04-papermark.md", "PM", "Papermark"),
    ("05-plane.md", "PL", "Plane"),
    ("06-mautic.md", "MT", "Mautic"),
    ("07-chatwoot.md", "CW", "Chatwoot"),
    ("08-novu.md", "NV", "Novu"),
    ("09-marketingskills.md", "MK", "Marketing Skills"),
    ("10-sellbird.md", "SB", "Sellbird"),
]
HEADER = [
    "ID", "Source repository", "Exact source feature name", "Description",
    "Source location / documentation reference", "Community availability",
    "Current status", "NOVARA module", "NOVARA implementation location",
    "Backend status", "Frontend status", "Database status", "API status",
    "Permissions / security status", "Integration status", "Tests / evidence",
    "Licensing constraint", "Priority", "Dependencies", "Remaining work",
    "Final acceptance criteria",
]
# Column shown first in the master CSV, followed by source label then the 21 contract columns.
CSV_HEADER = ["Master ID", "Source project"] + HEADER

rows = []
for fname, prefix, project in FILES:
    text = (SRC / fname).read_text(encoding="utf-8")
    lines = text.splitlines()
    hi = [i for i, l in enumerate(lines) if l.strip().startswith("| ID |")][0]
    for line in lines[hi + 2:]:
        s = line.strip()
        if s == "":
            continue
        if not s.startswith("|"):
            break
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 21:
            raise ValueError(f"{fname}: row has {len(cells)} columns: {cells[:2]}")
        rec = dict(zip(HEADER, cells))
        rec["Source project"] = project
        rec["Master ID"] = rec["ID"]
        rows.append(rec)

# Sanity: totals and uniqueness
assert len(rows) == 1488, len(rows)
assert len({r["ID"] for r in rows}) == len(rows), "duplicate IDs"

# Write master CSV
csv_path = BASE / "MASTER_FEATURE_MATRIX.csv"
with csv_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CSV_HEADER, quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in CSV_HEADER})

# Aggregates from real data
status_all = Counter(r["Current status"] for r in rows)
by_source = {}
for fname, prefix, project in FILES:
    srows = [r for r in rows if r["Source project"] == project]
    by_source[project] = {
        "prefix": prefix,
        "file": f"SOURCES/{fname}",
        "count": len(srows),
        "first_id": srows[0]["ID"],
        "last_id": srows[-1]["ID"],
        "statuses": dict(Counter(r["Current status"] for r in srows)),
        "priorities": dict(Counter(r["Priority"] for r in srows)),
        "availability": dict(Counter(r["Community availability"] for r in srows)),
        "modules": dict(Counter(r["NOVARA module"] for r in srows)),
    }
priority_all = Counter(r["Priority"] for r in rows)
availability_all = Counter(r["Community availability"] for r in rows)
module_all = Counter(r["NOVARA module"] for r in rows)

# Completion accounting
COMPLETE = {"VERIFIED_COMPLETE", "INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION"}
verified = status_all.get("VERIFIED_COMPLETE", 0)
replaced = status_all.get("INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION", 0)
implemented_unverified = status_all.get("IMPLEMENTED_UNVERIFIED", 0)
backend_only = status_all.get("BACKEND_ONLY", 0)
frontend_only = status_all.get("FRONTEND_ONLY", 0)
partial = status_all.get("PARTIALLY_IMPLEMENTED", 0)
restricted = status_all.get("LICENSING_RESTRICTED", 0)
blocked = status_all.get("EXTERNAL_DEPENDENCY_BLOCKED", 0)
not_impl = status_all.get("NOT_IMPLEMENTED", 0)
total = len(rows)
accounted_complete = verified + replaced + implemented_unverified + backend_only + frontend_only

summary = {
    "total": total,
    "by_source": by_source,
    "status_all": dict(status_all),
    "priority_all": dict(priority_all),
    "availability_all": dict(availability_all),
    "module_all": dict(module_all),
    "accounting": {
        "verified_complete": verified,
        "intentionally_replaced": replaced,
        "implemented_unverified": implemented_unverified,
        "backend_only": backend_only,
        "frontend_only": frontend_only,
        "partially_implemented": partial,
        "licensing_restricted": restricted,
        "external_dependency_blocked": blocked,
        "not_implemented": not_impl,
        "complete_or_equivalent_or_code_exists": accounted_complete,
        "complete_pct_of_total": round(100.0 * accounted_complete / total, 2),
        "verified_pct_of_total": round(100.0 * verified / total, 2),
        "remaining_not_implemented": not_impl,
        "remaining_partial": partial,
        "remaining_restricted": restricted,
        "remaining_blocked": blocked,
        "remaining_unverified": implemented_unverified,
    },
}

(BASE / "_master_data.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print("MASTER CSV:", csv_path)
print("ROWS:", total)
print("SUMMARY JSON:", BASE / "_master_data.json")
print("STATUS:", dict(status_all))
