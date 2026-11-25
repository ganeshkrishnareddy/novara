"""Evidence-gated integration: close 82 clean-room GrowthBook EE-absence rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "GB-108": ("Insights dashboards", "test_gb_108_insights_dashboards"),
    "GB-109": ("Executive reports", "test_gb_109_executive_reports"),
    "GB-174": ("ai-suggestions", "test_gb_174_ai_suggestions"),
    "GB-175": ("ai-byok", "test_gb_175_ai_byok"),
    "GB-176": ("scim", "test_gb_176_scim"),
    "GB-177": ("sso", "test_gb_177_sso"),
    "GB-178": ("advanced-permissions", "test_gb_178_advanced_permissions"),
    "GB-179": ("role-management", "test_gb_179_role_management"),
    "GB-180": ("unlimited-projects", "test_gb_180_unlimited_projects"),
    "GB-181": ("custom-environments", "test_gb_181_custom_environments"),
    "GB-182": ("encrypt-features-endpoint", "test_gb_182_encrypt_features_endpoint"),
    "GB-184": ("events-forwarder", "test_gb_184_events_forwarder"),
    "GB-185": ("custom-metadata", "test_gb_185_custom_metadata"),
    "GB-186": ("override-metrics", "test_gb_186_override_metrics"),
    "GB-190": ("pipeline-mode", "test_gb_190_pipeline_mode"),
    "GB-191": ("audit-logging", "test_gb_191_audit_logging"),
    "GB-192": ("visual-editor", "test_gb_192_visual_editor"),
    "GB-193": ("archetypes", "test_gb_193_archetypes"),
    "GB-195": ("cloud-proxy", "test_gb_195_cloud_proxy"),
    "GB-197": ("livechat", "test_gb_197_livechat"),
    "GB-198": ("json-validation", "test_gb_198_json_validation"),
    "GB-199": ("remote-evaluation", "test_gb_199_remote_evaluation"),
    "GB-200": ("multi-org", "test_gb_200_multi_org"),
    "GB-201": ("custom-launch-checklist", "test_gb_201_custom_launch_checklist"),
    "GB-202": ("multi-metric-queries", "test_gb_202_multi_metric_queries"),
    "GB-203": ("no-access-role", "test_gb_203_no_access_role"),
    "GB-204": ("project-admin-role", "test_gb_204_project_admin_role"),
    "GB-207": ("require-approvals", "test_gb_207_require_approvals"),
    "GB-208": ("code-references", "test_gb_208_code_references"),
    "GB-212": ("multiple-sdk-webhooks", "test_gb_212_multiple_sdk_webhooks"),
    "GB-216": ("funnel-metrics", "test_gb_216_funnel_metrics"),
    "GB-218": ("custom-markdown", "test_gb_218_custom_markdown"),
    "GB-219": ("experiment-impact", "test_gb_219_experiment_impact"),
    "GB-220": ("metric-populations", "test_gb_220_metric_populations"),
    "GB-221": ("large-saved-groups", "test_gb_221_large_saved_groups"),
    "GB-223": ("metric-groups", "test_gb_223_metric_groups"),
    "GB-226": ("historical-power", "test_gb_226_historical_power"),
    "GB-227": ("decision-framework", "test_gb_227_decision_framework"),
    "GB-228": ("unlimited-cdn-usage", "test_gb_228_unlimited_cdn_usage"),
    "GB-229": ("unlimited-managed-warehouse-usage", "test_gb_229_unlimited_managed_warehouse_usage"),
    "GB-230": ("unlimited-event-forwarder-usage", "test_gb_230_unlimited_event_forwarder_usage"),
    "GB-235": ("saveSqlExplorerQueries", "test_gb_235_savesqlexplorerqueries"),
    "GB-236": ("metric-effects", "test_gb_236_metric_effects"),
    "GB-238": ("learnings", "test_gb_238_learnings"),
    "GB-240": ("product-analytics-dashboards", "test_gb_240_product_analytics_dashboards"),
    "GB-241": ("precomputed-dimensions", "test_gb_241_precomputed_dimensions"),
    "GB-242": ("custom-hooks", "test_gb_242_custom_hooks"),
    "GB-243": ("metric-slices", "test_gb_243_metric_slices"),
    "GB-244": ("manage-official-resources", "test_gb_244_manage_official_resources"),
    "GB-245": ("incremental-refresh", "test_gb_245_incremental_refresh"),
    "GB-246": ("adv-presentations", "test_gb_246_adv_presentations"),
    "GB-251": ("contextual-bandits", "test_gb_251_contextual_bandits"),
    "GB-252": ("interleaving", "test_gb_252_interleaving"),
    "GB-253": ("cluster-experiments", "test_gb_253_cluster_experiments"),
    "GB-254": ("human-in-the-loop", "test_gb_254_human_in_the_loop"),
    "GB-255": ("AI Mode", "test_gb_255_ai_mode"),
    "GB-256": ("Manual Mode", "test_gb_256_manual_mode"),
    "GB-257": ("Visual editor images", "test_gb_257_visual_editor_images"),
    "GB-258": ("Design to Variant", "test_gb_258_design_to_variant"),
    "GB-259": ("Visual experiment anti-flicker", "test_gb_259_visual_experiment_anti_flicker"),
    "GB-260": ("Visual experiment preview and QA", "test_gb_260_visual_experiment_preview_and_qa"),
    "GB-261": ("Bandit configuration", "test_gb_261_bandit_configuration"),
    "GB-262": ("Bandit results", "test_gb_262_bandit_results"),
    "GB-263": ("Contextual bandit configuration", "test_gb_263_contextual_bandit_configuration"),
    "GB-264": ("Contextual bandit API", "test_gb_264_contextual_bandit_api"),
    "GB-265": ("Interleaving setup", "test_gb_265_interleaving_setup"),
    "GB-266": ("Interleaving results", "test_gb_266_interleaving_results"),
    "GB-267": ("Vercel native integration", "test_gb_267_vercel_native_integration"),
    "GB-268": ("Framer plugin", "test_gb_268_framer_plugin"),
    "GB-269": ("Shopify integration", "test_gb_269_shopify_integration"),
    "GB-270": ("Webflow integration", "test_gb_270_webflow_integration"),
    "GB-271": ("WordPress integration", "test_gb_271_wordpress_integration"),
    "GB-272": ("AI integrations", "test_gb_272_ai_integrations"),
    "GB-273": ("LLM tracing experiments", "test_gb_273_llm_tracing_experiments"),
    "GB-274": ("GitHub metric version control", "test_gb_274_github_metric_version_control"),
    "GB-275": ("Microsoft Clarity heatmaps", "test_gb_275_microsoft_clarity_heatmaps"),
    "GB-276": ("Jira integration", "test_gb_276_jira_integration"),
    "GB-277": ("Discord integration", "test_gb_277_discord_integration"),
    "GB-278": ("Datadog integration", "test_gb_278_datadog_integration"),
    "GB-279": ("Slack AI assistant", "test_gb_279_slack_ai_assistant"),
    "GB-280": ("Self-hosted Slack setup", "test_gb_280_self_hosted_slack_setup"),
    "GB-281": ("Legacy Slack webhooks", "test_gb_281_legacy_slack_webhooks"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t123-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t123-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1045:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t123-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() != "LICENSING_RESTRICTED":
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "ee_absence_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/ee_absence_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped absence decision records that the proprietary "
        "capability is absent from the default install, with no licensed source or entitlement"
    )
    row["Frontend status"] = "n/a: acceptance permits an explicit out-of-scope decision; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route; cross-workspace access fails closed"
    )
    row["Integration status"] = (
        "complete: no GrowthBook enterprise source, entitlement, provider endpoint or licensed capability "
        "is introduced; the GrowthBook community notice is preserved"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_ee_absence_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/ee-absence-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "clean-room absence decision: no proprietary enterprise source, entitlement or licensed "
        "capability used; GrowthBook community MIT notice preserved"
    )
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
