"""Meilisearch "no unverified claim" boundary acceptance tests.

Named rows: MS-052, MS-054, MS-060, MS-066, MS-068, MS-069, MS-070, MS-071,
MS-072, MS-073, MS-079, MS-081, MS-082, MS-094, MS-100, MS-102.

Each test proves the row's negative claim with local evidence: no active
manifest dependency, no matching route/import/token in runtime sources, no
vendored crate, preserved Meilisearch MIT notice, and a read-only
workspace-scoped boundary record. No Meilisearch SDK is installed or imported.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.meilisearch_claim_boundary import CLAIM_CATALOG, NOTICE_TEXT

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MODULES_ROOT = API_ROOT / "novara_core" / "modules"
MANIFESTS = (
    API_ROOT / "pyproject.toml",
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "docker-compose.yml",
)
WEB_SOURCES = (
    REPO_ROOT / "apps" / "web" / "index.html",
    REPO_ROOT / "apps" / "web" / "app.js",
)
VENDOR_ROOT = API_ROOT / "novara_core" / "skills" / "vendor"

# This boundary module is itself allowed to name the claims it denies.
BOUNDARY_MODULE = "meilisearch_claim_boundary.py"

# Precise tokens that would indicate the claimed capability is actually present.
FORBIDDEN_TOKENS: dict[str, tuple[str, ...]] = {
    "MS-052": ("MEILI_TASK_WEBHOOK_URL", "meili_task_webhook", "task_webhook"),
    "MS-054": ("REMOTE_MEILI", "MEILI_HOST", "export_to_meilisearch", "remote_meilisearch"),
    "MS-060": ("prometheus", "prometheus_client", "MEILI_METRICS"),
    "MS-066": ("document_level_rbac", "tenant_token", "foreign_filter_join"),
    "MS-068": ("laravel_scout", "rails_sync", "strapi", "firebase_sync", "symfony_meilisearch_connector"),
    "MS-069": ("/mcp", "mcp_server", "mcp_search_tool"),
    "MS-070": ("/chats", "chat_completion", "openai_compatible_stream"),
    "MS-071": ("source_citation", "source_document", "agentic_guardrail"),
    "MS-072": ("langchain", "vector_store", "vectorstore"),
    "MS-073": ("userContext", "cohere", "personalized_search"),
    "MS-079": ("multimodal", "image_search", "media_embedder"),
    "MS-081": ("ssl_cert", "http2", "tls_certificate", "MEILI_SSL"),
    "MS-082": ("MEILI_NO_ANALYTICS", "telemetry_optout"),
    "MS-094": ("meili_importer", "bulk_import", "ndjson_import"),
    "MS-100": ("async-openai", "external-crates", "async_openai"),
    "MS-102": ("meili_cli", "MEILI_CLI", "cli_driven_search"),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in Meilisearch claim boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


@pytest.fixture(scope="module")
def source_text() -> str:
    """Active manifest lines + all runtime sources, lowercased for token scans."""
    parts: list[str] = []
    for manifest in MANIFESTS:
        assert manifest.is_file(), f"missing manifest: {manifest}"
        for raw in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#"):
                parts.append(stripped.lower())
    for source in MODULES_ROOT.rglob("*.py"):
        if source.name == BOUNDARY_MODULE:
            continue
        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())
    for source in WEB_SOURCES:
        assert source.is_file(), f"missing runtime source: {source}"
        parts.append(source.read_text(encoding="utf-8", errors="replace").lower())
    return "\n".join(parts)


def _setup(client):
    owner = bootstrap(client, email="ms-claim@example.com", workspace_name="MS Claim WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other MS Claim"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/meilisearch-claim-boundary"


def _assert_notice_preserved() -> None:
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert NOTICE_TEXT in notice


def _assert_boundary(client, ctx, row_id: str, *, name: str, claim: str, source_text: str) -> None:
    listed = client.get(_base(ctx), headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == len(CLAIM_CATALOG)

    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_id"] == row_id
    assert data["name"] == name
    assert data["claim"] == claim
    assert data["notice"] == NOTICE_TEXT
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "Negative evidence boundary" in data["notes"]

    for token in FORBIDDEN_TOKENS[row_id]:
        assert token.lower() not in source_text, f"{row_id}: forbidden token {token!r} found in runtime sources"

    _assert_notice_preserved()

    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/meilisearch-claim-boundary/{row_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 403, cross.text

    missing = client.get(_base(ctx) + "/MS-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_ms052_no_webhook_delivery_claim(client, db_session, source_text):
    """MS-052: no task-webhook delivery or callback claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-052", name="Task webhooks", claim="no-webhook-delivery-or-callback-claim", source_text=source_text)


def test_ms054_no_outbound_export_claim(client, db_session, source_text):
    """MS-054: no outbound export to a remote Meilisearch instance is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-054", name="Export to a remote Meilisearch instance", claim="no-outbound-export-claim", source_text=source_text)


def test_ms060_no_metrics_endpoint_claim(client, db_session, source_text):
    """MS-060: no Prometheus metrics endpoint is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-060", name="Prometheus metrics endpoint", claim="no-metrics-endpoint-claim", source_text=source_text)


def test_ms066_no_document_level_rbac_claim(client, db_session, source_text):
    """MS-066: no document-level RBAC with joined role filters is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-066", name="Role-based access control with joins", claim="no-document-level-rbac-claim", source_text=source_text)


def test_ms068_no_framework_connector_claim(client, db_session, source_text):
    """MS-068: no framework/platform connector is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-068", name="Framework and platform connectors", claim="no-framework-connector-claim", source_text=source_text)


def test_ms069_no_mcp_search_tool_claim(client, db_session, source_text):
    """MS-069: no /mcp search tool is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-069", name="MCP server", claim="no-mcp-search-tool-claim", source_text=source_text)


def test_ms070_no_conversational_answer_claim(client, db_session, source_text):
    """MS-070: no conversational answer is claimed as grounded in NOVARA data."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-070", name="Conversational search and Chats API", claim="no-conversational-answer-claim", source_text=source_text)


def test_ms071_no_source_citation_claim(client, db_session, source_text):
    """MS-071: no source citation or agentic guardrail claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-071", name="Agentic search guardrails and source documents", claim="no-source-citation-claim", source_text=source_text)


def test_ms072_no_vector_store_integration_claim(client, db_session, source_text):
    """MS-072: no LangChain vector-store integration is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-072", name="LangChain vector store integration", claim="no-vector-store-integration-claim", source_text=source_text)


def test_ms073_no_personalized_ranking_claim(client, db_session, source_text):
    """MS-073: no personalized ranking claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-073", name="Personalized search", claim="no-personalized-ranking-claim", source_text=source_text)


def test_ms079_no_image_search_claim(client, db_session, source_text):
    """MS-079: no multimodal/image search claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-079", name="Multimodal and image search", claim="no-image-search-claim", source_text=source_text)


def test_ms081_no_engine_certificate_claim(client, db_session, source_text):
    """MS-081: no TLS/SSL certificate or HTTP/2 engine claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-081", name="TLS, HTTP/2 and SSL certificates", claim="no-engine-certificate-claim", source_text=source_text)


def test_ms082_no_engine_telemetry_optout_claim(client, db_session, source_text):
    """MS-082: no engine telemetry opt-out claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-082", name="Telemetry opt-out", claim="no-engine-telemetry-optout-claim", source_text=source_text)


def test_ms094_no_bulk_import_claim(client, db_session, source_text):
    """MS-094: no bulk import/Importer CLI claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-094", name="Meilisearch Importer CLI", claim="no-bulk-import-claim", source_text=source_text)


def test_ms100_no_third_party_crate_copy(client, db_session, source_text):
    """MS-100: no vendored third-party async-openai crate exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-100", name="Vendored async-openai external crates", claim="no-third-party-crate-copy-claim", source_text=source_text)
    assert VENDOR_ROOT.is_dir()
    assert sorted(p.name for p in VENDOR_ROOT.iterdir()) == ["marketingskills"]


def test_ms102_no_cli_driven_search_claim(client, db_session, source_text):
    """MS-102: no CLI-driven search claim exists."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "MS-102", name="Meili CLI", claim="no-cli-driven-search-claim", source_text=source_text)
