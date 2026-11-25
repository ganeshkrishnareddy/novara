"""Evidence-gated integration: close the eight Plane no-unverified-default rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "PL-067": ("Optional OpenAI SDK", "test_pl067_no_external_ai_model_default"),
    "PL-109": ("Instance edition and license model", "test_pl109_no_plane_edition_logic"),
    "PL-133": ("Desktop app", "test_pl133_no_desktop_build_claim"),
    "PL-134": ("Mobile app", "test_pl134_no_mobile_build_claim"),
    "PL-151": ("MinIO/S3 object storage", "test_pl151_no_external_object_storage_default"),
    "PL-153": ("Docker Compose deployment", "test_pl153_no_container_verification_claim"),
    "PL-154": ("Kubernetes/Helm deployment", "test_pl154_no_kubernetes_helm_claim"),
    "PL-156": ("Internal @plane/* monorepo packages", "test_pl156_no_plane_monorepo_package"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t121-fullsuite-clean-exit.txt").lstrip("\ufeff").strip()
exit_code = exit_code.removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t121-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 937:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t121-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    row["NOVARA module"] = "plane_claim_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/plane_claim_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped catalogue records the negative claim with a "
        "NOVARA-local boundary, preserved Plane AGPL notice, no declared dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance is negative evidence about unverified defaults; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403/404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route, cross-workspace access fails "
        "closed, no SDK/package import, build artifact or outbound call introduced"
    )
    row["Integration status"] = (
        "complete: no Plane package, external AI model default, edition logic, desktop/mobile build, "
        "external object storage, container/deployment or @plane/* monorepo package is introduced; "
        "the Plane AGPL notice remains in THIRD_PARTY_NOTICES.md"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_plane_claim_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/plane-claim-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "AGPL-3.0-only clean-room negative evidence: no Plane source copy, package, edition logic, "
        "build artifact or unverified deployment; existing third-party notices preserved"
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
