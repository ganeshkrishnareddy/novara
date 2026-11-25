"""One-off integration: close the ten clean-room Papermark data-room rows.

Source of truth is MASTER_FEATURE_MATRIX.csv, matching the established practice
for prior batches (the narrative deliverables are regenerated from that CSV).
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
    "PM-050": (
        "complete: a data room exposes permissioned documents, visitor/link counts, links and an append-only audit event stream end to end",
        "complete: room create/list/detail routes under /data-rooms with local events",
    ),
    "PM-057": (
        "complete: nested room folders can be created, listed and deleted with parent validation",
        "complete: folder create/list/delete routes under /data-rooms/{room_id}/folders",
    ),
    "PM-058": (
        "complete: a persisted integer ordering field for room items survives reads and reordering",
        "complete: item ordering read/update routes under /data-rooms/{room_id}/order",
    ),
    "PM-059": (
        "complete: viewer groups are scoped to one room and bindable to a link",
        "complete: group create/list and link/group binding routes",
    ),
    "PM-060": (
        "complete: email and domain membership rules admit exactly the intended viewers",
        "complete: rule create/list/delete routes with rule evaluation on access",
    ),
    "PM-061": (
        "complete: per-item group view/download permissions are enforced on read",
        "complete: group item permission routes with view/download enforcement",
    ),
    "PM-062": (
        "complete: updating a link's permission set immediately changes document visibility",
        "complete: link permission update route with no cached or external state",
    ),
    "PM-064": (
        "complete: room entitlement checks deny documents belonging to another room",
        "complete: access decision route records allow and deny decisions",
    ),
    "PM-065": (
        "complete: invitation acceptance grants access only to the invited room",
        "complete: invitation create/accept routes scoped by token and email",
    ),
    "PM-066": (
        "complete: a frozen room rejects attach, detach and move mutations",
        "complete: admin-only freeze route and mutation guards",
    ),
}

def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t111-fullsuite-exit.txt").strip()
log = read_text_any(EVIDENCE / "t111-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 830:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t111-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    row["NOVARA module"] = "dataroom_governance"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/dataroom_governance.py"
    row["Backend status"] = backend
    row["Frontend status"] = "n/a: API-level acceptance criteria; no dedicated SPA view claimed for this row"
    row["Database status"] = (
        "complete: eleven additive workspace-scoped drg_* tables created by migration a7b8c9d0e1f2"
    )
    row["API status"] = api
    row["Permissions / security status"] = (
        "complete: verify_workspace on every route plus require() with DOCUMENT_READ/DOCUMENT_WRITE/"
        "DOCUMENT_ADMIN as appropriate; room scoping, group membership rules, invitation email matching, "
        "admin-only freeze and recorded access decisions fail closed"
    )
    row["Integration status"] = (
        "complete: publishes dataroom_governance.* events on NOVARA's shared event spine; reuses existing "
        "document, link and visitor records by reference; no Papermark EE source, hosted instance, outbound "
        "HTTP, email or external delivery contacted"
    )
    row["Tests / evidence"] = (
        "apps/api/tests/test_dataroom_governance_p2.py (10 named tests); "
        "docs/evidence/dataroom-governance-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room implementation from documented public behaviour; no Papermark EE source or hosted service copied"
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("closed:", ", ".join(changed))
print("evidence:", match.group(0), "EXIT=" + exit_code)
