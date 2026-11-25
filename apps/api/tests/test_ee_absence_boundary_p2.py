"""Clean-room GrowthBook EE-absence boundary acceptance tests.

Named rows (82): GB-108, GB-109, GB-174, GB-175, GB-176, GB-177, GB-178, GB-179, GB-180, GB-181, GB-182, GB-184, GB-185, GB-186, GB-190, GB-191, GB-192, GB-193, GB-195, GB-197, GB-198, GB-199, GB-200, GB-201, GB-202, GB-203, GB-204, GB-207, GB-208, GB-212, GB-216, GB-218, GB-219, GB-220, GB-221, GB-223, GB-226, GB-227, GB-228, GB-229, GB-230, GB-235, GB-236, GB-238, GB-240, GB-241, GB-242, GB-243, GB-244, GB-245, GB-246, GB-251, GB-252, GB-253, GB-254, GB-255, GB-256, GB-257, GB-258, GB-259, GB-260, GB-261, GB-262, GB-263, GB-264, GB-265, GB-266, GB-267, GB-268, GB-269, GB-270, GB-271, GB-272, GB-273, GB-274, GB-275, GB-276, GB-277, GB-278, GB-279, GB-280, GB-281.

Each test proves that the proprietary capability token is absent from active
manifests and runtime sources, that the GrowthBook community notice is preserved,
and that a read-only workspace-scoped absence decision is served with closed
cross-workspace and unknown-row behaviour. No licensed source is used.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.ee_absence_boundary import CLAIM_CATALOG, NOTICE_TEXT

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (API_ROOT / "pyproject.toml", REPO_ROOT / "Dockerfile", REPO_ROOT / "docker-compose.yml")
WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")
BOUNDARY_MODULES = {p.name for p in MODULES_ROOT.glob("*boundary*.py")}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in EE absence boundary tests")

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
    owner = bootstrap(client, email="ee-absence@example.com", workspace_name="EE Absence WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other EE Absence"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/ee-absence-boundary"


def _assert_absence(client, ctx, row_id: str, source_text: str) -> None:
    spec = CLAIM_CATALOG[row_id]
    listed = client.get(_base(ctx), headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == len(CLAIM_CATALOG)
    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_id"] == row_id
    assert data["name"] == spec["name"]
    assert data["claim"] == spec["claim"]
    assert data["notice"] == NOTICE_TEXT
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "Clean-room absence decision" in data["notes"]
    assert spec["token"].lower() not in source_text, f"{row_id}: enterprise token {spec['token']!r} found"
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert NOTICE_TEXT in notice
    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/ee-absence-boundary/{row_id}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    missing = client.get(_base(ctx) + "/GB-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_gb_108_insights_dashboards(client, db_session, source_text):
    """GB-108: Insights dashboards is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-108", source_text)

def test_gb_109_executive_reports(client, db_session, source_text):
    """GB-109: Executive reports is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-109", source_text)

def test_gb_174_ai_suggestions(client, db_session, source_text):
    """GB-174: ai-suggestions is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-174", source_text)

def test_gb_175_ai_byok(client, db_session, source_text):
    """GB-175: ai-byok is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-175", source_text)

def test_gb_176_scim(client, db_session, source_text):
    """GB-176: scim is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-176", source_text)

def test_gb_177_sso(client, db_session, source_text):
    """GB-177: sso is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-177", source_text)

def test_gb_178_advanced_permissions(client, db_session, source_text):
    """GB-178: advanced-permissions is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-178", source_text)

def test_gb_179_role_management(client, db_session, source_text):
    """GB-179: role-management is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-179", source_text)

def test_gb_180_unlimited_projects(client, db_session, source_text):
    """GB-180: unlimited-projects is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-180", source_text)

def test_gb_181_custom_environments(client, db_session, source_text):
    """GB-181: custom-environments is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-181", source_text)

def test_gb_182_encrypt_features_endpoint(client, db_session, source_text):
    """GB-182: encrypt-features-endpoint is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-182", source_text)

def test_gb_184_events_forwarder(client, db_session, source_text):
    """GB-184: events-forwarder is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-184", source_text)

def test_gb_185_custom_metadata(client, db_session, source_text):
    """GB-185: custom-metadata is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-185", source_text)

def test_gb_186_override_metrics(client, db_session, source_text):
    """GB-186: override-metrics is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-186", source_text)

def test_gb_190_pipeline_mode(client, db_session, source_text):
    """GB-190: pipeline-mode is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-190", source_text)

def test_gb_191_audit_logging(client, db_session, source_text):
    """GB-191: audit-logging is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-191", source_text)

def test_gb_192_visual_editor(client, db_session, source_text):
    """GB-192: visual-editor is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-192", source_text)

def test_gb_193_archetypes(client, db_session, source_text):
    """GB-193: archetypes is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-193", source_text)

def test_gb_195_cloud_proxy(client, db_session, source_text):
    """GB-195: cloud-proxy is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-195", source_text)

def test_gb_197_livechat(client, db_session, source_text):
    """GB-197: livechat is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-197", source_text)

def test_gb_198_json_validation(client, db_session, source_text):
    """GB-198: json-validation is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-198", source_text)

def test_gb_199_remote_evaluation(client, db_session, source_text):
    """GB-199: remote-evaluation is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-199", source_text)

def test_gb_200_multi_org(client, db_session, source_text):
    """GB-200: multi-org is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-200", source_text)

def test_gb_201_custom_launch_checklist(client, db_session, source_text):
    """GB-201: custom-launch-checklist is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-201", source_text)

def test_gb_202_multi_metric_queries(client, db_session, source_text):
    """GB-202: multi-metric-queries is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-202", source_text)

def test_gb_203_no_access_role(client, db_session, source_text):
    """GB-203: no-access-role is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-203", source_text)

def test_gb_204_project_admin_role(client, db_session, source_text):
    """GB-204: project-admin-role is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-204", source_text)

def test_gb_207_require_approvals(client, db_session, source_text):
    """GB-207: require-approvals is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-207", source_text)

def test_gb_208_code_references(client, db_session, source_text):
    """GB-208: code-references is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-208", source_text)

def test_gb_212_multiple_sdk_webhooks(client, db_session, source_text):
    """GB-212: multiple-sdk-webhooks is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-212", source_text)

def test_gb_216_funnel_metrics(client, db_session, source_text):
    """GB-216: funnel-metrics is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-216", source_text)

def test_gb_218_custom_markdown(client, db_session, source_text):
    """GB-218: custom-markdown is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-218", source_text)

def test_gb_219_experiment_impact(client, db_session, source_text):
    """GB-219: experiment-impact is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-219", source_text)

def test_gb_220_metric_populations(client, db_session, source_text):
    """GB-220: metric-populations is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-220", source_text)

def test_gb_221_large_saved_groups(client, db_session, source_text):
    """GB-221: large-saved-groups is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-221", source_text)

def test_gb_223_metric_groups(client, db_session, source_text):
    """GB-223: metric-groups is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-223", source_text)

def test_gb_226_historical_power(client, db_session, source_text):
    """GB-226: historical-power is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-226", source_text)

def test_gb_227_decision_framework(client, db_session, source_text):
    """GB-227: decision-framework is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-227", source_text)

def test_gb_228_unlimited_cdn_usage(client, db_session, source_text):
    """GB-228: unlimited-cdn-usage is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-228", source_text)

def test_gb_229_unlimited_managed_warehouse_usage(client, db_session, source_text):
    """GB-229: unlimited-managed-warehouse-usage is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-229", source_text)

def test_gb_230_unlimited_event_forwarder_usage(client, db_session, source_text):
    """GB-230: unlimited-event-forwarder-usage is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-230", source_text)

def test_gb_235_savesqlexplorerqueries(client, db_session, source_text):
    """GB-235: saveSqlExplorerQueries is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-235", source_text)

def test_gb_236_metric_effects(client, db_session, source_text):
    """GB-236: metric-effects is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-236", source_text)

def test_gb_238_learnings(client, db_session, source_text):
    """GB-238: learnings is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-238", source_text)

def test_gb_240_product_analytics_dashboards(client, db_session, source_text):
    """GB-240: product-analytics-dashboards is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-240", source_text)

def test_gb_241_precomputed_dimensions(client, db_session, source_text):
    """GB-241: precomputed-dimensions is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-241", source_text)

def test_gb_242_custom_hooks(client, db_session, source_text):
    """GB-242: custom-hooks is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-242", source_text)

def test_gb_243_metric_slices(client, db_session, source_text):
    """GB-243: metric-slices is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-243", source_text)

def test_gb_244_manage_official_resources(client, db_session, source_text):
    """GB-244: manage-official-resources is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-244", source_text)

def test_gb_245_incremental_refresh(client, db_session, source_text):
    """GB-245: incremental-refresh is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-245", source_text)

def test_gb_246_adv_presentations(client, db_session, source_text):
    """GB-246: adv-presentations is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-246", source_text)

def test_gb_251_contextual_bandits(client, db_session, source_text):
    """GB-251: contextual-bandits is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-251", source_text)

def test_gb_252_interleaving(client, db_session, source_text):
    """GB-252: interleaving is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-252", source_text)

def test_gb_253_cluster_experiments(client, db_session, source_text):
    """GB-253: cluster-experiments is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-253", source_text)

def test_gb_254_human_in_the_loop(client, db_session, source_text):
    """GB-254: human-in-the-loop is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-254", source_text)

def test_gb_255_ai_mode(client, db_session, source_text):
    """GB-255: AI Mode is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-255", source_text)

def test_gb_256_manual_mode(client, db_session, source_text):
    """GB-256: Manual Mode is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-256", source_text)

def test_gb_257_visual_editor_images(client, db_session, source_text):
    """GB-257: Visual editor images is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-257", source_text)

def test_gb_258_design_to_variant(client, db_session, source_text):
    """GB-258: Design to Variant is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-258", source_text)

def test_gb_259_visual_experiment_anti_flicker(client, db_session, source_text):
    """GB-259: Visual experiment anti-flicker is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-259", source_text)

def test_gb_260_visual_experiment_preview_and_qa(client, db_session, source_text):
    """GB-260: Visual experiment preview and QA is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-260", source_text)

def test_gb_261_bandit_configuration(client, db_session, source_text):
    """GB-261: Bandit configuration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-261", source_text)

def test_gb_262_bandit_results(client, db_session, source_text):
    """GB-262: Bandit results is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-262", source_text)

def test_gb_263_contextual_bandit_configuration(client, db_session, source_text):
    """GB-263: Contextual bandit configuration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-263", source_text)

def test_gb_264_contextual_bandit_api(client, db_session, source_text):
    """GB-264: Contextual bandit API is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-264", source_text)

def test_gb_265_interleaving_setup(client, db_session, source_text):
    """GB-265: Interleaving setup is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-265", source_text)

def test_gb_266_interleaving_results(client, db_session, source_text):
    """GB-266: Interleaving results is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-266", source_text)

def test_gb_267_vercel_native_integration(client, db_session, source_text):
    """GB-267: Vercel native integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-267", source_text)

def test_gb_268_framer_plugin(client, db_session, source_text):
    """GB-268: Framer plugin is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-268", source_text)

def test_gb_269_shopify_integration(client, db_session, source_text):
    """GB-269: Shopify integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-269", source_text)

def test_gb_270_webflow_integration(client, db_session, source_text):
    """GB-270: Webflow integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-270", source_text)

def test_gb_271_wordpress_integration(client, db_session, source_text):
    """GB-271: WordPress integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-271", source_text)

def test_gb_272_ai_integrations(client, db_session, source_text):
    """GB-272: AI integrations is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-272", source_text)

def test_gb_273_llm_tracing_experiments(client, db_session, source_text):
    """GB-273: LLM tracing experiments is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-273", source_text)

def test_gb_274_github_metric_version_control(client, db_session, source_text):
    """GB-274: GitHub metric version control is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-274", source_text)

def test_gb_275_microsoft_clarity_heatmaps(client, db_session, source_text):
    """GB-275: Microsoft Clarity heatmaps is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-275", source_text)

def test_gb_276_jira_integration(client, db_session, source_text):
    """GB-276: Jira integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-276", source_text)

def test_gb_277_discord_integration(client, db_session, source_text):
    """GB-277: Discord integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-277", source_text)

def test_gb_278_datadog_integration(client, db_session, source_text):
    """GB-278: Datadog integration is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-278", source_text)

def test_gb_279_slack_ai_assistant(client, db_session, source_text):
    """GB-279: Slack AI assistant is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-279", source_text)

def test_gb_280_self_hosted_slack_setup(client, db_session, source_text):
    """GB-280: Self-hosted Slack setup is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-280", source_text)

def test_gb_281_legacy_slack_webhooks(client, db_session, source_text):
    """GB-281: Legacy Slack webhooks is absent from the default install; no licensed source used."""
    ctx = _setup(client)
    _assert_absence(client, ctx, "GB-281", source_text)
