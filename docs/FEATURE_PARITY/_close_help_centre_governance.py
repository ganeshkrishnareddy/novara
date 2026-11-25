"""Evidence-gated integration: close the eight clean-room Chatwoot help-centre rows.

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
    "CW-066": (
        "complete: gaps are derived only from stored local search events and are advisory only",
        "complete: gap refresh/report routes source local_search_events only",
    ),
    "CW-067": (
        "complete: FAQ indexing accepts only workspace-authorized documents and retains a citation for every entry",
        "complete: faq-index create/list routes with document authorization and retained citations",
    ),
    "CW-087": (
        "complete: rich-text articles carry validated embeds and metadata and create/publish/revise persists immutable revisions with access checks",
        "complete: article metadata/revision/create/patch routes with validated embeds",
    ),
    "CW-088": (
        "complete: two portals hold independent branding, categories and articles with no cross-portal leakage",
        "complete: portal branding/category/article routes scoped by portal and workspace",
    ),
    "CW-089": (
        "complete: article views and visitor search counts come from real persisted local workspace-scoped events",
        "complete: view/search recording and workspace-scoped report routes",
    ),
    "CW-090": (
        "complete: a widget surfaces published public articles and opening one never creates a support ticket",
        "complete: widget configure/list/article routes with no ticket creation",
    ),
    "CW-091": (
        "complete: private pages are invisible through every unauthenticated surface",
        "complete: visibility route plus hidden-article guards on both public article surfaces",
    ),
    "CW-092": (
        "complete: API article CRUD honours the same permissions as the staff UI",
        "complete: article CRUD routes with require() and verify_workspace parity",
    ),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t112-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t112-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 851:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t112-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "LICENSING_RESTRICTED"):
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    backend, api = ROWS[rid]
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "help_centre_governance"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/help_centre_governance.py"
    row["Backend status"] = backend
    row["Frontend status"] = "n/a: API-level acceptance criteria; no dedicated SPA view claimed for this row"
    row["Database status"] = (
        "complete: ten additive workspace-scoped hcg_* tables created by migration b7c8d9e0f1a2"
    )
    row["API status"] = api
    row["Permissions / security status"] = (
        "complete: verify_workspace on every route plus require() with CONTACT_READ/NOTE_WRITE/"
        "DOCUMENT_WRITE as appropriate; read-only members can read but not write; portal scoping, "
        "internal-page guards, cross-workspace 404/403 and allowed-host embed validation fail closed"
    )
    row["Integration status"] = (
        "complete: publishes help_centre_governance.changed events on NOVARA's shared event spine; "
        "reuses existing support portal/article and document records by reference; no Chatwoot source, "
        "hosted instance, Captain/LLM service, outbound HTTP, email or external delivery contacted"
    )
    row["Tests / evidence"] = (
        "apps/api/tests/test_chatwoot_help_centre_p2.py (8 named tests); "
        "docs/evidence/help-centre-governance-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room implementation from documented public behaviour; no Chatwoot or Captain source, paid tier or hosted service copied"
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
