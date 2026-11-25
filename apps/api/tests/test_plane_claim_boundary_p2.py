"""Plane "no unverified default" boundary acceptance tests.

Named rows: PL-067, PL-109, PL-133, PL-134, PL-151, PL-153, PL-154, PL-156.

Each test proves the row's negative claim with local evidence: no matching
manifest dependency, route, import or precise token in runtime sources, a
preserved Plane AGPL notice, and a read-only workspace-scoped boundary record.
No Plane package, external AI default, object store, desktop/mobile build or
container/Kubernetes capability is installed or claimed.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.plane_claim_boundary import CLAIM_CATALOG, NOTICE_TEXT

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

# This boundary module is itself allowed to name the claims it denies.
BOUNDARY_MODULE = "plane_claim_boundary.py"

# Precise tokens that would indicate the claimed capability is actually present.
# Bare "openai", "desktop", "mobile", "s3", "docker" and "container" are avoided
# because they also occur as unrelated UI labels, analytics device types,
# substring fragments or explanatory text; only capability-specific tokens are used.
FORBIDDEN_TOKENS: dict[str, tuple[str, ...]] = {
    "PL-067": ("openai-sdk", "import openai", "from openai", "openai_api_key", "external_ai_model_default"),
    "PL-109": ("plane edition", "plane_edition", "plane_license", "edition_gate", "plane_community"),
    "PL-133": ("electron", "tauri", "desktop_app", "desktop build"),
    "PL-134": ("mobile_app", "mobile build", "apk", "capacitor"),
    "PL-151": ("minio", "boto3", "object_storage", "remote_storage"),
    "PL-153": ("docker compose", "docker-compose", "docker_compose", "container verification"),
    "PL-154": ("kubernetes", "helm", "kubectl", "k8s"),
    "PL-156": ("@plane/", "@plane", "plane_core", "plane-blocks"),
}


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in Plane claim boundary tests")

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
    owner = bootstrap(client, email="plane-claim@example.com", workspace_name="Plane Claim WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other Plane Claim"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/plane-claim-boundary"


def _assert_notice_preserved() -> None:
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert NOTICE_TEXT in notice
    assert "SPDX-License-Identifier: AGPL-3.0-only" in notice


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
        f"/api/v1/workspaces/{ctx['ws']}/plane-claim-boundary/{row_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 403, cross.text

    missing = client.get(_base(ctx) + "/PL-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_pl067_no_external_ai_model_default(client, db_session, source_text):
    """PL-067: no default install calls an external AI model."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-067", name="Optional OpenAI SDK", claim="no-external-ai-model-default", source_text=source_text)


def test_pl109_no_plane_edition_logic(client, db_session, source_text):
    """PL-109: no Plane edition/licence logic is embedded in NOVARA."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-109", name="Instance edition and license model", claim="no-plane-edition-logic", source_text=source_text)


def test_pl133_no_desktop_build_claim(client, db_session, source_text):
    """PL-133: no NOVARA desktop build is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-133", name="Desktop app", claim="no-desktop-build-claim", source_text=source_text)


def test_pl134_no_mobile_build_claim(client, db_session, source_text):
    """PL-134: no NOVARA mobile build is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-134", name="Mobile app", claim="no-mobile-build-claim", source_text=source_text)


def test_pl151_no_external_object_storage_default(client, db_session, source_text):
    """PL-151: no default install requires external object storage."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-151", name="MinIO/S3 object storage", claim="no-external-object-storage-default", source_text=source_text)


def test_pl153_no_container_verification_claim(client, db_session, source_text):
    """PL-153: no Docker/container deployment verification is asserted."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-153", name="Docker Compose deployment", claim="no-container-verification-claim", source_text=source_text)


def test_pl154_no_kubernetes_helm_claim(client, db_session, source_text):
    """PL-154: no Kubernetes/Helm capability is claimed."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-154", name="Kubernetes/Helm deployment", claim="no-kubernetes-helm-claim", source_text=source_text)


def test_pl156_no_plane_monorepo_package(client, db_session, source_text):
    """PL-156: no @plane/* monorepo package appears in manifests/runtime."""
    ctx = _setup(client)
    _assert_boundary(client, ctx, "PL-156", name="Internal @plane/* monorepo packages", claim="no-plane-monorepo-package", source_text=source_text)
