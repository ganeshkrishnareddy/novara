"""No-default-dependency boundary acceptance tests.

Named rows: MS-067, MS-097, PL-068, PL-149, PL-150, CW-122, NV-058, NV-059,
NV-094. Each test proves the row's negative claim with local evidence: no active
manifest dependency, no runtime import, no vendored upstream package, preserved
third-party notices, and a read-only workspace-scoped boundary record.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.dependency_boundary import BOUNDARY_CATALOG

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = (
    REPO_ROOT / "apps" / "api" / "pyproject.toml",
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "docker-compose.yml",
)
RUNTIME_SOURCES = (
    REPO_ROOT / "apps" / "web" / "index.html",
    REPO_ROOT / "apps" / "web" / "app.js",
)
VENDOR_ROOTS = (
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "meilisearch",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "plane",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "chatwoot",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "novu",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "lmdb",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "slack",
    REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "rabbitmq",
)
ACTIVE_DEPENDENCY_TOKENS = (
    "slack", "redis", "rabbit", "@novu", "meilisearch", "lmdb", "@chatwoot",
)


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in dependency boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, email="dep-boundary@example.com", workspace_name="DEP WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other DEP"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/dependency-boundary"


def _active_manifest_text() -> str:
    lines: list[str] = []
    for manifest in MANIFESTS:
        assert manifest.is_file(), f"missing manifest: {manifest}"
        for raw in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped.lower())
    return "\n".join(lines)


def _assert_no_default_dependencies() -> None:
    active = _active_manifest_text()
    for token in ACTIVE_DEPENDENCY_TOKENS:
        assert token not in active, f"active dependency token {token!r} found in manifests"
    for source in RUNTIME_SOURCES:
        assert source.is_file(), f"missing runtime source: {source}"
        text = source.read_text(encoding="utf-8", errors="replace").lower()
        for token in ("slack", "redis", "rabbitmq", "@novu", "meilisearch", "lmdb", "@chatwoot"):
            assert f"import {token}" not in text
            assert f"from {token}" not in text
            assert f"require('{token}" not in text
            assert f'require("{token}' not in text
    for root in VENDOR_ROOTS:
        assert not root.exists(), f"unverified package vendored at {root}"


def _assert_notices_preserved() -> None:
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8", errors="replace")
    assert "Meilisearch core — Meili SAS" in notice
    assert "OpenLDAP license text must be preserved for the `heed`/LMDB connector" in notice
    assert "Plane — Plane Software, Inc. and contributors" in notice
    assert "Chatwoot (community) — Chatwoot Inc." in notice
    assert "Novu (community) — Noti-fire Apps Ltd." in notice


def _assert_search_is_local() -> None:
    source = (
        REPO_ROOT / "apps" / "api" / "novara_core" / "modules" / "search.py"
    ).read_text(encoding="utf-8", errors="replace").lower()
    assert "meilisearch" not in source
    assert "mock" not in source


def _assert_boundary(client, ctx, row_id: str, *, name: str, provider: str, boundary: str) -> None:
    listed = client.get(_base(ctx), headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == len(BOUNDARY_CATALOG)

    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_id"] == row_id
    assert data["name"] == name
    assert data["provider"] == provider
    assert data["boundary"] == boundary
    assert data["notice"] == BOUNDARY_CATALOG[row_id]["notice"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "No default dependency claim" in data["notes"]

    _assert_no_default_dependencies()
    _assert_notices_preserved()

    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/dependency-boundary/{row_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 403, cross.text

    missing = client.get(_base(ctx) + "/XX-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_ms067_official_client_sdk_dependency_boundary(client, db_session):
    """MS-067: no Meilisearch SDK dependency or mock search output is claimed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "MS-067", name="Official client SDKs",
        provider="Meilisearch", boundary="no-meilisearch-sdk-dependency",
    )
    _assert_search_is_local()


def test_ms097_lmdb_connector_not_created(client, db_session):
    """MS-097: no LMDB connector or extra notice obligation is created."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "MS-097", name="LMDB storage connector and OpenLDAP license",
        provider="Meilisearch", boundary="no-lmdb-connector",
    )


def test_pl068_no_slack_sdk_requirement(client, db_session):
    """PL-068: the default install has no Slack SDK requirement."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "PL-068", name="Slack SDK dependency",
        provider="Plane", boundary="no-slack-sdk-requirement",
    )


def test_pl149_no_unverified_redis_dependency(client, db_session):
    """PL-149: no unverified Redis dependency is claimed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "PL-149", name="Redis cache and Channels backend",
        provider="Plane", boundary="no-unverified-redis-dependency",
    )


def test_pl150_no_unverified_broker_dependency(client, db_session):
    """PL-150: no unverified RabbitMQ broker dependency is claimed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "PL-150", name="RabbitMQ message broker",
        provider="Plane", boundary="no-unverified-broker-dependency",
    )


def test_cw122_no_unverified_chatwoot_packages(client, db_session):
    """CW-122: no @chatwoot/* package is vendored without notice review."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "CW-122", name="@chatwoot/* utility packages",
        provider="Chatwoot", boundary="no-unverified-chatwoot-package",
    )


def test_nv058_no_fabricated_server_sdk(client, db_session):
    """NV-058: no fabricated Novu server SDK or endpoint is documented."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "NV-058", name="Server SDKs (@novu/api, Python, Go, PHP, .NET, Java)",
        provider="Novu", boundary="no-fabricated-server-sdk",
    )


def test_nv059_no_verified_mobile_sdk_claim(client, db_session):
    """NV-059: no mobile Novu SDK is claimed as verified."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "NV-059", name="Client SDKs (@novu/js, @novu/react, @novu/react-native)",
        provider="Novu", boundary="no-verified-mobile-sdk-claim",
    )


def test_nv094_no_unverified_nextjs_sdk(client, db_session):
    """NV-094: no framework-specific Novu SDK is claimed as verified."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "NV-094", name="@novu/nextjs SDK",
        provider="Novu", boundary="no-unverified-nextjs-sdk",
    )
