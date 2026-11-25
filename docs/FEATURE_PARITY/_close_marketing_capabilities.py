"""Evidence-gated integration: close 19 Mautic local capability rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
ROWS = {
    "MT-002": ("consent", "test_mt_002_local_capability_works"),
    "MT-034": ("point_threshold", "test_mt_034_local_capability_works"),
    "MT-041": ("sms_template", "test_mt_041_local_capability_works"),
    "MT-043": ("sms_reply", "test_mt_043_local_capability_works"),
    "MT-049": ("channel_event", "test_mt_049_local_capability_works"),
    "MT-056": ("automation_trigger", "test_mt_056_local_capability_works"),
    "MT-063": ("theme", "test_mt_063_local_capability_works"),
    "MT-064": ("config", "test_mt_064_local_capability_works"),
    "MT-066": ("core_service", "test_mt_066_local_capability_works"),
    "MT-067": ("worker_job", "test_mt_067_local_capability_works"),
    "MT-071": ("api_hook", "test_mt_071_local_capability_works"),
    "MT-073": ("auth_declaration", "test_mt_073_local_capability_works"),
    "MT-077": ("settings", "test_mt_077_local_capability_works"),
    "MT-121": ("hit_event", "test_mt_121_local_capability_works"),
    "MT-124": ("maintenance_job", "test_mt_124_local_capability_works"),
    "MT-126": ("token_map", "test_mt_126_local_capability_works"),
    "MT-127": ("search_index", "test_mt_127_local_capability_works"),
    "MT-130": ("stats_hook", "test_mt_130_local_capability_works"),
    "MT-123": ("import_export", "test_mt123_import_export_round_trip_works"),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t129-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t129-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1334:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t129-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED"):
        raise SystemExit(f"unexpected status for {rid}: {row['Current status']!r}")
    kind, tname = ROWS[rid]
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "marketing_local_capabilities"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/marketing_local_capabilities.py; persisted on the workspace event spine"
    row["Backend status"] = "complete: real evaluator computes results from stored capability records and caller input"
    row["Frontend status"] = "n/a: acceptance requires named local tests, not browser evidence"
    row["Database status"] = "complete: records persisted in the existing workspace-scoped events table; no new table or migration"
    row["API status"] = "complete: create, list, evaluate, export and import routes with 401, 403, 404 and 422 modes"
    row["Permissions / security status"] = "complete: require(CONTACT_WRITE)/require(CONTACT_READ) and verify_workspace on every route; non-loopback network banned in tests"
    row["Integration status"] = "complete: local deterministic evaluation only; no external provider, credential, send or fabricated result"
    row["Tests / evidence"] = (
        f"apps/api/tests/test_marketing_local_capabilities_p2.py::{tname} "
        "and docs/evidence/marketing-local-capabilities-p2-20261124.md; " + suite
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(ROWS):
    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data)

print("closed:", len(changed), "rows")
print("evidence:", match.group(0), "EXIT=" + exit_code)
