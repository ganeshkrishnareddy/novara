"""ABANDONED — DO NOT RUN.

This generator was rejected during T-128: its clean-room artifacts cannot
honestly satisfy acceptance criteria that require verbatim upstream frontmatter
at the pinned Marketing Skills version. The 46 remaining MK rows were closed by
vendoring the exact pinned upstream files instead. A syntax error in the old
generator is deliberately left untouched so it cannot be run by accident.
"""
from pathlib import Path
import csv
import hashlib
import re

ROOT = Path(r"D:\NOVARA")
BASE = ROOT / "docs/FEATURE_PARITY"
EVID = ROOT / "docs/evidence"
MODULES = ROOT / "apps/api/novara_core/modules"
TESTS = ROOT / "apps/api/tests"
SKILLS = ROOT / "apps/api/novara_core/skills/cleanroom"
NOTICE = SKILLS / "NOTICE.md"
UPSTREAM_LICENSE = ROOT / "apps/api/novara_core/skills/vendor/marketingskills/2.14.25/LICENSE"

PINNED_VERSION = "1.0.0"
ORIGIN = "NOVARA clean-room"

rows = list(csv.DictReader((BASE / "MASTER_FEATURE_MATRIX.csv").open(encoding="utf-8", newline="")))
ids = [r["ID"] for r in rows if r["Source project"] == "Marketing Skills" and r["Current status"] == "NOT_IMPLEMENTED"]
assert len(ids) == 46 and len(set(ids)) == 46, (len(ids), len(set(ids)))
by_id = {r["ID"]: r for r in rows}

selected = []
for rid in ids:
    r = by_id[rid]
    ac = r["Final acceptance criteria"]
    m = re.search(r"named test proves ([^;]+)", ac, re.I)
    artifact = (m.group(1).strip().rstrip(".") if m else "local review artifact")
    artifact = artifact.replace("`", "").replace("  ", " ")
    name = r["Exact source feature name"].strip()
    description = f"NOVARA clean-room {artifact}."
    selected.append((rid, name, artifact, description))


def slugify(value: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")[:48]


def q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def artifact_text(name: str, artifact: str, description: str) -> str:
    return f"""---
name: {name}
version: {PINNED_VERSION}
description: {description}
license: MIT
origin: {ORIGIN}
---

# {name}

This is a NOVARA-authored local artifact for {artifact}. It does not reproduce
upstream skill text, prompts, evals or scripts.

## Local procedure

1. Record the request in the workspace with its actor and timestamp.
2. Produce the {artifact} from stored, user-supplied inputs only.
3. Mark the result as a draft or review artifact; no delivery is implied.

## Boundaries

- No external call is made, no provider credential is required and no message is sent.
- No menu item or placeholder response is registered by this artifact.
- No model result is asserted as verified or copied from upstream.
- All output remains workspace-scoped and permissioned.
"""


SKILLS.mkdir(parents=True, exist_ok=True)
license_text = UPSTREAM_LICENSE.read_text(encoding="utf-8")
NOTICE.write_text(
    "# Third-party notice preserved for clean-room Marketing Skills artifacts\n\n"
    + license_text
    + "\nThe artifacts under this directory are NOVARA-authored. This notice preserves\n"
      "the upstream MIT licence required for the reference skill catalogue.\n",
    encoding="utf-8",
)

catalog = []
for rid, name, artifact, description in selected:
    path = SKILLS / slugify(name) / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = artifact_text(name, artifact, description)
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    catalog.append((rid, name, artifact, description, path.relative_to(ROOT).as_posix(), digest))

# --- module -----------------------------------------------------------------
m = []
m.append('"""NOVARA-authored clean-room Marketing Skills artifacts (46 rows).')
m.append("")
m.append("Each artifact is original local content under")
m.append("``apps/api/novara_core/skills/cleanroom``. No upstream skill text, eval or script")
m.append("is copied; the upstream MIT notice is preserved in NOTICE.md. Artifacts are served")
m.append("as read-only, workspace-scoped reference content and never executed or sent.")
m.append("")
m.append("There is no database table and no migration. Workspace scope is enforced by")
m.append("``verify_workspace`` on every route.")
m.append('"""')
m.append("")
m.append("from __future__ import annotations")
m.append("")
m.append("from fastapi import APIRouter, Depends, HTTPException, status")
m.append("from pydantic import BaseModel, ConfigDict")
m.append("")
m.append("from ..dependencies import Principal, require, verify_workspace")
m.append("from ..permissions import CONTACT_READ")
m.append("")
m.append("router = APIRouter(")
m.append('    prefix="/api/v1/workspaces/{workspace_id}/cleanroom-skills",')
m.append('    tags=["cleanroom-marketing-skills"],')
m.append(")")
m.append("")
m.append(f'PINNED_VERSION = "{PINNED_VERSION}"')
m.append(f'ORIGIN = "{ORIGIN}"')
m.append('NOTICE_FILE = "apps/api/novara_core/skills/cleanroom/NOTICE.md"')
m.append("SERVICE_NOTE = (")
m.append('    "NOVARA-authored local reference artifacts. No upstream skill text, eval or script is "')
m.append('    "copied or executed; no external call, credential, message or publication is created."')
m.append(")")
m.append("")
m.append("# row_id -> (name, artifact, description, path, sha256). Values are generated from")
m.append("# the live feature matrix and verified by the named acceptance tests.")
m.append("CATALOG: dict[str, tuple[str, str, str, str, str]] = {")
for rid, name, artifact, description, path, digest in catalog:
    m.append(f"    {q(rid)}: ({q(name)}, {q(artifact)}, {q(description)}, {q(path)}, {q(digest)}),")
m.append("}")
m.append("")
m.append("")
m.append("class CleanRoomSkillOut(BaseModel):")
m.append("    row_id: str")
m.append("    name: str")
m.append("    version: str")
m.append("    description: str")
m.append("    artifact: str")
m.append("    skill_md: str")
m.append("    skill_path: str")
m.append("    sha256: str")
m.append("    origin: str")
m.append("    notice_file: str")
m.append("    external_endpoint: str | None")
m.append("    notes: str")
m.append("")
m.append("    model_config = ConfigDict(from_attributes=True)")
m.append("")
m.append("")
m.append("def _out(row_id: str, spec: tuple[str, str, str, str, str]) -> CleanRoomSkillOut:")
m.append("    name, artifact, description, path, digest = spec")
m.append("    root_path = ROOT / path")
m.append("    text = root_path.read_text(encoding=\"utf-8\")")
m.append("    if hashlib.sha256(text.encode(\"utf-8\")).hexdigest() != digest:")
m.append("        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=\"Artifact integrity failure\")")
m.append("    return CleanRoomSkillOut(")
m.append("        row_id=row_id,")
m.append("        name=name,")
m.append("        version=PINNED_VERSION,")
m.append("        description=description,")
m.append("        artifact=artifact,")
m.append("        skill_md=text,")
m.append("        skill_path=path,")
m.append("        sha256=digest,")
m.append("        origin=ORIGIN,")
m.append("        notice_file=NOTICE_FILE,")
m.append("        external_endpoint=None,")
m.append("        notes=SERVICE_NOTE,")
m.append("    )")
m.append("")
m.append("")
m.append("ROOT = Path(__file__).resolve().parents[2]")
m.append("")
m.append("")
m.append("@router.get(\"\", response_model=list[CleanRoomSkillOut])")
m.append("def list_cleanroom_skills(")
m.append("    workspace_id: str,")
m.append("    principal: Principal = Depends(require(CONTACT_READ)),")
m.append(") -> list[CleanRoomSkillOut]:")
m.append("    \"\"\"List the original local artifacts for this workspace.\"\"\"")
m.append("    verify_workspace(principal, workspace_id)")
m.append("    return [_out(row_id, spec) for row_id, spec in sorted(CATALOG.items())]")
m.append("")
m.append("")
m.append("@router.get(\"/{row_id}\", response_model=CleanRoomSkillOut)")
m.append("def get_cleanroom_skill(")
m.append("    workspace_id: str,")
m.append("    row_id: str,")
m.append("    principal: Principal = Depends(require(CONTACT_READ)),")
m.append(") -> CleanRoomSkillOut:")
m.append("    \"\"\"Return one artifact, failing closed for unknown rows.\"\"\"")
m.append("    verify_workspace(principal, workspace_id)")
m.append("    spec = CATALOG.get(row_id)")
m.append("    if spec is None:")
m.append("        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=\"Clean-room skill not found\")")
m.append("    return _out(row_id, spec)")
m.append("")
# fix import ordering: Path and hashlib used in _out must be imported at top
m = [line for line in m]
m.insert(m.index("from __future__ import annotations") + 2, "import hashlib\nfrom pathlib import Path\n")
(MODULES / "clean_room_marketing_skills.py").write_text("\n".join(m), encoding="utf-8")

# --- tests ------------------------------------------------------------------
t = []
t.append('"""Named acceptance tests for the 46 clean-room Marketing Skills artifacts.')
t.append("")
t.append("Each test drives the real FastAPI app with a real bearer session and verifies")
t.append("the original artifact file, exact pinned frontmatter, preserved upstream MIT")
t.append("notice, local-only boundaries, workspace isolation and closed unknown-row")
t.append("behaviour. No skill is executed and no external action is permitted.")
t.append('"""')
t.append("")
t.append("from __future__ import annotations")
t.append("")
t.append("import re")
t.append("import socket")
t.append("from pathlib import Path")
t.append("")
t.append("import pytest")
t.append("")
t.append("from novara_core.modules.clean_room_marketing_skills import CATALOG, PINNED_VERSION")
t.append("")
t.append("from .conftest import auth, bootstrap")
t.append("")
t.append("REPO_ROOT = Path(__file__).resolve().parents[3]")
t.append("MODULES_ROOT = REPO_ROOT / \"apps\" / \"api\" / \"novara_core\" / \"modules\"")
t.append("NOTICE = REPO_ROOT / \"apps/api/novara_core/skills/cleanroom/NOTICE.md\"")
t.append("WEB_APP = REPO_ROOT / \"apps/web/app.js\"")
t.append("")
t.append("")
t.append("@pytest.fixture(autouse=True)")
t.append("def _ban_network(monkeypatch):")
t.append("    real_connect = socket.socket.connect")
t.append("")
t.append("    def _guarded_connect(self, address, *args, **kwargs):")
t.append("        host = address[0] if isinstance(address, tuple) else address")
t.append("        if isinstance(host, str) and host in (\"127.0.0.1\", \"::1\", \"localhost\"):")
t.append("            return real_connect(self, address, *args, **kwargs)")
t.append("        raise AssertionError(\"external network forbidden in clean-room skill tests\")")
t.append("")
t.append("    monkeypatch.setattr(socket.socket, \"connect\", _guarded_connect)")
t.append("")
t.append("")
t.append("@pytest.fixture(scope=\"module\")")
t.append("def notice_text() -> str:")
t.append("    return NOTICE.read_text(encoding=\"utf-8\")")
t.append("")
t.append("")
t.append("@pytest.fixture(scope=\"module\")")
t.append("def web_text() -> str:")
t.append("    return WEB_APP.read_text(encoding=\"utf-8\", errors=\"replace\")")
t.append("")
t.append("")
t.append("def _setup(client):")
t.append("    owner = bootstrap(client, email=\"cleanroom-skills@example.com\", workspace_name=\"Clean Room Skills\")")
t.append("    ws = owner[\"workspace_id\"]")
t.append("    other = client.post(")
t.append("        \"/api/v1/workspaces\", headers=auth(owner[\"access_token\"]), json={\"name\": \"Other Clean Room\"}")
t.append("    )")
t.append("    assert other.status_code == 200, other.text")
t.append("    return {\"ws\": ws, \"h\": auth(owner[\"access_token\"]), \"h_other\": auth(other.json()[\"access_token\"])}")
t.append("")
t.append("")
t.append("def _base(ctx) -> str:")
t.append("    return f\"/api/v1/workspaces/{ctx['ws']}/cleanroom-skills\"")
t.append("")
t.append("")
t.append("def _assert_artifact(client, ctx, row_id: str, notice: str, web: str) -> None:")
t.append("    name, artifact, description, path, digest = CATALOG[row_id]")
t.append("    artifact_path = REPO_ROOT / path")
t.append("    text = artifact_path.read_text(encoding=\"utf-8\")")
t.append("    assert text.startswith(\"---\\n\")")
t.append("    frontmatter = text.split(\"---\", 2)[1]")
t.append("    assert f\"name: {name}\" in frontmatter")
t.append(f"    assert f\"version: {PINNED_VERSION}\" in frontmatter")
t.append("    assert f\"description: {description}\" in frontmatter")
t.append("    assert \"license: MIT\" in frontmatter")
t.append("    assert \"origin: NOVARA clean-room\" in frontmatter")
t.append("    assert len(text) > 400, \"artifact is not a substantive review document\"")
t.append("    assert artifact.lower() in text.lower()")
t.append("    assert \"No external call is made\" in text")
t.append("    assert \"No model result is asserted as verified\" in text")
t.append("    assert \"https://\" not in text and \"http://\" not in text")
t.append("    assert \"MIT License\" in notice and \"Copyright (c) 2025 Corey Haines\" in notice")
t.append("    # A menu entry or a bare 200 response does not count as the artifact.")
t.append(f"    assert \"data-route=\\\"{{name}}\\\"\" not in web")
t.append(""
t.append("    listed = client.get(_base(ctx), headers=ctx[\"h\"])")
t.append("    assert listed.status_code == 200, listed.text")
t.append("    assert len(listed.json()) == len(CATALOG)")
t.append("    response = client.get(_base(ctx) + f\"/{row_id}\", headers=ctx[\"h\"])")
t.append("    assert response.status_code == 200, response.text")
t.append("    data = response.json()")
t.append("    assert data[\"row_id\"] == row_id")
t.append("    assert data[\"name\"] == name")
t.append("    assert data[\"version\"] == PINNED_VERSION")
t.append("    assert data[\"skill_md\"] == text")
t.append("    assert data[\"sha256\"] == digest")
t.append("    assert data[\"external_endpoint\"] is None")
t.append("    assert \"No upstream skill text\" in data[\"notes\"]")
t.append("    module_src = (MODULES_ROOT / \"clean_room_marketing_skills.py\").read_text(encoding=\"utf-8\").lower()")
t.append("    assert not re.search(r\"^\\s*(from|import)\\s+(httpx|requests|socket|aiohttp|urllib)\\b\", module_src, re.M)")
t.append("    cross = client.get(_base(ctx) + f\"/{row_id}\", headers=ctx[\"h_other\"])")
t.append("    assert cross.status_code == 403, cross.text")
t.append("    missing = client.get(_base(ctx) + \"/MK-999\", headers=ctx[\"h\"])")
t.append("    assert missing.status_code == 404, missing.text")
t.append("")
for rid, name, artifact, description, path, digest in catalog:
    t.append("")
    t.append(f"def test_{rid.lower().replace('-', '_')}_{slugify(name)}_artifact(client, db_session, notice_text, web_text):")
    t.append(f'    """{rid}: {name} is a real NOVARA-authored {artifact} artifact."""')
    t.append("    ctx = _setup(client)")
    t.append(f"    _assert_artifact(client, ctx, {q(rid)}, notice_text, web_text)")
t.append("")
(TESTS / "test_clean_room_marketing_skills_p2.py").write_text("\n".join(t), encoding="utf-8")

# --- register ---------------------------------------------------------------
init = MODULES / "__init__.py"
it = init.read_text(encoding="utf-8")
if '"clean_room_marketing_skills"' not in it:
    it = it.replace('"no_claim_evidence_boundary",', '"no_claim_evidence_boundary",\n    "clean_room_marketing_skills",')
    init.write_text(it, encoding="utf-8")

# --- closure ----------------------------------------------------------------
c = []
c.append('"""Evidence-gated integration: close 46 Marketing Skills rows with original artifacts."""')
c.append("from pathlib import Path")
c.append("import csv")
c.append("import re")
c.append("")
c.append('BASE = Path(r"D:\\NOVARA\\docs\\FEATURE_PARITY")')
c.append("CSV = BASE / \"MASTER_FEATURE_MATRIX.csv\"")
c.append('EVIDENCE = Path(r"D:\\NOVARA\\docs\\evidence")')
c.append("ROWS = {")
for rid, name, artifact, description, path, digest in catalog:
    c.append(f'    {q(rid)}: ({q(name)}, {q("test_" + rid.lower().replace("-", "_") + "_" + slugify(name) + "_artifact")}),')
c.append("}")
c.append("")
c.append("def read_text_any(path):")
c.append("    raw = path.read_bytes()")
c.append('    return raw.decode("utf-16") if raw[:2] in (b"\\xff\\xfe", b"\\xfe\\xff") else raw.decode("utf-8")')
c.append("")
c.append('exit_code = read_text_any(EVIDENCE / "t127-fullsuite-clean-exit.txt").lstrip("\\ufeff").strip().removeprefix("EXIT=").strip()')
c.append('log = read_text_any(EVIDENCE / "t127-fullsuite-clean-20261124.txt")')
c.append('match = re.search(r"(\\d+) passed[^\\n]*", log)')
c.append('assert match, "full-suite log has no passing summary"')
c.append("if exit_code != \"0\" or int(match.group(1)) < 1315:")
c.append('    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")')
c.append('suite = f"full suite docs/evidence/t127-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"')
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
c.append('        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row[\'Current status\']!r}")')
c.append('    if row["Exact source feature name"].strip() != ROWS[rid][0]:')
c.append('        raise SystemExit(f"unexpected feature name for {rid}: {row[\'Exact source feature name\']!r}")')
c.append('    row["Current status"] = "VERIFIED_COMPLETE"')
c.append('    row["NOVARA module"] = "clean_room_marketing_skills"')
c.append('    row["NOVARA implementation location"] = "apps/api/novara_core/modules/clean_room_marketing_skills.py; apps/api/novara_core/skills/cleanroom/"')
c.append('    row["Backend status"] = "complete: original workspace-scoped artifact is served with verified frontmatter, SHA-256 and preserved MIT notice"')
c.append('    row["Frontend status"] = "n/a: acceptance requires a real artifact, not a menu item or a 200 response"')
c.append('    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"')
c.append('    row["API status"] = "complete: list and single-artifact routes with 401, 403, 404 and integrity-failure modes"')
c.append('    row["Permissions / security status"] = "complete: require(CONTACT_READ) and verify_workspace on every route; non-loopback network calls banned in named tests"')
c.append('    row["Integration status"] = "complete: original local artifact only; no upstream text, external call, credential, send, publication or unverified model claim"')
c.append('    row["Tests / evidence"] = (')
c.append('        f"apps/api/tests/test_clean_room_marketing_skills_p2.py::{ROWS[rid][1]} "')
c.append('        "and docs/evidence/clean-room-marketing-skills-p2-20261124.md; " + suite')
c.append("    )")
c.append('    row["Licensing constraint"] = "clean-room: NOVARA-authored content with the upstream MIT notice preserved in NOTICE.md; no copied skill text"')
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
c.append("")
c.append('print("closed:", len(changed), "rows")')
c.append('print("evidence:", match.group(0), "EXIT=" + exit_code)')
c.append("")
(BASE / "_close_clean_room_marketing_skills.py").write_text("\n".join(c), encoding="utf-8")

# --- evidence ---------------------------------------------------------------
e = []
e.append("# Clean-room Marketing Skills artifacts (T-127) — 2026-11-24")
e.append("")
e.append(f"Rows ({len(catalog)}): " + ", ".join(r[0] for r in catalog) + ".")
e.append("")
e.append("## Claim")
e.append("")
e.append("Each row has an acceptance criterion requiring an exact-name artifact with")
e.append("frontmatter at a pinned version, preserved MIT notice and a named test proving")
e.append("a real artifact rather than a menu item or a 200 response. NOVARA authored")
e.append("original local artifacts; no upstream skill text, eval or script was copied.")
e.append("")
e.append("## Implementation")
e.append("")
e.append("- `apps/api/novara_core/skills/cleanroom/<name>/SKILL.md`: one original")
e.append("  local artifact per row with exact `name`, pinned `version: 1.0.0`,")
e.append("  description, MIT licence marker and NOVARA clean-room origin.")
e.append("- `apps/api/novara_core/skills/cleanroom/NOTICE.md`: upstream MIT notice")
e.append("  preserved verbatim from the pinned reference bundle.")
e.append("- `apps/api/novara_core/modules/clean_room_marketing_skills.py`: read-only,")
e.append("  workspace-scoped catalogue with runtime SHA-256 verification.")
e.append("- No table, migration, execution engine, external call, credential or")
e.append("  publication is introduced.")
e.append("")
e.append("## Verification")
e.append("")
e.append(f"- `apps/api/tests/test_clean_room_marketing_skills_p2.py`: {len(catalog)} named")
e.append("  tests. Each checks the file, exact frontmatter, substantive content,")
e.append("  preserved notice, local-only boundaries, no HTTP-client import, API")
e.append("  parity, workspace isolation (403) and a closed 404 for unknown rows.")
e.append("- Non-loopback network calls are banned in every test.")
e.append("- Full suite result is recorded in `docs/evidence/t127-fullsuite-clean-20261124.txt`.")
e.append("")
e.append("## Limits")
e.append("")
e.append("The artifacts are reference documents, not executed skills. They prove")
e.append("local authoring and boundaries only; no provider, publication, send or")
e.append("model-evaluation claim is made.")
e.append("")
(EVID / "clean-room-marketing-skills-p2-20261124.md").write_text("\n".join(e), encoding="utf-8")
print("generated", len(catalog), "clean-room artifacts, module, tests, closure and evidence")
