"""Clean-room Meilisearch "no unverified claim" boundary (MS-052..MS-102).

These rows are negative evidence claims: NOVARA must not advertise a webhook
delivery, remote export, metrics, MCP/chat, vector-store, personalized,
multimodal, TLS, telemetry, importer, CLI or vendored-crate capability that is
backed by an unverified Meilisearch dependency or external service. This module
serves a read-only, workspace-scoped catalogue of those boundaries. It does not
import a Meilisearch SDK, create a network client, or present a mock result as
search output.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/meilisearch-claim-boundary",
    tags=["meilisearch-claim-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NOTICE_TEXT = "Meilisearch core — Meili SAS"
NO_DEFAULT_NOTE = (
    "Negative evidence boundary: NOVARA makes no such claim; no dependency, "
    "external endpoint, vendored crate or unverified result is created here."
)

# Values are NOVARA-local boundary descriptors. They record what is explicitly
# NOT claimed by the default product, not an installed or verified dependency.
CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "MS-052": {
        "name": "Task webhooks",
        "claim": "no-webhook-delivery-or-callback-claim",
        "note": "No MEILI_TASK_WEBHOOK_URL handling, task callback delivery or outbound webhook is claimed.",
    },
    "MS-054": {
        "name": "Export to a remote Meilisearch instance",
        "claim": "no-outbound-export-claim",
        "note": "No document/settings export stream to a remote Meilisearch server is claimed.",
    },
    "MS-060": {
        "name": "Prometheus metrics endpoint",
        "claim": "no-metrics-endpoint-claim",
        "note": "No Prometheus-format engine metrics exposition endpoint is claimed.",
    },
    "MS-066": {
        "name": "Role-based access control with joins",
        "claim": "no-document-level-rbac-claim",
        "note": "No document-level RBAC or joined tenant/role visibility filter is claimed.",
    },
    "MS-068": {
        "name": "Framework and platform connectors",
        "claim": "no-framework-connector-claim",
        "note": "No Laravel/Rails/Symfony/Strapi/Firebase sync connector is claimed.",
    },
    "MS-069": {
        "name": "MCP server",
        "claim": "no-mcp-search-tool-claim",
        "note": "No /mcp search tool for LLM clients is claimed.",
    },
    "MS-070": {
        "name": "Conversational search and Chats API",
        "claim": "no-conversational-answer-claim",
        "note": "No chat-completions answer claimed as grounded in NOVARA indexes is made.",
    },
    "MS-071": {
        "name": "Agentic search guardrails and source documents",
        "claim": "no-source-citation-claim",
        "note": "No grounded source citation or agentic search guardrail is claimed.",
    },
    "MS-072": {
        "name": "LangChain vector store integration",
        "claim": "no-vector-store-integration-claim",
        "note": "No LangChain vector-store integration or provider cost is claimed.",
    },
    "MS-073": {
        "name": "Personalized search",
        "claim": "no-personalized-ranking-claim",
        "note": "No userContext/personalize ranking or external key dependency is claimed.",
    },
    "MS-079": {
        "name": "Multimodal and image search",
        "claim": "no-image-search-claim",
        "note": "No multimodal embedder or image fragment search is claimed.",
    },
    "MS-081": {
        "name": "TLS, HTTP/2 and SSL certificates",
        "claim": "no-engine-certificate-claim",
        "note": "No engine SSL certificate/key options or HTTP/2 transport claim is made.",
    },
    "MS-082": {
        "name": "Telemetry opt-out",
        "claim": "no-engine-telemetry-optout-claim",
        "note": "No MEILI_NO_ANALYTICS engine telemetry opt-out is claimed.",
    },
    "MS-094": {
        "name": "Meilisearch Importer CLI",
        "claim": "no-bulk-import-claim",
        "note": "No bulk CSV/NDJSON import tool or CLI-driven import is claimed.",
    },
    "MS-100": {
        "name": "Vendored async-openai external crates",
        "claim": "no-third-party-crate-copy-claim",
        "note": "No external-crates/async-openai fork or macro crate is copied into NOVARA.",
    },
    "MS-102": {
        "name": "Meili CLI",
        "claim": "no-cli-driven-search-claim",
        "note": "No meili command-line search/task/settings tool is claimed.",
    },
}


class ClaimBoundaryOut(BaseModel):
    row_id: str
    name: str
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
        claim=spec["claim"],
        notice=NOTICE_TEXT,
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=NO_DEFAULT_NOTE + " " + spec["note"],
    )


@router.get("", response_model=list[ClaimBoundaryOut])
def list_meilisearch_claim_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[ClaimBoundaryOut]:
    """List the immutable no-unverified-claim boundaries for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=ClaimBoundaryOut)
def get_meilisearch_claim_boundary(
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
            detail="Meilisearch claim boundary not found",
        )
    return _out(row_id, spec)
