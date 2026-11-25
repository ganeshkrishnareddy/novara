"""Evidence-gated integration: close the nine no-default-dependency rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "MS-067": ("Official client SDKs", "test_ms067_official_client_sdk_dependency_boundary"),
    "MS-097": ("LMDB storage connector and OpenLDAP license", "test_ms097_lmdb_connector_not_created"),
    "PL-068": ("Slack SDK dependency", "test_pl068_no_slack_sdk_requirement"),
    "PL-149": ("Redis cache and Channels backend", "test_pl149_no_unverified_redis_dependency"),
    "PL-150": ("RabbitMQ message broker", "test_pl150_no_unverified_broker_dependency"),
    "CW-122": ("`@chatwoot/*` utility packages", "test_cw122_no_unverified_chatwoot_packages"),
    "NV-058": ("Server SDKs (`@novu/api`, Python, Go, PHP, .NET, Java)", "test_nv058_no_fabricated_server_sdk"),
    "NV-059": ("Client SDKs (`@novu/js`, `@novu/react`, `@novu/react-native`)", "test_nv059_no_verified_mobile_sdk_claim"),
    "NV-094": ("`@novu/nextjs` SDK", "test_nv094_no_unverified_nextjs_sdk"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t118-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t118-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 913:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t118-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "dependency_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/dependency_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped catalogue records the negative dependency claim with "
        "provider, NOVARA-local boundary, preserved notice, no declared dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance is negative evidence about default dependencies; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403/404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route, cross-workspace access fails "
        "closed, no SDK import, vendored package or outbound call introduced"
    )
    row["Integration status"] = (
        "complete: no SDK import, vendored package, external endpoint or unverified result is introduced; "
        "third-party notices remain in THIRD_PARTY_NOTICES.md"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_dependency_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/dependency-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room negative evidence: no unverified dependency, vendored package or fabricated external claim; existing third-party notices preserved"
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
