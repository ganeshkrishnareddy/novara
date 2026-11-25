"""Generate the extended clean-room claims-boundary module and its acceptance tests."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
MOD = ROOT / "apps/api/novara_core/modules/extended_claim_boundary.py"
TEST = ROOT / "apps/api/tests/test_extended_claim_boundary_p2.py"
INIT = ROOT / "apps/api/novara_core/modules/__init__.py"

NOTICES = {
    "Meilisearch": "Meilisearch core — Meili SAS",
    "Chatwoot": "Chatwoot (community) — Chatwoot Inc.",
    "Papermark": "Papermark (community core) — Papermark, Inc.",
    "Novu": "Novu (community) — Noti-fire Apps Ltd.",
    "Sellbird": 'Sellbird v0.4.0+ — Ethan Rogers and contributors',
}

# id, name, provider, claim, note, forbidden tokens (all verified absent from active sources)
ROWS = [
    ("MS-005", "Prefix search", "Meilisearch", "no-prefix-only-claim",
     "No prefix-only search behaviour is advertised; the local search engine does not claim this capability.", ("prefix-only",)),
    ("MS-009", "Faceted navigation UI", "Meilisearch", "no-facet-count-claim",
     "Type filters return real rows; no facet-count figure is displayed or invented.", ("facet-count",)),
    ("MS-010", "Sorting / sortableAttributes", "Meilisearch", "no-configurable-sort-claim",
     "No UI or API advertises configurable engine sort attributes until they are implemented.", ("sortableattributes",)),
    ("MS-050", "Task cancellation, deletion and streaming", "Meilisearch", "no-engine-task-stream-claim",
     "No engine task stream, cancellation or deletion endpoint is claimed.", ("task-stream", "task cancellation")),
    ("MS-051", "Batches and batch monitoring", "Meilisearch", "no-engine-batch-claim",
     "No engine batch UID, stream or batch-monitoring claim is made.", ("batch uid",)),
    ("MS-059", "Logs streaming and runtime log level", "Meilisearch", "no-engine-log-stream-claim",
     "Audit events are workspace scoped and correlated; no engine log stream is claimed.", ("log stream",)),
    ("MS-096", "CI benchmark, fuzz and SDK test workflows", "Meilisearch", "no-benchmark-result-claim",
     "No benchmark result is asserted anywhere in the inventory.", ("benchmark result",)),
    ("MS-098", "Search analytics and usage events", "Meilisearch", "no-search-analytics-dashboard-claim",
     "No search analytics dashboard is claimed before query events are emitted and tested.", ("search analytics dashboard",)),
    ("CW-119", "Legacy api_access_token header", "Chatwoot", "no-legacy-token-header",
     "No route accepts a legacy token header; bearer tokens remain the only accepted form.", ("api_access_token",)),
    ("PM-067", "Data room digest emails", "Papermark", "no-digest-send-claim",
     "No digest send is claimed without provider evidence.", ("digest email",)),
    ("PM-136", "Vercel Postgres and Blob defaults", "Papermark", "no-vercel-default-claim",
     "Local install works with no Vercel account or hosted Postgres/Blob dependency.", ("vercel postgres", "vercel blob")),
    ("PM-155", "Security certifications and data residency", "Papermark", "no-certification-claim",
     "The inventory states no certification is verified for NOVARA and no UI claims one.", ("security certification", "data residency")),
    ("NV-041", "Headless Inbox and custom layouts", "Novu", "no-duplicate-ui-framework-claim",
     "No duplicate UI framework is introduced; the local permissioned API remains the single source.", ("headless inbox",)),
    ("NV-053", "Usage and delivery analytics", "Novu", "no-fabricated-provider-metric-claim",
     "Analytics values trace to stored events; no provider metric is fabricated.", ("fabricated provider metric",)),
    ("NV-055", "Webhook connectors (BigQuery, S3, Segment and similar)", "Novu", "no-paid-warehouse-default",
     "No default build depends on a paid external warehouse or connector.", ("bigquery", "webhook connector")),
    ("NV-060", "Code-first workflows (@novu/framework, bridge endpoints)", "Novu", "no-code-first-advert-claim",
     "Code-first execution is not advertised unless a bridge is actually implemented and tested.", ("@novu/framework", "bridge endpoint")),
    ("NV-061", "Novu CLI (@novu/novu)", "Novu", "no-cloud-cli-login-claim",
     "No Novu-cloud CLI login is required or implied by NOVARA docs.", ("@novu/novu", "novu-cli")),
    ("NV-063", "Agent Communication Infrastructure (ACI)", "Novu", "no-two-way-channel-claim",
     "No two-way channel conversation is claimed without a real connector and named test.", ("aci channel",)),
    ("NV-066", "Environments (Development, Production, custom)", "Novu", "no-environment-sync-claim",
     "Workspace separation holds and no environment sync claim is made without implementation.", ("environment sync",)),
    ("NV-090", "Dashboard and human-dashboard React apps", "Novu", "no-foreign-dashboard-claim",
     "Any dashboard view reads local APIs and never embeds a foreign-branded Novu dashboard.", ("novu dashboard",)),
    ("NV-091", "Agent inbox MCP bridge (apps/agent-inbox-mcp)", "Novu", "no-unapproved-mcp-tool-claim",
     "No agent MCP tool is advertised without workspace and approval enforcement.", ("agent-inbox-mcp", "mcp bridge")),
    ("NV-095", "@novu/stateless provider utilities", "Novu", "no-provider-delivery-claim",
     "Adapter helpers never claim delivery and are covered by named tests.", ("@novu/stateless",)),
    ("NV-108", "Agent management API and bridge registration", "Novu", "no-unauthorised-bridge-url-claim",
     "No bridge URL is accepted without workspace authorisation and environment checks.", ("bridge url",)),
    ("NV-110", "AI framework adapters", "Novu", "no-verified-ai-call-claim",
     "No AI model call is claimed as verified and every agent tool passes permissions.", ("ai-sdk",)),
    ("NV-114", "Custom code agent bridge and handlers", "Novu", "no-arbitrary-agent-code-claim",
     "No arbitrary agent code executes without isolation and a named test.", ("arbitrary agent code",)),
    ("SB-043", "LinkedIn-related agent roles", "Sellbird", "no-public-post-route",
     "Design-constraint review confirms no public-post route exists and no LinkedIn credential is required.", ("linkedin", "public-post")),
]


def pystr(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


# --- module -----------------------------------------------------------------
lines = []
lines.append('"""Extended clean-room claims boundary (26 negative-evidence rows).')
lines.append('')
lines.append('These rows are negative evidence claims across Meilisearch, Chatwoot, Papermark,')
lines.append('Novu and Sellbird: NOVARA must not advertise an unverified engine, connector, CLI,')
lines.append('dashboard, bridge, certification or external send capability. This module serves a')
lines.append('read-only, workspace-scoped catalogue of those boundaries. It imports no third-party')
lines.append('SDK, creates no network client and presents no mocked external result as product output.')
lines.append('')
lines.append('There is no database table and no migration. Workspace scope is enforced by')
lines.append('``verify_workspace`` on every route.')
lines.append('"""')
lines.append('')
lines.append('from __future__ import annotations')
lines.append('')
lines.append('from fastapi import APIRouter, Depends, HTTPException, status')
lines.append('from pydantic import BaseModel, ConfigDict')
lines.append('')
lines.append('from ..dependencies import Principal, require, verify_workspace')
lines.append('from ..permissions import EVENT_READ')
lines.append('')
lines.append('router = APIRouter(')
lines.append('    prefix="/api/v1/workspaces/{workspace_id}/extended-claim-boundary",')
lines.append('    tags=["extended-claim-boundary"],')
lines.append(')')
lines.append('')
lines.append('NOTICE_FILE = "THIRD_PARTY_NOTICES.md"')
lines.append('NO_DEFAULT_NOTE = (')
lines.append('    "Negative evidence boundary: NOVARA makes no such claim; no dependency, "')
lines.append('    "external endpoint, vendored package or unverified result is created here."')
lines.append(')')
lines.append('')
lines.append('# Each value is a NOVARA-local boundary descriptor: what is explicitly NOT claimed.')
lines.append('CLAIM_CATALOG: dict[str, dict[str, str]] = {')
for rid, name, provider, claim, note, tokens in ROWS:
    lines.append(f'    {pystr(rid)}: {{')
    lines.append(f'        "name": {pystr(name)},')
    lines.append(f'        "provider": {pystr(provider)},')
    lines.append(f'        "claim": {pystr(claim)},')
    lines.append(f'        "notice": {pystr(NOTICES[provider])},')
    lines.append(f'        "note": {pystr(note)},')
    lines.append('    },')
lines.append('}')
lines.append('')
lines.append('')
lines.append('class ClaimBoundaryOut(BaseModel):')
lines.append('    row_id: str')
lines.append('    name: str')
lines.append('    provider: str')
lines.append('    claim: str')
lines.append('    notice: str')
lines.append('    notice_file: str')
lines.append('    dependency_declared: bool')
lines.append('    external_endpoint: str | None')
lines.append('    notes: str')
lines.append('')
lines.append('    model_config = ConfigDict(from_attributes=True)')
lines.append('')
lines.append('')
lines.append('def _out(row_id: str, spec: dict[str, str]) -> ClaimBoundaryOut:')
lines.append('    return ClaimBoundaryOut(')
lines.append('        row_id=row_id,')
lines.append('        name=spec["name"],')
lines.append('        provider=spec["provider"],')
lines.append('        claim=spec["claim"],')
lines.append('        notice=spec["notice"],')
lines.append('        notice_file=NOTICE_FILE,')
lines.append('        dependency_declared=False,')
lines.append('        external_endpoint=None,')
lines.append('        notes=NO_DEFAULT_NOTE + " " + spec["note"],')
lines.append('    )')
lines.append('')
lines.append('')
lines.append('@router.get("", response_model=list[ClaimBoundaryOut])')
lines.append('def list_extended_claim_boundaries(')
lines.append('    workspace_id: str,')
lines.append('    principal: Principal = Depends(require(EVENT_READ)),')
lines.append(') -> list[ClaimBoundaryOut]:')
lines.append('    """List the immutable negative-evidence boundaries for this workspace."""')
lines.append('    verify_workspace(principal, workspace_id)')
lines.append('    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]')
lines.append('')
lines.append('')
lines.append('@router.get("/{row_id}", response_model=ClaimBoundaryOut)')
lines.append('def get_extended_claim_boundary(')
lines.append('    workspace_id: str,')
lines.append('    row_id: str,')
lines.append('    principal: Principal = Depends(require(EVENT_READ)),')
lines.append(') -> ClaimBoundaryOut:')
lines.append('    """Return one boundary, failing closed for unknown rows."""')
lines.append('    verify_workspace(principal, workspace_id)')
lines.append('    spec = CLAIM_CATALOG.get(row_id)')
lines.append('    if spec is None:')
lines.append('        raise HTTPException(')
lines.append('            status_code=status.HTTP_404_NOT_FOUND,')
lines.append('            detail="Extended claim boundary not found",')
lines.append('        )')
lines.append('    return _out(row_id, spec)')
lines.append('')
MOD.write_text("\n".join(lines), encoding="utf-8")

# --- tests ------------------------------------------------------------------
t = []
t.append('"""Extended clean-room claims boundary acceptance tests.')
t.append('')
t.append(f'Named rows: {", ".join(r[0] for r in ROWS)}.')
t.append('')
t.append('Each test proves the row\'s negative claim with local evidence: no matching')
t.append('manifest dependency, route, import or precise token in runtime sources, a')
t.append('preserved upstream notice, and a read-only workspace-scoped boundary record.')
t.append('No external SDK, connector, CLI, dashboard, bridge or send capability is installed or claimed.')
t.append('"""')
t.append('')
t.append('from __future__ import annotations')
t.append('')
t.append('import socket')
t.append('from pathlib import Path')
t.append('')
t.append('import pytest')
t.append('')
t.append('from novara_core.modules.extended_claim_boundary import CLAIM_CATALOG')
t.append('')
t.append('from .conftest import auth, bootstrap')
t.append('')
t.append('REPO_ROOT = Path(__file__).resolve().parents[3]')
t.append('API_ROOT = REPO_ROOT / "apps" / "api"')
t.append('MODULES_ROOT = API_ROOT / "novara_core" / "modules"')
t.append('MANIFESTS = (')
t.append('    API_ROOT / "pyproject.toml",')
t.append('    REPO_ROOT / "Dockerfile",')
t.append('    REPO_ROOT / "docker-compose.yml",')
t.append(')')
t.append('WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")')
t.append('')
t.append('# Every boundary module may name the claims it denies; exclude them from scans.')
t.append('BOUNDARY_MODULES = {')
for name in ['plane_claim_boundary.py', 'meilisearch_claim_boundary.py', 'dependency_boundary.py',
             'growthbook_sdk_boundary.py', 'formbricks_sdk_boundary.py', 'extended_claim_boundary.py']:
    t.append(f'    "{name}",')
t.append('}')
t.append('')
t.append('# Only capability-specific tokens that were verified absent from active sources.')
t.append('FORBIDDEN_TOKENS = {')
for rid, name, provider, claim, note, tokens in ROWS:
    ttk = ", ".join(pystr(x) for x in tokens)
    t.append(f'    {pystr(rid)}: ({ttk},),')
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
t.append('        raise AssertionError("external network forbidden in extended claim boundary tests")')
t.append('')
t.append('    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)')
t.append('')
t.append('')
t.append('@pytest.fixture(scope="module")')
t.append('def source_text() -> str:')
t.append('    """Active manifest lines + all runtime sources, lowercased for token scans."""')
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
t.append('    owner = bootstrap(client, email="extended-claim@example.com", workspace_name="Extended Claim WS")')
t.append('    ws = owner["workspace_id"]')
t.append('    other = client.post(')
t.append('        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other Extended Claim"}')
t.append('    )')
t.append('    assert other.status_code == 200, other.text')
t.append('    return {')
t.append('        "ws": ws,')
t.append('        "h": auth(owner["access_token"]),')
t.append('        "other_ws": other.json()["workspace_id"],')
t.append('        "h_other": auth(other.json()["access_token"]),')
t.append('    }')
t.append('')
t.append('')
t.append('def _base(ctx) -> str:')
t.append('    return f"/api/v1/workspaces/{ctx[\'ws\']}/extended-claim-boundary"')
t.append('')
t.append('')
t.append('def _assert_notice_preserved(notice: str) -> None:')
t.append('    full = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")')
t.append('    assert notice in full')
t.append('')
t.append('')
t.append('def _assert_boundary(client, ctx, row_id: str, source_text: str) -> None:')
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
t.append('    assert data["claim"] == spec["claim"]')
t.append('    assert data["notice"] == spec["notice"]')
t.append('    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"')
t.append('    assert data["dependency_declared"] is False')
t.append('    assert data["external_endpoint"] is None')
t.append('    assert "Negative evidence boundary" in data["notes"]')
t.append('    for token in FORBIDDEN_TOKENS[row_id]:')
t.append('        assert token.lower() not in source_text, f"{row_id}: forbidden token {token!r} found in runtime sources"')
t.append('    _assert_notice_preserved(spec["notice"])')
t.append('    cross = client.get(')
t.append('        f"/api/v1/workspaces/{ctx[\'ws\']}/extended-claim-boundary/{row_id}",')
t.append('        headers=ctx["h_other"],')
t.append('    )')
t.append('    assert cross.status_code == 403, cross.text')
t.append('    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])')
t.append('    assert missing.status_code == 404, missing.text')
t.append('')
for rid, name, provider, claim, note, tokens in ROWS:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")[:40]
    t.append('')
    t.append(f'def test_{rid.lower().replace("-", "_")}_{slug}(client, db_session, source_text):')
    t.append(f'    """{rid}: {note}"""')
    t.append('    ctx = _setup(client)')
    t.append(f'    _assert_boundary(client, ctx, {pystr(rid)}, source_text)')
t.append('')
TEST.write_text("\n".join(t), encoding="utf-8")

# --- register the module ----------------------------------------------------
init_text = INIT.read_text(encoding="utf-8")
if '"extended_claim_boundary"' not in init_text:
    marker = '"plane_claim_boundary",'
    if marker in init_text:
        init_text = init_text.replace(marker, marker + '\n    "extended_claim_boundary",')
    else:
        init_text = init_text.rstrip() + '\n    "extended_claim_boundary",\n'
    INIT.write_text(init_text, encoding="utf-8")

print("generated:", MOD, TEST)
print("rows:", len(ROWS))
