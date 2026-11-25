"""Extended clean-room GrowthBook SDK compatibility boundary tests.

Named rows: GB-158, GB-159, GB-160, GB-161, GB-162, GB-163, GB-164, GB-165,
GB-166, GB-167, GB-168, GB-169, GB-170, GB-171, GB-172, GB-173. Each test
proves the advertised SDK/provider path has a discoverable local compatibility
boundary, preserved MIT attribution and no default SDK dependency or outbound
provider call. No GrowthBook SDK package is installed or imported.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.growthbook_sdk_boundary import ATTRIBUTION, SDK_CATALOG, notice_text

from .conftest import auth, bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
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
    owner = bootstrap(client, email="gb-sdk-ext-owner@example.com", workspace_name="GBSDK EXT WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other GBSDK EXT"}
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


def test_gb158_csharp_sdk_boundary_and_attribution(client, db_session):
    """GB-158: the C# SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-158", name="C# SDK", ecosystem="dotnet",
        boundary="dotnet-evaluator-boundary",
    )


def test_gb159_elixir_sdk_boundary_and_attribution(client, db_session):
    """GB-159: the Elixir SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-159", name="Elixir SDK", ecosystem="elixir",
        boundary="local-evaluator-boundary",
    )


def test_gb160_rust_sdk_boundary_and_attribution(client, db_session):
    """GB-160: the Rust SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-160", name="Rust SDK", ecosystem="rust",
        boundary="local-evaluator-boundary",
    )


def test_gb161_kotlin_jvm_sdk_boundary_and_attribution(client, db_session):
    """GB-161: the Kotlin JVM SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-161", name="Kotlin JVM SDK", ecosystem="kotlin-jvm",
        boundary="jvm-evaluator-boundary",
    )


def test_gb162_kotlin_android_sdk_boundary_and_attribution(client, db_session):
    """GB-162: the Kotlin Android SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-162", name="Kotlin Android SDK", ecosystem="kotlin-android",
        boundary="android-evaluator-boundary",
    )


def test_gb163_swift_sdk_boundary_and_attribution(client, db_session):
    """GB-163: the Swift SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-163", name="Swift SDK", ecosystem="swift",
        boundary="apple-evaluator-boundary",
    )


def test_gb164_flutter_sdk_boundary_and_attribution(client, db_session):
    """GB-164: the Flutter SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-164", name="Flutter SDK", ecosystem="flutter",
        boundary="dart-evaluator-boundary",
    )


def test_gb165_react_native_sdk_boundary_and_attribution(client, db_session):
    """GB-165: the React Native SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-165", name="React Native SDK", ecosystem="react-native",
        boundary="react-native-boundary",
    )


def test_gb166_roku_sdk_boundary_and_attribution(client, db_session):
    """GB-166: the Roku SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-166", name="Roku SDK", ecosystem="roku",
        boundary="roku-evaluator-boundary",
    )


def test_gb167_html_script_tag_boundary_and_attribution(client, db_session):
    """GB-167: the HTML script-tag boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-167", name="HTML script tag", ecosystem="html-script",
        boundary="script-tag-boundary",
    )


def test_gb168_openfeature_provider_boundary_and_attribution(client, db_session):
    """GB-168: the OpenFeature provider boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-168", name="OpenFeature provider", ecosystem="openfeature",
        boundary="provider-boundary",
    )


def test_gb169_cloudflare_workers_sdk_boundary_and_attribution(client, db_session):
    """GB-169: the Cloudflare Workers SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-169", name="Cloudflare Workers SDK", ecosystem="cloudflare-workers",
        boundary="edge-boundary",
    )


def test_gb170_fastly_compute_sdk_boundary_and_attribution(client, db_session):
    """GB-170: the Fastly Compute SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-170", name="Fastly Compute SDK", ecosystem="fastly-compute",
        boundary="edge-boundary",
    )


def test_gb171_lambda_edge_sdk_boundary_and_attribution(client, db_session):
    """GB-171: the Lambda@Edge SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-171", name="Lambda@Edge SDK", ecosystem="lambda-edge",
        boundary="edge-boundary",
    )


def test_gb172_vercel_flags_sdk_boundary_and_attribution(client, db_session):
    """GB-172: the Vercel Flags SDK boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-172", name="Vercel Flags SDK", ecosystem="vercel-flags",
        boundary="flags-provider-boundary",
    )


def test_gb173_build_your_own_sdk_spec_boundary_and_attribution(client, db_session):
    """GB-173: the build-your-own SDK spec boundary is discoverable and attributed."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "GB-173", name="Build your own SDK spec", ecosystem="sdk-spec",
        boundary="specification-boundary",
    )
