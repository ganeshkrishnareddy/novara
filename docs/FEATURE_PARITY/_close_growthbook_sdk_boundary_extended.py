"""Evidence-gated integration: close the 16 extended clean-room SDK rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "GB-158": ("C# SDK", "test_gb158_csharp_sdk_boundary_and_attribution"),
    "GB-159": ("Elixir SDK", "test_gb159_elixir_sdk_boundary_and_attribution"),
    "GB-160": ("Rust SDK", "test_gb160_rust_sdk_boundary_and_attribution"),
    "GB-161": ("Kotlin JVM SDK", "test_gb161_kotlin_jvm_sdk_boundary_and_attribution"),
    "GB-162": ("Kotlin Android SDK", "test_gb162_kotlin_android_sdk_boundary_and_attribution"),
    "GB-163": ("Swift SDK", "test_gb163_swift_sdk_boundary_and_attribution"),
    "GB-164": ("Flutter SDK", "test_gb164_flutter_sdk_boundary_and_attribution"),
    "GB-165": ("React Native SDK", "test_gb165_react_native_sdk_boundary_and_attribution"),
    "GB-166": ("Roku SDK", "test_gb166_roku_sdk_boundary_and_attribution"),
    "GB-167": ("HTML script tag", "test_gb167_html_script_tag_boundary_and_attribution"),
    "GB-168": ("OpenFeature provider", "test_gb168_openfeature_provider_boundary_and_attribution"),
    "GB-169": ("Cloudflare Workers SDK", "test_gb169_cloudflare_workers_sdk_boundary_and_attribution"),
    "GB-170": ("Fastly Compute SDK", "test_gb170_fastly_compute_sdk_boundary_and_attribution"),
    "GB-171": ("Lambda@Edge SDK", "test_gb171_lambda_edge_sdk_boundary_and_attribution"),
    "GB-172": ("Vercel Flags SDK", "test_gb172_vercel_flags_sdk_boundary_and_attribution"),
    "GB-173": ("Build your own SDK spec", "test_gb173_build_your_own_sdk_spec_boundary_and_attribution"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t116-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t116-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 893:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t116-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    row["NOVARA module"] = "growthbook_sdk_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/growthbook_sdk_boundary.py"
    row["Backend status"] = (
        "complete: workspace-scoped gbsdk_boundaries records the public documentation reference, "
        "a NOVARA-local compatibility boundary and adapter name, preserved MIT attribution, "
        "no default dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance criterion is a named boundary/attribution test; no SDK import or SPA surface claimed"
    row["Database status"] = (
        "complete: no schema change; extended catalogue data in the additive gbsdk_boundaries table "
        "created by migration e0f1a2b3c4d5"
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
        f"apps/api/tests/test_growthbook_sdk_boundary_extended_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/growthbook-sdk-boundary-extended-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room compatibility boundary from public documentation; GrowthBook Inc MIT notice preserved in THIRD_PARTY_NOTICES.md; no enterprise code copied"
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
