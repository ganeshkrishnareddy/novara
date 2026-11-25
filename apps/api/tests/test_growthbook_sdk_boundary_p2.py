"""Clean-room GrowthBook SDK compatibility boundary acceptance tests.

Named rows: GB-148, GB-149, GB-150, GB-151, GB-152, GB-153, GB-154, GB-155,
GB-156, GB-157. Each test proves the advertised SDK has a discoverable local
compatibility boundary, preserved MIT attribution and no default SDK dependency
or outbound provider call. No growthbook SDK package is installed or imported.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.growthbook_sdk_boundary import ATTRIBUTION, SDK_CATALOG, notice_text

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
# The web client is plain static JS (no npm manifest). These are the files that
# could actually introduce a default SDK dependency at runtime. Textual
# attribution notes are allowed; import/require statements are not.
DEPENDENCY_MANIFESTS = (
    REPO_ROOT / "apps" / "api" / "pyproject.toml",
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "docker-compose.yml",
)
RUNTIME_SOURCES = (
    REPO_ROOT / "apps" / "web" / "index.html",
    REPO_ROOT / "apps" / "web" / "app.js",
)
FORBIDDEN_PACKAGES = ("growthbook", "growthbook-sdk", "@growthbook")


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room SDK boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, email="gbsdk-owner@example.com", workspace_name="GBSDK WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other GBSDK"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/sdk-boundaries"


def _assert_no_default_dependency() -> None:
    for manifest in DEPENDENCY_MANIFESTS:
        assert manifest.is_file(), f"missing manifest: {manifest}"
        text = manifest.read_text(encoding="utf-8", errors="replace").lower()
        for package in FORBIDDEN_PACKAGES:
            assert package.lower() not in text, f"{package} appears in {manifest.name}"
    for source in RUNTIME_SOURCES:
        assert source.is_file(), f"missing runtime source: {source}"
        text = source.read_text(encoding="utf-8", errors="replace").lower()
        assert "import growthbook" not in text
        assert "require('growthbook')" not in text
        assert 'require("growthbook")' not in text
    module_source = (
        REPO_ROOT / "apps" / "api" / "novara_core" / "modules" / "growthbook_sdk_boundary.py"
    ).read_text(encoding="utf-8", errors="replace")
    lowered = module_source.lower()
    assert "import growthbook" not in lowered
    assert "from growthbook" not in lowered


def _assert_attribution_preserved() -> None:
    notice = notice_text(REPO_ROOT)
    assert "Copyright (c) 2025 GrowthBook, Inc." in notice
    assert "Permission is hereby granted, free of charge" in notice
    assert "The above copyright notice and this permission notice" in notice


def _assert_boundary(client, ctx, sdk_id: str, *, name: str, ecosystem: str, boundary: str) -> None:
    created = client.post(_base(ctx) + "/seed", headers=ctx["h"], json={})
    assert created.status_code == 201, created.text
    assert len(created.json()["created"]) == len(SDK_CATALOG)

    response = client.get(_base(ctx) + f"/{sdk_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["sdk_id"] == sdk_id
    assert data["name"] == name
    assert data["ecosystem"] == ecosystem
    assert data["boundary"] == boundary
    assert data["adapter"] == SDK_CATALOG[sdk_id]["adapter"]
    assert data["adapter"].startswith("novara_")
    assert data["attribution"] == ATTRIBUTION
    assert data["docs_reference"] == SDK_CATALOG[sdk_id]["docs_reference"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["default_dependency"] is False
    assert data["external_endpoint"] is None
    assert "no default SDK dependency" in data["notes"]

    _assert_no_default_dependency()
    _assert_attribution_preserved()

    repeated = client.post(_base(ctx) + "/seed", headers=ctx["h"], json={})
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["created"] == []
    assert repeated.json()["total"] == len(SDK_CATALOG)

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/sdk-boundaries/{sdk_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text


def test_gb148_javascript_sdk_boundary_and_attribution(client, db_session):
    """GB-148: the JavaScript SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-148", name="JavaScript SDK", ecosystem="browser",
        boundary="browser-bridge",
    )


def test_gb149_react_sdk_boundary_and_attribution(client, db_session):
    """GB-149: the React SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-149", name="React SDK", ecosystem="react",
        boundary="react-hook-boundary",
    )


def test_gb150_nextjs_sdk_boundary_and_attribution(client, db_session):
    """GB-150: the Next.js SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-150", name="Next.js SDK", ecosystem="nextjs",
        boundary="server-safe-boundary",
    )


def test_gb151_vue_sdk_boundary_and_attribution(client, db_session):
    """GB-151: the Vue SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-151", name="Vue SDK", ecosystem="vue",
        boundary="vue-composable-boundary",
    )


def test_gb152_nodejs_sdk_boundary_and_attribution(client, db_session):
    """GB-152: the Node.js SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-152", name="Node.js SDK", ecosystem="node",
        boundary="server-bridge",
    )


def test_gb153_python_sdk_boundary_and_attribution(client, db_session):
    """GB-153: the Python SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-153", name="Python SDK", ecosystem="python",
        boundary="local-evaluator-boundary",
    )


def test_gb154_ruby_sdk_boundary_and_attribution(client, db_session):
    """GB-154: the Ruby SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-154", name="Ruby SDK", ecosystem="ruby",
        boundary="local-evaluator-boundary",
    )


def test_gb155_php_sdk_boundary_and_attribution(client, db_session):
    """GB-155: the PHP SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-155", name="PHP SDK", ecosystem="php",
        boundary="local-evaluator-boundary",
    )


def test_gb156_java_sdk_boundary_and_attribution(client, db_session):
    """GB-156: the Java SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-156", name="Java SDK", ecosystem="java",
        boundary="jvm-evaluator-boundary",
    )


def test_gb157_go_sdk_boundary_and_attribution(client, db_session):
    """GB-157: the Go SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-157", name="Go SDK", ecosystem="go",
        boundary="local-evaluator-boundary",
    )
