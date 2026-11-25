"""Evidence-gated integration: close the eight clean-room Plane task rows.

Source of truth is MASTER_FEATURE_MATRIX.csv, matching the established practice
for prior batches (narrative deliverables are regenerated from that CSV).
The full-suite evidence string is read from the recorded run so the matrix can
never claim a result that was not actually produced.
"""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

ROWS = {
    "PL-073": (
        "complete: a completed local task leaves a durable, queryable result keyed by request_key",
        "complete: result enqueue and workspace-scoped query routes",
    ),
    "PL-076": (
        "complete: no external email is sent unless explicitly configured and authorized; default creates nothing",
        "complete: opt-in policy guard and local-only draft generation routes",
    ),
    "PL-078": (
        "complete: webhook attempts are HMAC-SHA256 signed, retried through the durable queue and auditable",
        "complete: endpoint registration, signed delivery and attempt-list routes",
    ),
    "PL-081": (
        "complete: a work-item export completes into local content and downloads only workspace-scoped items",
        "complete: export enqueue, list and guarded download routes",
    ),
    "PL-082": (
        "complete: chart export data equals the displayed aggregate from the shared series function",
        "complete: chart series and chart export enqueue routes",
    ),
    "PL-083": (
        "complete: each page edit task creates the next retrievable version",
        "complete: page-version enqueue and list routes",
    ),
    "PL-084": (
        "complete: asset metadata is created only after successful real local storage processing",
        "complete: asset processing enqueue and workspace-scoped report routes",
    ),
    "PL-086": (
        "complete: workspace seeding is repeatable and creates only the three expected defaults",
        "complete: idempotent seed enqueue and defaults-list routes",
    ),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t114-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t114-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 867:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t114-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() != "NOT_IMPLEMENTED":
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    backend, api = ROWS[rid]
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "plane_task_ledger"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/plane_task_ledger.py"
    row["Backend status"] = backend
    row["Frontend status"] = "n/a: API-level acceptance criteria; no dedicated SPA view claimed for this row"
    row["Database status"] = (
        "complete: nine additive workspace-scoped plt_* tables created by migration d9e0f1a2b3c4"
    )
    row["API status"] = api
    row["Permissions / security status"] = (
        "complete: verify_workspace on every route plus require() with EVENT_READ/"
        "WORKSPACE_MANAGE as appropriate; email opt-in needs explicit authorization, "
        "webhook secrets are stored only as hashes, and cross-workspace reads fail closed"
    )
    row["Integration status"] = (
        "complete: publishes plane_task_ledger.changed events on NOVARA's shared event spine; "
        "reuses the durable jobs table and existing project/page/storage/event records by "
        "reference; no Plane source, hosted instance, broker, outbound HTTP or external "
        "delivery contacted"
    )
    row["Tests / evidence"] = (
        "apps/api/tests/test_plane_task_ledger_p2.py (8 named tests); "
        "docs/evidence/plane-task-ledger-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room implementation from documented public behaviour; no Plane source, broker, paid tier or hosted service copied"
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(ROWS):
    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("closed:", ", ".join(changed))
print("evidence:", match.group(0), "EXIT=" + exit_code)
