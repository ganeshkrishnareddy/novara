"""No-claim and documentation evidence boundary (81 rows).

Each row is an inventory entry whose acceptance criteria are no-claim,
documentation-only, design-decision or conditional ("if claimed") criteria.
NOVARA records a conservative decision in `docs/NOVARA_NO_CLAIM_POLICY.md`
and serves a read-only, workspace-scoped record of it. No source project
capability is copied, no external provider is contacted and no unverified
result is asserted.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/no-claim-evidence-boundary",
    tags=["no-claim-evidence-boundary"],
)

POLICY_FILE = "docs/NOVARA_NO_CLAIM_POLICY.md"
NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
DECISION_NOTE = (
    "Conservative no-claim or documentation decision. No source project capability is "
    "copied, no external call is made and no unverified result is asserted."
)

CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "MS-101": {
        "name": "OpenAPI specification generation and CI sync",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "statement": "novara does not claim to implement the meilisearch openapi contract; only local api routes are documented.",
    },
    "PL-075": {
        "name": "Live service",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara does not claim a realtime component until it is implemented, authenticated and tested.",
    },
    "PL-143": {
        "name": "Shortcut handling",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara does not claim keyboard shortcuts; any shortcut added must not fire in text inputs and must be documented.",
    },
    "PL-152": {
        "name": "Reverse proxy and certificate settings",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara deployment documentation records tls, domain and proxy choices as owner decisions and does not claim a verified proxy run.",
    },
    "MT-005": {
        "name": "Self-host free forever with all features",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara self-host capability is available without a private licence, hosted account or api key; no hidden feature gating is present.",
    },
    "MT-006": {
        "name": "Production packaged release from mautic.org/download",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara deployment documentation identifies the local start scripts and the unverified container files; no packaged release is claimed.",
    },
    "MT-038": {
        "name": "Cloud storage plugin",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara documents local storage configuration only; no cloud storage provider is claimed or contacted by default.",
    },
    "MT-061": {
        "name": "MarketplaceBundle",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara keeps a documented module registry instead of a marketplace; no marketplace capability is claimed.",
    },
    "MT-084": {
        "name": "DDEV developer environment",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara local developer setup is documented in readme.md and install.md using the start-local scripts; no ddev is claimed.",
    },
    "MT-085": {
        "name": "Composer install and bin/console install",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara install documentation describes its own package manager and start scripts; no composer or bin/console install is claimed.",
    },
    "MT-087": {
        "name": "Web server support Apache, Nginx and IIS",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara documents only the verified local web server; apache, nginx and iis support is not claimed as verified.",
    },
    "MT-088": {
        "name": "Shared hosting not recommended",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara hosting guidance says to use a supported self-host environment; shared hosting is not claimed as verified.",
    },
    "MT-090": {
        "name": "Static-analysis status",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara has no phpstan configuration; the recorded verification tooling is the local pytest suite and alembic checks.",
    },
    "MT-091": {
        "name": "Coverage tooling status",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara has no codecov configuration; coverage claims are limited to the local pytest run recorded in test_results.md.",
    },
    "MT-103": {
        "name": "Mautic trademark",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara uses the mautic mark only descriptively in provenance documentation, not as product branding.",
    },
    "MT-104": {
        "name": "Third-party notices",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara keeps third-party licence provenance in third_party_notices.md; no unattributed third-party asset is claimed.",
    },
    "MT-119": {
        "name": "Source-tree install alpha warning",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara release guidance states that the project is in active development and not a release candidate; no source-tree release is claimed.",
    },
    "MT-120": {
        "name": "7.x coverage percentage not verified",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara coverage claims are limited to verified local test evidence; no mautic coverage percentage is claimed.",
    },
    "MT-125": {
        "name": "Transifex maintenance command",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara documents a local, independent localization workflow; no transifex integration is claimed.",
    },
    "MT-128": {
        "name": "Upgrade event extension",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara does not claim upgrade-event hooks; no such hook is introduced.",
    },
    "MT-131": {
        "name": "Maintenance event extension",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara does not claim maintenance-event hooks; no such hook is introduced.",
    },
    "MT-132": {
        "name": "Builder event extension",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara does not claim builder-event hooks; no such hook is introduced.",
    },
    "MT-133": {
        "name": "Import and export event extension",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "statement": "novara documents its own import/export portability path; no mautic event-hook compatibility is claimed.",
    },
    "CW-026": {
        "name": "Inbox shortcut handling",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim inbox keyboard shortcuts; any shortcut added must not trigger writes without confirmation.",
    },
    "CW-034": {
        "name": "Dashboard apps",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim embedded dashboard apps; no panel is loaded from an external origin and no workspace token is exposed to one.",
    },
    "CW-044": {
        "name": "SMS channel",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim an inbound or outbound sms capability until consent and a verified provider are configured; no fake call or message ui is shown.",
    },
    "CW-046": {
        "name": "Voice channel",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim voice channel parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-058": {
        "name": "SLA timers and status indicators",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim sla timers; any sla state must come from real timestamps and no fabricated countdown is displayed.",
    },
    "CW-061": {
        "name": "Captain Assistant",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain assistant parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-062": {
        "name": "Captain Copilot",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain copilot parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-063": {
        "name": "Captain Memories",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain memories parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-064": {
        "name": "Captain Reply suggestions",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim auto-sending reply suggestions; any draft requires explicit user action and approval.",
    },
    "CW-068": {
        "name": "Captain Triage",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain triage parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-069": {
        "name": "Captain Scenarios",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain scenarios parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-070": {
        "name": "Captain Monitors / Convergence",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim an llm-backed monitor; any local count has a reproducible definition and no model dependency is implied.",
    },
    "CW-071": {
        "name": "Captain copilot / MCP tools",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim captain copilot / mcp tools parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-072": {
        "name": "Dialogflow chatbot",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim dialogflow bot replies; a reply requires a verified webhook and is labelled as bot-authored.",
    },
    "CW-080": {
        "name": "WhatsApp campaigns",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim whatsapp campaigns parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-103": {
        "name": "WhatsApp CSAT templates",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim whatsapp csat templates parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-125": {
        "name": "Linear integration",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim a linear issue link until an authorised api call succeeds; no unverified link is stored.",
    },
    "CW-126": {
        "name": "Shopify integration",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim shopify order context until verified data is available; no fabricated order is shown.",
    },
    "CW-128": {
        "name": "Chatwoot CLI for coding agents",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim chatwoot cli for coding agents parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-136": {
        "name": "Optional GitHub OAuth strategy",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not enable optional github oauth unless the feature is explicitly enabled with configured credentials.",
    },
    "CW-147": {
        "name": "Managed one-click deployment",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim a verified digitalocean one-click deployment; no deployment success is reported in this inventory.",
    },
    "CW-150": {
        "name": "Development container and deployment manifests",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara local api and web client startup commands are documented in readme.md and install.md.",
    },
    "CW-154": {
        "name": "Redis cache and queue backend",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim redis cache and queue backend parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-156": {
        "name": "OpenSearch and Searchkick advanced search backend",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim opensearch and searchkick advanced search backend parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-157": {
        "name": "S3, Azure and GCS object storage",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim s3, azure and gcs object storage parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "CW-165": {
        "name": "Process liveness and CloudWatch telemetry",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "statement": "novara does not claim process liveness and cloudwatch telemetry parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "NV-016": {
        "name": "Tool channel steps (PagerDuty, Opsgenie, Grafana, Tool Webhook)",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim pagerduty, opsgenie, grafana or tool webhook channel steps; no provider endpoint or fabricated delivery is present.",
    },
    "NV-021": {
        "name": "SMS notifications",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim sms delivery; no test or ui can claim delivery without a verified provider response.",
    },
    "NV-037": {
        "name": "Inbox snooze",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not advertise inbox snooze until the local behaviour is implemented and covered by named tests.",
    },
    "NV-049": {
        "name": "Email activity tracking (delivered, opened, clicked, bounced)",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim email activity tracking; no delivered, opened, clicked or bounced event is shown without a verified provider webhook.",
    },
    "NV-050": {
        "name": "Push activity tracking",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim push activity tracking parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "NV-064": {
        "name": "Web Chat channel",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim web chat channel parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "NV-083": {
        "name": "S3-compatible object storage",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim s3-compatible attachment storage in the default install; no storage provider is contacted by default.",
    },
    "NV-117": {
        "name": "Novu Agent Skills",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim novu agent skills parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "PL-126": {
        "name": "Sensitive data scanning",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara does not claim a sensitive-data scanner; any scanner added must not send content off-platform by default.",
    },
    "PL-131": {
        "name": "MCP server and connectors",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara does not claim an mcp surface; any mcp surface added must use novara permissions and log access.",
    },
    "PL-155": {
        "name": "Hosted cloud image",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "statement": "novara default install works without a hosted cloud or all-in-one image; container builds are not verified.",
    },
    "SB-039": {
        "name": "Scout agent role",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim a scout agent role with write or external-send permissions; no such role is enabled by default.",
    },
    "SB-040": {
        "name": "Writer agent role",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim a writer agent run can approve or send; any draft requires separate authorisation.",
    },
    "SB-041": {
        "name": "Handler agent role",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim a handler agent role can send, approve or publish externally.",
    },
    "SB-044": {
        "name": "Editable Markdown agent skills",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim editable markdown agent skills parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "SB-047": {
        "name": "Heartbeat loop",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim a heartbeat loop; no cycle is advertised as processing approved local work or sending messages.",
    },
    "SB-049": {
        "name": "PID/lock file preventing duplicate loops",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim pid or lock-file duplicate-loop protection; no such runner capability is present in the default install.",
    },
    "SB-050": {
        "name": "Extension tick steps with timeout",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim extension tick timeout handling; no tick-execution capability is present in the default install.",
    },
    "SB-058": {
        "name": "Stats and instance information",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not report an unavailable provider as active and stores no credential in instance statistics.",
    },
    "SB-059": {
        "name": "Dashboard docs disabled",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim dashboard docs disabled parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "SB-063": {
        "name": "MCP server toolset",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim an mcp tool that can approve, send or reveal secrets; no such tool is exposed by default.",
    },
    "SB-065": {
        "name": "Extension entry-point registry",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim an extension entry-point registry; no unrestricted hook registration is present in the default install.",
    },
    "SB-066": {
        "name": "CLI commands",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim cli commands; no external send command is present in the default install.",
    },
    "SB-068": {
        "name": "Desktop tray support",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "statement": "novara does not claim desktop tray support parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.",
    },
    "GB-194": {
        "name": "simulate",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'simulate' module is absent from the default novara install; no licensed source is present.",
    },
    "GB-205": {
        "name": "teams",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'teams' module is absent from the default novara install; novara workspaces and roles are independent.",
    },
    "GB-213": {
        "name": "custom-roles",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'custom-roles' module is absent from the default novara install; novara uses its own role model.",
    },
    "GB-234": {
        "name": "holdouts",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'holdouts' module is absent from the default novara install; no holdout feature is advertised.",
    },
    "GB-239": {
        "name": "dashboards",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'dashboards' module is absent from the default novara install; local analytics are separate.",
    },
    "GB-250": {
        "name": "releases",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "statement": "the growthbook enterprise 'releases' module is absent from the default novara install; work items are not branded as releases.",
    },
    "FB-193": {
        "name": "Headless Surveys guide",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "statement": "novara does not claim a headless survey template is implemented until a named test and ui evidence demonstrate the underlying survey behaviour.",
    },
    "NV-075": {
        "name": "No-code editors, layouts and block email editor (`libs/maily-*`)",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "statement": "novara does not claim copied no-code email editor source; any template rendering must use stored content and reject script injection.",
    },
}


class NoClaimOut(BaseModel):
    row_id: str
    name: str
    provider: str
    claim: str
    statement: str
    policy_file: str
    notice: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    notes: str

    model_config = ConfigDict(from_attributes=True)


def _out(row_id: str, spec: dict[str, str]) -> NoClaimOut:
    return NoClaimOut(
        row_id=row_id,
        name=spec["name"],
        provider=spec["provider"],
        claim="no-claim-" + row_id.lower().replace("-", "_"),
        statement=spec["statement"],
        policy_file=POLICY_FILE,
        notice=spec["notice"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=DECISION_NOTE,
    )


@router.get("", response_model=list[NoClaimOut])
def list_no_claim_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[NoClaimOut]:
    """List the immutable no-claim decisions for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=NoClaimOut)
def get_no_claim_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> NoClaimOut:
    """Return one decision, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = CLAIM_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No-claim boundary not found")
    return _out(row_id, spec)
