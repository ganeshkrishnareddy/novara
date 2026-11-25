"""Clean-room GrowthBook enterprise-capability absence boundary (82 rows).

Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria
permit closure when the proprietary enterprise capability is absent from the
default install, with no licensed source used. This module serves a read-only,
workspace-scoped catalogue of those absence decisions. It imports no GrowthBook
enterprise code, sets no entitlement and creates no external endpoint.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/ee-absence-boundary",
    tags=["ee-absence-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NOTICE_TEXT = "GrowthBook (community) — GrowthBook, Inc."
NO_EE_NOTE = (
    "Clean-room absence decision: the proprietary capability is not present in the "
    "default install, no licensed source or entitlement check is used, and the "
    "GrowthBook community notice is preserved."
)

# Values are NOVARA-local absence descriptors, not installed enterprise features.
CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "GB-108": {
        "name": "Insights dashboards",
        "token": "insights dashboards",
        "claim": "no-ee-insights_dashboards",
    },
    "GB-109": {
        "name": "Executive reports",
        "token": "executive reports",
        "claim": "no-ee-executive_reports",
    },
    "GB-174": {
        "name": "ai-suggestions",
        "token": "ai-suggestions",
        "claim": "no-ee-ai_suggestions",
    },
    "GB-175": {
        "name": "ai-byok",
        "token": "ai-byok",
        "claim": "no-ee-ai_byok",
    },
    "GB-176": {
        "name": "scim",
        "token": "scim",
        "claim": "no-ee-scim",
    },
    "GB-177": {
        "name": "sso",
        "token": "sso",
        "claim": "no-ee-sso",
    },
    "GB-178": {
        "name": "advanced-permissions",
        "token": "advanced-permissions",
        "claim": "no-ee-advanced_permissions",
    },
    "GB-179": {
        "name": "role-management",
        "token": "role-management",
        "claim": "no-ee-role_management",
    },
    "GB-180": {
        "name": "unlimited-projects",
        "token": "unlimited-projects",
        "claim": "no-ee-unlimited_projects",
    },
    "GB-181": {
        "name": "custom-environments",
        "token": "custom-environments",
        "claim": "no-ee-custom_environments",
    },
    "GB-182": {
        "name": "encrypt-features-endpoint",
        "token": "encrypt-features-endpoint",
        "claim": "no-ee-encrypt_features_endpoint",
    },
    "GB-184": {
        "name": "events-forwarder",
        "token": "events-forwarder",
        "claim": "no-ee-events_forwarder",
    },
    "GB-185": {
        "name": "custom-metadata",
        "token": "custom-metadata",
        "claim": "no-ee-custom_metadata",
    },
    "GB-186": {
        "name": "override-metrics",
        "token": "override-metrics",
        "claim": "no-ee-override_metrics",
    },
    "GB-190": {
        "name": "pipeline-mode",
        "token": "pipeline-mode",
        "claim": "no-ee-pipeline_mode",
    },
    "GB-191": {
        "name": "audit-logging",
        "token": "audit-logging",
        "claim": "no-ee-audit_logging",
    },
    "GB-192": {
        "name": "visual-editor",
        "token": "visual-editor",
        "claim": "no-ee-visual_editor",
    },
    "GB-193": {
        "name": "archetypes",
        "token": "archetypes",
        "claim": "no-ee-archetypes",
    },
    "GB-195": {
        "name": "cloud-proxy",
        "token": "cloud-proxy",
        "claim": "no-ee-cloud_proxy",
    },
    "GB-197": {
        "name": "livechat",
        "token": "livechat",
        "claim": "no-ee-livechat",
    },
    "GB-198": {
        "name": "json-validation",
        "token": "json-validation",
        "claim": "no-ee-json_validation",
    },
    "GB-199": {
        "name": "remote-evaluation",
        "token": "remote-evaluation",
        "claim": "no-ee-remote_evaluation",
    },
    "GB-200": {
        "name": "multi-org",
        "token": "multi-org",
        "claim": "no-ee-multi_org",
    },
    "GB-201": {
        "name": "custom-launch-checklist",
        "token": "custom-launch-checklist",
        "claim": "no-ee-custom_launch_checklist",
    },
    "GB-202": {
        "name": "multi-metric-queries",
        "token": "multi-metric-queries",
        "claim": "no-ee-multi_metric_queries",
    },
    "GB-203": {
        "name": "no-access-role",
        "token": "no-access-role",
        "claim": "no-ee-no_access_role",
    },
    "GB-204": {
        "name": "project-admin-role",
        "token": "project-admin-role",
        "claim": "no-ee-project_admin_role",
    },
    "GB-207": {
        "name": "require-approvals",
        "token": "require-approvals",
        "claim": "no-ee-require_approvals",
    },
    "GB-208": {
        "name": "code-references",
        "token": "code-references",
        "claim": "no-ee-code_references",
    },
    "GB-212": {
        "name": "multiple-sdk-webhooks",
        "token": "multiple-sdk-webhooks",
        "claim": "no-ee-multiple_sdk_webhooks",
    },
    "GB-216": {
        "name": "funnel-metrics",
        "token": "funnel-metrics",
        "claim": "no-ee-funnel_metrics",
    },
    "GB-218": {
        "name": "custom-markdown",
        "token": "custom-markdown",
        "claim": "no-ee-custom_markdown",
    },
    "GB-219": {
        "name": "experiment-impact",
        "token": "experiment-impact",
        "claim": "no-ee-experiment_impact",
    },
    "GB-220": {
        "name": "metric-populations",
        "token": "metric-populations",
        "claim": "no-ee-metric_populations",
    },
    "GB-221": {
        "name": "large-saved-groups",
        "token": "large-saved-groups",
        "claim": "no-ee-large_saved_groups",
    },
    "GB-223": {
        "name": "metric-groups",
        "token": "metric-groups",
        "claim": "no-ee-metric_groups",
    },
    "GB-226": {
        "name": "historical-power",
        "token": "historical-power",
        "claim": "no-ee-historical_power",
    },
    "GB-227": {
        "name": "decision-framework",
        "token": "decision-framework",
        "claim": "no-ee-decision_framework",
    },
    "GB-228": {
        "name": "unlimited-cdn-usage",
        "token": "unlimited-cdn-usage",
        "claim": "no-ee-unlimited_cdn_usage",
    },
    "GB-229": {
        "name": "unlimited-managed-warehouse-usage",
        "token": "unlimited-managed-warehouse-usage",
        "claim": "no-ee-unlimited_managed_warehouse_usage",
    },
    "GB-230": {
        "name": "unlimited-event-forwarder-usage",
        "token": "unlimited-event-forwarder-usage",
        "claim": "no-ee-unlimited_event_forwarder_usage",
    },
    "GB-235": {
        "name": "saveSqlExplorerQueries",
        "token": "savesqlexplorerqueries",
        "claim": "no-ee-savesqlexplorerqueries",
    },
    "GB-236": {
        "name": "metric-effects",
        "token": "metric-effects",
        "claim": "no-ee-metric_effects",
    },
    "GB-238": {
        "name": "learnings",
        "token": "learnings",
        "claim": "no-ee-learnings",
    },
    "GB-240": {
        "name": "product-analytics-dashboards",
        "token": "product-analytics-dashboards",
        "claim": "no-ee-product_analytics_dashboards",
    },
    "GB-241": {
        "name": "precomputed-dimensions",
        "token": "precomputed-dimensions",
        "claim": "no-ee-precomputed_dimensions",
    },
    "GB-242": {
        "name": "custom-hooks",
        "token": "custom-hooks",
        "claim": "no-ee-custom_hooks",
    },
    "GB-243": {
        "name": "metric-slices",
        "token": "metric-slices",
        "claim": "no-ee-metric_slices",
    },
    "GB-244": {
        "name": "manage-official-resources",
        "token": "manage-official-resources",
        "claim": "no-ee-manage_official_resources",
    },
    "GB-245": {
        "name": "incremental-refresh",
        "token": "incremental-refresh",
        "claim": "no-ee-incremental_refresh",
    },
    "GB-246": {
        "name": "adv-presentations",
        "token": "adv-presentations",
        "claim": "no-ee-adv_presentations",
    },
    "GB-251": {
        "name": "contextual-bandits",
        "token": "contextual-bandits",
        "claim": "no-ee-contextual_bandits",
    },
    "GB-252": {
        "name": "interleaving",
        "token": "interleaving",
        "claim": "no-ee-interleaving",
    },
    "GB-253": {
        "name": "cluster-experiments",
        "token": "cluster-experiments",
        "claim": "no-ee-cluster_experiments",
    },
    "GB-254": {
        "name": "human-in-the-loop",
        "token": "human-in-the-loop",
        "claim": "no-ee-human_in_the_loop",
    },
    "GB-255": {
        "name": "AI Mode",
        "token": "ai mode",
        "claim": "no-ee-ai_mode",
    },
    "GB-256": {
        "name": "Manual Mode",
        "token": "manual mode",
        "claim": "no-ee-manual_mode",
    },
    "GB-257": {
        "name": "Visual editor images",
        "token": "visual editor images",
        "claim": "no-ee-visual_editor_images",
    },
    "GB-258": {
        "name": "Design to Variant",
        "token": "design to variant",
        "claim": "no-ee-design_to_variant",
    },
    "GB-259": {
        "name": "Visual experiment anti-flicker",
        "token": "visual experiment anti-flicker",
        "claim": "no-ee-visual_experiment_anti_flicker",
    },
    "GB-260": {
        "name": "Visual experiment preview and QA",
        "token": "visual experiment preview and qa",
        "claim": "no-ee-visual_experiment_preview_and_qa",
    },
    "GB-261": {
        "name": "Bandit configuration",
        "token": "bandit configuration",
        "claim": "no-ee-bandit_configuration",
    },
    "GB-262": {
        "name": "Bandit results",
        "token": "bandit results",
        "claim": "no-ee-bandit_results",
    },
    "GB-263": {
        "name": "Contextual bandit configuration",
        "token": "contextual bandit configuration",
        "claim": "no-ee-contextual_bandit_configuration",
    },
    "GB-264": {
        "name": "Contextual bandit API",
        "token": "contextual bandit api",
        "claim": "no-ee-contextual_bandit_api",
    },
    "GB-265": {
        "name": "Interleaving setup",
        "token": "interleaving setup",
        "claim": "no-ee-interleaving_setup",
    },
    "GB-266": {
        "name": "Interleaving results",
        "token": "interleaving results",
        "claim": "no-ee-interleaving_results",
    },
    "GB-267": {
        "name": "Vercel native integration",
        "token": "vercel native integration",
        "claim": "no-ee-vercel_native_integration",
    },
    "GB-268": {
        "name": "Framer plugin",
        "token": "framer plugin",
        "claim": "no-ee-framer_plugin",
    },
    "GB-269": {
        "name": "Shopify integration",
        "token": "shopify integration",
        "claim": "no-ee-shopify_integration",
    },
    "GB-270": {
        "name": "Webflow integration",
        "token": "webflow integration",
        "claim": "no-ee-webflow_integration",
    },
    "GB-271": {
        "name": "WordPress integration",
        "token": "wordpress integration",
        "claim": "no-ee-wordpress_integration",
    },
    "GB-272": {
        "name": "AI integrations",
        "token": "ai integrations",
        "claim": "no-ee-ai_integrations",
    },
    "GB-273": {
        "name": "LLM tracing experiments",
        "token": "llm tracing experiments",
        "claim": "no-ee-llm_tracing_experiments",
    },
    "GB-274": {
        "name": "GitHub metric version control",
        "token": "github metric version control",
        "claim": "no-ee-github_metric_version_control",
    },
    "GB-275": {
        "name": "Microsoft Clarity heatmaps",
        "token": "microsoft clarity heatmaps",
        "claim": "no-ee-microsoft_clarity_heatmaps",
    },
    "GB-276": {
        "name": "Jira integration",
        "token": "jira integration",
        "claim": "no-ee-jira_integration",
    },
    "GB-277": {
        "name": "Discord integration",
        "token": "discord integration",
        "claim": "no-ee-discord_integration",
    },
    "GB-278": {
        "name": "Datadog integration",
        "token": "datadog integration",
        "claim": "no-ee-datadog_integration",
    },
    "GB-279": {
        "name": "Slack AI assistant",
        "token": "slack ai assistant",
        "claim": "no-ee-slack_ai_assistant",
    },
    "GB-280": {
        "name": "Self-hosted Slack setup",
        "token": "self-hosted slack setup",
        "claim": "no-ee-self_hosted_slack_setup",
    },
    "GB-281": {
        "name": "Legacy Slack webhooks",
        "token": "legacy slack webhooks",
        "claim": "no-ee-legacy_slack_webhooks",
    },
}


class AbsenceOut(BaseModel):
    row_id: str
    name: str
    claim: str
    notice: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    notes: str

    model_config = ConfigDict(from_attributes=True)


def _out(row_id: str, spec: dict[str, str]) -> AbsenceOut:
    return AbsenceOut(
        row_id=row_id,
        name=spec["name"],
        claim=spec["claim"],
        notice=NOTICE_TEXT,
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=NO_EE_NOTE,
    )


@router.get("", response_model=list[AbsenceOut])
def list_ee_absence_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[AbsenceOut]:
    """List the immutable enterprise-absence decisions for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=AbsenceOut)
def get_ee_absence_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> AbsenceOut:
    """Return one absence decision, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = CLAIM_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EE absence boundary not found")
    return _out(row_id, spec)
