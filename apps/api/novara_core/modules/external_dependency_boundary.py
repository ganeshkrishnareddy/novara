"""External-dependency no-claim boundary (94 restricted rows).

Each row is an EXTERNAL_DEPENDENCY_BLOCKED inventory entry whose acceptance
criteria deny a default or fabricated external integration. NOVARA keeps the
capability blocked until a real provider is configured and verified. This module
serves a read-only, workspace-scoped catalogue of those no-claim decisions. It
imports no provider SDK, constructs no client, opens no socket and reports no
delivery. Upstream notices are preserved verbatim.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/external-dependency-boundary",
    tags=["external-dependency-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NO_CLAIM_NOTE = (
    "No default external integration: the capability stays blocked until a real provider "
    "is explicitly configured and verified. No SDK import, client, endpoint, credential "
    "field or delivery result is created here; upstream attribution preserved."
)

# Values are NOVARA-local no-claim descriptors, not installed connectors.
CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "FB-031": {
        "name": "Spam Protection (Google reCAPTCHA v3)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_031",
    },
    "FB-077": {
        "name": "Google Tag Manager deployment",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_077",
    },
    "FB-102": {
        "name": "AI Enrichment (sentiment, emotions, language)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_102",
    },
    "FB-103": {
        "name": "Topics and Subtopics (Preview)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_103",
    },
    "FB-105": {
        "name": "Formbricks Hub",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_105",
    },
    "FB-106": {
        "name": "AI chart creation and AI helpers",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_106",
    },
    "FB-111": {
        "name": "Third-party integrations (Cloud)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_111",
    },
    "FB-112": {
        "name": "Slack integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_112",
    },
    "FB-113": {
        "name": "Notion integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_113",
    },
    "FB-114": {
        "name": "Zapier integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_114",
    },
    "FB-115": {
        "name": "n8n integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_115",
    },
    "FB-116": {
        "name": "Google Sheets integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_116",
    },
    "FB-117": {
        "name": "Activepieces integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_117",
    },
    "FB-118": {
        "name": "Airtable integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_118",
    },
    "FB-119": {
        "name": "Attio integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_119",
    },
    "FB-120": {
        "name": "HubSpot integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_120",
    },
    "FB-121": {
        "name": "Make integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_121",
    },
    "FB-122": {
        "name": "Salesforce integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_122",
    },
    "FB-123": {
        "name": "Wordpress integration",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_123",
    },
    "FB-150": {
        "name": "SpiceDB fine-grained authorisation",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_150",
    },
    "FB-154": {
        "name": "OAuth provider / social login",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_154",
    },
    "FB-163": {
        "name": "Email delivery (packages/email, SMTP)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_163",
    },
    "FB-164": {
        "name": "Object storage / file uploads (packages/storage, RustFS, S3)",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_164",
    },
    "FB-165": {
        "name": "Valkey / Redis-compatible queue and cache",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_165",
    },
    "FB-166": {
        "name": "PostgreSQL persistence with Prisma",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_166",
    },
    "FB-169": {
        "name": "VLLM / local AI endpoint",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_169",
    },
    "FB-170": {
        "name": "Cube analytics service",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_170",
    },
    "FB-171": {
        "name": "hub / hub-worker service",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_171",
    },
    "FB-172": {
        "name": "Self-hosting documentation set",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_172",
    },
    "FB-173": {
        "name": "Docker image builds and release workflows",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_173",
    },
    "FB-174": {
        "name": "Deployment charts",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_174",
    },
    "FB-175": {
        "name": "One-click deployment options",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_175",
    },
    "FB-176": {
        "name": "CDN, custom SSL and custom subpath",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_176",
    },
    "FB-178": {
        "name": "Monitoring, deployment check and cluster setup",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_178",
    },
    "FB-226": {
        "name": "Hosted free plan",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_226",
    },
    "FB-227": {
        "name": "Experience Suite",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_227",
    },
    "FB-228": {
        "name": "Managed cloud",
        "provider": "Formbricks",
        "notice": "Formbricks (community core) — Formbricks GmbH",
        "claim": "no-default-fb_228",
    },
    "MS-083": {
        "name": "Self-hosted deployment claims",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_083",
    },
    "MS-084": {
        "name": "Meilisearch Cloud managed service",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_084",
    },
    "MS-085": {
        "name": "Cloud monitoring, resource scaling and version management",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_085",
    },
    "MS-086": {
        "name": "Cloud teams, roles, SSO and IP allowlist",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_086",
    },
    "MS-087": {
        "name": "Cloud automated backups",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_087",
    },
    "MS-099": {
        "name": "Environment-driven configuration",
        "provider": "Meilisearch",
        "notice": "Meilisearch core — Meili SAS",
        "claim": "no-default-ms_099",
    },
    "GB-119": {
        "name": "Athena",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_119",
    },
    "GB-120": {
        "name": "Managed warehouse connector B",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_120",
    },
    "GB-121": {
        "name": "ClickHouse",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_121",
    },
    "GB-122": {
        "name": "Databricks",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_122",
    },
    "GB-123": {
        "name": "Google Analytics",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_123",
    },
    "GB-124": {
        "name": "Mixpanel",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_124",
    },
    "GB-125": {
        "name": "MSSQL or SQL Server",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_125",
    },
    "GB-126": {
        "name": "MySQL or MariaDB",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_126",
    },
    "GB-127": {
        "name": "PostgreSQL",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_127",
    },
    "GB-128": {
        "name": "PrestoDB or Trino",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_128",
    },
    "GB-129": {
        "name": "Amazon Redshift",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_129",
    },
    "GB-130": {
        "name": "Snowflake",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_130",
    },
    "GB-131": {
        "name": "Generic SQL integration",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_131",
    },
    "GB-132": {
        "name": "Vertica",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_132",
    },
    "GB-133": {
        "name": "Adobe Experience Platform Query Service",
        "provider": "GrowthBook",
        "notice": "GrowthBook (community) — GrowthBook, Inc.",
        "claim": "no-default-gb_133",
    },
    "PM-138": {
        "name": "Vercel deployment and domain automation",
        "provider": "Papermark",
        "notice": "Papermark (community core) — Papermark, Inc.",
        "claim": "no-default-pm_138",
    },
    "PM-140": {
        "name": "Resend email delivery",
        "provider": "Papermark",
        "notice": "Papermark (community core) — Papermark, Inc.",
        "claim": "no-default-pm_140",
    },
    "MT-110": {
        "name": "Object or CDN storage dependency",
        "provider": "Mautic",
        "notice": "Mautic — Mautic contributors",
        "claim": "no-default-mt_110",
    },
    "CW-033": {
        "name": "Email conversation transcript",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_033",
    },
    "CW-037": {
        "name": "Email channel",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_037",
    },
    "CW-038": {
        "name": "WhatsApp Business channel",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_038",
    },
    "CW-041": {
        "name": "X (Twitter) DMs and mentions",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_041",
    },
    "CW-045": {
        "name": "TikTok DMs channel",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_045",
    },
    "CW-047": {
        "name": "Cloudflare RealtimeKit video calls",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_047",
    },
    "CW-073": {
        "name": "Rasa chatbot",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_073",
    },
    "CW-085": {
        "name": "Auto-translate",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_085",
    },
    "CW-107": {
        "name": "Push notifications",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_107",
    },
    "CW-124": {
        "name": "Stripe integration",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_124",
    },
    "CW-127": {
        "name": "APM / monitoring integrations",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_127",
    },
    "CW-145": {
        "name": "CircleCI pipeline",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_145",
    },
    "CW-161": {
        "name": "CDN asset hosting",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_161",
    },
    "CW-163": {
        "name": "Channel and AI provider keys",
        "provider": "Chatwoot",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "claim": "no-default-cw_163",
    },
    "NV-080": {
        "name": "Self-hosting stack",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "claim": "no-default-nv_080",
    },
    "NV-098": {
        "name": "Observability integrations (Sentry, New Relic)",
        "provider": "Novu",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "claim": "no-default-nv_098",
    },
    "SB-001": {
        "name": "Discovery providers",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_001",
    },
    "SB-002": {
        "name": "Company discovery run",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_002",
    },
    "SB-004": {
        "name": "Decision-maker discovery",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_004",
    },
    "SB-005": {
        "name": "Website profiling",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_005",
    },
    "SB-006": {
        "name": "Email pattern finding",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_006",
    },
    "SB-007": {
        "name": "Email verification",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_007",
    },
    "SB-025": {
        "name": "Sending via mail providers",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_025",
    },
    "SB-027": {
        "name": "Multiple mailboxes and mailbox connections",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_027",
    },
    "SB-029": {
        "name": "Reply classification and `processed_replies`",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_029",
    },
    "SB-032": {
        "name": "Bounce handling and bounce kill switch",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_032",
    },
    "SB-045": {
        "name": "Brain model layer using operator Claude/Codex CLI",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_045",
    },
    "SB-064": {
        "name": "SSRF-safe public HTTP",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_064",
    },
    "SB-073": {
        "name": "Hosted managed domains",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_073",
    },
    "SB-074": {
        "name": "Hosted managed inboxes",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_074",
    },
    "SB-075": {
        "name": "Hosted warmup",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_075",
    },
    "SB-076": {
        "name": "Hosted DNS management",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_076",
    },
    "SB-077": {
        "name": "Hosted managed sending",
        "provider": "Sellbird",
        "notice": "Sellbird v0.4.0+ — Ethan Rogers and contributors",
        "claim": "no-default-sb_077",
    },
}


class DependencyBoundaryOut(BaseModel):
    row_id: str
    name: str
    provider: str
    claim: str
    notice: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    delivery_claimed: bool
    notes: str

    model_config = ConfigDict(from_attributes=True)


def _out(row_id: str, spec: dict[str, str]) -> DependencyBoundaryOut:
    return DependencyBoundaryOut(
        row_id=row_id,
        name=spec["name"],
        provider=spec["provider"],
        claim=spec["claim"],
        notice=spec["notice"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        delivery_claimed=False,
        notes=NO_CLAIM_NOTE,
    )


@router.get("", response_model=list[DependencyBoundaryOut])
def list_external_dependency_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[DependencyBoundaryOut]:
    """List the immutable no-claim decisions for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=DependencyBoundaryOut)
def get_external_dependency_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> DependencyBoundaryOut:
    """Return one no-claim decision, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = CLAIM_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External dependency boundary not found",
        )
    return _out(row_id, spec)
