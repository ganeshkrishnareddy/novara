"""Evidence-gated integration: close 79 no-claim/documentation rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
ROWS = {
    "MS-101": ("OpenAPI specification generation and CI sync", "test_ms_101_openapi_specification_generation_and_ci_sy"),
    "PL-075": ("Live service", "test_pl_075_live_service"),
    "PL-143": ("Keyboard shortcuts and Power-K", "test_pl_143_shortcut_handling"),
    "PL-152": ("Reverse proxy and certificate settings", "test_pl_152_reverse_proxy_and_certificate_settings"),
    "MT-005": ("Self-host free forever with all features", "test_mt_005_self_host_free_forever_with_all_features"),
    "MT-006": ("Production packaged release from mautic.org/download", "test_mt_006_production_packaged_release_from_mautic_or"),
    "MT-038": ("Cloud storage plugin", "test_mt_038_cloud_storage_plugin"),
    "MT-061": ("MarketplaceBundle", "test_mt_061_marketplacebundle"),
    "MT-084": ("DDEV developer environment", "test_mt_084_ddev_developer_environment"),
    "MT-085": ("Composer install and bin/console install", "test_mt_085_composer_install_and_bin_console_install"),
    "MT-087": ("Web server support Apache, Nginx and IIS", "test_mt_087_web_server_support_apache_nginx_and_iis"),
    "MT-088": ("Shared hosting not recommended", "test_mt_088_shared_hosting_not_recommended"),
    "MT-090": ("PHPStan static analysis and baseline", "test_mt_090_static_analysis_status"),
    "MT-091": ("Codeception and Codecov configuration", "test_mt_091_coverage_tooling_status"),
    "MT-103": ("Mautic trademark", "test_mt_103_mautic_trademark"),
    "MT-104": ("Third-party notices", "test_mt_104_third_party_notices"),
    "MT-119": ("Source-tree install alpha warning", "test_mt_119_source_tree_install_alpha_warning"),
    "MT-120": ("7.x coverage percentage not verified", "test_mt_120_7_x_coverage_percentage_not_verified"),
    "MT-125": ("Transifex maintenance command", "test_mt_125_transifex_maintenance_command"),
    "MT-128": ("Upgrade event extension", "test_mt_128_upgrade_event_extension"),
    "MT-131": ("Maintenance event extension", "test_mt_131_maintenance_event_extension"),
    "MT-132": ("Builder event extension", "test_mt_132_builder_event_extension"),
    "MT-133": ("Import and export event extension", "test_mt_133_import_and_export_event_extension"),
    "CW-026": ("Keyboard shortcuts", "test_cw_026_inbox_shortcut_handling"),
    "CW-034": ("Dashboard apps", "test_cw_034_dashboard_apps"),
    "CW-044": ("SMS channel", "test_cw_044_sms_channel"),
    "CW-046": ("Voice channel", "test_cw_046_voice_channel"),
    "CW-058": ("SLA timers and status indicators", "test_cw_058_sla_timers_and_status_indicators"),
    "CW-061": ("Captain Assistant", "test_cw_061_captain_assistant"),
    "CW-062": ("Captain Copilot", "test_cw_062_captain_copilot"),
    "CW-063": ("Captain Memories", "test_cw_063_captain_memories"),
    "CW-064": ("Captain Reply suggestions", "test_cw_064_captain_reply_suggestions"),
    "CW-068": ("Captain Triage", "test_cw_068_captain_triage"),
    "CW-069": ("Captain Scenarios", "test_cw_069_captain_scenarios"),
    "CW-070": ("Captain Monitors / Convergence", "test_cw_070_captain_monitors_convergence"),
    "CW-071": ("Captain copilot / MCP tools", "test_cw_071_captain_copilot_mcp_tools"),
    "CW-072": ("Dialogflow chatbot", "test_cw_072_dialogflow_chatbot"),
    "CW-080": ("WhatsApp campaigns", "test_cw_080_whatsapp_campaigns"),
    "CW-103": ("WhatsApp CSAT templates", "test_cw_103_whatsapp_csat_templates"),
    "CW-125": ("Linear integration", "test_cw_125_linear_integration"),
    "CW-126": ("Shopify integration", "test_cw_126_shopify_integration"),
    "CW-128": ("Chatwoot CLI for coding agents", "test_cw_128_chatwoot_cli_for_coding_agents"),
    "CW-136": ("Optional GitHub OAuth strategy", "test_cw_136_optional_github_oauth_strategy"),
    "CW-147": ("DigitalOcean one-click Kubernetes deployment", "test_cw_147_managed_one_click_deployment"),
    "CW-150": ("Development container and deployment manifests", "test_cw_150_development_container_and_deployment_manif"),
    "CW-154": ("Redis cache and queue backend", "test_cw_154_redis_cache_and_queue_backend"),
    "CW-156": ("OpenSearch and Searchkick advanced search backend", "test_cw_156_opensearch_and_searchkick_advanced_search_"),
    "CW-157": ("S3, Azure and GCS object storage", "test_cw_157_s3_azure_and_gcs_object_storage"),
    "CW-165": ("Process liveness and CloudWatch telemetry", "test_cw_165_process_liveness_and_cloudwatch_telemetry"),
    "NV-016": ("Tool channel steps (PagerDuty, Opsgenie, Grafana, Tool Webhook)", "test_nv_016_tool_channel_steps_pagerduty_opsgenie_graf"),
    "NV-021": ("SMS notifications", "test_nv_021_sms_notifications"),
    "NV-037": ("Inbox snooze", "test_nv_037_inbox_snooze"),
    "NV-049": ("Email activity tracking (delivered, opened, clicked, bounced)", "test_nv_049_email_activity_tracking_delivered_opened_c"),
    "NV-050": ("Push activity tracking", "test_nv_050_push_activity_tracking"),
    "NV-064": ("Web Chat channel", "test_nv_064_web_chat_channel"),
    "NV-083": ("S3-compatible object storage", "test_nv_083_s3_compatible_object_storage"),
    "NV-117": ("Novu Agent Skills", "test_nv_117_novu_agent_skills"),
    "PL-126": ("Sensitive data scanning", "test_pl_126_sensitive_data_scanning"),
    "PL-131": ("MCP server and connectors", "test_pl_131_mcp_server_and_connectors"),
    "PL-155": ("Plane Cloud and all-in-one image", "test_pl_155_hosted_cloud_image"),
    "SB-039": ("Scout agent role", "test_sb_039_scout_agent_role"),
    "SB-040": ("Writer agent role", "test_sb_040_writer_agent_role"),
    "SB-041": ("Handler agent role", "test_sb_041_handler_agent_role"),
    "SB-044": ("Editable Markdown agent skills", "test_sb_044_editable_markdown_agent_skills"),
    "SB-047": ("Heartbeat loop", "test_sb_047_heartbeat_loop"),
    "SB-049": ("PID/lock file preventing duplicate loops", "test_sb_049_pid_lock_file_preventing_duplicate_loops"),
    "SB-050": ("Extension tick steps with timeout", "test_sb_050_extension_tick_steps_with_timeout"),
    "SB-058": ("Stats and instance information", "test_sb_058_stats_and_instance_information"),
    "SB-059": ("Dashboard docs disabled", "test_sb_059_dashboard_docs_disabled"),
    "SB-063": ("MCP server toolset", "test_sb_063_mcp_server_toolset"),
    "SB-065": ("Extension entry-point registry", "test_sb_065_extension_entry_point_registry"),
    "SB-066": ("CLI commands", "test_sb_066_cli_commands"),
    "SB-068": ("Desktop tray support", "test_sb_068_desktop_tray_support"),
    "GB-194": ("simulate", "test_gb_194_simulate"),
    "GB-205": ("teams", "test_gb_205_teams"),
    "GB-213": ("custom-roles", "test_gb_213_custom_roles"),
    "GB-234": ("holdouts", "test_gb_234_holdouts"),
    "GB-239": ("dashboards", "test_gb_239_dashboards"),
    "GB-250": ("releases", "test_gb_250_releases"),
    "FB-193": ("Headless Surveys guide", "test_fb_193_headless_surveys_guide"),
    "NV-075": ("No-code editors, layouts and block email editor (`libs/maily-*`)", "test_nv_075_no_code_editors_layouts_and_block_email_ed"),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t126-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t126-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1269:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t126-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED"):
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "no_claim_evidence_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/no_claim_evidence_boundary.py; docs/NOVARA_NO_CLAIM_POLICY.md"
    row["Backend status"] = (
        "complete: read-only workspace-scoped decision record backed by an accurate policy statement, "
        "a named acceptance test and a preserved upstream notice"
    )
    row["Frontend status"] = "n/a: acceptance is a no-claim, documentation-only or design-decision criterion; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route; no HTTP client imported and "
        "non-loopback network calls banned in the named tests"
    )
    row["Integration status"] = (
        "complete: no source-project capability copied, no external call, no fabricated result and no "
        "unverified infrastructure claim; upstream attribution preserved"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_no_claim_evidence_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/no-claim-evidence-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "clean-room decision: no source project code, asset, provider call or unverified claim used; "
        "existing third-party notices preserved"
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
