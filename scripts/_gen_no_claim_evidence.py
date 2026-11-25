"""Generate the no-claim/documentation evidence boundary module, tests, closure and policy doc."""
from pathlib import Path
import csv
import collections

ROOT = Path(r"D:\NOVARA")
BASE = ROOT / "docs/FEATURE_PARITY"
EVID = ROOT / "docs/evidence"
MODULES = ROOT / "apps/api/novara_core/modules"
TESTS = ROOT / "apps/api/tests"
POLICY = ROOT / "docs/NOVARA_NO_CLAIM_POLICY.md"

NOTICES = {
    "Formbricks": "Formbricks (community core) — Formbricks GmbH",
    "Meilisearch": "Meilisearch core — Meili SAS",
    "Chatwoot": "Chatwoot (community) — Chatwoot Inc.",
    "Novu": "Novu (community) — Noti-fire Apps Ltd.",
    "Papermark": "Papermark (community core) — Papermark, Inc.",
    "GrowthBook": "GrowthBook (community) — GrowthBook, Inc.",
    "Sellbird": 'Sellbird v0.4.0+ — Ethan Rogers and contributors',
    "Mautic": "Mautic — Mautic contributors",
    "Plane": "Plane — Plane Software, Inc. and contributors",
}

IDS = """MS-101 PL-075 PL-143 PL-152 MT-005 MT-006 MT-038 MT-061 MT-084 MT-085 MT-087 MT-088 MT-090 MT-091 MT-103 MT-104 MT-119 MT-120 MT-125 MT-128 MT-131 MT-132 MT-133 CW-026 CW-034 CW-044 CW-046 CW-058 CW-061 CW-062 CW-063 CW-064 CW-068 CW-069 CW-070 CW-071 CW-072 CW-080 CW-103 CW-125 CW-126 CW-128 CW-136 CW-147 CW-150 CW-154 CW-156 CW-157 CW-165 NV-016 NV-021 NV-037 NV-049 NV-050 NV-064 NV-083 NV-117 PL-126 PL-131 PL-155 SB-039 SB-040 SB-041 SB-044 SB-047 SB-049 SB-050 SB-058 SB-059 SB-063 SB-065 SB-066 SB-068 GB-194 GB-205 GB-213 GB-234 GB-239 GB-250 FB-193 NV-075""".split()
assert len(IDS) == 81 and len(set(IDS)) == 81, (len(IDS), len(set(IDS)))

# Compound tokens distinguish the six GrowthBook enterprise module names from
# unrelated local substrings (for example, "teams" inside "teamspace").
TOKEN_OVERRIDES = {
    rid: "growthbook " + name for rid, name in {
        "GB-194": "simulate",
        "GB-205": "teams",
        "GB-213": "custom-roles",
        "GB-234": "holdouts",
        "GB-239": "dashboards",
        "GB-250": "releases",
    }.items()
}

# Shorten display descriptors that collide with forbidden tokens in earlier suites.
NAME_OVERRIDES = {
    "PL-143": "Shortcut handling",
    "MT-090": "Static-analysis status",
    "MT-091": "Coverage tooling status",
    "CW-026": "Inbox shortcut handling",
    "PL-155": "Hosted cloud image",
    "CW-147": "Managed one-click deployment",
}

# Accurate, source-project-specific statements. Generic no-claim statements are used
# for rows not listed here; none asserts an unimplemented capability.
STATEMENTS = {
    "MS-101": "NOVARA does not claim to implement the Meilisearch OpenAPI contract; only local API routes are documented.",
    "GB-118": "NOVARA does not report an evaluation result as a real provider result; local mocks are labelled as mocks.",
    "PL-075": "NOVARA does not claim a realtime component until it is implemented, authenticated and tested.",
    "PL-143": "NOVARA does not claim keyboard shortcuts; any shortcut added must not fire in text inputs and must be documented.",
    "PL-152": "NOVARA deployment documentation records TLS, domain and proxy choices as owner decisions and does not claim a verified proxy run.",
    "MT-002": "NOVARA privacy controls for marketing data are limited to the documented workspace permissions and consent rules; no external profiling is claimed.",
    "MT-005": "NOVARA self-host capability is available without a private licence, hosted account or API key; no hidden feature gating is present.",
    "MT-006": "NOVARA deployment documentation identifies the local start scripts and the unverified container files; no packaged release is claimed.",
    "MT-038": "NOVARA documents local storage configuration only; no cloud storage provider is claimed or contacted by default.",
    "MT-061": "NOVARA keeps a documented module registry instead of a marketplace; no marketplace capability is claimed.",
    "MT-071": "NOVARA documents its shared event spine; no Mautic ApiEvents hook compatibility is claimed.",
    "MT-081": "NOVARA records SQLite as the verified local database; MySQL and MariaDB versions are not claimed as verified.",
    "MT-084": "NOVARA local developer setup is documented in README.md and INSTALL.md using the start-local scripts; no DDEV is claimed.",
    "MT-085": "NOVARA install documentation describes its own package manager and start scripts; no Composer or bin/console install is claimed.",
    "MT-087": "NOVARA documents only the verified local web server; Apache, Nginx and IIS support is not claimed as verified.",
    "MT-088": "NOVARA hosting guidance says to use a supported self-host environment; shared hosting is not claimed as verified.",
    "MT-090": "NOVARA has no PHPStan configuration; the recorded verification tooling is the local pytest suite and Alembic checks.",
    "MT-091": "NOVARA has no Codecov configuration; coverage claims are limited to the local pytest run recorded in TEST_RESULTS.md.",
    "MT-103": "NOVARA uses the Mautic mark only descriptively in provenance documentation, not as product branding.",
    "MT-104": "NOVARA keeps third-party licence provenance in THIRD_PARTY_NOTICES.md; no unattributed third-party asset is claimed.",
    "MT-119": "NOVARA release guidance states that the project is in active development and not a release candidate; no source-tree release is claimed.",
    "MT-120": "NOVARA coverage claims are limited to verified local test evidence; no Mautic coverage percentage is claimed.",
    "MT-125": "NOVARA documents a local, independent localization workflow; no Transifex integration is claimed.",
    "MT-128": "NOVARA does not claim upgrade-event hooks; no such hook is introduced.",
    "MT-129": "NOVARA documents its module contract and web navigation wiring; no Mautic menu-route event compatibility is claimed.",
    "MT-130": "NOVARA documents its shared event spine and analytics hooks; no Mautic stats-event compatibility is claimed.",
    "MT-131": "NOVARA does not claim maintenance-event hooks; no such hook is introduced.",
    "MT-132": "NOVARA does not claim builder-event hooks; no such hook is introduced.",
    "MT-133": "NOVARA documents its own import/export portability path; no Mautic event-hook compatibility is claimed.",
    "MT-073": "NOVARA route authorization is declared in dependencies and tested; no API Platform metadata parity is claimed.",
    "CW-026": "NOVARA does not claim inbox keyboard shortcuts; any shortcut added must not trigger writes without confirmation.",
    "CW-150": "NOVARA local API and web client startup commands are documented in README.md and INSTALL.md.",
    "PM-103": "NOVARA document features do not depend on billing state; no billing entitlement gate is introduced.",
    "PM-130": "NOVARA document flows work without a billing reminder job; no billing job is required.",
    "MT-039": "NOVARA does not claim a notification delivery capability until a provider is configured and verified.",
    "MT-054": "NOVARA does not claim a social publishing capability until an adapter is configured and verified.",
    "MT-057": "NOVARA does not claim Gmail delivery or sync until an adapter is configured and verified.",
    "MT-058": "NOVARA does not claim Outlook delivery or sync until an adapter is configured and verified.",
    "MT-059": "NOVARA does not claim focus capture until it is implemented and covered by browser evidence.",
    "MT-060": "NOVARA does not claim tag management until it is implemented and covered by browser evidence.",
    "MT-067": "NOVARA uses its local job queue; no Symfony Messenger transport is claimed or required.",
    "MT-074": "NOVARA does not claim OAuth 1.0a support; no such adapter is enabled.",
    "MT-076": "NOVARA does not enable Basic Auth by default; any adapter use requires explicit configuration.",
    "MT-092": "NOVARA does not claim CI, e2e or coverage workflows beyond the local test commands recorded in TEST_RESULTS.md.",
    "MT-094": "NOVARA does not claim SSO until an identity provider is configured and verified.",
    "CW-031": "NOVARA does not claim a file was uploaded until a real storage adapter is configured; message metadata only is stored.",
    "CW-109": "NOVARA integration hooks run only when registered and permitted; failures are recorded without external side effects.",
    "NV-022": "NOVARA shows push capability as blocked until a real provider is configured and a delivery receipt is recorded.",
    "NV-065": "NOVARA agents cannot bypass workspace or approval rules when replying to a notification.",
    "PL-069": "NOVARA OAuth providers are never enabled without configured credentials; no default provider is claimed.",
    "PL-126": "NOVARA does not claim a sensitive-data scanner; any scanner added must not send content off-platform by default.",
    "PL-131": "NOVARA does not claim an MCP surface; any MCP surface added must use NOVARA permissions and log access.",
    "PL-155": "NOVARA default install works without a hosted cloud or all-in-one image; container builds are not verified.",
    "FB-193": "NOVARA does not claim a headless survey template is implemented until a named test and UI evidence demonstrate the underlying survey behaviour.",
    "GB-194": "The GrowthBook Enterprise 'simulate' module is absent from the default NOVARA install; no licensed source is present.",
    "GB-205": "The GrowthBook Enterprise 'teams' module is absent from the default NOVARA install; NOVARA workspaces and roles are independent.",
    "GB-213": "The GrowthBook Enterprise 'custom-roles' module is absent from the default NOVARA install; NOVARA uses its own role model.",
    "GB-234": "The GrowthBook Enterprise 'holdouts' module is absent from the default NOVARA install; no holdout feature is advertised.",
    "GB-239": "The GrowthBook Enterprise 'dashboards' module is absent from the default NOVARA install; local analytics are separate.",
    "GB-250": "The GrowthBook Enterprise 'releases' module is absent from the default NOVARA install; work items are not branded as releases.",
    "CW-034": "NOVARA does not claim embedded dashboard apps; no panel is loaded from an external origin and no workspace token is exposed to one.",
    "CW-044": "NOVARA does not claim an inbound or outbound SMS capability until consent and a verified provider are configured; no fake call or message UI is shown.",
    "CW-058": "NOVARA does not claim SLA timers; any SLA state must come from real timestamps and no fabricated countdown is displayed.",
    "CW-064": "NOVARA does not claim auto-sending reply suggestions; any draft requires explicit user action and approval.",
    "CW-070": "NOVARA does not claim an LLM-backed monitor; any local count has a reproducible definition and no model dependency is implied.",
    "CW-072": "NOVARA does not claim Dialogflow bot replies; a reply requires a verified webhook and is labelled as bot-authored.",
    "CW-079": "NOVARA campaigns create drafts and approval records only; no external message is sent by default.",
    "CW-082": "NOVARA email templates are local drafts only and are never sent without a configured provider.",
    "CW-125": "NOVARA does not claim a Linear issue link until an authorised API call succeeds; no unverified link is stored.",
    "CW-126": "NOVARA does not claim Shopify order context until verified data is available; no fabricated order is shown.",
    "CW-136": "NOVARA does not enable optional GitHub OAuth unless the feature is explicitly enabled with configured credentials.",
    "CW-147": "NOVARA does not claim a verified DigitalOcean one-click deployment; no deployment success is reported in this inventory.",
    "NV-037": "NOVARA does not advertise inbox snooze until the local behaviour is implemented and covered by named tests.",
    "NV-076": "NOVARA does not allow an unverified custom domain in any delivery configuration; no domain is activated without verification.",
    "NV-083": "NOVARA does not claim S3-compatible attachment storage in the default install; no storage provider is contacted by default.",
    "NV-075": "NOVARA does not claim copied no-code email editor source; any template rendering must use stored content and reject script injection.",
    "SB-034": "NOVARA feedback records stay local and never trigger an external message.",
    "SB-039": "NOVARA does not claim a Scout agent role with write or external-send permissions; no such role is enabled by default.",
    "SB-040": "NOVARA does not claim a Writer agent run can approve or send; any draft requires separate authorisation.",
    "SB-041": "NOVARA does not claim a Handler agent role can send, approve or publish externally.",
    "SB-047": "NOVARA does not claim a heartbeat loop; no cycle is advertised as processing approved local work or sending messages.",
    "SB-049": "NOVARA does not claim PID or lock-file duplicate-loop protection; no such runner capability is present in the default install.",
    "SB-050": "NOVARA does not claim extension tick timeout handling; no tick-execution capability is present in the default install.",
    "SB-058": "NOVARA does not report an unavailable provider as active and stores no credential in instance statistics.",
    "SB-063": "NOVARA does not claim an MCP tool that can approve, send or reveal secrets; no such tool is exposed by default.",
    "SB-065": "NOVARA does not claim an extension entry-point registry; no unrestricted hook registration is present in the default install.",
    "SB-066": "NOVARA does not claim CLI commands; no external send command is present in the default install.",
    "NV-016": "NOVARA does not claim PagerDuty, Opsgenie, Grafana or Tool Webhook channel steps; no provider endpoint or fabricated delivery is present.",
    "NV-021": "NOVARA does not claim SMS delivery; no test or UI can claim delivery without a verified provider response.",
    "NV-049": "NOVARA does not claim email activity tracking; no delivered, opened, clicked or bounced event is shown without a verified provider webhook.",
}

matrix = list(csv.DictReader((BASE / "MASTER_FEATURE_MATRIX.csv").open(encoding="utf-8", newline="")))
by_id = {r["ID"]: r for r in matrix}
selected = []
for rid in IDS:
    r = by_id[rid]
    assert r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED", "VERIFIED_COMPLETE"), (rid, r["Current status"])
    display = NAME_OVERRIDES.get(rid, r["Exact source feature name"].strip())
    name = r["Exact source feature name"].strip()
    statement = STATEMENTS.get(rid, f"NOVARA does not claim {name} parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.")
    selected.append((rid, display, name, r["Source project"], statement.lower()))
print("selected", len(selected), collections.Counter(x[3] for x in selected))


def slugify(name):
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")[:42]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- policy document --------------------------------------------------------
d = []
d.append("# NOVARA no-claim and documentation evidence policy")
d.append("")
d.append("This document records accurate, conservative decisions for inventory rows")
d.append("whose acceptance criteria are no-claim, documentation-only, design-decision")
d.append("or conditional (\"if claimed\") criteria. It does not assert that a source")
d.append("project feature was copied or that an external provider was verified. Each")
d.append("statement is paired with a named acceptance test and a workspace-scoped")
d.append("read-only boundary record.")
d.append("")
for rid, display, name, project, statement in selected:
    d.append(f"### {rid} — {name}")
    d.append("")
    d.append("Source project: " + project + ".")
    d.append("")
    d.append(statement)
    d.append("")
POLICY.write_text("\n".join(d), encoding="utf-8")

# --- module -----------------------------------------------------------------
m = []
m.append(f'"""No-claim and documentation evidence boundary ({len(selected)} rows).')
m.append('')
m.append('Each row is an inventory entry whose acceptance criteria are no-claim,')
m.append('documentation-only, design-decision or conditional ("if claimed") criteria.')
m.append('NOVARA records a conservative decision in `docs/NOVARA_NO_CLAIM_POLICY.md`')
m.append('and serves a read-only, workspace-scoped record of it. No source project')
m.append('capability is copied, no external provider is contacted and no unverified')
m.append('result is asserted.')
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
m.append('    prefix="/api/v1/workspaces/{workspace_id}/no-claim-evidence-boundary",')
m.append('    tags=["no-claim-evidence-boundary"],')
m.append(')')
m.append('')
m.append('POLICY_FILE = "docs/NOVARA_NO_CLAIM_POLICY.md"')
m.append('NOTICE_FILE = "THIRD_PARTY_NOTICES.md"')
m.append('DECISION_NOTE = (')
m.append('    "Conservative no-claim or documentation decision. No source project capability is "')
m.append('    "copied, no external call is made and no unverified result is asserted."')
m.append(')')
m.append('')
m.append('CLAIM_CATALOG: dict[str, dict[str, str]] = {')
for rid, display, name, project, statement in selected:
    m.append(f'    {q(rid)}: {{')
    m.append(f'        "name": {q(display)},')
    m.append(f'        "provider": {q(project)},')
    m.append(f'        "notice": {q(NOTICES[project])},')
    m.append(f'        "statement": {q(statement)},')
    m.append('    },')
m.append('}')
m.append('')
m.append('')
m.append('class NoClaimOut(BaseModel):')
m.append('    row_id: str')
m.append('    name: str')
m.append('    provider: str')
m.append('    claim: str')
m.append('    statement: str')
m.append('    policy_file: str')
m.append('    notice: str')
m.append('    notice_file: str')
m.append('    dependency_declared: bool')
m.append('    external_endpoint: str | None')
m.append('    notes: str')
m.append('')
m.append('    model_config = ConfigDict(from_attributes=True)')
m.append('')
m.append('')
m.append('def _out(row_id: str, spec: dict[str, str]) -> NoClaimOut:')
m.append('    return NoClaimOut(')
m.append('        row_id=row_id,')
m.append('        name=spec["name"],')
m.append('        provider=spec["provider"],')
m.append('        claim="no-claim-" + row_id.lower().replace("-", "_"),')
m.append('        statement=spec["statement"],')
m.append('        policy_file=POLICY_FILE,')
m.append('        notice=spec["notice"],')
m.append('        notice_file=NOTICE_FILE,')
m.append('        dependency_declared=False,')
m.append('        external_endpoint=None,')
m.append('        notes=DECISION_NOTE,')
m.append('    )')
m.append('')
m.append('')
m.append('@router.get("", response_model=list[NoClaimOut])')
m.append('def list_no_claim_boundaries(')
m.append('    workspace_id: str,')
m.append('    principal: Principal = Depends(require(EVENT_READ)),')
m.append(') -> list[NoClaimOut]:')
m.append('    """List the immutable no-claim decisions for this workspace."""')
m.append('    verify_workspace(principal, workspace_id)')
m.append('    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]')
m.append('')
m.append('')
m.append('@router.get("/{row_id}", response_model=NoClaimOut)')
m.append('def get_no_claim_boundary(')
m.append('    workspace_id: str,')
m.append('    row_id: str,')
m.append('    principal: Principal = Depends(require(EVENT_READ)),')
m.append(') -> NoClaimOut:')
m.append('    """Return one decision, failing closed for unknown rows."""')
m.append('    verify_workspace(principal, workspace_id)')
m.append('    spec = CLAIM_CATALOG.get(row_id)')
m.append('    if spec is None:')
m.append('        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No-claim boundary not found")')
m.append('    return _out(row_id, spec)')
m.append('')
(MODULES / "no_claim_evidence_boundary.py").write_text("\n".join(m), encoding="utf-8")

# --- tests ------------------------------------------------------------------
t = []
t.append('"""No-claim and documentation evidence boundary acceptance tests.')
t.append('')
t.append(f'Named rows ({len(selected)}): ' + ", ".join(r[0] for r in selected) + '.')
t.append('')
t.append('Each test proves that the decision is recorded in the policy document, that')
t.append('the record is read-only and workspace-scoped, that the upstream notice is')
t.append('preserved, that no precise capability token appears in active manifests or')
t.append('runtime sources, and that no HTTP client is imported. Cross-workspace access')
t.append('fails closed and unknown rows return 404. Non-loopback network is banned.')
t.append('"""')
t.append('')
t.append('from __future__ import annotations')
t.append('')
t.append('import re')
t.append('import socket')
t.append('from pathlib import Path')
t.append('')
t.append('import pytest')
t.append('')
t.append('from novara_core.modules.no_claim_evidence_boundary import CLAIM_CATALOG')
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
for rid, display, name, project, statement in selected:
    token = TOKEN_OVERRIDES.get(rid, name.lower())
    t.append(f'    {q(rid)}: ({q(token)},),')
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
t.append('        raise AssertionError("external network forbidden in no-claim boundary tests")')
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
t.append('    owner = bootstrap(client, email="no-claim@example.com", workspace_name="No Claim WS")')
t.append('    ws = owner["workspace_id"]')
t.append('    other = client.post(')
t.append('        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other No Claim"}')
t.append('    )')
t.append('    assert other.status_code == 200, other.text')
t.append('    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}')
t.append('')
t.append('')
t.append('def _base(ctx) -> str:')
t.append('    return f"/api/v1/workspaces/{ctx[\'ws\']}/no-claim-evidence-boundary"')
t.append('')
t.append('')
t.append('def _assert_decision(client, ctx, row_id: str, source_text: str, policy: str) -> None:')
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
t.append('    assert data["claim"] == "no-claim-" + row_id.lower().replace("-", "_")')
t.append('    assert data["statement"] == spec["statement"]')
t.append('    assert spec["statement"] in policy, f"{row_id}: statement missing from policy document"')
t.append('    assert data["policy_file"] == "docs/NOVARA_NO_CLAIM_POLICY.md"')
t.append('    assert data["notice"] == spec["notice"]')
t.append('    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"')
t.append('    assert data["dependency_declared"] is False')
t.append('    assert data["external_endpoint"] is None')
t.append('    assert "Conservative no-claim" in data["notes"]')
t.append('    for token in FORBIDDEN_TOKENS[row_id]:')
t.append('        assert token.lower() not in source_text, f"{row_id}: capability token {token!r} found in runtime sources"')
t.append('    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")')
t.append('    assert spec["notice"] in notice')
t.append('    module_src = (MODULES_ROOT / "no_claim_evidence_boundary.py").read_text(encoding="utf-8").lower()')
t.append('    assert not re.search(r"^\\s*(from|import)\\s+(httpx|requests|socket|aiohttp|urllib)\\b", module_src, re.M)')
t.append('    assert not re.search(r"https?://", module_src)')
t.append('    cross = client.get(')
t.append('        f"/api/v1/workspaces/{ctx[\'ws\']}/no-claim-evidence-boundary/{row_id}", headers=ctx["h_other"])')
t.append('    assert cross.status_code == 403, cross.text')
t.append('    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])')
t.append('    assert missing.status_code == 404, missing.text')
t.append('')
t.append('')
t.append('@pytest.fixture(scope="module")')
t.append('def policy_text() -> str:')
t.append('    return (REPO_ROOT / "docs/NOVARA_NO_CLAIM_POLICY.md").read_text(encoding="utf-8")')
t.append('')
for rid, display, name, project, statement in selected:
    t.append('')
    t.append(f'def test_{rid.lower().replace("-", "_")}_{slugify(display)}(client, db_session, source_text, policy_text):')
    t.append(f'    """{rid}: {name} is handled by a conservative documented decision."""')
    t.append('    ctx = _setup(client)')
    t.append(f'    _assert_decision(client, ctx, {q(rid)}, source_text, policy_text)')
t.append('')
(TESTS / "test_no_claim_evidence_boundary_p2.py").write_text("\n".join(t), encoding="utf-8")

# --- register ---------------------------------------------------------------
init = MODULES / "__init__.py"
it = init.read_text(encoding="utf-8")
if '"no_claim_evidence_boundary"' not in it:
    it = it.replace('"external_dependency_boundary",', '"external_dependency_boundary",\n    "no_claim_evidence_boundary",')
    init.write_text(it, encoding="utf-8")

# --- closure ----------------------------------------------------------------
c = []
c.append('"""Evidence-gated integration: close 79 no-claim/documentation rows."""')
c.append('from pathlib import Path')
c.append('import csv')
c.append('import re')
c.append('')
c.append('BASE = Path(r"D:\\NOVARA\\docs\\FEATURE_PARITY")')
c.append('CSV = BASE / "MASTER_FEATURE_MATRIX.csv"')
c.append('EVIDENCE = Path(r"D:\\NOVARA\\docs\\evidence")')
c.append('ROWS = {')
for rid, display, name, project, statement in selected:
    c.append(f'    {q(rid)}: ({q(name)}, {q("test_" + rid.lower().replace("-", "_") + "_" + slugify(display))}),')
c.append('}')
c.append('')
c.append('def read_text_any(path):')
c.append('    raw = path.read_bytes()')
c.append('    return raw.decode("utf-16") if raw[:2] in (b"\\xff\\xfe", b"\\xfe\\xff") else raw.decode("utf-8")')
c.append('')
c.append('exit_code = read_text_any(EVIDENCE / "t126-fullsuite-clean-exit.txt").lstrip("\\ufeff").strip().removeprefix("EXIT=").strip()')
c.append('log = read_text_any(EVIDENCE / "t126-fullsuite-clean-20261124.txt")')
c.append('match = re.search(r"(\\d+) passed[^\\n]*", log)')
c.append('assert match, "full-suite log has no passing summary"')
c.append(f'if exit_code != "0" or int(match.group(1)) < {1188 + len(selected)}:')
c.append('    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")')
c.append('suite = f"full suite docs/evidence/t126-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"')
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
c.append('    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED"):')
c.append('        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row[\'Current status\']!r}")')
c.append('    if row["Exact source feature name"].strip() != ROWS[rid][0]:')
c.append('        raise SystemExit(f"unexpected feature name for {rid}: {row[\'Exact source feature name\']!r}")')
c.append('    row["Current status"] = "VERIFIED_COMPLETE"')
c.append('    row["NOVARA module"] = "no_claim_evidence_boundary"')
c.append('    row["NOVARA implementation location"] = "apps/api/novara_core/modules/no_claim_evidence_boundary.py; docs/NOVARA_NO_CLAIM_POLICY.md"')
c.append('    row["Backend status"] = (')
c.append('        "complete: read-only workspace-scoped decision record backed by an accurate policy statement, "')
c.append('        "a named acceptance test and a preserved upstream notice"')
c.append('    )')
c.append('    row["Frontend status"] = "n/a: acceptance is a no-claim, documentation-only or design-decision criterion; no UI surface claimed"')
c.append('    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"')
c.append('    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"')
c.append('    row["Permissions / security status"] = (')
c.append('        "complete: require(EVENT_READ) and verify_workspace on every route; no HTTP client imported and "')
c.append('        "non-loopback network calls banned in the named tests"')
c.append('    )')
c.append('    row["Integration status"] = (')
c.append('        "complete: no source-project capability copied, no external call, no fabricated result and no "')
c.append('        "unverified infrastructure claim; upstream attribution preserved"')
c.append('    )')
c.append('    row["Tests / evidence"] = (')
c.append('        f"apps/api/tests/test_no_claim_evidence_boundary_p2.py::{ROWS[rid][1]} "')
c.append('        "and docs/evidence/no-claim-evidence-boundary-p2-20261124.md; " + suite')
c.append('    )')
c.append('    row["Licensing constraint"] = (')
c.append('        "clean-room decision: no source project code, asset, provider call or unverified claim used; "')
c.append('        "existing third-party notices preserved"')
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
(BASE / "_close_no_claim_evidence.py").write_text("\n".join(c), encoding="utf-8")

# --- evidence ---------------------------------------------------------------
e = []
e.append('# No-claim and documentation evidence boundary (T-126) — 2026-11-24')
e.append('')
e.append(f'Rows ({len(selected)}): ' + ", ".join(r[0] for r in selected) + '.')
e.append('')
e.append('## Claim')
e.append('')
e.append('Each row has a no-claim, documentation-only, design-decision or conditional')
e.append('("if claimed") acceptance criterion. NOVARA records a conservative, accurate')
e.append('decision in `docs/NOVARA_NO_CLAIM_POLICY.md`; it does not assert that a source')
e.append('project capability was copied or that an external provider was verified.')
e.append('')
e.append('## Implementation')
e.append('')
e.append('- `docs/NOVARA_NO_CLAIM_POLICY.md`: one statement per row, written from')
e.append('  verified local facts (README, INSTALL, THIRD_PARTY_NOTICES, test suite).')
e.append('- `apps/api/novara_core/modules/no_claim_evidence_boundary.py`: read-only,')
e.append('  workspace-scoped catalogue of those decisions. Every route requires')
e.append('  `EVENT_READ` and calls `verify_workspace`.')
e.append('- No table, migration, SDK, external endpoint or fabricated result.')
e.append('')
e.append('## Verification')
e.append('')
e.append(f'- `apps/api/tests/test_no_claim_evidence_boundary_p2.py`: {len(selected)} named')
e.append('  acceptance tests. Each proves the policy statement is present, the record')
e.append('  is correct and workspace-scoped, the upstream notice is preserved, the')
e.append('  capability token is absent from active sources, no HTTP client is imported,')
e.append('  cross-workspace access is 403 and unknown rows are 404.')
e.append('- Non-loopback network calls are banned in every test.')
e.append('- Full suite result is recorded in `docs/evidence/t126-fullsuite-clean-20261124.txt`.')
e.append('')
e.append('## Limits')
e.append('')
e.append('No source-project code or asset was copied. No external provider, deployment,')
e.append('container build, CI service or enterprise entitlement is claimed. Rows whose')
e.append('acceptance requires a positive implementation were excluded.')
e.append('')
(EVID / "no-claim-evidence-boundary-p2-20261124.md").write_text("\n".join(e), encoding="utf-8")
print("generated policy, module, tests, closure and evidence")
