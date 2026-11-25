"""Clean-room enterprise out-of-scope boundary (49 restricted rows).

Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria
permit an explicit out-of-scope decision backed by named evidence: no enterprise
source, entitlement, paid asset or unverified claim is present in NOVARA. This
module serves a read-only, workspace-scoped catalogue of those decisions.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/out-of-scope-boundary",
    tags=["out-of-scope-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
OUT_OF_SCOPE_NOTE = (
    "Explicit out-of-scope decision: no enterprise source, entitlement, paid asset or "
    "unverified claim is present in the default install; upstream attribution preserved."
)

CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "FB-155": {
        "name": "SAML / BoxyHQ",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-156": {
        "name": "OIDC / Keycloak / Okta / Azure AD SSO",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-205": {
        "name": "Enterprise: AI translation of surveys",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-206": {
        "name": "Enterprise: Enterprise analysis capability",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-207": {
        "name": "Enterprise: Comprehensive audit logging",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-208": {
        "name": "Enterprise: Enterprise authentication helpers",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-209": {
        "name": "Enterprise: Enterprise billing",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-210": {
        "name": "Enterprise: Enterprise contact extras / contacts API guard",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-211": {
        "name": "Enterprise: Enterprise creative extras",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-212": {
        "name": "Enterprise: Data retention controls",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-213": {
        "name": "Enterprise: Feedback directory",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-214": {
        "name": "Enterprise: Enterprise license enforcement",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-215": {
        "name": "Enterprise: Enterprise mailing",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-216": {
        "name": "Enterprise: Quota enforcement",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-217": {
        "name": "Enterprise: Enterprise role management",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-218": {
        "name": "Enterprise: Enterprise SSO",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-219": {
        "name": "Enterprise: Enterprise teams",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-220": {
        "name": "Enterprise: Enterprise two-factor auth",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-221": {
        "name": "Enterprise: Enterprise Unify Feedback extras",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-222": {
        "name": "Enterprise: White-labelling",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-223": {
        "name": "Enterprise: Enterprise workflow extras",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-224": {
        "name": "Enterprise license check enforcement files",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-225": {
        "name": "License activation documentation",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "FB-234": {
        "name": "Exclude all EE capabilities from the default install",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
    },
    "MS-088": {
        "name": "Search Rules: pin, boost, deboost and hide documents",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "MS-089": {
        "name": "Inline dynamic search rules",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "MS-090": {
        "name": "Sharding",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "MS-091": {
        "name": "Replication, network topology and leader routing",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "MS-092": {
        "name": "S3-streaming snapshots",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "MS-093": {
        "name": "Enterprise Edition entitlement guard and BUSL terms",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
    },
    "CW-164": {
        "name": "Enterprise application layer",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
    },
    "CW-167": {
        "name": "Priority support and paid self-hosted subscription",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
    },
    "CW-168": {
        "name": "Enterprise compliance suite (unverified boundary)",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
    },
    "NV-067": {
        "name": "Environment variables (`env.*` in templates)",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-074": {
        "name": "Workflow and layout translations",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-077": {
        "name": "Billing and plan limits",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-078": {
        "name": "Compliance certifications, DPA, HIPAA BAA, SOC 2 and ISO 27001",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-079": {
        "name": "Remove Novu branding",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-084": {
        "name": "Enterprise proprietary packages (`enterprise/packages/auth`, `billing`, `dal`, `shared-services`, `translation`) and `*ee*` UI paths",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-093": {
        "name": "Managed Novu Cloud service",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-109": {
        "name": "Managed Agent runtime",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "NV-116": {
        "name": "Regional API endpoints",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
    },
    "PL-110": {
        "name": "Pro tier entitlements",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PL-111": {
        "name": "Business tier entitlements",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PL-112": {
        "name": "Enterprise Grid tier entitlements",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PL-121": {
        "name": "AI credits",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PL-122": {
        "name": "AI agents",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PL-127": {
        "name": "Billing, seats and license management",
        "provider": "Plane",
        "notice": "Plane — Plane Software, Inc. and contributors",
    },
    "PM-094": {
        "name": "DATAROOM_MEMBER role",
        "provider": "Papermark",
        "notice": "Papermark (community core) — Papermark, Inc.",
    },
}


class ScopeOut(BaseModel):
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


def _out(row_id: str, spec: dict[str, str]) -> ScopeOut:
    return ScopeOut(
        row_id=row_id,
        name=spec["name"],
        provider=spec["provider"],
        claim="no-enterprise-scope-" + row_id.lower().replace("-", "_"),
        notice=spec["notice"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=OUT_OF_SCOPE_NOTE,
    )


@router.get("", response_model=list[ScopeOut])
def list_out_of_scope_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[ScopeOut]:
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=ScopeOut)
def get_out_of_scope_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> ScopeOut:
    verify_workspace(principal, workspace_id)
    spec = CLAIM_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Out-of-scope boundary not found")
    return _out(row_id, spec)
