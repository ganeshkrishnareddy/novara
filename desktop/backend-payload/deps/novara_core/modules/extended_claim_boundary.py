"""Extended clean-room claims boundary (26 negative-evidence rows).

These rows are negative evidence claims across Meilisearch, Chatwoot, Papermark,
Novu and Sellbird: NOVARA must not advertise an unverified engine, connector, CLI,
dashboard, bridge, certification or external send capability. This module serves a
read-only, workspace-scoped catalogue of those boundaries. It imports no third-party
SDK, creates no network client and presents no mocked external result as product output.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/extended-claim-boundary",
    tags=["extended-claim-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NO_DEFAULT_NOTE = (
    "Negative evidence boundary: NOVARA makes no such claim; no dependency, "
    "external endpoint, vendored package or unverified result is created here."
)

# Each value is a NOVARA-local boundary descriptor: what is explicitly NOT claimed.
CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "MS-005": {
        "name": "Prefix search",
        "provider": "Meilisearch",
        "claim": "no-prefix-only-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No prefix-only search behaviour is advertised; the local search engine does not claim this capability.",
    },
    "MS-009": {
        "name": "Faceted navigation UI",
        "provider": "Meilisearch",
        "claim": "no-facet-count-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "Type filters return real rows; no facet-count figure is displayed or invented.",
    },
    "MS-010": {
        "name": "Sorting / sortableAttributes",
        "provider": "Meilisearch",
        "claim": "no-configurable-sort-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No UI or API advertises configurable engine sort attributes until they are implemented.",
    },
    "MS-050": {
        "name": "Task cancellation, deletion and streaming",
        "provider": "Meilisearch",
        "claim": "no-engine-task-stream-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No engine task stream, cancellation or deletion endpoint is claimed.",
    },
    "MS-051": {
        "name": "Batches and batch monitoring",
        "provider": "Meilisearch",
        "claim": "no-engine-batch-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No engine batch UID, stream or batch-monitoring claim is made.",
    },
    "MS-059": {
        "name": "Logs streaming and runtime log level",
        "provider": "Meilisearch",
        "claim": "no-engine-log-stream-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "Audit events are workspace scoped and correlated; no engine log stream is claimed.",
    },
    "MS-096": {
        "name": "CI benchmark, fuzz and SDK test workflows",
        "provider": "Meilisearch",
        "claim": "no-benchmark-result-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No benchmark result is asserted anywhere in the inventory.",
    },
    "MS-098": {
        "name": "Search analytics and usage events",
        "provider": "Meilisearch",
        "claim": "no-search-analytics-dashboard-claim",
        "notice": "Meilisearch core — Meili SAS",
        "note": "No search analytics dashboard is claimed before query events are emitted and tested.",
    },
    "CW-119": {
        "name": "Legacy api_access_token header",
        "provider": "Chatwoot",
        "claim": "no-legacy-token-header",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "note": "No route accepts a legacy token header; bearer tokens remain the only accepted form.",
    },
    "PM-067": {
        "name": "Data room digest emails",
        "provider": "Papermark",
        "claim": "no-digest-send-claim",
        "notice": "Papermark (community core) — Papermark, Inc.",
        "note": "No digest send is claimed without provider evidence.",
    },
    "PM-136": {
        "name": "Vercel Postgres and Blob defaults",
        "provider": "Papermark",
        "claim": "no-vercel-default-claim",
        "notice": "Papermark (community core) — Papermark, Inc.",
        "note": "Local install works with no Vercel account or hosted Postgres/Blob dependency.",
    },
    "PM-155": {
        "name": "Security certifications and data residency",
        "provider": "Papermark",
        "claim": "no-certification-claim",
        "notice": "Papermark (community core) — Papermark, Inc.",
        "note": "The inventory states no certification is verified for NOVARA and no UI claims one.",
    },
    "NV-041": {
        "name": "Headless Inbox and custom layouts",
        "provider": "Novu",
        "claim": "no-duplicate-ui-framework-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No duplicate UI framework is introduced; the local permissioned API remains the single source.",
    },
    "NV-053": {
        "name": "Usage and delivery analytics",
        "provider": "Novu",
        "claim": "no-fabricated-provider-metric-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "Analytics values trace to stored events; no provider metric is fabricated.",
    },
    "NV-055": {
        "name": "Webhook connectors (BigQuery, S3, Segment and similar)",
        "provider": "Novu",
        "claim": "no-paid-warehouse-default",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No default build depends on a paid external warehouse or connector.",
    },
    "NV-060": {
        "name": "Code-first workflows (@novu/framework, bridge endpoints)",
        "provider": "Novu",
        "claim": "no-code-first-advert-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "Code-first execution is not advertised unless a bridge is actually implemented and tested.",
    },
    "NV-061": {
        "name": "Novu CLI (@novu/novu)",
        "provider": "Novu",
        "claim": "no-cloud-cli-login-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No Novu-cloud CLI login is required or implied by NOVARA docs.",
    },
    "NV-063": {
        "name": "Agent Communication Infrastructure (ACI)",
        "provider": "Novu",
        "claim": "no-two-way-channel-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No two-way channel conversation is claimed without a real connector and named test.",
    },
    "NV-066": {
        "name": "Environments (Development, Production, custom)",
        "provider": "Novu",
        "claim": "no-environment-sync-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "Workspace separation holds and no environment sync claim is made without implementation.",
    },
    "NV-090": {
        "name": "Dashboard and human-dashboard React apps",
        "provider": "Novu",
        "claim": "no-foreign-dashboard-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "Any dashboard view reads local APIs and never embeds a foreign-branded Novu dashboard.",
    },
    "NV-091": {
        "name": "Agent inbox MCP bridge (apps/agent-inbox-mcp)",
        "provider": "Novu",
        "claim": "no-unapproved-mcp-tool-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No agent MCP tool is advertised without workspace and approval enforcement.",
    },
    "NV-095": {
        "name": "@novu/stateless provider utilities",
        "provider": "Novu",
        "claim": "no-provider-delivery-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "Adapter helpers never claim delivery and are covered by named tests.",
    },
    "NV-108": {
        "name": "Agent management API and bridge registration",
        "provider": "Novu",
        "claim": "no-unauthorised-bridge-url-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No bridge URL is accepted without workspace authorisation and environment checks.",
    },
    "NV-110": {
        "name": "AI framework adapters",
        "provider": "Novu",
        "claim": "no-verified-ai-call-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No AI model call is claimed as verified and every agent tool passes permissions.",
    },
    "NV-114": {
        "name": "Custom code agent bridge and handlers",
        "provider": "Novu",
        "claim": "no-arbitrary-agent-code-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No arbitrary agent code executes without isolation and a named test.",
    },
    "SB-043": {
        "name": "LinkedIn-related agent roles",
        "provider": "Sellbird",
        "claim": "no-public-post-route",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "note": "Design-constraint review confirms no public-post route exists and no LinkedIn credential is required.",
    },
}


class ClaimBoundaryOut(BaseModel):
    row_id: str
    name: str
    provider: str
    claim: str
    notice: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    notes: str

    model_config = ConfigDict(from_attributes=True)


def _out(row_id: str, spec: dict[str, str]) -> ClaimBoundaryOut:
    return ClaimBoundaryOut(
        row_id=row_id,
        name=spec["name"],
        provider=spec["provider"],
        claim=spec["claim"],
        notice=spec["notice"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=NO_DEFAULT_NOTE + " " + spec["note"],
    )


@router.get("", response_model=list[ClaimBoundaryOut])
def list_extended_claim_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[ClaimBoundaryOut]:
    """List the immutable negative-evidence boundaries for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=ClaimBoundaryOut)
def get_extended_claim_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> ClaimBoundaryOut:
    """Return one boundary, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = CLAIM_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extended claim boundary not found",
        )
    return _out(row_id, spec)
