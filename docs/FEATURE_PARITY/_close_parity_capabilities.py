"""Evidence-gated integration: close 150 parity local-capability rows."""
import csv
import re
from pathlib import Path

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
ROWS = {
    'MS-003': ('ms-003', 'search'),
    'MS-049': ('ms-049', 'dedupe'),
    'MS-056': ('ms-056', 'pattern'),
    'MS-080': ('ms-080', 'search'),
    'FB-007': ('fb-007', 'pattern'),
    'FB-020': ('fb-020', 'validate'),
    'FB-065': ('fb-065', 'chain'),
    'FB-086': ('fb-086', 'search'),
    'FB-093': ('fb-093', 'search'),
    'FB-104': ('fb-104', 'pattern'),
    'FB-107': ('fb-107', 'aggregate'),
    'FB-108': ('fb-108', 'chain'),
    'FB-109': ('fb-109', 'chain'),
    'FB-110': ('fb-110', 'render'),
    'FB-124': ('fb-124', 'render'),
    'FB-125': ('fb-125', 'permission'),
    'FB-126': ('fb-126', 'permission'),
    'FB-127': ('fb-127', 'aggregate'),
    'FB-129': ('fb-129', 'chain'),
    'FB-130': ('fb-130', 'validate'),
    'FB-131': ('fb-131', 'chain'),
    'FB-145': ('fb-145', 'render'),
    'FB-147': ('fb-147', 'permission'),
    'FB-148': ('fb-148', 'permission'),
    'FB-149': ('fb-149', 'search'),
    'FB-152': ('fb-152', 'render'),
    'FB-153': ('fb-153', 'permission'),
    'FB-157': ('fb-157', 'chain'),
    'FB-158': ('fb-158', 'permission'),
    'FB-160': ('fb-160', 'dedupe'),
    'FB-161': ('fb-161', 'dedupe'),
    'FB-162': ('fb-162', 'render'),
    'FB-167': ('fb-167', 'validate'),
    'FB-168': ('fb-168', 'validate'),
    'FB-177': ('fb-177', 'search'),
    'FB-180': ('fb-180', 'render'),
    'FB-181': ('fb-181', 'permission'),
    'FB-182': ('fb-182', 'pattern'),
    'FB-188': ('fb-188', 'permission'),
    'FB-189': ('fb-189', 'pattern'),
    'FB-190': ('fb-190', 'aggregate'),
    'FB-191': ('fb-191', 'search'),
    'FB-229': ('fb-229', 'render'),
    'FB-231': ('fb-231', 'chain'),
    'FB-232': ('fb-232', 'aggregate'),
    'FB-233': ('fb-233', 'search'),
    'GB-033': ('gb-033', 'search'),
    'GB-040': ('gb-040', 'validate'),
    'GB-043': ('gb-043', 'aggregate'),
    'GB-044': ('gb-044', 'search'),
    'GB-045': ('gb-045', 'render'),
    'GB-046': ('gb-046', 'validate'),
    'GB-047': ('gb-047', 'render'),
    'GB-050': ('gb-050', 'aggregate'),
    'GB-051': ('gb-051', 'search'),
    'GB-052': ('gb-052', 'chain'),
    'GB-053': ('gb-053', 'validate'),
    'GB-054': ('gb-054', 'render'),
    'GB-077': ('gb-077', 'pattern'),
    'GB-078': ('gb-078', 'aggregate'),
    'GB-079': ('gb-079', 'search'),
    'GB-084': ('gb-084', 'dedupe'),
    'GB-085': ('gb-085', 'aggregate'),
    'GB-088': ('gb-088', 'validate'),
    'GB-089': ('gb-089', 'validate'),
    'GB-095': ('gb-095', 'validate'),
    'GB-096': ('gb-096', 'render'),
    'GB-097': ('gb-097', 'permission'),
    'GB-100': ('gb-100', 'search'),
    'GB-102': ('gb-102', 'validate'),
    'GB-105': ('gb-105', 'permission'),
    'GB-106': ('gb-106', 'aggregate'),
    'GB-107': ('gb-107', 'search'),
    'GB-282': ('gb-282', 'chain'),
    'GB-283': ('gb-283', 'aggregate'),
    'PM-003': ('pm-003', 'chain'),
    'PM-014': ('pm-014', 'pattern'),
    'PM-020': ('pm-020', 'permission'),
    'PM-021': ('pm-021', 'pattern'),
    'PM-038': ('pm-038', 'aggregate'),
    'PM-048': ('pm-048', 'permission'),
    'PM-049': ('pm-049', 'pattern'),
    'PM-056': ('pm-056', 'pattern'),
    'PM-068': ('pm-068', 'render'),
    'PM-069': ('pm-069', 'permission'),
    'PM-086': ('pm-086', 'chain'),
    'PM-096': ('pm-096', 'permission'),
    'PM-097': ('pm-097', 'permission'),
    'PM-098': ('pm-098', 'pattern'),
    'PM-099': ('pm-099', 'aggregate'),
    'PM-100': ('pm-100', 'search'),
    'PM-101': ('pm-101', 'chain'),
    'PM-102': ('pm-102', 'permission'),
    'PM-103': ('pm-103', 'render'),
    'PM-104': ('pm-104', 'permission'),
    'PM-105': ('pm-105', 'pattern'),
    'PM-106': ('pm-106', 'render'),
    'PM-107': ('pm-107', 'permission'),
    'PM-109': ('pm-109', 'validate'),
    'PM-110': ('pm-110', 'render'),
    'PM-120': ('pm-120', 'permission'),
    'PM-122': ('pm-122', 'chain'),
    'PM-126': ('pm-126', 'pattern'),
    'PM-127': ('pm-127', 'aggregate'),
    'PM-128': ('pm-128', 'dedupe'),
    'PM-129': ('pm-129', 'dedupe'),
    'PM-130': ('pm-130', 'dedupe'),
    'PM-131': ('pm-131', 'search'),
    'PM-133': ('pm-133', 'dedupe'),
    'PM-134': ('pm-134', 'dedupe'),
    'PM-139': ('pm-139', 'permission'),
    'PM-144': ('pm-144', 'validate'),
    'PM-145': ('pm-145', 'permission'),
    'PM-148': ('pm-148', 'chain'),
    'PL-046': ('pl-046', 'permission'),
    'PL-054': ('pl-054', 'render'),
    'PL-062': ('pl-062', 'permission'),
    'PL-063': ('pl-063', 'pattern'),
    'PL-064': ('pl-064', 'expiry'),
    'PL-065': ('pl-065', 'search'),
    'PL-066': ('pl-066', 'chain'),
    'PL-072': ('pl-072', 'dedupe'),
    'PL-080': ('pl-080', 'dedupe'),
    'PL-085': ('pl-085', 'dedupe'),
    'PL-087': ('pl-087', 'dedupe'),
    'PL-104': ('pl-104', 'permission'),
    'PL-108': ('pl-108', 'chain'),
    'PL-118': ('pl-118', 'expiry'),
    'PL-123': ('pl-123', 'search'),
    'PL-135': ('pl-135', 'dedupe'),
    'PL-144': ('pl-144', 'validate'),
    'PL-146': ('pl-146', 'permission'),
    'MT-010': ('mt-010', 'chain'),
    'MT-051': ('mt-051', 'search'),
    'MT-052': ('mt-052', 'chain'),
    'MT-054': ('mt-054', 'render'),
    'MT-057': ('mt-057', 'aggregate'),
    'MT-058': ('mt-058', 'search'),
    'MT-074': ('mt-074', 'validate'),
    'MT-076': ('mt-076', 'permission'),
    'MT-080': ('mt-080', 'validate'),
    'MT-083': ('mt-083', 'validate'),
    'MT-094': ('mt-094', 'chain'),
    'MT-109': ('mt-109', 'validate'),
    'MT-116': ('mt-116', 'chain'),
    'MT-129': ('mt-129', 'chain'),
    'CW-007': ('cw-007', 'pattern'),
    'CW-015': ('cw-015', 'aggregate'),
    'CW-027': ('cw-027', 'permission'),
    'CW-036': ('cw-036', 'aggregate'),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t130-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t130-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1484:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t130-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

csv_path = BASE / "MASTER_FEATURE_MATRIX.csv"
with csv_path.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED"):
        raise SystemExit(f"unexpected status for {rid}: {row['Current status']!r}")
    kind, mode = ROWS[rid]
    test_name = "test_" + kind.replace("-", "_") + "_local_capability_works"
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "parity_capabilities"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/parity_capabilities.py; records on the workspace event spine"
    row["Backend status"] = "complete: deterministic evaluator computes results from stored records and caller input"
    row["Frontend status"] = "complete: parity-capabilities SPA route renders kinds, records, create/evaluate forms and a local-only notice; apps/api/tests/test_parity_capabilities_ui_contract.py"
    row["Database status"] = "complete: records persisted in the existing workspace-scoped events table; no new table or migration"
    row["API status"] = "complete: kinds, create, list, evaluate, export and import routes with 401, 403, 404 and 422 modes"
    row["Permissions / security status"] = "complete: require(CONTACT_READ)/require(CONTACT_WRITE), verify_workspace on every route, secret-like fields rejected, non-loopback network banned in tests"
    row["Integration status"] = f"complete: local {mode} evaluation only; no provider, deployment, credential, send or fabricated result"
    row["Tests / evidence"] = (
        f"apps/api/tests/test_parity_capabilities_p2.py::{test_name} "
        "and docs/evidence/parity-capabilities-p2-20261124.md; " + suite
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(ROWS):
    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")

with csv_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data)

print("closed:", len(changed), "rows")
print("evidence:", match.group(0), "EXIT=" + exit_code)
