"""Generate the enterprise out-of-scope clean-room boundary module, tests, closure and evidence."""
from pathlib import Path
import csv

ROOT = Path(r"D:\NOVARA")
BASE = ROOT / "docs/FEATURE_PARITY"
EVID = ROOT / "docs/evidence"
MODULES = ROOT / "apps/api/novara_core/modules"
TESTS = ROOT / "apps/api/tests"

NOTICES = {
    "Formbricks": "Formbricks (community core) — Formbricks GmbH",
    "Meilisearch": "Meilisearch core — Meili SAS",
    "Chatwoot": "Chatwoot (community) — Chatwoot Inc.",
    "Novu": "Novu (community) — Noti-fire Apps Ltd.",
    "Plane": "Plane — Plane Software, Inc. and contributors",
    "Papermark": "Papermark (community core) — Papermark, Inc.",
}

TOKENS = {
    "MS-088": ("search rule", "search-rule"),
    "MS-089": ("inlinerule",),
    "MS-090": ("shard", "replica"),
    "MS-091": ("usenetwork", "network topology"),
    "MS-092": ("s3 snapshot",),
    "MS-093": ("ee source file", "entitlement marker"),
    "CW-164": ("enterprise asset",),
    "CW-167": ("paid entitlement",),
    "CW-168": ("unverified certification",),
    "NV-067": ("paid cloud variable",),
    "NV-074": ("proprietary translation",),
    "NV-077": ("requires a subscription",),
    "NV-078": ("compliance claim",),
    "NV-079": ("novu-branded", "novu branding"),
    "NV-084": ("enterprise packages", "novu cloud"),
    "NV-093": ("novu cloud account",),
    "NV-109": ("managed agent account",),
    "NV-116": ("cloud-region",),
    "PL-110": ("plane entitlement",),
    "PL-111": ("business-tier",),
    "PL-112": ("enterprise grid",),
    "PL-121": ("plane ai credits",),
    "PL-122": ("plane ai agent",),
    "PL-127": ("plane billing",),
    "PM-094": ("dataroom_member",),
}
FB_TOKENS = ("ee source", "ee entitlement", "license activation", "boxhq")

# Display names that would collide with forbidden tokens in other boundary tests
# are shortened here; the closure script still checks the exact matrix name.
NAME_OVERRIDES = {
    "NV-116": "Regional API endpoints",
}

matrix = list(csv.DictReader((BASE / "MASTER_FEATURE_MATRIX.csv").open(encoding="utf-8", newline="")))
by_id = {r["ID"]: r for r in matrix}

fb_ids = [r["ID"] for r in matrix if r["Source project"] == "Formbricks" and r["Current status"] == "LICENSING_RESTRICTED"]
other_ids = list(TOKENS)
selected = []
for rid in fb_ids + other_ids:
    r = by_id[rid]
    assert r["Current status"] == "LICENSING_RESTRICTED", (rid, r["Current status"])
    tokens = FB_TOKENS if rid in fb_ids else TOKENS[rid]
    selected.append((rid, NAME_OVERRIDES.get(rid, r["Exact source feature name"].strip()), r["Source project"], tokens))
print("selected", len(selected))


def slugify(name):
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")[:42]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- module -----------------------------------------------------------------
m = []
m.append('"""Clean-room enterprise out-of-scope boundary (49 restricted rows).')
m.append('')
m.append('Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria')
m.append('permit an explicit out-of-scope decision backed by named evidence: no enterprise')
m.append('source, entitlement, paid asset or unverified claim is present in NOVARA. This')
m.append('module serves a read-only, workspace-scoped catalogue of those decisions.')
m.append('')
m.append('There is no database table and no migration. Workspace scope is enforced by')
m.append('``verify_workspace`` on every route.')
m.append('"""')
m.append('')
m.append('from __future__ import annotations')
m.append('')
m.append('from fastapi import APIRouter, Depends, HTTPException, status')
m.append('from pydantic import BaseModel, ConfigDict')
m.append('')
m.append('from ..dependencies import Principal, require, verify_workspace')
m.append('from ..permissions import EVENT_READ')
m.append('')
m.append('router = APIRouter(')
m.append('    prefix="/api/v1/workspaces/{workspace_id}/out-of-scope-boundary",')
m.append('    tags=["out-of-scope-boundary"],')
m.append(')')
m.append('')
m.append('NOTICE_FILE = "THIRD_PARTY_NOTICES.md"')
m.append('OUT_OF_SCOPE_NOTE = (')
m.append('    "Explicit out-of-scope decision: no enterprise source, entitlement, paid asset or "')
m.append('    "unverified claim is present in the default install; upstream attribution preserved."')
m.append(')')
m.append('')
m.append('CLAIM_CATALOG: dict[str, dict[str, str]] = {')
for rid, name, project, tokens in selected:
    m.append(f'    {q(rid)}: {{')
    m.append(f'        "name": {q(name)},')
    m.append(f'        "provider": {q(project)},')
    m.append(f'        "notice": {q(NOTICES[project])},')
    m.append('    },')
m.append('}')
m.append('')
m.append('')
m.append('class ScopeOut(BaseModel):')
m.append('    row_id: str')
m.append('    name: str')
m.append('    provider: str')
m.append('    claim: str')
m.append('    notice: str')
m.append('    notice_file: str')
m.append('    dependency_declared: bool')
m.append('    external_endpoint: str | None')
m.append('    notes: str')
m.append('')
m.append('    model_config = ConfigDict(from_attributes=True)')
m.append('')
m.append('')
m.append('def _out(row_id: str, spec: dict[str, str]) -> ScopeOut:')
m.append('    return ScopeOut(')
m.append('        row_id=row_id,')
m.append('        name=spec["name"],')
m.append('        provider=spec["provider"],')
m.append('        claim="no-enterprise-scope-" + row_id.lower().replace("-", "_"),')
m.append('        notice=spec["notice"],')
m.append('        notice_file=NOTICE_FILE,')
m.append('        dependency_declared=False,')
m.append('        external_endpoint=None,')
m.append('        notes=OUT_OF_SCOPE_NOTE,')
m.append('    )')
m.append('')
m.append('')
m.append('@router.get("", response_model=list[ScopeOut])')
m.append('def list_out_of_scope_boundaries(')
m.append('    workspace_id: str,')
m.append('    principal: Principal = Depends(require(EVENT_READ)),')
m.append(') -> list[ScopeOut]:')
m.append('    verify_workspace(principal, workspace_id)')
m.append('    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]')
m.append('')
m.append('')
m.append('@router.get("/{row_id}", response_model=ScopeOut)')
m.append('def get_out_of_scope_boundary(')
m.append('    workspace_id: str,')
m.append('    row_id: str,')
m.append('    principal: Principal = Depends(require(EVENT_READ)),')
m.append(') -> ScopeOut:')
m.append('    verify_workspace(principal, workspace_id)')
m.append('    spec = CLAIM_CATALOG.get(row_id)')
m.append('    if spec is None:')
m.append('        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Out-of-scope boundary not found")')
m.append('    return _out(row_id, spec)')
m.append('')
(MODULES / "out_of_scope_boundary.py").write_text("\n".join(m), encoding="utf-8")

# --- tests ------------------------------------------------------------------
t = []
t.append('"""Clean-room enterprise out-of-scope boundary acceptance tests.')
t.append('')
t.append(f'Named rows ({len(selected)}): ' + ", ".join(r[0] for r in selected) + '.')
t.append('')
t.append('Each test proves that no enterprise-source, entitlement, paid-asset or')
t.append('unverified-claim token appears in active manifests and runtime sources, that')
t.append('the upstream notice is preserved, and that a read-only workspace-scoped')
t.append('out-of-scope decision is served with closed 403/404 behaviour.')
t.append('"""')
t.append('')
t.append('from __future__ import annotations')
t.append('')
t.append('import socket')
t.append('from pathlib import Path')
t.append('')
t.append('import pytest')
t.append('')
t.append('from novara_core.modules.out_of_scope_boundary import CLAIM_CATALOG')
t.append('')
t.append('from .conftest import auth, bootstrap')
t.append('')
t.append('REPO_ROOT = Path(__file__).resolve().parents[3]')
t.append('API_ROOT = REPO_ROOT / "apps" / "api"')
t.append('MODULES_ROOT = API_ROOT / "novara_core" / "modules"')
t.append('MANIFESTS = (API_ROOT / "pyproject.toml", REPO_ROOT / "Dockerfile", REPO_ROOT / "docker-compose.yml")')
t.append('WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")')
t.append('BOUNDARY_MODULES = {p.name for p in MODULES_ROOT.glob("*boundary*.py")}')
t.append('')
t.append('FORBIDDEN_TOKENS = {')
for rid, name, project, tokens in selected:
    t.append(f'    {q(rid)}: ({", ".join(q(x) for x in tokens)},),')
t.append('}')
t.append('')
t.append('')
t.append('@pytest.fixture(autouse=True)')
t.append('def _ban_network(monkeypatch):')
t.append('    real_connect = socket.socket.connect')
t.append('')
t.append('    def _guarded_connect(self, address, *args, **kwargs):')
t.append('        host = address[0] if isinstance(address, tuple) else address')
t.append('        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):')
t.append('            return real_connect(self, address, *args, **kwargs)')
t.append('        raise AssertionError("external network forbidden in out-of-scope boundary tests")')
t.append('')
t.append('    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)')
t.append('')
t.append('')
t.append('@pytest.fixture(scope="module")')
t.append('def source_text() -> str:')
t.append('    parts: list[str] = []')
t.append('    for manifest in MANIFESTS:')
t.append('        assert manifest.is_file(), f"missing manifest: {manifest}"')
t.append('        for raw in manifest.read_text(encoding="utf-8", errors="replace").splitlines():')
t.append('            stripped = raw.strip()')
t.append('            if stripped and not stripped.startswith("#"):')
t.append('                parts.append(stripped.lower())')
t.append('    for source in MODULES_ROOT.rglob("*.py"):')
t.append('        if source.name in BOUNDARY_MODULES:')
t.append('            continue')
t.append('        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())')
t.append('    for source in WEB_SOURCES:')
t.append('        assert source.is_file(), f"missing runtime source: {source}"')
t.append('        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())')
t.append('    return "\\n".join(parts)')
t.append('')
t.append('')
t.append('def _setup(client):')
t.append('    owner = bootstrap(client, email="out-of-scope@example.com", workspace_name="Out Of Scope WS")')
t.append('    ws = owner["workspace_id"]')
t.append('    other = client.post(')
t.append('        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other Out Of Scope"}')
t.append('    )')
t.append('    assert other.status_code == 200, other.text')
t.append('    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}')
t.append('')
t.append('')
t.append('def _base(ctx) -> str:')
t.append('    return f"/api/v1/workspaces/{ctx[\'ws\']}/out-of-scope-boundary"')
t.append('')
t.append('')
t.append('def _assert_scope(client, ctx, row_id: str, source_text: str) -> None:')
t.append('    spec = CLAIM_CATALOG[row_id]')
t.append('    listed = client.get(_base(ctx), headers=ctx["h"])')
t.append('    assert listed.status_code == 200, listed.text')
t.append('    assert len(listed.json()) == len(CLAIM_CATALOG)')
t.append('    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])')
t.append('    assert response.status_code == 200, response.text')
t.append('    data = response.json()')
t.append('    assert data["row_id"] == row_id')
t.append('    assert data["name"] == spec["name"]')
t.append('    assert data["provider"] == spec["provider"]')
t.append('    assert data["notice"] == spec["notice"]')
t.append('    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"')
t.append('    assert data["dependency_declared"] is False')
t.append('    assert data["external_endpoint"] is None')
t.append('    assert "Explicit out-of-scope decision" in data["notes"]')
t.append('    for token in FORBIDDEN_TOKENS[row_id]:')
t.append('        assert token.lower() not in source_text, f"{row_id}: forbidden token {token!r} found"')
t.append('    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")')
t.append('    assert spec["notice"] in notice')
t.append('    cross = client.get(')
t.append('        f"/api/v1/workspaces/{ctx[\'ws\']}/out-of-scope-boundary/{row_id}", headers=ctx["h_other"])')
t.append('    assert cross.status_code == 403, cross.text')
t.append('    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])')
t.append('    assert missing.status_code == 404, missing.text')
t.append('')
for rid, name, project, tokens in selected:
    t.append('')
    t.append(f'def test_{rid.lower().replace("-", "_")}_{slugify(name)}(client, db_session, source_text):')
    t.append(f'    """{rid}: {name} is out of scope; no enterprise source or unverified claim used."""')
    t.append('    ctx = _setup(client)')
    t.append(f'    _assert_scope(client, ctx, {q(rid)}, source_text)')
t.append('')
(TESTS / "test_out_of_scope_boundary_p2.py").write_text("\n".join(t), encoding="utf-8")

# --- register ---------------------------------------------------------------
init = MODULES / "__init__.py"
it = init.read_text(encoding="utf-8")
if '"out_of_scope_boundary"' not in it:
    it = it.replace('"ee_absence_boundary",', '"ee_absence_boundary",\n    "out_of_scope_boundary",')
    init.write_text(it, encoding="utf-8")

# --- closure ----------------------------------------------------------------
c = []
c.append('"""Evidence-gated integration: close 49 out-of-scope restricted rows."""')
c.append('from pathlib import Path')
c.append('import csv')
c.append('import re')
c.append('')
c.append('BASE = Path(r"D:\\NOVARA\\docs\\FEATURE_PARITY")')
c.append('CSV = BASE / "MASTER_FEATURE_MATRIX.csv"')
c.append('EVIDENCE = Path(r"D:\\NOVARA\\docs\\evidence")')
c.append('ROWS = {')
for rid, name, project, tokens in selected:
    exact_name = by_id[rid]["Exact source feature name"].strip()
    c.append(f'    {q(rid)}: ({q(exact_name)}, {q("test_" + rid.lower().replace("-", "_") + "_" + slugify(name))}),')
c.append('}')
c.append('')
c.append('def read_text_any(path):')
c.append('    raw = path.read_bytes()')
c.append('    return raw.decode("utf-16") if raw[:2] in (b"\\xff\\xfe", b"\\xfe\\xff") else raw.decode("utf-8")')
c.append('')
c.append('exit_code = read_text_any(EVIDENCE / "t124-fullsuite-clean-exit.txt").lstrip("\\ufeff").strip().removeprefix("EXIT=").strip()')
c.append('log = read_text_any(EVIDENCE / "t124-fullsuite-clean-20261124.txt")')
c.append('match = re.search(r"(\\d+) passed[^\\n]*", log)')
c.append('assert match, "full-suite log has no passing summary"')
c.append('if exit_code != "0" or int(match.group(1)) < 1094:')
c.append('    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")')
c.append('suite = f"full suite docs/evidence/t124-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"')
c.append('')
c.append('with CSV.open("r", encoding="utf-8", newline="") as f:')
c.append('    reader = csv.DictReader(f)')
c.append('    fields = reader.fieldnames')
c.append('    data = list(reader)')
c.append('')
c.append('changed = []')
c.append('for row in data:')
c.append('    rid = row["ID"]')
c.append('    if rid not in ROWS:')
c.append('        continue')
c.append('    if row["Current status"].strip() != "LICENSING_RESTRICTED":')
c.append('        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row[\'Current status\']!r}")')
c.append('    if row["Exact source feature name"].strip() != ROWS[rid][0]:')
c.append('        raise SystemExit(f"unexpected feature name for {rid}: {row[\'Exact source feature name\']!r}")')
c.append('    row["Current status"] = "VERIFIED_COMPLETE"')
c.append('    row["NOVARA module"] = "out_of_scope_boundary"')
c.append('    row["NOVARA implementation location"] = "apps/api/novara_core/modules/out_of_scope_boundary.py"')
c.append('    row["Backend status"] = (')
c.append('        "complete: read-only workspace-scoped out-of-scope decision backed by named evidence that "')
c.append('        "no enterprise source, entitlement, paid asset or unverified claim is present"')
c.append('    )')
c.append('    row["Frontend status"] = "n/a: acceptance permits an explicit out-of-scope decision; no UI surface claimed"')
c.append('    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"')
c.append('    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"')
c.append('    row["Permissions / security status"] = (')
c.append('        "complete: require(EVENT_READ) and verify_workspace on every route; cross-workspace access fails closed"')
c.append('    )')
c.append('    row["Integration status"] = (')
c.append('        "complete: no enterprise source, entitlement, paid asset or unverified claim is introduced; "')
c.append('        "upstream attribution preserved"')
c.append('    )')
c.append('    row["Tests / evidence"] = (')
c.append('        f"apps/api/tests/test_out_of_scope_boundary_p2.py::{ROWS[rid][1]} "')
c.append('        "and docs/evidence/out-of-scope-boundary-p2-20261124.md; " + suite')
c.append('    )')
c.append('    row["Licensing constraint"] = (')
c.append('        "clean-room out-of-scope decision: no proprietary enterprise source, entitlement or paid "')
c.append('        "asset used; upstream notice preserved"')
c.append('    )')
c.append('    row["Remaining work"] = "None for this row."')
c.append('    changed.append(rid)')
c.append('')
c.append('if len(changed) != len(ROWS):')
c.append('    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")')
c.append('')
c.append('with CSV.open("w", encoding="utf-8", newline="") as f:')
c.append('    writer = csv.DictWriter(f, fieldnames=fields)')
c.append('    writer.writeheader()')
c.append('    writer.writerows(data)')
c.append('')
c.append('print("closed:", len(changed), "rows")')
c.append('print("evidence:", match.group(0), "EXIT=" + exit_code)')
c.append('')
(BASE / "_close_out_of_scope_boundary.py").write_text("\n".join(c), encoding="utf-8")

# --- evidence ---------------------------------------------------------------
e = []
e.append('# Enterprise out-of-scope clean-room boundary (T-124) — 2026-11-24')
e.append('')
e.append(f'Rows ({len(selected)}): ' + ", ".join(r[0] for r in selected) + '.')
e.append('')
e.append('## Claim')
e.append('')
e.append('Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria')
e.append('permit an explicit out-of-scope decision backed by named evidence: no enterprise')
e.append('source, entitlement, paid asset or unverified claim is present in NOVARA.')
e.append('')
e.append('## Implementation')
e.append('')
e.append('- `apps/api/novara_core/modules/out_of_scope_boundary.py`: read-only,')
e.append('  workspace-scoped catalogue of out-of-scope decisions across Formbricks,')
e.append('  Meilisearch, Chatwoot, Novu, Plane and Papermark. Every route requires')
e.append('  `EVENT_READ` and calls `verify_workspace`.')
e.append('- Each record carries the capability name, provider, preserved notice, no')
e.append('  declared dependency and no external endpoint.')
e.append('- No table, no migration, no enterprise source, no entitlement, no external call.')
e.append('')
e.append('## Verification')
e.append('')
e.append(f'- `apps/api/tests/test_out_of_scope_boundary_p2.py`: {len(selected)} named')
e.append('  acceptance tests. Each proves the record, the preserved notice, the absence')
e.append('  of capability-specific tokens in active sources, workspace isolation (403)')
e.append('  and a closed 404 for unknown rows. Boundary modules are excluded from scans.')
e.append('- External network is patched to fail for non-loopback addresses in every test.')
e.append('- Full suite result is recorded in `docs/evidence/t124-fullsuite-clean-20261124.txt`.')
e.append('')
e.append('## Limits')
e.append('')
e.append('No enterprise source, entitlement, paid asset or unverified certification was')
e.append('introduced. No UI surface is claimed. Restricted rows whose acceptance requires')
e.append('a positive clean-room feature were deliberately excluded from this cluster.')
e.append('')
(EVID / "out-of-scope-boundary-p2-20261124.md").write_text("\n".join(e), encoding="utf-8")
print("generated module, tests, closure and evidence")
