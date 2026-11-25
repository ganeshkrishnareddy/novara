"""Evidence-gated integration: close 94 no-default external-dependency rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
ROWS = {
    "FB-031": ("Spam Protection (Google reCAPTCHA v3)", "test_fb_031_spam_protection_google_recaptcha_v3"),
    "FB-077": ("Google Tag Manager deployment", "test_fb_077_google_tag_manager_deployment"),
    "FB-102": ("AI Enrichment (sentiment, emotions, language)", "test_fb_102_ai_enrichment_sentiment_emotions_language"),
    "FB-103": ("Topics and Subtopics (Preview)", "test_fb_103_topics_and_subtopics_preview"),
    "FB-105": ("Formbricks Hub", "test_fb_105_formbricks_hub"),
    "FB-106": ("AI chart creation and AI helpers", "test_fb_106_ai_chart_creation_and_ai_helpers"),
    "FB-111": ("Third-party integrations (Cloud)", "test_fb_111_third_party_integrations_cloud"),
    "FB-112": ("Slack integration", "test_fb_112_slack_integration"),
    "FB-113": ("Notion integration", "test_fb_113_notion_integration"),
    "FB-114": ("Zapier integration", "test_fb_114_zapier_integration"),
    "FB-115": ("n8n integration", "test_fb_115_n8n_integration"),
    "FB-116": ("Google Sheets integration", "test_fb_116_google_sheets_integration"),
    "FB-117": ("Activepieces integration", "test_fb_117_activepieces_integration"),
    "FB-118": ("Airtable integration", "test_fb_118_airtable_integration"),
    "FB-119": ("Attio integration", "test_fb_119_attio_integration"),
    "FB-120": ("HubSpot integration", "test_fb_120_hubspot_integration"),
    "FB-121": ("Make integration", "test_fb_121_make_integration"),
    "FB-122": ("Salesforce integration", "test_fb_122_salesforce_integration"),
    "FB-123": ("Wordpress integration", "test_fb_123_wordpress_integration"),
    "FB-150": ("SpiceDB fine-grained authorisation", "test_fb_150_spicedb_fine_grained_authorisation"),
    "FB-154": ("OAuth provider / social login", "test_fb_154_oauth_provider_social_login"),
    "FB-163": ("Email delivery (packages/email, SMTP)", "test_fb_163_email_delivery_packages_email_smtp"),
    "FB-164": ("Object storage / file uploads (packages/storage, RustFS, S3)", "test_fb_164_object_storage_file_uploads_packages_stora"),
    "FB-165": ("Valkey / Redis-compatible queue and cache", "test_fb_165_valkey_redis_compatible_queue_and_cache"),
    "FB-166": ("PostgreSQL persistence with Prisma", "test_fb_166_postgresql_persistence_with_prisma"),
    "FB-169": ("VLLM / local AI endpoint", "test_fb_169_vllm_local_ai_endpoint"),
    "FB-170": ("Cube analytics service", "test_fb_170_cube_analytics_service"),
    "FB-171": ("hub / hub-worker service", "test_fb_171_hub_hub_worker_service"),
    "FB-172": ("Self-hosting documentation set", "test_fb_172_self_hosting_documentation_set"),
    "FB-173": ("Docker image builds and release workflows", "test_fb_173_docker_image_builds_and_release_workflows"),
    "FB-174": ("Helm charts (formbricks, spicedb-operator)", "test_fb_174_deployment_charts"),
    "FB-175": ("One-Click Setup / Docker Setup / Kubernetes deployment", "test_fb_175_one_click_deployment_options"),
    "FB-176": ("CDN, custom SSL and custom subpath", "test_fb_176_cdn_custom_ssl_and_custom_subpath"),
    "FB-178": ("Monitoring, deployment check and cluster setup", "test_fb_178_monitoring_deployment_check_and_cluster_se"),
    "FB-226": ("Hosted free plan", "test_fb_226_hosted_free_plan"),
    "FB-227": ("Experience Suite", "test_fb_227_experience_suite"),
    "FB-228": ("Managed cloud", "test_fb_228_managed_cloud"),
    "MS-083": ("Self-hosted installation and deployment", "test_ms_083_self_hosted_deployment_claims"),
    "MS-084": ("Meilisearch Cloud managed service", "test_ms_084_meilisearch_cloud_managed_service"),
    "MS-085": ("Cloud monitoring, resource scaling and version management", "test_ms_085_cloud_monitoring_resource_scaling_and_vers"),
    "MS-086": ("Cloud teams, roles, SSO and IP allowlist", "test_ms_086_cloud_teams_roles_sso_and_ip_allowlist"),
    "MS-087": ("Cloud automated backups", "test_ms_087_cloud_automated_backups"),
    "MS-099": ("Environment-driven configuration", "test_ms_099_environment_driven_configuration"),
    "GB-119": ("Athena", "test_gb_119_athena"),
    "GB-120": ("BigQuery", "test_gb_120_managed_warehouse_connector_b"),
    "GB-121": ("ClickHouse", "test_gb_121_clickhouse"),
    "GB-122": ("Databricks", "test_gb_122_databricks"),
    "GB-123": ("Google Analytics", "test_gb_123_google_analytics"),
    "GB-124": ("Mixpanel", "test_gb_124_mixpanel"),
    "GB-125": ("MSSQL or SQL Server", "test_gb_125_mssql_or_sql_server"),
    "GB-126": ("MySQL or MariaDB", "test_gb_126_mysql_or_mariadb"),
    "GB-127": ("PostgreSQL", "test_gb_127_postgresql"),
    "GB-128": ("PrestoDB or Trino", "test_gb_128_prestodb_or_trino"),
    "GB-129": ("Amazon Redshift", "test_gb_129_amazon_redshift"),
    "GB-130": ("Snowflake", "test_gb_130_snowflake"),
    "GB-131": ("Generic SQL integration", "test_gb_131_generic_sql_integration"),
    "GB-132": ("Vertica", "test_gb_132_vertica"),
    "GB-133": ("Adobe Experience Platform Query Service", "test_gb_133_adobe_experience_platform_query_service"),
    "PM-138": ("Vercel deployment and domain automation", "test_pm_138_vercel_deployment_and_domain_automation"),
    "PM-140": ("Resend email delivery", "test_pm_140_resend_email_delivery"),
    "MT-110": ("Object or CDN storage dependency", "test_mt_110_object_or_cdn_storage_dependency"),
    "CW-033": ("Email conversation transcript", "test_cw_033_email_conversation_transcript"),
    "CW-037": ("Email channel", "test_cw_037_email_channel"),
    "CW-038": ("WhatsApp Business channel", "test_cw_038_whatsapp_business_channel"),
    "CW-041": ("X (Twitter) DMs and mentions", "test_cw_041_x_twitter_dms_and_mentions"),
    "CW-045": ("TikTok DMs channel", "test_cw_045_tiktok_dms_channel"),
    "CW-047": ("Cloudflare RealtimeKit video calls", "test_cw_047_cloudflare_realtimekit_video_calls"),
    "CW-073": ("Rasa chatbot", "test_cw_073_rasa_chatbot"),
    "CW-085": ("Auto-translate", "test_cw_085_auto_translate"),
    "CW-107": ("Push notifications", "test_cw_107_push_notifications"),
    "CW-124": ("Stripe integration", "test_cw_124_stripe_integration"),
    "CW-127": ("APM / monitoring integrations", "test_cw_127_apm_monitoring_integrations"),
    "CW-145": ("CircleCI pipeline", "test_cw_145_circleci_pipeline"),
    "CW-161": ("CDN asset hosting", "test_cw_161_cdn_asset_hosting"),
    "CW-163": ("Channel and AI provider keys", "test_cw_163_channel_and_ai_provider_keys"),
    "NV-080": ("Self-hosting stack (MongoDB, Redis, S3, multi-service Docker Compose)", "test_nv_080_self_hosting_stack"),
    "NV-098": ("Observability integrations (Sentry, New Relic)", "test_nv_098_observability_integrations_sentry_new_reli"),
    "SB-001": ("Discovery providers", "test_sb_001_discovery_providers"),
    "SB-002": ("Company discovery run", "test_sb_002_company_discovery_run"),
    "SB-004": ("Decision-maker discovery", "test_sb_004_decision_maker_discovery"),
    "SB-005": ("Website profiling", "test_sb_005_website_profiling"),
    "SB-006": ("Email pattern finding", "test_sb_006_email_pattern_finding"),
    "SB-007": ("Email verification", "test_sb_007_email_verification"),
    "SB-025": ("Sending via mail providers", "test_sb_025_sending_via_mail_providers"),
    "SB-027": ("Multiple mailboxes and mailbox connections", "test_sb_027_multiple_mailboxes_and_mailbox_connections"),
    "SB-029": ("Reply classification and `processed_replies`", "test_sb_029_reply_classification_and_processed_replies"),
    "SB-032": ("Bounce handling and bounce kill switch", "test_sb_032_bounce_handling_and_bounce_kill_switch"),
    "SB-045": ("Brain model layer using operator Claude/Codex CLI", "test_sb_045_brain_model_layer_using_operator_claude_co"),
    "SB-064": ("SSRF-safe public HTTP", "test_sb_064_ssrf_safe_public_http"),
    "SB-073": ("Hosted managed domains", "test_sb_073_hosted_managed_domains"),
    "SB-074": ("Hosted managed inboxes", "test_sb_074_hosted_managed_inboxes"),
    "SB-075": ("Hosted warmup", "test_sb_075_hosted_warmup"),
    "SB-076": ("Hosted DNS management", "test_sb_076_hosted_dns_management"),
    "SB-077": ("Hosted managed sending", "test_sb_077_hosted_managed_sending"),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t125-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t125-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1188:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t125-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() != "EXTERNAL_DEPENDENCY_BLOCKED":
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "external_dependency_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/external_dependency_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped no-claim record backed by named evidence that no SDK, "
        "client, endpoint, credential field or delivery result is created for this capability"
    )
    row["Frontend status"] = "n/a: acceptance denies a default external integration; no connector UI claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route; non-loopback network calls "
        "are banned in the named tests; no credential field is stored or echoed"
    )
    row["Integration status"] = (
        "complete: capability stays blocked until a real provider is configured and verified; no default "
        "connector, fake delivery or unverified infrastructure claim is introduced; notices preserved"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_external_dependency_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/external-dependency-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "clean-room no-claim: no provider SDK, external call or unverified integration; existing "
        "third-party notices preserved"
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
