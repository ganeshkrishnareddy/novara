"""Evidence-gated integration: close 46 rows with exact pinned upstream skills."""
from pathlib import Path
import csv
import json
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
BUNDLE = Path(r"D:\NOVARA\apps\api\novara_core\skills\vendor\marketingskills\2.14.25")
MANIFEST = json.loads((BUNDLE / "MANIFEST.json").read_text(encoding="utf-8"))
ROWS = {
    "MK-002": ("ad-creative", "test_mk_002_skill_is_pinned_verified_and_isolated"),
    "MK-003": ("ads", "test_mk_003_skill_is_pinned_verified_and_isolated"),
    "MK-004": ("ai-seo", "test_mk_004_skill_is_pinned_verified_and_isolated"),
    "MK-006": ("aso", "test_mk_006_skill_is_pinned_verified_and_isolated"),
    "MK-007": ("attribution", "test_mk_007_skill_is_pinned_verified_and_isolated"),
    "MK-008": ("churn-prevention", "test_mk_008_skill_is_pinned_verified_and_isolated"),
    "MK-009": ("co-marketing", "test_mk_009_skill_is_pinned_verified_and_isolated"),
    "MK-010": ("cold-email", "test_mk_010_skill_is_pinned_verified_and_isolated"),
    "MK-011": ("community-marketing", "test_mk_011_skill_is_pinned_verified_and_isolated"),
    "MK-012": ("competitor-profiling", "test_mk_012_skill_is_pinned_verified_and_isolated"),
    "MK-013": ("competitors", "test_mk_013_skill_is_pinned_verified_and_isolated"),
    "MK-014": ("content-strategy", "test_mk_014_skill_is_pinned_verified_and_isolated"),
    "MK-016": ("copy-editing", "test_mk_016_skill_is_pinned_verified_and_isolated"),
    "MK-019": ("customer-research", "test_mk_019_skill_is_pinned_verified_and_isolated"),
    "MK-020": ("directory-submissions", "test_mk_020_skill_is_pinned_verified_and_isolated"),
    "MK-021": ("emails", "test_mk_021_skill_is_pinned_verified_and_isolated"),
    "MK-022": ("events", "test_mk_022_skill_is_pinned_verified_and_isolated"),
    "MK-023": ("free-tools", "test_mk_023_skill_is_pinned_verified_and_isolated"),
    "MK-024": ("image", "test_mk_024_skill_is_pinned_verified_and_isolated"),
    "MK-025": ("influencer-marketing", "test_mk_025_skill_is_pinned_verified_and_isolated"),
    "MK-026": ("launch", "test_mk_026_skill_is_pinned_verified_and_isolated"),
    "MK-027": ("lead-magnets", "test_mk_027_skill_is_pinned_verified_and_isolated"),
    "MK-028": ("link-building", "test_mk_028_skill_is_pinned_verified_and_isolated"),
    "MK-029": ("marketing-council", "test_mk_029_skill_is_pinned_verified_and_isolated"),
    "MK-030": ("marketing-ideas", "test_mk_030_skill_is_pinned_verified_and_isolated"),
    "MK-031": ("marketing-loops", "test_mk_031_skill_is_pinned_verified_and_isolated"),
    "MK-032": ("marketing-plan", "test_mk_032_skill_is_pinned_verified_and_isolated"),
    "MK-033": ("marketing-psychology", "test_mk_033_skill_is_pinned_verified_and_isolated"),
    "MK-034": ("offers", "test_mk_034_skill_is_pinned_verified_and_isolated"),
    "MK-035": ("onboarding", "test_mk_035_skill_is_pinned_verified_and_isolated"),
    "MK-036": ("paywalls", "test_mk_036_skill_is_pinned_verified_and_isolated"),
    "MK-037": ("popups", "test_mk_037_skill_is_pinned_verified_and_isolated"),
    "MK-038": ("pricing", "test_mk_038_skill_is_pinned_verified_and_isolated"),
    "MK-040": ("programmatic-seo", "test_mk_040_skill_is_pinned_verified_and_isolated"),
    "MK-041": ("prospecting", "test_mk_041_skill_is_pinned_verified_and_isolated"),
    "MK-042": ("public-relations", "test_mk_042_skill_is_pinned_verified_and_isolated"),
    "MK-043": ("referrals", "test_mk_043_skill_is_pinned_verified_and_isolated"),
    "MK-044": ("reverse-engineer-marketing", "test_mk_044_skill_is_pinned_verified_and_isolated"),
    "MK-045": ("revops", "test_mk_045_skill_is_pinned_verified_and_isolated"),
    "MK-046": ("sales-enablement", "test_mk_046_skill_is_pinned_verified_and_isolated"),
    "MK-047": ("schema", "test_mk_047_skill_is_pinned_verified_and_isolated"),
    "MK-049": ("signup", "test_mk_049_skill_is_pinned_verified_and_isolated"),
    "MK-050": ("site-architecture", "test_mk_050_skill_is_pinned_verified_and_isolated"),
    "MK-051": ("sms", "test_mk_051_skill_is_pinned_verified_and_isolated"),
    "MK-052": ("social", "test_mk_052_skill_is_pinned_verified_and_isolated"),
    "MK-053": ("video", "test_mk_053_skill_is_pinned_verified_and_isolated"),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t128-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t128-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1315:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t128-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() != "NOT_IMPLEMENTED":
        raise SystemExit(f"unexpected status for {rid}: {row['Current status']!r}")
    skill, tname = ROWS[rid]
    if row["Exact source feature name"].strip() != skill:
        raise SystemExit(f"unexpected skill name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "marketing_skills"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/marketing_skills.py; apps/api/novara_core/skills/vendor/marketingskills/2.14.25/skills/" + skill
    row["Backend status"] = "complete: exact pinned upstream SKILL.md and all listed files verified live by SHA-256, byte length and Git blob SHA"
    row["Frontend status"] = "n/a: acceptance requires the exact upstream artifact under a named test, not a menu item or a 200 response"
    row["Database status"] = "n/a: read-only vendored bundle with workspace scope from the shared dependency; no new table or migration"
    row["API status"] = "complete: list, provenance and named single-skill routes with 401, 403 and 404 modes"
    row["Permissions / security status"] = "complete: require(CONTACT_READ) and verify_workspace on every route; upstream evals and scripts are never executed"
    row["Integration status"] = "complete: exact pinned upstream artifact, MIT notice preserved; no external action, credential or model spend is claimed"
    row["Tests / evidence"] = (
        f"apps/api/tests/test_marketing_skills_remaining_p2.py::{tname} "
        "and docs/evidence/marketing-skills-remaining-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = "MIT: upstream licence preserved verbatim at apps/api/novara_core/skills/vendor/marketingskills/2.14.25/LICENSE"
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
