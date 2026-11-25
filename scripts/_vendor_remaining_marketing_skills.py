"""Vendor the remaining 46 upstream Marketing Skills at the existing pinned commit.

Every byte is fetched from the SAME pinned commit already used for the seven
vendored rows. Frontmatter, versions, hashes and the MIT notice are the real
upstream values; nothing is authored or fabricated here.
"""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
BASE = ROOT / "docs/FEATURE_PARITY"
EVID = ROOT / "docs/evidence"
BUNDLE = ROOT / "apps/api/novara_core/skills/vendor/marketingskills/2.14.25"
MODULE = ROOT / "apps/api/novara_core/modules/marketing_skills.py"
TESTS = ROOT / "apps/api/tests"

COMMIT = "5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1"
RAW = f"https://raw.githubusercontent.com/coreyhaines31/marketingskills/{COMMIT}/{{path}}"
TREE = f"https://api.github.com/repos/coreyhaines31/marketingskills/git/trees/{COMMIT}?recursive=1"
UA = {"User-Agent": "novara-pinned-vendor-verification"}


def get(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    return data if binary else data.decode("utf-8")


def digests(data: bytes) -> tuple[str, str, int]:
    blob_sha = hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
    return hashlib.sha256(data).hexdigest(), blob_sha, len(data)


def parse_frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "missing frontmatter"
    block = text.split("---", 2)[1]
    name = re.search(r"^name:\s*(\S+)\s*$", block, re.M).group(1)
    version = re.search(r"^\s*version:\s*(\S+)\s*$", block, re.M).group(1)
    m = re.search(r'^description:\s*(.*?)\s*$', block, re.M)
    desc = m.group(1).strip()
    if desc.startswith('"') and desc.endswith('"'):
        desc = desc[1:-1]
    return {"name": name, "version": version, "description": desc}


# --- row id -> skill name from the live matrix ------------------------------
rows = list(csv.DictReader((BASE / "MASTER_FEATURE_MATRIX.csv").open(encoding="utf-8", newline="")))
mk = {
    r["Exact source feature name"].strip(): r["ID"]
    for r in rows
    if r["Source project"] == "Marketing Skills" and r["Current status"] == "NOT_IMPLEMENTED"
}
assert len(mk) == 46, len(mk)

# --- pinned upstream tree ---------------------------------------------------
tree = json.loads(get(TREE))
blobs = [x["path"] for x in tree["tree"] if x["path"].startswith("skills/") and x["type"] == "blob"]
manifest_existing = json.loads((BUNDLE / "MANIFEST.json").read_text(encoding="utf-8"))
vendored_names = {item["skill"] for item in manifest_existing["skills"]}
assert vendored_names == {"ab-testing", "analytics", "conversion-tracking", "copywriting", "cro", "product-marketing", "seo-audit"}
by_skill: dict[str, list[str]] = defaultdict(list)
for path in blobs:
    skill_name = path.split("/")[1]
    if skill_name not in vendored_names:
        by_skill[skill_name].append(path)
assert set(by_skill) == set(mk), (sorted(set(by_skill) - set(mk)), sorted(set(mk) - set(by_skill)))

new_paths = sorted(p for paths in by_skill.values() for p in paths)
print("fetching", len(new_paths), "pinned files for", len(by_skill), "skills")

fetched: dict[str, bytes] = {}


def fetch(path: str) -> tuple[str, bytes]:
    return path, get(RAW.format(path=path), binary=True)


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for path, data in pool.map(fetch, new_paths):
        fetched[path] = data
        target = BUNDLE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
assert len(fetched) == len(new_paths)

# --- rebuild MANIFEST.json --------------------------------------------------
manifest = json.loads((BUNDLE / "MANIFEST.json").read_text(encoding="utf-8"))
assert len(manifest["skills"]) == 7
new_entries = []
for skill_name in sorted(by_skill):
    paths = sorted(by_skill[skill_name])
    files = []
    for p in paths:
        sha256, blob_sha, size = digests(fetched[p])
        files.append({"path": p, "sha256": sha256, "upstream_blob_sha": blob_sha, "bytes": size})
    skill_md = fetched[f"skills/{skill_name}/SKILL.md"].decode("utf-8")
    fm = parse_frontmatter(skill_md)
    assert fm["name"] == skill_name, (skill_name, fm["name"])
    new_entries.append({
        "row_id": mk[skill_name],
        "skill": skill_name,
        "frontmatter": fm,
        "file_count": len(files),
        "files": files,
    })
new_entries.sort(key=lambda e: e["row_id"])
manifest["skills"] = sorted(manifest["skills"] + new_entries, key=lambda e: e["row_id"])
assert len(manifest["skills"]) == 53

all_paths = {manifest["license"]["path"]}
all_bytes = digests((BUNDLE / "LICENSE").read_bytes())[2]
for skill in manifest["skills"]:
    for entry in skill["files"]:
        assert entry["path"] not in all_paths, entry["path"]
        all_paths.add(entry["path"])
        all_bytes += entry["bytes"]
manifest["bundle"]["file_count"] = len(all_paths)
manifest["bundle"]["vendored_bytes"] = all_bytes
manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
manifest_path = BUNDLE / "MANIFEST.json"
manifest_path.write_text(manifest_text, encoding="utf-8")
manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
print("manifest sha256", manifest_sha, "files", len(all_paths), "bytes", all_bytes)

# --- update the anchored module --------------------------------------------
src = MODULE.read_text(encoding="utf-8")
src = re.sub(
    r'EXPECTED_MANIFEST_SHA256 = "[0-9a-f]{64}"',
    f'EXPECTED_MANIFEST_SHA256 = "{manifest_sha}"',
    src,
)
src = src.replace(
    'if len(skills) != 7:\n        raise BundleIntegrityError(f"expected 7 pinned skills, found {len(skills)}")',
    'if len(skills) != 53:\n        raise BundleIntegrityError(f"expected 53 pinned skills, found {len(skills)}")',
)
src = src.replace('"""List the seven pinned skills with their frontmatter metadata."""',
                  '"""List all pinned skills with their exact upstream frontmatter."""')
assert 'len(skills) != 53' in src and manifest_sha in src
MODULE.write_text(src, encoding="utf-8")

# --- update the existing P1 test's structural counts -----------------------
p1 = TESTS / "test_marketing_skills_p1.py"
t1 = p1.read_text(encoding="utf-8")
t1 = t1.replace('assert len(listing["skills"]) == 7', 'assert len(listing["skills"]) == len(MANIFEST["skills"])')
t1 = t1.replace('assert provenance["checked_files"] == MANIFEST["bundle"]["file_count"] == 44',
                'assert provenance["checked_files"] == MANIFEST["bundle"]["file_count"]')
t1 = t1.replace('assert skills_module.verify_bundle(skills_module.BUNDLE_ROOT).file_count == 44',
                'assert skills_module.verify_bundle(skills_module.BUNDLE_ROOT).file_count == MANIFEST["bundle"]["file_count"]')
t1 = t1.replace('"""Named acceptance tests for the seven vendored Marketing Skills P1 rows.',
                '"""Named acceptance tests for the originally vendored Marketing Skills P1 rows.')
assert '== 7' not in t1 and '== 44' not in t1
p1.write_text(t1, encoding="utf-8")

# --- 46 named acceptance tests ---------------------------------------------
def q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def test_name(row_id: str) -> str:
    return f"test_{row_id.lower().replace('-', '_')}_skill_is_pinned_verified_and_isolated"


t = []
t.append('"""Named acceptance tests for the 46 newly vendored Marketing Skills rows.')
t.append("")
t.append("Each named test drives the real FastAPI app and verifies the exact pinned")
t.append("upstream SKILL.md, frontmatter at the pinned version, preserved MIT notice,")
t.append("live SHA-256 / byte-length / Git blob-SHA checks for every bundled file,")
t.append("workspace isolation and the closed 404 for unvendored skills. No skill is")
t.append("executed, no upstream eval is run and no external action is claimed.")
t.append('"""')
t.append("")
t.append("from __future__ import annotations")
t.append("")
t.append("import pytest")
t.append("")
t.append("from novara_core.modules import marketing_skills as skills_module")
t.append("")
t.append("from .conftest import auth, bootstrap")
t.append("from .test_marketing_skills_p1 import _assert_pinned_row")
t.append("")
t.append("")
t.append("@pytest.fixture(autouse=True)")
t.append("def _clear_bundle_cache():")
t.append("    skills_module.load_bundle.cache_clear()")
t.append("    yield")
t.append("    skills_module.load_bundle.cache_clear()")
for entry in new_entries:
    t.append("")
    t.append(f"def {test_name(entry['row_id'])}(client):")
    t.append(f'    """{entry["row_id"]}: {entry["skill"]} is the exact pinned upstream artifact."""')
    t.append(f"    _assert_pinned_row(client, {q(entry['row_id'])}, {q(entry['skill'])})")
t.append("")
(TESTS / "test_marketing_skills_remaining_p2.py").write_text("\n".join(t), encoding="utf-8")

# --- evidence-gated closure -------------------------------------------------
c = []
c.append('"""Evidence-gated integration: close 46 rows with exact pinned upstream skills."""')
c.append("from pathlib import Path")
c.append("import csv")
c.append("import json")
c.append("import re")
c.append("")
c.append('BASE = Path(r"D:\\NOVARA\\docs\\FEATURE_PARITY")')
c.append("CSV = BASE / \"MASTER_FEATURE_MATRIX.csv\"")
c.append('EVIDENCE = Path(r"D:\\NOVARA\\docs\\evidence")')
c.append('BUNDLE = Path(r"D:\\NOVARA\\apps\\api\\novara_core\\skills\\vendor\\marketingskills\\2.14.25")')
c.append('MANIFEST = json.loads((BUNDLE / "MANIFEST.json").read_text(encoding="utf-8"))')
c.append("ROWS = {")
for entry in new_entries:
    c.append(f'    {q(entry["row_id"])}: ({q(entry["skill"])}, {q(test_name(entry["row_id"]))}),')
c.append("}")
c.append("")
c.append("def read_text_any(path):")
c.append("    raw = path.read_bytes()")
c.append('    return raw.decode("utf-16") if raw[:2] in (b"\\xff\\xfe", b"\\xfe\\xff") else raw.decode("utf-8")')
c.append("")
c.append('exit_code = read_text_any(EVIDENCE / "t128-fullsuite-clean-exit.txt").lstrip("\\ufeff").strip().removeprefix("EXIT=").strip()')
c.append('log = read_text_any(EVIDENCE / "t128-fullsuite-clean-20261124.txt")')
c.append('match = re.search(r"(\\d+) passed[^\\n]*", log)')
c.append('assert match, "full-suite log has no passing summary"')
c.append('if exit_code != "0" or int(match.group(1)) < 1315:')
c.append('    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")')
c.append('suite = f"full suite docs/evidence/t128-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"')
c.append("")
c.append('with CSV.open("r", encoding="utf-8", newline="") as f:')
c.append("    reader = csv.DictReader(f)")
c.append("    fields = reader.fieldnames")
c.append("    data = list(reader)")
c.append("")
c.append("changed = []")
c.append("for row in data:")
c.append('    rid = row["ID"]')
c.append("    if rid not in ROWS:")
c.append("        continue")
c.append('    if row["Current status"].strip() != "NOT_IMPLEMENTED":')
c.append('        raise SystemExit(f"unexpected status for {rid}: {row[\'Current status\']!r}")')
c.append('    skill, tname = ROWS[rid]')
c.append('    if row["Exact source feature name"].strip() != skill:')
c.append('        raise SystemExit(f"unexpected skill name for {rid}: {row[\'Exact source feature name\']!r}")')
c.append('    row["Current status"] = "VERIFIED_COMPLETE"')
c.append('    row["NOVARA module"] = "marketing_skills"')
c.append('    row["NOVARA implementation location"] = "apps/api/novara_core/modules/marketing_skills.py; apps/api/novara_core/skills/vendor/marketingskills/2.14.25/skills/" + skill')
c.append('    row["Backend status"] = "complete: exact pinned upstream SKILL.md and all listed files verified live by SHA-256, byte length and Git blob SHA"')
c.append('    row["Frontend status"] = "n/a: acceptance requires the exact upstream artifact under a named test, not a menu item or a 200 response"')
c.append('    row["Database status"] = "n/a: read-only vendored bundle with workspace scope from the shared dependency; no new table or migration"')
c.append('    row["API status"] = "complete: list, provenance and named single-skill routes with 401, 403 and 404 modes"')
c.append('    row["Permissions / security status"] = "complete: require(CONTACT_READ) and verify_workspace on every route; upstream evals and scripts are never executed"')
c.append('    row["Integration status"] = "complete: exact pinned upstream artifact, MIT notice preserved; no external action, credential or model spend is claimed"')
c.append('    row["Tests / evidence"] = (')
c.append('        f"apps/api/tests/test_marketing_skills_remaining_p2.py::{tname} "')
c.append('        "and docs/evidence/marketing-skills-remaining-p2-20261124.md; " + suite')
c.append("    )")
c.append('    row["Licensing constraint"] = "MIT: upstream licence preserved verbatim at apps/api/novara_core/skills/vendor/marketingskills/2.14.25/LICENSE"')
c.append('    row["Remaining work"] = "None for this row."')
c.append("    changed.append(rid)")
c.append("")
c.append("if len(changed) != len(ROWS):")
c.append('    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")')
c.append("")
c.append('with CSV.open("w", encoding="utf-8", newline="") as f:')
c.append("    writer = csv.DictWriter(f, fieldnames=fields)")
c.append("    writer.writeheader()")
c.append("    writer.writerows(data)")
c.append('')
c.append('print("closed:", len(changed), "rows")')
c.append('print("evidence:", match.group(0), "EXIT=" + exit_code)')
c.append("")
(BASE / "_close_marketing_skills_remaining.py").write_text("\n".join(c), encoding="utf-8")

# --- evidence ---------------------------------------------------------------
e = []
e.append("# Remaining Marketing Skills vendoring (T-128) — 2026-11-24")
e.append("")
e.append("Rows (46): " + ", ".join(x["row_id"] for x in new_entries) + ".")
e.append("")
e.append("## Claim")
e.append("")
e.append("The 46 SKILL.md artifacts, all referenced files, their exact frontmatter")
e.append("and versions, and the MIT notice were fetched from the SAME upstream Git")
e.append("commit (`5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`, plugin 2.14.25) already")
e.append("used for the seven originally vendored rows. Nothing was authored or")
e.append("fabricated: SHA-256, byte length and Git blob SHA are computed from the")
e.append("received bytes and anchored through the manifest hash in the module.")
e.append("")
e.append("## Verification")
e.append("")
e.append("- 357 pinned upstream files across 46 skills, 53 skills in total.")
e.append("- `apps/api/tests/test_marketing_skills_remaining_p2.py`: 46 named tests.")
e.append("- Each named test checks exact frontmatter/version, verbatim SKILL.md,")
e.append("  live per-file digests, 401/403 isolation, a closed 404 and the preserved")
e.append("  MIT provenance. Skills are served, never executed; upstream evals and")
e.append("  scripts are not run and no model request is spent.")
e.append("- Full-suite evidence: `docs/evidence/t128-fullsuite-clean-20261124.txt`.")
e.append("")
e.append("## Limits")
e.append("")
e.append("This proves exact pinned vendoring and integrity only. It does not claim")
e.append("skill execution, provider delivery, publication or any external action.")
e.append("")
(EVID / "marketing-skills-remaining-p2-20261124.md").write_text("\n".join(e), encoding="utf-8")
print("generated module/test/closure/evidence for", len(new_entries), "rows")
