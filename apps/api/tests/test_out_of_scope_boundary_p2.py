"""Clean-room enterprise out-of-scope boundary acceptance tests.

Named rows (49): FB-155, FB-156, FB-205, FB-206, FB-207, FB-208, FB-209, FB-210, FB-211, FB-212, FB-213, FB-214, FB-215, FB-216, FB-217, FB-218, FB-219, FB-220, FB-221, FB-222, FB-223, FB-224, FB-225, FB-234, MS-088, MS-089, MS-090, MS-091, MS-092, MS-093, CW-164, CW-167, CW-168, NV-067, NV-074, NV-077, NV-078, NV-079, NV-084, NV-093, NV-109, NV-116, PL-110, PL-111, PL-112, PL-121, PL-122, PL-127, PM-094.

Each test proves that no enterprise-source, entitlement, paid-asset or
unverified-claim token appears in active manifests and runtime sources, that
the upstream notice is preserved, and that a read-only workspace-scoped
out-of-scope decision is served with closed 403/404 behaviour.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.out_of_scope_boundary import CLAIM_CATALOG

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (API_ROOT / "pyproject.toml", REPO_ROOT / "Dockerfile", REPO_ROOT / "docker-compose.yml")
WEB_SOURCES = (REPO_ROOT / "apps" / "web" / "index.html", REPO_ROOT / "apps" / "web" / "app.js")
BOUNDARY_MODULES = {p.name for p in MODULES_ROOT.glob("*boundary*.py")}

FORBIDDEN_TOKENS = {
    "FB-155": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-156": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-205": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-206": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-207": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-208": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-209": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-210": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-211": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-212": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-213": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-214": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-215": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-216": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-217": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-218": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-219": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-220": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-221": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-222": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-223": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-224": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-225": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "FB-234": ("ee source", "ee entitlement", "license activation", "boxhq",),
    "MS-088": ("search rule", "search-rule",),
    "MS-089": ("inlinerule",),
    "MS-090": ("shard", "replica",),
    "MS-091": ("usenetwork", "network topology",),
    "MS-092": ("s3 snapshot",),
    "MS-093": ("ee source file", "entitlement marker",),
    "CW-164": ("enterprise asset",),
    "CW-167": ("paid entitlement",),
    "CW-168": ("unverified certification",),
    "NV-067": ("paid cloud variable",),
    "NV-074": ("proprietary translation",),
    "NV-077": ("requires a subscription",),
    "NV-078": ("compliance claim",),
    "NV-079": ("novu-branded", "novu branding",),
    "NV-084": ("enterprise packages", "novu cloud",),
    "NV-093": ("novu cloud account",),
    "NV-109": ("managed agent account",),
    "NV-116": ("cloud-region",),
    "PL-110": ("plane entitlement",),
    "PL-111": ("business-tier",),
    "PL-112": ("enterprise grid",),
    "PL-121": ("plane ai credits",),
    "PL-122": ("plane ai agent",),
    "PL-127": ("plane billing",),
    "PM-094": ("dataroom_member",),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in out-of-scope boundary tests")

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
    owner = bootstrap(client, email="out-of-scope@example.com", workspace_name="Out Of Scope WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other Out Of Scope"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/out-of-scope-boundary"


def _assert_scope(client, ctx, row_id: str, source_text: str) -> None:
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
    assert data["notice"] == spec["notice"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "Explicit out-of-scope decision" in data["notes"]
    for token in FORBIDDEN_TOKENS[row_id]:
        assert token.lower() not in source_text, f"{row_id}: forbidden token {token!r} found"
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert spec["notice"] in notice
    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/out-of-scope-boundary/{row_id}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    missing = client.get(_base(ctx) + "/ZZ-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_fb_155_saml_boxyhq(client, db_session, source_text):
    """FB-155: SAML / BoxyHQ is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-155", source_text)

def test_fb_156_oidc_keycloak_okta_azure_ad_sso(client, db_session, source_text):
    """FB-156: OIDC / Keycloak / Okta / Azure AD SSO is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-156", source_text)

def test_fb_205_enterprise_ai_translation_of_surveys(client, db_session, source_text):
    """FB-205: Enterprise: AI translation of surveys is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-205", source_text)

def test_fb_206_enterprise_enterprise_analysis_capability(client, db_session, source_text):
    """FB-206: Enterprise: Enterprise analysis capability is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-206", source_text)

def test_fb_207_enterprise_comprehensive_audit_logging(client, db_session, source_text):
    """FB-207: Enterprise: Comprehensive audit logging is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-207", source_text)

def test_fb_208_enterprise_enterprise_authentication_helpe(client, db_session, source_text):
    """FB-208: Enterprise: Enterprise authentication helpers is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-208", source_text)

def test_fb_209_enterprise_enterprise_billing(client, db_session, source_text):
    """FB-209: Enterprise: Enterprise billing is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-209", source_text)

def test_fb_210_enterprise_enterprise_contact_extras_conta(client, db_session, source_text):
    """FB-210: Enterprise: Enterprise contact extras / contacts API guard is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-210", source_text)

def test_fb_211_enterprise_enterprise_creative_extras(client, db_session, source_text):
    """FB-211: Enterprise: Enterprise creative extras is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-211", source_text)

def test_fb_212_enterprise_data_retention_controls(client, db_session, source_text):
    """FB-212: Enterprise: Data retention controls is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-212", source_text)

def test_fb_213_enterprise_feedback_directory(client, db_session, source_text):
    """FB-213: Enterprise: Feedback directory is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-213", source_text)

def test_fb_214_enterprise_enterprise_license_enforcement(client, db_session, source_text):
    """FB-214: Enterprise: Enterprise license enforcement is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-214", source_text)

def test_fb_215_enterprise_enterprise_mailing(client, db_session, source_text):
    """FB-215: Enterprise: Enterprise mailing is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-215", source_text)

def test_fb_216_enterprise_quota_enforcement(client, db_session, source_text):
    """FB-216: Enterprise: Quota enforcement is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-216", source_text)

def test_fb_217_enterprise_enterprise_role_management(client, db_session, source_text):
    """FB-217: Enterprise: Enterprise role management is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-217", source_text)

def test_fb_218_enterprise_enterprise_sso(client, db_session, source_text):
    """FB-218: Enterprise: Enterprise SSO is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-218", source_text)

def test_fb_219_enterprise_enterprise_teams(client, db_session, source_text):
    """FB-219: Enterprise: Enterprise teams is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-219", source_text)

def test_fb_220_enterprise_enterprise_two_factor_auth(client, db_session, source_text):
    """FB-220: Enterprise: Enterprise two-factor auth is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-220", source_text)

def test_fb_221_enterprise_enterprise_unify_feedback_extra(client, db_session, source_text):
    """FB-221: Enterprise: Enterprise Unify Feedback extras is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-221", source_text)

def test_fb_222_enterprise_white_labelling(client, db_session, source_text):
    """FB-222: Enterprise: White-labelling is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-222", source_text)

def test_fb_223_enterprise_enterprise_workflow_extras(client, db_session, source_text):
    """FB-223: Enterprise: Enterprise workflow extras is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-223", source_text)

def test_fb_224_enterprise_license_check_enforcement_files(client, db_session, source_text):
    """FB-224: Enterprise license check enforcement files is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-224", source_text)

def test_fb_225_license_activation_documentation(client, db_session, source_text):
    """FB-225: License activation documentation is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-225", source_text)

def test_fb_234_exclude_all_ee_capabilities_from_the_defau(client, db_session, source_text):
    """FB-234: Exclude all EE capabilities from the default install is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "FB-234", source_text)

def test_ms_088_search_rules_pin_boost_deboost_and_hide_do(client, db_session, source_text):
    """MS-088: Search Rules: pin, boost, deboost and hide documents is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-088", source_text)

def test_ms_089_inline_dynamic_search_rules(client, db_session, source_text):
    """MS-089: Inline dynamic search rules is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-089", source_text)

def test_ms_090_sharding(client, db_session, source_text):
    """MS-090: Sharding is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-090", source_text)

def test_ms_091_replication_network_topology_and_leader_ro(client, db_session, source_text):
    """MS-091: Replication, network topology and leader routing is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-091", source_text)

def test_ms_092_s3_streaming_snapshots(client, db_session, source_text):
    """MS-092: S3-streaming snapshots is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-092", source_text)

def test_ms_093_enterprise_edition_entitlement_guard_and_b(client, db_session, source_text):
    """MS-093: Enterprise Edition entitlement guard and BUSL terms is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "MS-093", source_text)

def test_cw_164_enterprise_application_layer(client, db_session, source_text):
    """CW-164: Enterprise application layer is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "CW-164", source_text)

def test_cw_167_priority_support_and_paid_self_hosted_subs(client, db_session, source_text):
    """CW-167: Priority support and paid self-hosted subscription is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "CW-167", source_text)

def test_cw_168_enterprise_compliance_suite_unverified_bou(client, db_session, source_text):
    """CW-168: Enterprise compliance suite (unverified boundary) is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "CW-168", source_text)

def test_nv_067_environment_variables_env_in_templates(client, db_session, source_text):
    """NV-067: Environment variables (`env.*` in templates) is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-067", source_text)

def test_nv_074_workflow_and_layout_translations(client, db_session, source_text):
    """NV-074: Workflow and layout translations is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-074", source_text)

def test_nv_077_billing_and_plan_limits(client, db_session, source_text):
    """NV-077: Billing and plan limits is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-077", source_text)

def test_nv_078_compliance_certifications_dpa_hipaa_baa_so(client, db_session, source_text):
    """NV-078: Compliance certifications, DPA, HIPAA BAA, SOC 2 and ISO 27001 is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-078", source_text)

def test_nv_079_remove_novu_branding(client, db_session, source_text):
    """NV-079: Remove Novu branding is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-079", source_text)

def test_nv_084_enterprise_proprietary_packages_enterprise(client, db_session, source_text):
    """NV-084: Enterprise proprietary packages (`enterprise/packages/auth`, `billing`, `dal`, `shared-services`, `translation`) and `*ee*` UI paths is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-084", source_text)

def test_nv_093_managed_novu_cloud_service(client, db_session, source_text):
    """NV-093: Managed Novu Cloud service is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-093", source_text)

def test_nv_109_managed_agent_runtime(client, db_session, source_text):
    """NV-109: Managed Agent runtime is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-109", source_text)

def test_nv_116_regional_api_endpoints(client, db_session, source_text):
    """NV-116: Regional API endpoints is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "NV-116", source_text)

def test_pl_110_pro_tier_entitlements(client, db_session, source_text):
    """PL-110: Pro tier entitlements is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-110", source_text)

def test_pl_111_business_tier_entitlements(client, db_session, source_text):
    """PL-111: Business tier entitlements is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-111", source_text)

def test_pl_112_enterprise_grid_tier_entitlements(client, db_session, source_text):
    """PL-112: Enterprise Grid tier entitlements is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-112", source_text)

def test_pl_121_ai_credits(client, db_session, source_text):
    """PL-121: AI credits is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-121", source_text)

def test_pl_122_ai_agents(client, db_session, source_text):
    """PL-122: AI agents is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-122", source_text)

def test_pl_127_billing_seats_and_license_management(client, db_session, source_text):
    """PL-127: Billing, seats and license management is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PL-127", source_text)

def test_pm_094_dataroom_member_role(client, db_session, source_text):
    """PM-094: DATAROOM_MEMBER role is out of scope; no enterprise source or unverified claim used."""
    ctx = _setup(client)
    _assert_scope(client, ctx, "PM-094", source_text)
