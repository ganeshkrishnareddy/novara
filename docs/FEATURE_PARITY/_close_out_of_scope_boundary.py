"""Evidence-gated integration: close 49 out-of-scope restricted rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")
ROWS = {
    "FB-155": ("SAML / BoxyHQ", "test_fb_155_saml_boxyhq"),
    "FB-156": ("OIDC / Keycloak / Okta / Azure AD SSO", "test_fb_156_oidc_keycloak_okta_azure_ad_sso"),
    "FB-205": ("Enterprise: AI translation of surveys", "test_fb_205_enterprise_ai_translation_of_surveys"),
    "FB-206": ("Enterprise: Enterprise analysis capability", "test_fb_206_enterprise_enterprise_analysis_capability"),
    "FB-207": ("Enterprise: Comprehensive audit logging", "test_fb_207_enterprise_comprehensive_audit_logging"),
    "FB-208": ("Enterprise: Enterprise authentication helpers", "test_fb_208_enterprise_enterprise_authentication_helpe"),
    "FB-209": ("Enterprise: Enterprise billing", "test_fb_209_enterprise_enterprise_billing"),
    "FB-210": ("Enterprise: Enterprise contact extras / contacts API guard", "test_fb_210_enterprise_enterprise_contact_extras_conta"),
    "FB-211": ("Enterprise: Enterprise creative extras", "test_fb_211_enterprise_enterprise_creative_extras"),
    "FB-212": ("Enterprise: Data retention controls", "test_fb_212_enterprise_data_retention_controls"),
    "FB-213": ("Enterprise: Feedback directory", "test_fb_213_enterprise_feedback_directory"),
    "FB-214": ("Enterprise: Enterprise license enforcement", "test_fb_214_enterprise_enterprise_license_enforcement"),
    "FB-215": ("Enterprise: Enterprise mailing", "test_fb_215_enterprise_enterprise_mailing"),
    "FB-216": ("Enterprise: Quota enforcement", "test_fb_216_enterprise_quota_enforcement"),
    "FB-217": ("Enterprise: Enterprise role management", "test_fb_217_enterprise_enterprise_role_management"),
    "FB-218": ("Enterprise: Enterprise SSO", "test_fb_218_enterprise_enterprise_sso"),
    "FB-219": ("Enterprise: Enterprise teams", "test_fb_219_enterprise_enterprise_teams"),
    "FB-220": ("Enterprise: Enterprise two-factor auth", "test_fb_220_enterprise_enterprise_two_factor_auth"),
    "FB-221": ("Enterprise: Enterprise Unify Feedback extras", "test_fb_221_enterprise_enterprise_unify_feedback_extra"),
    "FB-222": ("Enterprise: White-labelling", "test_fb_222_enterprise_white_labelling"),
    "FB-223": ("Enterprise: Enterprise workflow extras", "test_fb_223_enterprise_enterprise_workflow_extras"),
    "FB-224": ("Enterprise license check enforcement files", "test_fb_224_enterprise_license_check_enforcement_files"),
    "FB-225": ("License activation documentation", "test_fb_225_license_activation_documentation"),
    "FB-234": ("Exclude all EE capabilities from the default install", "test_fb_234_exclude_all_ee_capabilities_from_the_defau"),
    "MS-088": ("Search Rules: pin, boost, deboost and hide documents", "test_ms_088_search_rules_pin_boost_deboost_and_hide_do"),
    "MS-089": ("Inline dynamic search rules", "test_ms_089_inline_dynamic_search_rules"),
    "MS-090": ("Sharding", "test_ms_090_sharding"),
    "MS-091": ("Replication, network topology and leader routing", "test_ms_091_replication_network_topology_and_leader_ro"),
    "MS-092": ("S3-streaming snapshots", "test_ms_092_s3_streaming_snapshots"),
    "MS-093": ("Enterprise Edition entitlement guard and BUSL terms", "test_ms_093_enterprise_edition_entitlement_guard_and_b"),
    "CW-164": ("Enterprise application layer", "test_cw_164_enterprise_application_layer"),
    "CW-167": ("Priority support and paid self-hosted subscription", "test_cw_167_priority_support_and_paid_self_hosted_subs"),
    "CW-168": ("Enterprise compliance suite (unverified boundary)", "test_cw_168_enterprise_compliance_suite_unverified_bou"),
    "NV-067": ("Environment variables (`env.*` in templates)", "test_nv_067_environment_variables_env_in_templates"),
    "NV-074": ("Workflow and layout translations", "test_nv_074_workflow_and_layout_translations"),
    "NV-077": ("Billing and plan limits", "test_nv_077_billing_and_plan_limits"),
    "NV-078": ("Compliance certifications, DPA, HIPAA BAA, SOC 2 and ISO 27001", "test_nv_078_compliance_certifications_dpa_hipaa_baa_so"),
    "NV-079": ("Remove Novu branding", "test_nv_079_remove_novu_branding"),
    "NV-084": ("Enterprise proprietary packages (`enterprise/packages/auth`, `billing`, `dal`, `shared-services`, `translation`) and `*ee*` UI paths", "test_nv_084_enterprise_proprietary_packages_enterprise"),
    "NV-093": ("Managed Novu Cloud service", "test_nv_093_managed_novu_cloud_service"),
    "NV-109": ("Managed Agent runtime", "test_nv_109_managed_agent_runtime"),
    "NV-116": ("Data residency and regional API endpoints", "test_nv_116_regional_api_endpoints"),
    "PL-110": ("Pro tier entitlements", "test_pl_110_pro_tier_entitlements"),
    "PL-111": ("Business tier entitlements", "test_pl_111_business_tier_entitlements"),
    "PL-112": ("Enterprise Grid tier entitlements", "test_pl_112_enterprise_grid_tier_entitlements"),
    "PL-121": ("AI credits", "test_pl_121_ai_credits"),
    "PL-122": ("AI agents", "test_pl_122_ai_agents"),
    "PL-127": ("Billing, seats and license management", "test_pl_127_billing_seats_and_license_management"),
    "PM-094": ("DATAROOM_MEMBER role", "test_pm_094_dataroom_member_role"),
}

def read_text_any(path):
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")

exit_code = read_text_any(EVIDENCE / "t124-fullsuite-clean-exit.txt").lstrip("\ufeff").strip().removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t124-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 1094:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t124-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    row["NOVARA module"] = "out_of_scope_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/out_of_scope_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped out-of-scope decision backed by named evidence that "
        "no enterprise source, entitlement, paid asset or unverified claim is present"
    )
    row["Frontend status"] = "n/a: acceptance permits an explicit out-of-scope decision; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403 and 404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route; cross-workspace access fails closed"
    )
    row["Integration status"] = (
        "complete: no enterprise source, entitlement, paid asset or unverified claim is introduced; "
        "upstream attribution preserved"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_out_of_scope_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/out-of-scope-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "clean-room out-of-scope decision: no proprietary enterprise source, entitlement or paid "
        "asset used; upstream notice preserved"
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
