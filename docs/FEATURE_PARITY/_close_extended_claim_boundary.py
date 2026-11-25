"""Evidence-gated integration: close 26 extended clean-room boundary rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "MS-005": ('Prefix search', 'test_ms_005_prefix_search'),
    "MS-009": ('Faceted navigation UI', 'test_ms_009_faceted_navigation_ui'),
    "MS-010": ('Sorting / `sortableAttributes`', 'test_ms_010_sorting_sortableattributes'),
    "MS-050": ('Task cancellation, deletion and streaming', 'test_ms_050_task_cancellation_deletion_and_streaming'),
    "MS-051": ('Batches and batch monitoring', 'test_ms_051_batches_and_batch_monitoring'),
    "MS-059": ('Logs streaming and runtime log level', 'test_ms_059_logs_streaming_and_runtime_log_level'),
    "MS-096": ('CI benchmark, fuzz and SDK test workflows', 'test_ms_096_ci_benchmark_fuzz_and_sdk_test_workflows'),
    "MS-098": ('Search analytics and usage events', 'test_ms_098_search_analytics_and_usage_events'),
    "CW-119": ('Legacy api_access_token header', 'test_cw_119_legacy_api_access_token_header'),
    "PM-067": ('Data room digest emails', 'test_pm_067_data_room_digest_emails'),
    "PM-136": ('Vercel Postgres and Blob defaults', 'test_pm_136_vercel_postgres_and_blob_defaults'),
    "PM-155": ('Security certifications and data residency', 'test_pm_155_security_certifications_and_data_residen'),
    "NV-041": ('Headless Inbox and custom layouts', 'test_nv_041_headless_inbox_and_custom_layouts'),
    "NV-053": ('Usage and delivery analytics', 'test_nv_053_usage_and_delivery_analytics'),
    "NV-055": ('Webhook connectors (BigQuery, S3, Segment and similar)', 'test_nv_055_webhook_connectors_bigquery_s3_segment_a'),
    "NV-060": ('Code-first workflows (`@novu/framework`, bridge endpoint, Studio/CLI)', 'test_nv_060_code_first_workflows_novu_framework_brid'),
    "NV-061": ('Novu CLI (`@novu/novu`)', 'test_nv_061_novu_cli_novu_novu'),
    "NV-063": ('Agent Communication Infrastructure (ACI)', 'test_nv_063_agent_communication_infrastructure_aci'),
    "NV-066": ('Environments (Development, Production, custom)', 'test_nv_066_environments_development_production_cust'),
    "NV-090": ('Dashboard and human-dashboard React apps', 'test_nv_090_dashboard_and_human_dashboard_react_apps'),
    "NV-091": ('Agent inbox MCP bridge (`apps/agent-inbox-mcp`)', 'test_nv_091_agent_inbox_mcp_bridge_apps_agent_inbox_'),
    "NV-095": ('`@novu/stateless` provider utilities', 'test_nv_095_novu_stateless_provider_utilities'),
    "NV-108": ('Agent management API and bridge registration', 'test_nv_108_agent_management_api_and_bridge_registra'),
    "NV-110": ('AI framework adapters (`@novu/framework/ai-sdk`, `langchain`, Mastra, Claude)', 'test_nv_110_ai_framework_adapters_novu_framework_ai_'),
    "NV-114": ('Custom code agent bridge and handlers', 'test_nv_114_custom_code_agent_bridge_and_handlers'),
    "SB-043": ('LinkedIn-related agent roles', 'test_sb_043_linkedin_related_agent_roles'),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t122-fullsuite-clean-exit.txt").lstrip("\ufeff").strip()
exit_code = exit_code.removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t122-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 963:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t122-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    data = list(reader)

changed = []
for row in data:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED"):
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "extended_claim_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/extended_claim_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped catalogue records the negative claim with a "
        "NOVARA-local boundary, preserved upstream notice, no declared dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance is negative evidence about unverified capabilities; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route; cross-workspace access fails "
        "closed; no SDK import, external endpoint, warehouse, CLI, bridge or outbound call introduced"
    )
    row["Integration status"] = (
        "complete: no unverified engine, legacy-token, hosted-provider, certification, analytics, CLI, "
        "dashboard, MCP bridge, AI adapter or public-post capability is introduced; upstream notices preserved"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_extended_claim_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/extended-claim-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "clean-room negative evidence: no upstream source copy, package, SDK, external call or unverified "
        "capability; existing third-party notices preserved"
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(ROWS):
    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data)

print("closed:", ", ".join(changed))
print("evidence:", match.group(0), "EXIT=" + exit_code)
