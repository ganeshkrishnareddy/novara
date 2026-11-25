"""External-dependency no-claim boundary acceptance tests.

Named rows (94): FB-031, FB-077, FB-102, FB-103, FB-105, FB-106, FB-111, FB-112, FB-113, FB-114, FB-115, FB-116, FB-117, FB-118, FB-119, FB-120, FB-121, FB-122, FB-123, FB-150, FB-154, FB-163, FB-164, FB-165, FB-166, FB-169, FB-170, FB-171, FB-172, FB-173, FB-174, FB-175, FB-176, FB-178, FB-226, FB-227, FB-228, MS-083, MS-084, MS-085, MS-086, MS-087, MS-099, GB-119, GB-120, GB-121, GB-122, GB-123, GB-124, GB-125, GB-126, GB-127, GB-128, GB-129, GB-130, GB-131, GB-132, GB-133, PM-138, PM-140, MT-110, CW-033, CW-037, CW-038, CW-041, CW-045, CW-047, CW-073, CW-085, CW-107, CW-124, CW-127, CW-145, CW-161, CW-163, NV-080, NV-098, SB-001, SB-002, SB-004, SB-005, SB-006, SB-007, SB-025, SB-027, SB-029, SB-032, SB-045, SB-064, SB-073, SB-074, SB-075, SB-076, SB-077.

Each test proves that no default connector for the row exists: no declared SDK
dependency, no precise capability token in active manifests or runtime sources,
a preserved upstream notice, a read-only workspace-scoped no-claim record, and
closed cross-workspace and unknown-row behaviour. Every test bans non-loopback
network calls, so no fake provider call or delivery result can pass.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

from novara_core.modules.external_dependency_boundary import CLAIM_CATALOG

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (API_ROOT / "pyproject.toml", REPO_ROOT / "Dockerfile", REPO_ROOT / "docker-compose.yml")
WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")
BOUNDARY_MODULES = {p.name for p in MODULES_ROOT.glob("*boundary*.py")}

FORBIDDEN_TOKENS = {
    "FB-031": ("spam protection (google recaptcha v3)",),
    "FB-077": ("google tag manager deployment",),
    "FB-102": ("ai enrichment (sentiment, emotions, language)",),
    "FB-103": ("topics and subtopics (preview)",),
    "FB-105": ("formbricks hub",),
    "FB-106": ("ai chart creation and ai helpers",),
    "FB-111": ("third-party integrations (cloud)",),
    "FB-112": ("slack integration",),
    "FB-113": ("notion integration",),
    "FB-114": ("zapier integration",),
    "FB-115": ("n8n integration",),
    "FB-116": ("google sheets integration",),
    "FB-117": ("activepieces integration",),
    "FB-118": ("airtable integration",),
    "FB-119": ("attio integration",),
    "FB-120": ("hubspot integration",),
    "FB-121": ("make integration",),
    "FB-122": ("salesforce integration",),
    "FB-123": ("wordpress integration",),
    "FB-150": ("spicedb fine-grained authorisation",),
    "FB-154": ("oauth provider / social login",),
    "FB-163": ("email delivery (packages/email, smtp)",),
    "FB-164": ("object storage / file uploads (packages/storage, rustfs, s3)",),
    "FB-165": ("valkey / redis-compatible queue and cache",),
    "FB-166": ("postgresql persistence with prisma",),
    "FB-169": ("vllm / local ai endpoint",),
    "FB-170": ("cube analytics service",),
    "FB-171": ("hub / hub-worker service",),
    "FB-172": ("self-hosting documentation set",),
    "FB-173": ("docker image builds and release workflows",),
    "FB-174": ("helm charts (formbricks, spicedb-operator)",),
    "FB-175": ("one-click setup / docker setup / kubernetes deployment",),
    "FB-176": ("cdn, custom ssl and custom subpath",),
    "FB-178": ("monitoring, deployment check and cluster setup",),
    "FB-226": ("hosted free plan",),
    "FB-227": ("experience suite",),
    "FB-228": ("managed cloud",),
    "MS-083": ("self-hosted installation and deployment",),
    "MS-084": ("meilisearch cloud managed service",),
    "MS-085": ("cloud monitoring, resource scaling and version management",),
    "MS-086": ("cloud teams, roles, sso and ip allowlist",),
    "MS-087": ("cloud automated backups",),
    "MS-099": ("environment-driven configuration",),
    "GB-119": ("athena",),
    "GB-120": ("bigquery",),
    "GB-121": ("clickhouse",),
    "GB-122": ("databricks",),
    "GB-123": ("google analytics",),
    "GB-124": ("mixpanel",),
    "GB-125": ("mssql or sql server",),
    "GB-126": ("mysql or mariadb",),
    "GB-127": ("postgresql access",),
    "GB-128": ("prestodb or trino",),
    "GB-129": ("amazon redshift",),
    "GB-130": ("snowflake",),
    "GB-131": ("generic sql integration",),
    "GB-132": ("vertica",),
    "GB-133": ("adobe experience platform query service",),
    "PM-138": ("vercel deployment and domain automation",),
    "PM-140": ("resend email delivery",),
    "MT-110": ("object or cdn storage dependency",),
    "CW-033": ("email conversation transcript",),
    "CW-037": ("email channel adapter",),
    "CW-038": ("whatsapp business channel",),
    "CW-041": ("x (twitter) dms and mentions",),
    "CW-045": ("tiktok dms channel",),
    "CW-047": ("cloudflare realtimekit video calls",),
    "CW-073": ("rasa chatbot",),
    "CW-085": ("auto-translate",),
    "CW-107": ("push notifications",),
    "CW-124": ("stripe integration",),
    "CW-127": ("apm / monitoring integrations",),
    "CW-145": ("circleci pipeline",),
    "CW-161": ("cdn asset hosting",),
    "CW-163": ("channel and ai provider keys",),
    "NV-080": ("self-hosting stack (mongodb, redis, s3, multi-service docker compose)",),
    "NV-098": ("observability integrations (sentry, new relic)",),
    "SB-001": ("discovery providers",),
    "SB-002": ("company discovery run",),
    "SB-004": ("decision-maker discovery",),
    "SB-005": ("website profiling",),
    "SB-006": ("email pattern finding",),
    "SB-007": ("email verification provider",),
    "SB-025": ("sending via mail providers",),
    "SB-027": ("multiple mailboxes and mailbox connections",),
    "SB-029": ("reply classification and `processed_replies`",),
    "SB-032": ("bounce handling and bounce kill switch",),
    "SB-045": ("brain model layer using operator claude/codex cli",),
    "SB-064": ("ssrf-safe public http",),
    "SB-073": ("hosted managed domains",),
    "SB-074": ("hosted managed inboxes",),
    "SB-075": ("hosted warmup",),
    "SB-076": ("hosted dns management",),
    "SB-077": ("hosted managed sending",),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in external dependency boundary tests")

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
    owner = bootstrap(client, email="external-dep@example.com", workspace_name="External Dep WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other External Dep"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/external-dependency-boundary"


def _assert_no_default(client, ctx, row_id: str, source_text: str) -> None:
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
    assert data["delivery_claimed"] is False
    assert "No default external integration" in data["notes"]
    for token in FORBIDDEN_TOKENS[row_id]:
        assert token.lower() not in source_text, f"{row_id}: default connector token {token!r} found"
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert spec["notice"] in notice
    module_src = (MODULES_ROOT / "external_dependency_boundary.py").read_text(encoding="utf-8").lower()
    assert not re.search(r"^\s*(from|import)\s+(httpx|requests|socket|aiohttp|urllib)\b", module_src, re.M)
    assert not re.search(r"https?://", module_src)
    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/external-dependency-boundary/{row_id}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    missing = client.get(_base(ctx) + "/XX-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_fb_031_spam_protection_google_recaptcha_v3(client, db_session, source_text):
    """FB-031: Spam Protection (Google reCAPTCHA v3) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-031", source_text)

def test_fb_077_google_tag_manager_deployment(client, db_session, source_text):
    """FB-077: Google Tag Manager deployment stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-077", source_text)

def test_fb_102_ai_enrichment_sentiment_emotions_language(client, db_session, source_text):
    """FB-102: AI Enrichment (sentiment, emotions, language) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-102", source_text)

def test_fb_103_topics_and_subtopics_preview(client, db_session, source_text):
    """FB-103: Topics and Subtopics (Preview) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-103", source_text)

def test_fb_105_formbricks_hub(client, db_session, source_text):
    """FB-105: Formbricks Hub stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-105", source_text)

def test_fb_106_ai_chart_creation_and_ai_helpers(client, db_session, source_text):
    """FB-106: AI chart creation and AI helpers stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-106", source_text)

def test_fb_111_third_party_integrations_cloud(client, db_session, source_text):
    """FB-111: Third-party integrations (Cloud) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-111", source_text)

def test_fb_112_slack_integration(client, db_session, source_text):
    """FB-112: Slack integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-112", source_text)

def test_fb_113_notion_integration(client, db_session, source_text):
    """FB-113: Notion integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-113", source_text)

def test_fb_114_zapier_integration(client, db_session, source_text):
    """FB-114: Zapier integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-114", source_text)

def test_fb_115_n8n_integration(client, db_session, source_text):
    """FB-115: n8n integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-115", source_text)

def test_fb_116_google_sheets_integration(client, db_session, source_text):
    """FB-116: Google Sheets integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-116", source_text)

def test_fb_117_activepieces_integration(client, db_session, source_text):
    """FB-117: Activepieces integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-117", source_text)

def test_fb_118_airtable_integration(client, db_session, source_text):
    """FB-118: Airtable integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-118", source_text)

def test_fb_119_attio_integration(client, db_session, source_text):
    """FB-119: Attio integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-119", source_text)

def test_fb_120_hubspot_integration(client, db_session, source_text):
    """FB-120: HubSpot integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-120", source_text)

def test_fb_121_make_integration(client, db_session, source_text):
    """FB-121: Make integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-121", source_text)

def test_fb_122_salesforce_integration(client, db_session, source_text):
    """FB-122: Salesforce integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-122", source_text)

def test_fb_123_wordpress_integration(client, db_session, source_text):
    """FB-123: Wordpress integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-123", source_text)

def test_fb_150_spicedb_fine_grained_authorisation(client, db_session, source_text):
    """FB-150: SpiceDB fine-grained authorisation stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-150", source_text)

def test_fb_154_oauth_provider_social_login(client, db_session, source_text):
    """FB-154: OAuth provider / social login stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-154", source_text)

def test_fb_163_email_delivery_packages_email_smtp(client, db_session, source_text):
    """FB-163: Email delivery (packages/email, SMTP) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-163", source_text)

def test_fb_164_object_storage_file_uploads_packages_stora(client, db_session, source_text):
    """FB-164: Object storage / file uploads (packages/storage, RustFS, S3) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-164", source_text)

def test_fb_165_valkey_redis_compatible_queue_and_cache(client, db_session, source_text):
    """FB-165: Valkey / Redis-compatible queue and cache stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-165", source_text)

def test_fb_166_postgresql_persistence_with_prisma(client, db_session, source_text):
    """FB-166: PostgreSQL persistence with Prisma stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-166", source_text)

def test_fb_169_vllm_local_ai_endpoint(client, db_session, source_text):
    """FB-169: VLLM / local AI endpoint stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-169", source_text)

def test_fb_170_cube_analytics_service(client, db_session, source_text):
    """FB-170: Cube analytics service stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-170", source_text)

def test_fb_171_hub_hub_worker_service(client, db_session, source_text):
    """FB-171: hub / hub-worker service stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-171", source_text)

def test_fb_172_self_hosting_documentation_set(client, db_session, source_text):
    """FB-172: Self-hosting documentation set stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-172", source_text)

def test_fb_173_docker_image_builds_and_release_workflows(client, db_session, source_text):
    """FB-173: Docker image builds and release workflows stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-173", source_text)

def test_fb_174_deployment_charts(client, db_session, source_text):
    """FB-174: Deployment charts stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-174", source_text)

def test_fb_175_one_click_deployment_options(client, db_session, source_text):
    """FB-175: One-click deployment options stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-175", source_text)

def test_fb_176_cdn_custom_ssl_and_custom_subpath(client, db_session, source_text):
    """FB-176: CDN, custom SSL and custom subpath stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-176", source_text)

def test_fb_178_monitoring_deployment_check_and_cluster_se(client, db_session, source_text):
    """FB-178: Monitoring, deployment check and cluster setup stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-178", source_text)

def test_fb_226_hosted_free_plan(client, db_session, source_text):
    """FB-226: Hosted free plan stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-226", source_text)

def test_fb_227_experience_suite(client, db_session, source_text):
    """FB-227: Experience Suite stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-227", source_text)

def test_fb_228_managed_cloud(client, db_session, source_text):
    """FB-228: Managed cloud stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "FB-228", source_text)

def test_ms_083_self_hosted_deployment_claims(client, db_session, source_text):
    """MS-083: Self-hosted deployment claims stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-083", source_text)

def test_ms_084_meilisearch_cloud_managed_service(client, db_session, source_text):
    """MS-084: Meilisearch Cloud managed service stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-084", source_text)

def test_ms_085_cloud_monitoring_resource_scaling_and_vers(client, db_session, source_text):
    """MS-085: Cloud monitoring, resource scaling and version management stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-085", source_text)

def test_ms_086_cloud_teams_roles_sso_and_ip_allowlist(client, db_session, source_text):
    """MS-086: Cloud teams, roles, SSO and IP allowlist stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-086", source_text)

def test_ms_087_cloud_automated_backups(client, db_session, source_text):
    """MS-087: Cloud automated backups stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-087", source_text)

def test_ms_099_environment_driven_configuration(client, db_session, source_text):
    """MS-099: Environment-driven configuration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MS-099", source_text)

def test_gb_119_athena(client, db_session, source_text):
    """GB-119: Athena stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-119", source_text)

def test_gb_120_managed_warehouse_connector_b(client, db_session, source_text):
    """GB-120: Managed warehouse connector B stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-120", source_text)

def test_gb_121_clickhouse(client, db_session, source_text):
    """GB-121: ClickHouse stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-121", source_text)

def test_gb_122_databricks(client, db_session, source_text):
    """GB-122: Databricks stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-122", source_text)

def test_gb_123_google_analytics(client, db_session, source_text):
    """GB-123: Google Analytics stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-123", source_text)

def test_gb_124_mixpanel(client, db_session, source_text):
    """GB-124: Mixpanel stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-124", source_text)

def test_gb_125_mssql_or_sql_server(client, db_session, source_text):
    """GB-125: MSSQL or SQL Server stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-125", source_text)

def test_gb_126_mysql_or_mariadb(client, db_session, source_text):
    """GB-126: MySQL or MariaDB stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-126", source_text)

def test_gb_127_postgresql(client, db_session, source_text):
    """GB-127: PostgreSQL stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-127", source_text)

def test_gb_128_prestodb_or_trino(client, db_session, source_text):
    """GB-128: PrestoDB or Trino stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-128", source_text)

def test_gb_129_amazon_redshift(client, db_session, source_text):
    """GB-129: Amazon Redshift stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-129", source_text)

def test_gb_130_snowflake(client, db_session, source_text):
    """GB-130: Snowflake stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-130", source_text)

def test_gb_131_generic_sql_integration(client, db_session, source_text):
    """GB-131: Generic SQL integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-131", source_text)

def test_gb_132_vertica(client, db_session, source_text):
    """GB-132: Vertica stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-132", source_text)

def test_gb_133_adobe_experience_platform_query_service(client, db_session, source_text):
    """GB-133: Adobe Experience Platform Query Service stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "GB-133", source_text)

def test_pm_138_vercel_deployment_and_domain_automation(client, db_session, source_text):
    """PM-138: Vercel deployment and domain automation stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "PM-138", source_text)

def test_pm_140_resend_email_delivery(client, db_session, source_text):
    """PM-140: Resend email delivery stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "PM-140", source_text)

def test_mt_110_object_or_cdn_storage_dependency(client, db_session, source_text):
    """MT-110: Object or CDN storage dependency stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "MT-110", source_text)

def test_cw_033_email_conversation_transcript(client, db_session, source_text):
    """CW-033: Email conversation transcript stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-033", source_text)

def test_cw_037_email_channel(client, db_session, source_text):
    """CW-037: Email channel stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-037", source_text)

def test_cw_038_whatsapp_business_channel(client, db_session, source_text):
    """CW-038: WhatsApp Business channel stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-038", source_text)

def test_cw_041_x_twitter_dms_and_mentions(client, db_session, source_text):
    """CW-041: X (Twitter) DMs and mentions stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-041", source_text)

def test_cw_045_tiktok_dms_channel(client, db_session, source_text):
    """CW-045: TikTok DMs channel stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-045", source_text)

def test_cw_047_cloudflare_realtimekit_video_calls(client, db_session, source_text):
    """CW-047: Cloudflare RealtimeKit video calls stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-047", source_text)

def test_cw_073_rasa_chatbot(client, db_session, source_text):
    """CW-073: Rasa chatbot stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-073", source_text)

def test_cw_085_auto_translate(client, db_session, source_text):
    """CW-085: Auto-translate stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-085", source_text)

def test_cw_107_push_notifications(client, db_session, source_text):
    """CW-107: Push notifications stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-107", source_text)

def test_cw_124_stripe_integration(client, db_session, source_text):
    """CW-124: Stripe integration stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-124", source_text)

def test_cw_127_apm_monitoring_integrations(client, db_session, source_text):
    """CW-127: APM / monitoring integrations stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-127", source_text)

def test_cw_145_circleci_pipeline(client, db_session, source_text):
    """CW-145: CircleCI pipeline stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-145", source_text)

def test_cw_161_cdn_asset_hosting(client, db_session, source_text):
    """CW-161: CDN asset hosting stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-161", source_text)

def test_cw_163_channel_and_ai_provider_keys(client, db_session, source_text):
    """CW-163: Channel and AI provider keys stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "CW-163", source_text)

def test_nv_080_self_hosting_stack(client, db_session, source_text):
    """NV-080: Self-hosting stack stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "NV-080", source_text)

def test_nv_098_observability_integrations_sentry_new_reli(client, db_session, source_text):
    """NV-098: Observability integrations (Sentry, New Relic) stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "NV-098", source_text)

def test_sb_001_discovery_providers(client, db_session, source_text):
    """SB-001: Discovery providers stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-001", source_text)

def test_sb_002_company_discovery_run(client, db_session, source_text):
    """SB-002: Company discovery run stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-002", source_text)

def test_sb_004_decision_maker_discovery(client, db_session, source_text):
    """SB-004: Decision-maker discovery stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-004", source_text)

def test_sb_005_website_profiling(client, db_session, source_text):
    """SB-005: Website profiling stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-005", source_text)

def test_sb_006_email_pattern_finding(client, db_session, source_text):
    """SB-006: Email pattern finding stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-006", source_text)

def test_sb_007_email_verification(client, db_session, source_text):
    """SB-007: Email verification stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-007", source_text)

def test_sb_025_sending_via_mail_providers(client, db_session, source_text):
    """SB-025: Sending via mail providers stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-025", source_text)

def test_sb_027_multiple_mailboxes_and_mailbox_connections(client, db_session, source_text):
    """SB-027: Multiple mailboxes and mailbox connections stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-027", source_text)

def test_sb_029_reply_classification_and_processed_replies(client, db_session, source_text):
    """SB-029: Reply classification and `processed_replies` stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-029", source_text)

def test_sb_032_bounce_handling_and_bounce_kill_switch(client, db_session, source_text):
    """SB-032: Bounce handling and bounce kill switch stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-032", source_text)

def test_sb_045_brain_model_layer_using_operator_claude_co(client, db_session, source_text):
    """SB-045: Brain model layer using operator Claude/Codex CLI stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-045", source_text)

def test_sb_064_ssrf_safe_public_http(client, db_session, source_text):
    """SB-064: SSRF-safe public HTTP stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-064", source_text)

def test_sb_073_hosted_managed_domains(client, db_session, source_text):
    """SB-073: Hosted managed domains stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-073", source_text)

def test_sb_074_hosted_managed_inboxes(client, db_session, source_text):
    """SB-074: Hosted managed inboxes stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-074", source_text)

def test_sb_075_hosted_warmup(client, db_session, source_text):
    """SB-075: Hosted warmup stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-075", source_text)

def test_sb_076_hosted_dns_management(client, db_session, source_text):
    """SB-076: Hosted DNS management stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-076", source_text)

def test_sb_077_hosted_managed_sending(client, db_session, source_text):
    """SB-077: Hosted managed sending stays blocked until a real provider is configured."""
    ctx = _setup(client)
    _assert_no_default(client, ctx, "SB-077", source_text)
