"""No-claim and documentation evidence boundary acceptance tests.

Named rows (81): MS-101, PL-075, PL-143, PL-152, MT-005, MT-006, MT-038, MT-061, MT-084, MT-085, MT-087, MT-088, MT-090, MT-091, MT-103, MT-104, MT-119, MT-120, MT-125, MT-128, MT-131, MT-132, MT-133, CW-026, CW-034, CW-044, CW-046, CW-058, CW-061, CW-062, CW-063, CW-064, CW-068, CW-069, CW-070, CW-071, CW-072, CW-080, CW-103, CW-125, CW-126, CW-128, CW-136, CW-147, CW-150, CW-154, CW-156, CW-157, CW-165, NV-016, NV-021, NV-037, NV-049, NV-050, NV-064, NV-083, NV-117, PL-126, PL-131, PL-155, SB-039, SB-040, SB-041, SB-044, SB-047, SB-049, SB-050, SB-058, SB-059, SB-063, SB-065, SB-066, SB-068, GB-194, GB-205, GB-213, GB-234, GB-239, GB-250, FB-193, NV-075.

Each test proves that the decision is recorded in the policy document, that
the record is read-only and workspace-scoped, that the upstream notice is
preserved, that no precise capability token appears in active manifests or
runtime sources, and that no HTTP client is imported. Cross-workspace access
fails closed and unknown rows return 404. Non-loopback network is banned.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

from novara_core.modules.no_claim_evidence_boundary import CLAIM_CATALOG

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (API_ROOT / "pyproject.toml", REPO_ROOT / "Dockerfile", REPO_ROOT / "docker-compose.yml")
WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")
BOUNDARY_MODULES = {p.name for p in MODULES_ROOT.glob("*boundary*.py")}

FORBIDDEN_TOKENS = {
    "MS-101": ("openapi specification generation and ci sync",),
    "PL-075": ("live service",),
    "PL-143": ("keyboard shortcuts and power-k",),
    "PL-152": ("reverse proxy and certificate settings",),
    "MT-005": ("self-host free forever with all features",),
    "MT-006": ("production packaged release from mautic.org/download",),
    "MT-038": ("cloud storage plugin",),
    "MT-061": ("marketplacebundle",),
    "MT-084": ("ddev developer environment",),
    "MT-085": ("composer install and bin/console install",),
    "MT-087": ("web server support apache, nginx and iis",),
    "MT-088": ("shared hosting not recommended",),
    "MT-090": ("phpstan static analysis and baseline",),
    "MT-091": ("codeception and codecov configuration",),
    "MT-103": ("mautic trademark",),
    "MT-104": ("third-party notices",),
    "MT-119": ("source-tree install alpha warning",),
    "MT-120": ("7.x coverage percentage not verified",),
    "MT-125": ("transifex maintenance command",),
    "MT-128": ("upgrade event extension",),
    "MT-131": ("maintenance event extension",),
    "MT-132": ("builder event extension",),
    "MT-133": ("import and export event extension",),
    "CW-026": ("keyboard shortcuts",),
    "CW-034": ("dashboard apps",),
    "CW-044": ("sms channel",),
    "CW-046": ("voice channel",),
    "CW-058": ("sla timers and status indicators",),
    "CW-061": ("captain assistant",),
    "CW-062": ("captain copilot",),
    "CW-063": ("captain memories",),
    "CW-064": ("captain reply suggestions",),
    "CW-068": ("captain triage",),
    "CW-069": ("captain scenarios",),
    "CW-070": ("captain monitors / convergence",),
    "CW-071": ("captain copilot / mcp tools",),
    "CW-072": ("dialogflow chatbot",),
    "CW-080": ("whatsapp campaigns",),
    "CW-103": ("whatsapp csat templates",),
    "CW-125": ("linear integration",),
    "CW-126": ("shopify integration",),
    "CW-128": ("chatwoot cli for coding agents",),
    "CW-136": ("optional github oauth strategy",),
    "CW-147": ("digitalocean one-click kubernetes deployment",),
    "CW-150": ("development container and deployment manifests",),
    "CW-154": ("redis cache and queue backend",),
    "CW-156": ("opensearch and searchkick advanced search backend",),
    "CW-157": ("s3, azure and gcs object storage",),
    "CW-165": ("process liveness and cloudwatch telemetry",),
    "NV-016": ("tool channel steps (pagerduty, opsgenie, grafana, tool webhook)",),
    "NV-021": ("sms notifications",),
    "NV-037": ("inbox snooze",),
    "NV-049": ("email activity tracking (delivered, opened, clicked, bounced)",),
    "NV-050": ("push activity tracking",),
    "NV-064": ("web chat channel",),
    "NV-083": ("s3-compatible object storage",),
    "NV-117": ("novu agent skills",),
    "PL-126": ("sensitive data scanning",),
    "PL-131": ("mcp server and connectors",),
    "PL-155": ("plane cloud and all-in-one image",),
    "SB-039": ("scout agent role",),
    "SB-040": ("writer agent role",),
    "SB-041": ("handler agent role",),
    "SB-044": ("editable markdown agent skills",),
    "SB-047": ("heartbeat loop",),
    "SB-049": ("pid/lock file preventing duplicate loops",),
    "SB-050": ("extension tick steps with timeout",),
    "SB-058": ("stats and instance information",),
    "SB-059": ("dashboard docs disabled",),
    "SB-063": ("mcp server toolset",),
    "SB-065": ("extension entry-point registry",),
    "SB-066": ("cli commands",),
    "SB-068": ("desktop tray support",),
    "GB-194": ("growthbook simulate",),
    "GB-205": ("growthbook teams",),
    "GB-213": ("growthbook custom-roles",),
    "GB-234": ("growthbook holdouts",),
    "GB-239": ("growthbook dashboards",),
    "GB-250": ("growthbook releases",),
    "FB-193": ("headless surveys guide",),
    "NV-075": ("no-code editors, layouts and block email editor (`libs/maily-*`)",),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in no-claim boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


@pytest.fixture(scope="module")
def source_text() -> str:
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
    owner = bootstrap(client, email="no-claim@example.com", workspace_name="No Claim WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other No Claim"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/no-claim-evidence-boundary"


def _assert_decision(client, ctx, row_id: str, source_text: str, policy: str) -> None:
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
    assert data["claim"] == "no-claim-" + row_id.lower().replace("-", "_")
    assert data["statement"] == spec["statement"]
    assert spec["statement"] in policy, f"{row_id}: statement missing from policy document"
    assert data["policy_file"] == "docs/NOVARA_NO_CLAIM_POLICY.md"
    assert data["notice"] == spec["notice"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "Conservative no-claim" in data["notes"]
    for token in FORBIDDEN_TOKENS[row_id]:
        assert token.lower() not in source_text, f"{row_id}: capability token {token!r} found in runtime sources"
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert spec["notice"] in notice
    module_src = (MODULES_ROOT / "no_claim_evidence_boundary.py").read_text(encoding="utf-8").lower()
    assert not re.search(r"^\s*(from|import)\s+(httpx|requests|socket|aiohttp|urllib)\b", module_src, re.M)
    assert not re.search(r"https?://", module_src)
    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/no-claim-evidence-boundary/{row_id}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


@pytest.fixture(scope="module")
def policy_text() -> str:
    return (REPO_ROOT / "docs/NOVARA_NO_CLAIM_POLICY.md").read_text(encoding="utf-8")


def test_ms_101_openapi_specification_generation_and_ci_sy(client, db_session, source_text, policy_text):
    """MS-101: OpenAPI specification generation and CI sync is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MS-101", source_text, policy_text)

def test_pl_075_live_service(client, db_session, source_text, policy_text):
    """PL-075: Live service is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-075", source_text, policy_text)

def test_pl_143_shortcut_handling(client, db_session, source_text, policy_text):
    """PL-143: Keyboard shortcuts and Power-K is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-143", source_text, policy_text)

def test_pl_152_reverse_proxy_and_certificate_settings(client, db_session, source_text, policy_text):
    """PL-152: Reverse proxy and certificate settings is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-152", source_text, policy_text)

def test_mt_005_self_host_free_forever_with_all_features(client, db_session, source_text, policy_text):
    """MT-005: Self-host free forever with all features is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-005", source_text, policy_text)

def test_mt_006_production_packaged_release_from_mautic_or(client, db_session, source_text, policy_text):
    """MT-006: Production packaged release from mautic.org/download is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-006", source_text, policy_text)

def test_mt_038_cloud_storage_plugin(client, db_session, source_text, policy_text):
    """MT-038: Cloud storage plugin is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-038", source_text, policy_text)

def test_mt_061_marketplacebundle(client, db_session, source_text, policy_text):
    """MT-061: MarketplaceBundle is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-061", source_text, policy_text)

def test_mt_084_ddev_developer_environment(client, db_session, source_text, policy_text):
    """MT-084: DDEV developer environment is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-084", source_text, policy_text)

def test_mt_085_composer_install_and_bin_console_install(client, db_session, source_text, policy_text):
    """MT-085: Composer install and bin/console install is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-085", source_text, policy_text)

def test_mt_087_web_server_support_apache_nginx_and_iis(client, db_session, source_text, policy_text):
    """MT-087: Web server support Apache, Nginx and IIS is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-087", source_text, policy_text)

def test_mt_088_shared_hosting_not_recommended(client, db_session, source_text, policy_text):
    """MT-088: Shared hosting not recommended is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-088", source_text, policy_text)

def test_mt_090_static_analysis_status(client, db_session, source_text, policy_text):
    """MT-090: PHPStan static analysis and baseline is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-090", source_text, policy_text)

def test_mt_091_coverage_tooling_status(client, db_session, source_text, policy_text):
    """MT-091: Codeception and Codecov configuration is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-091", source_text, policy_text)

def test_mt_103_mautic_trademark(client, db_session, source_text, policy_text):
    """MT-103: Mautic trademark is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-103", source_text, policy_text)

def test_mt_104_third_party_notices(client, db_session, source_text, policy_text):
    """MT-104: Third-party notices is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-104", source_text, policy_text)

def test_mt_119_source_tree_install_alpha_warning(client, db_session, source_text, policy_text):
    """MT-119: Source-tree install alpha warning is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-119", source_text, policy_text)

def test_mt_120_7_x_coverage_percentage_not_verified(client, db_session, source_text, policy_text):
    """MT-120: 7.x coverage percentage not verified is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-120", source_text, policy_text)

def test_mt_125_transifex_maintenance_command(client, db_session, source_text, policy_text):
    """MT-125: Transifex maintenance command is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-125", source_text, policy_text)

def test_mt_128_upgrade_event_extension(client, db_session, source_text, policy_text):
    """MT-128: Upgrade event extension is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-128", source_text, policy_text)

def test_mt_131_maintenance_event_extension(client, db_session, source_text, policy_text):
    """MT-131: Maintenance event extension is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-131", source_text, policy_text)

def test_mt_132_builder_event_extension(client, db_session, source_text, policy_text):
    """MT-132: Builder event extension is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-132", source_text, policy_text)

def test_mt_133_import_and_export_event_extension(client, db_session, source_text, policy_text):
    """MT-133: Import and export event extension is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "MT-133", source_text, policy_text)

def test_cw_026_inbox_shortcut_handling(client, db_session, source_text, policy_text):
    """CW-026: Keyboard shortcuts is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-026", source_text, policy_text)

def test_cw_034_dashboard_apps(client, db_session, source_text, policy_text):
    """CW-034: Dashboard apps is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-034", source_text, policy_text)

def test_cw_044_sms_channel(client, db_session, source_text, policy_text):
    """CW-044: SMS channel is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-044", source_text, policy_text)

def test_cw_046_voice_channel(client, db_session, source_text, policy_text):
    """CW-046: Voice channel is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-046", source_text, policy_text)

def test_cw_058_sla_timers_and_status_indicators(client, db_session, source_text, policy_text):
    """CW-058: SLA timers and status indicators is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-058", source_text, policy_text)

def test_cw_061_captain_assistant(client, db_session, source_text, policy_text):
    """CW-061: Captain Assistant is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-061", source_text, policy_text)

def test_cw_062_captain_copilot(client, db_session, source_text, policy_text):
    """CW-062: Captain Copilot is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-062", source_text, policy_text)

def test_cw_063_captain_memories(client, db_session, source_text, policy_text):
    """CW-063: Captain Memories is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-063", source_text, policy_text)

def test_cw_064_captain_reply_suggestions(client, db_session, source_text, policy_text):
    """CW-064: Captain Reply suggestions is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-064", source_text, policy_text)

def test_cw_068_captain_triage(client, db_session, source_text, policy_text):
    """CW-068: Captain Triage is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-068", source_text, policy_text)

def test_cw_069_captain_scenarios(client, db_session, source_text, policy_text):
    """CW-069: Captain Scenarios is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-069", source_text, policy_text)

def test_cw_070_captain_monitors_convergence(client, db_session, source_text, policy_text):
    """CW-070: Captain Monitors / Convergence is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-070", source_text, policy_text)

def test_cw_071_captain_copilot_mcp_tools(client, db_session, source_text, policy_text):
    """CW-071: Captain copilot / MCP tools is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-071", source_text, policy_text)

def test_cw_072_dialogflow_chatbot(client, db_session, source_text, policy_text):
    """CW-072: Dialogflow chatbot is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-072", source_text, policy_text)

def test_cw_080_whatsapp_campaigns(client, db_session, source_text, policy_text):
    """CW-080: WhatsApp campaigns is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-080", source_text, policy_text)

def test_cw_103_whatsapp_csat_templates(client, db_session, source_text, policy_text):
    """CW-103: WhatsApp CSAT templates is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-103", source_text, policy_text)

def test_cw_125_linear_integration(client, db_session, source_text, policy_text):
    """CW-125: Linear integration is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-125", source_text, policy_text)

def test_cw_126_shopify_integration(client, db_session, source_text, policy_text):
    """CW-126: Shopify integration is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-126", source_text, policy_text)

def test_cw_128_chatwoot_cli_for_coding_agents(client, db_session, source_text, policy_text):
    """CW-128: Chatwoot CLI for coding agents is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-128", source_text, policy_text)

def test_cw_136_optional_github_oauth_strategy(client, db_session, source_text, policy_text):
    """CW-136: Optional GitHub OAuth strategy is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-136", source_text, policy_text)

def test_cw_147_managed_one_click_deployment(client, db_session, source_text, policy_text):
    """CW-147: DigitalOcean one-click Kubernetes deployment is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-147", source_text, policy_text)

def test_cw_150_development_container_and_deployment_manif(client, db_session, source_text, policy_text):
    """CW-150: Development container and deployment manifests is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-150", source_text, policy_text)

def test_cw_154_redis_cache_and_queue_backend(client, db_session, source_text, policy_text):
    """CW-154: Redis cache and queue backend is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-154", source_text, policy_text)

def test_cw_156_opensearch_and_searchkick_advanced_search_(client, db_session, source_text, policy_text):
    """CW-156: OpenSearch and Searchkick advanced search backend is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-156", source_text, policy_text)

def test_cw_157_s3_azure_and_gcs_object_storage(client, db_session, source_text, policy_text):
    """CW-157: S3, Azure and GCS object storage is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-157", source_text, policy_text)

def test_cw_165_process_liveness_and_cloudwatch_telemetry(client, db_session, source_text, policy_text):
    """CW-165: Process liveness and CloudWatch telemetry is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "CW-165", source_text, policy_text)

def test_nv_016_tool_channel_steps_pagerduty_opsgenie_graf(client, db_session, source_text, policy_text):
    """NV-016: Tool channel steps (PagerDuty, Opsgenie, Grafana, Tool Webhook) is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-016", source_text, policy_text)

def test_nv_021_sms_notifications(client, db_session, source_text, policy_text):
    """NV-021: SMS notifications is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-021", source_text, policy_text)

def test_nv_037_inbox_snooze(client, db_session, source_text, policy_text):
    """NV-037: Inbox snooze is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-037", source_text, policy_text)

def test_nv_049_email_activity_tracking_delivered_opened_c(client, db_session, source_text, policy_text):
    """NV-049: Email activity tracking (delivered, opened, clicked, bounced) is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-049", source_text, policy_text)

def test_nv_050_push_activity_tracking(client, db_session, source_text, policy_text):
    """NV-050: Push activity tracking is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-050", source_text, policy_text)

def test_nv_064_web_chat_channel(client, db_session, source_text, policy_text):
    """NV-064: Web Chat channel is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-064", source_text, policy_text)

def test_nv_083_s3_compatible_object_storage(client, db_session, source_text, policy_text):
    """NV-083: S3-compatible object storage is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-083", source_text, policy_text)

def test_nv_117_novu_agent_skills(client, db_session, source_text, policy_text):
    """NV-117: Novu Agent Skills is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-117", source_text, policy_text)

def test_pl_126_sensitive_data_scanning(client, db_session, source_text, policy_text):
    """PL-126: Sensitive data scanning is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-126", source_text, policy_text)

def test_pl_131_mcp_server_and_connectors(client, db_session, source_text, policy_text):
    """PL-131: MCP server and connectors is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-131", source_text, policy_text)

def test_pl_155_hosted_cloud_image(client, db_session, source_text, policy_text):
    """PL-155: Plane Cloud and all-in-one image is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "PL-155", source_text, policy_text)

def test_sb_039_scout_agent_role(client, db_session, source_text, policy_text):
    """SB-039: Scout agent role is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-039", source_text, policy_text)

def test_sb_040_writer_agent_role(client, db_session, source_text, policy_text):
    """SB-040: Writer agent role is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-040", source_text, policy_text)

def test_sb_041_handler_agent_role(client, db_session, source_text, policy_text):
    """SB-041: Handler agent role is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-041", source_text, policy_text)

def test_sb_044_editable_markdown_agent_skills(client, db_session, source_text, policy_text):
    """SB-044: Editable Markdown agent skills is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-044", source_text, policy_text)

def test_sb_047_heartbeat_loop(client, db_session, source_text, policy_text):
    """SB-047: Heartbeat loop is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-047", source_text, policy_text)

def test_sb_049_pid_lock_file_preventing_duplicate_loops(client, db_session, source_text, policy_text):
    """SB-049: PID/lock file preventing duplicate loops is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-049", source_text, policy_text)

def test_sb_050_extension_tick_steps_with_timeout(client, db_session, source_text, policy_text):
    """SB-050: Extension tick steps with timeout is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-050", source_text, policy_text)

def test_sb_058_stats_and_instance_information(client, db_session, source_text, policy_text):
    """SB-058: Stats and instance information is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-058", source_text, policy_text)

def test_sb_059_dashboard_docs_disabled(client, db_session, source_text, policy_text):
    """SB-059: Dashboard docs disabled is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-059", source_text, policy_text)

def test_sb_063_mcp_server_toolset(client, db_session, source_text, policy_text):
    """SB-063: MCP server toolset is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-063", source_text, policy_text)

def test_sb_065_extension_entry_point_registry(client, db_session, source_text, policy_text):
    """SB-065: Extension entry-point registry is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-065", source_text, policy_text)

def test_sb_066_cli_commands(client, db_session, source_text, policy_text):
    """SB-066: CLI commands is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-066", source_text, policy_text)

def test_sb_068_desktop_tray_support(client, db_session, source_text, policy_text):
    """SB-068: Desktop tray support is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "SB-068", source_text, policy_text)

def test_gb_194_simulate(client, db_session, source_text, policy_text):
    """GB-194: simulate is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-194", source_text, policy_text)

def test_gb_205_teams(client, db_session, source_text, policy_text):
    """GB-205: teams is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-205", source_text, policy_text)

def test_gb_213_custom_roles(client, db_session, source_text, policy_text):
    """GB-213: custom-roles is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-213", source_text, policy_text)

def test_gb_234_holdouts(client, db_session, source_text, policy_text):
    """GB-234: holdouts is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-234", source_text, policy_text)

def test_gb_239_dashboards(client, db_session, source_text, policy_text):
    """GB-239: dashboards is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-239", source_text, policy_text)

def test_gb_250_releases(client, db_session, source_text, policy_text):
    """GB-250: releases is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "GB-250", source_text, policy_text)

def test_fb_193_headless_surveys_guide(client, db_session, source_text, policy_text):
    """FB-193: Headless Surveys guide is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "FB-193", source_text, policy_text)

def test_nv_075_no_code_editors_layouts_and_block_email_ed(client, db_session, source_text, policy_text):
    """NV-075: No-code editors, layouts and block email editor (`libs/maily-*`) is handled by a conservative documented decision."""
    ctx = _setup(client)
    _assert_decision(client, ctx, "NV-075", source_text, policy_text)
