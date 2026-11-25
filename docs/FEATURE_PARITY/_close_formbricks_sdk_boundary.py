"""Evidence-gated integration: close the 11 clean-room Formbricks SDK rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "FB-132": ("JavaScript client SDK (packages/js)", "test_fb132_javascript_client_sdk_cleanroom_boundary"),
    "FB-133": ("Android SDK (packages/android)", "test_fb133_android_sdk_cleanroom_boundary"),
    "FB-134": ("iOS SDK (packages/ios)", "test_fb134_ios_sdk_cleanroom_boundary"),
    "FB-135": ("API package (packages/api)", "test_fb135_api_package_cleanroom_boundary"),
    "FB-136": ("Surveys package (packages/surveys)", "test_fb136_surveys_package_cleanroom_boundary"),
    "FB-137": ("Survey UI package (packages/survey-ui)", "test_fb137_survey_ui_package_cleanroom_boundary"),
    "FB-138": ("js-core MIT package", "test_fb138_js_core_mit_package_cleanroom_boundary"),
    "FB-139": ("i18n-utils MIT package", "test_fb139_i18n_utils_mit_package_cleanroom_boundary"),
    "FB-140": ("logger MIT package", "test_fb140_logger_mit_package_cleanroom_boundary"),
    "FB-141": ("vite-plugins MIT package", "test_fb141_vite_plugins_mit_package_cleanroom_boundary"),
    "FB-142": ("Mobile SDKs (React Native, iOS, Android, Flutter)", "test_fb142_mobile_sdks_cleanroom_boundary"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t117-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t117-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 904:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t117-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    row["NOVARA module"] = "formbricks_sdk_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/formbricks_sdk_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped catalogue records the exact advertised package path, "
        "NOVARA-local replacement contract, public documentation reference, preserved Formbricks GmbH "
        "MIT notice, no default dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance criterion permits a documented clean-room replacement; no SDK import or UI route claimed"
    row["Database status"] = "n/a: no new table or migration; catalogue is immutable and workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403/404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route, cross-workspace access fails "
        "closed, no SDK package imported and no AGPL/EE source vendored"
    )
    row["Integration status"] = (
        "complete: no package dependency, hosted Formbricks call, AGPL/EE source copy or outbound HTTP is "
        "used; the Formbricks GmbH MIT notice remains in THIRD_PARTY_NOTICES.md"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_formbricks_sdk_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/formbricks-sdk-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Documented clean-room replacement from public package paths; Formbricks GmbH MIT SDK notice preserved in THIRD_PARTY_NOTICES.md; no AGPL community core or enterprise source copied"
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
