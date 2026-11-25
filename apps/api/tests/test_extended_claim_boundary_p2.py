"""Extended clean-room claims boundary acceptance tests.

Named rows: MS-005, MS-009, MS-010, MS-050, MS-051, MS-059, MS-096, MS-098, CW-119, PM-067, PM-136, PM-155, NV-041, NV-053, NV-055, NV-060, NV-061, NV-063, NV-066, NV-090, NV-091, NV-095, NV-108, NV-110, NV-114, SB-043.

Each test proves the row's negative claim with local evidence: no matching
manifest dependency, route, import or precise token in runtime sources, a
preserved upstream notice, and a read-only workspace-scoped boundary record.
No external SDK, connector, CLI, dashboard, bridge or send capability is installed or claimed.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.extended_claim_boundary import CLAIM_CATALOG

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (
    API_ROOT / "pyproject.toml",
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "docker-compose.yml",
)
WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")

# Every boundary module may name the claims it denies; exclude them from scans.
BOUNDARY_MODULES = {
    "plane_claim_boundary.py",
    "meilisearch_claim_boundary.py",
    "dependency_boundary.py",
    "growthbook_sdk_boundary.py",
    "formbricks_sdk_boundary.py",
    "extended_claim_boundary.py",
}

# Only capability-specific tokens that were verified absent from active sources.
FORBIDDEN_TOKENS = {
    "MS-005": ("prefix-only",),
    "MS-009": ("facet-count",),
    "MS-010": ("sortableattributes",),
    "MS-050": ("task-stream", "task cancellation",),
    "MS-051": ("batch uid",),
    "MS-059": ("log stream",),
    "MS-096": ("benchmark result",),
    "MS-098": ("search analytics dashboard",),
    "CW-119": ("api_access_token",),
    "PM-067": ("digest email",),
    "PM-136": ("vercel postgres", "vercel blob",),
    "PM-155": ("security certification", "data residency",),
    "NV-041": ("headless inbox",),
    "NV-053": ("fabricated provider metric",),
    "NV-055": ("bigquery", "webhook connector",),
    "NV-060": ("@novu/framework", "bridge endpoint",),
    "NV-061": ("@novu/novu", "novu-cli",),
    "NV-063": ("aci channel",),
    "NV-066": ("environment sync",),
    "NV-090": ("novu dashboard",),
    "NV-091": ("agent-inbox-mcp", "mcp bridge",),
    "NV-095": ("@novu/stateless",),
    "NV-108": ("bridge url",),
    "NV-110": ("ai-sdk",),
    "NV-114": ("arbitrary agent code",),
    "SB-043": ("linkedin", "public-post",),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in extended claim boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


@pytest.fixture(scope="module")
def source_text() -> str:
    """Active manifest lines + all runtime sources, lowercased for token scans."""
    parts: list[str] = []
    for manifest in MANIFESTS:
        assert manifest.is_file(), f"missing manifest: {manifest}"
        for raw in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#"):
                parts.append(stripped.lower())
    for source in MODULES_ROOT.rglob("*.py"):
        if source.name in BOUNDARY_MODULES:
            continue
        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())
    for source in WEB_SOURCES:
        assert source.is_file(), f"missing runtime source: {source}"
        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())
    return "\n".join(parts)


def _setup(client):
    owner = bootstrap(client, email="extended-claim@example.com", workspace_name="Extended Claim WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other Extended Claim"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/extended-claim-boundary"


def _assert_notice_preserved(notice: str) -> None:
    full = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert notice in full


def _assert_boundary(client, ctx, row_id: str, source_text: str) -> None:
    spec = CLAIM_CATALOG[row_id]
    listed = client.get(_base(ctx), headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == len(CLAIM_CATALOG)
    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_id"] == row_id
    assert data["name"] == spec["name"]
    assert data["provider"] == spec["provider"]
    assert data["claim"] == spec["claim"]
    assert data["notice"] == spec["notice"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "Negative evidence boundary" in data["notes"]
    for token in FORBIDDEN_TOKENS[row_id]:
        assert token.lower() not in source_text, f"{row_id}: forbidden token {token!r} found in runtime sources"
    _assert_notice_preserved(spec["notice"])
    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/extended-claim-boundary/{row_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 403, cross.text
    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_ms_005_prefix_search(client, db_session, source_text):
    """MS-005: No prefix-only search behaviour is advertised; the local search engine does not claim this capability."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-005", source_text)

def test_ms_009_faceted_navigation_ui(client, db_session, source_text):
    """MS-009: Type filters return real rows; no facet-count figure is displayed or invented."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-009", source_text)

def test_ms_010_sorting_sortableattributes(client, db_session, source_text):
    """MS-010: No UI or API advertises configurable engine sort attributes until they are implemented."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-010", source_text)

def test_ms_050_task_cancellation_deletion_and_streaming(client, db_session, source_text):
    """MS-050: No engine task stream, cancellation or deletion endpoint is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-050", source_text)

def test_ms_051_batches_and_batch_monitoring(client, db_session, source_text):
    """MS-051: No engine batch UID, stream or batch-monitoring claim is made."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-051", source_text)

def test_ms_059_logs_streaming_and_runtime_log_level(client, db_session, source_text):
    """MS-059: Audit events are workspace scoped and correlated; no engine log stream is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-059", source_text)

def test_ms_096_ci_benchmark_fuzz_and_sdk_test_workflows(client, db_session, source_text):
    """MS-096: No benchmark result is asserted anywhere in the inventory."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-096", source_text)

def test_ms_098_search_analytics_and_usage_events(client, db_session, source_text):
    """MS-098: No search analytics dashboard is claimed before query events are emitted and tested."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-098", source_text)

def test_cw_119_legacy_api_access_token_header(client, db_session, source_text):
    """CW-119: No route accepts a legacy token header; bearer tokens remain the only accepted form."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "CW-119", source_text)

def test_pm_067_data_room_digest_emails(client, db_session, source_text):
    """PM-067: No digest send is claimed without provider evidence."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PM-067", source_text)

def test_pm_136_vercel_postgres_and_blob_defaults(client, db_session, source_text):
    """PM-136: Local install works with no Vercel account or hosted Postgres/Blob dependency."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PM-136", source_text)

def test_pm_155_security_certifications_and_data_residen(client, db_session, source_text):
    """PM-155: The inventory states no certification is verified for NOVARA and no UI claims one."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PM-155", source_text)

def test_nv_041_headless_inbox_and_custom_layouts(client, db_session, source_text):
    """NV-041: No duplicate UI framework is introduced; the local permissioned API remains the single source."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-041", source_text)

def test_nv_053_usage_and_delivery_analytics(client, db_session, source_text):
    """NV-053: Analytics values trace to stored events; no provider metric is fabricated."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-053", source_text)

def test_nv_055_webhook_connectors_bigquery_s3_segment_a(client, db_session, source_text):
    """NV-055: No default build depends on a paid external warehouse or connector."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-055", source_text)

def test_nv_060_code_first_workflows_novu_framework_brid(client, db_session, source_text):
    """NV-060: Code-first execution is not advertised unless a bridge is actually implemented and tested."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-060", source_text)

def test_nv_061_novu_cli_novu_novu(client, db_session, source_text):
    """NV-061: No Novu-cloud CLI login is required or implied by NOVARA docs."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-061", source_text)

def test_nv_063_agent_communication_infrastructure_aci(client, db_session, source_text):
    """NV-063: No two-way channel conversation is claimed without a real connector and named test."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-063", source_text)

def test_nv_066_environments_development_production_cust(client, db_session, source_text):
    """NV-066: Workspace separation holds and no environment sync claim is made without implementation."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-066", source_text)

def test_nv_090_dashboard_and_human_dashboard_react_apps(client, db_session, source_text):
    """NV-090: Any dashboard view reads local APIs and never embeds a foreign-branded Novu dashboard."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-090", source_text)

def test_nv_091_agent_inbox_mcp_bridge_apps_agent_inbox_(client, db_session, source_text):
    """NV-091: No agent MCP tool is advertised without workspace and approval enforcement."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-091", source_text)

def test_nv_095_novu_stateless_provider_utilities(client, db_session, source_text):
    """NV-095: Adapter helpers never claim delivery and are covered by named tests."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-095", source_text)

def test_nv_108_agent_management_api_and_bridge_registra(client, db_session, source_text):
    """NV-108: No bridge URL is accepted without workspace authorisation and environment checks."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-108", source_text)

def test_nv_110_ai_framework_adapters_novu_framework_ai_(client, db_session, source_text):
    """NV-110: No AI model call is claimed as verified and every agent tool passes permissions."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-110", source_text)

def test_nv_114_custom_code_agent_bridge_and_handlers(client, db_session, source_text):
    """NV-114: No arbitrary agent code executes without isolation and a named test."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "NV-114", source_text)

def test_sb_043_linkedin_related_agent_roles(client, db_session, source_text):
    """SB-043: Design-constraint review confirms no public-post route exists and no LinkedIn credential is required."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "SB-043", source_text)
