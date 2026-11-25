"""Evidence-gated integration: close the ten clean-room GrowthBook SDK rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

SDK_NAMES = {
    "GB-148": "JavaScript SDK",
    "GB-149": "React SDK",
    "GB-150": "Next.js SDK",
    "GB-151": "Vue SDK",
    "GB-152": "Node.js SDK",
    "GB-153": "Python SDK",
    "GB-154": "Ruby SDK",
    "GB-155": "PHP SDK",
    "GB-156": "Java SDK",
    "GB-157": "Go SDK",
}

TEST_SLUGS = {
    "GB-148": "javascript",
    "GB-149": "react",
    "GB-150": "nextjs",
    "GB-151": "vue",
    "GB-152": "nodejs",
    "GB-153": "python",
    "GB-154": "ruby",
    "GB-155": "php",
    "GB-156": "java",
    "GB-157": "go",
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t115-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t115-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 877:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t115-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    rid = row["ID"]
    if rid not in SDK_NAMES:
        continue
    if row["Current status"].strip() != "NOT_IMPLEMENTED":
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "growthbook_sdk_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/growthbook_sdk_boundary.py"
    row["Backend status"] = (
        "complete: workspace-scoped gbsdk_boundaries records the public documentation reference, "
        "a NOVARA-local compatibility boundary and adapter name, preserved MIT attribution, "
        "no default dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance criterion is a named boundary/attribution test; no SDK import or SPA surface claimed"
    row["Database status"] = (
        "complete: one additive workspace-scoped gbsdk_boundaries table created by migration e0f1a2b3c4d5"
    )
    row["API status"] = (
        "complete: idempotent seed, list and single-boundary lookup routes with 403/404/422 failure modes"
    )
    row["Permissions / security status"] = (
        "complete: require(WORKSPACE_MANAGE) for seed and require(EVENT_READ) for reads, verify_workspace "
        "on every route, cross-workspace reads fail closed, no SDK package imported"
    )
    row["Integration status"] = (
        "complete: publishes growthbook_sdk_boundary.changed on NOVARA's shared event spine; no GrowthBook "
        "SDK package, hosted endpoint, licence server, warehouse or outbound HTTP is used"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_growthbook_sdk_boundary_p2.py::test_{rid.lower().replace('-', '')}_{TEST_SLUGS[rid]}_sdk_boundary_and_attribution "
        "and docs/evidence/growthbook-sdk-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room compatibility boundary from public documentation; GrowthBook Inc MIT notice preserved in THIRD_PARTY_NOTICES.md; no enterprise code copied"
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(SDK_NAMES):
    raise SystemExit(f"expected {len(SDK_NAMES)} rows, found {len(changed)}")

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("closed:", ", ".join(changed))
print("evidence:", match.group(0), "EXIT=" + exit_code)
