"""Clean-room Formbricks SDK replacement-boundary acceptance tests.

Named rows: FB-132, FB-133, FB-134, FB-135, FB-136, FB-137, FB-138, FB-139,
FB-140, FB-141, FB-142. Each test proves the advertised MIT SDK package path
has a documented NOVARA-local replacement, preserved Formbricks GmbH notice and
no default dependency, source copy or external call. No Formbricks SDK package
is installed or imported.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from novara_core.modules.formbricks_sdk_boundary import ATTRIBUTION, SDK_CATALOG, notice_text

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
FORBIDDEN_MANIFEST_TOKENS = ("@formbricks", "formbricks-sdk", "formbricks")


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room Formbricks boundary tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, email="fb-sdk-owner@example.com", workspace_name="FBSDK WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other FBSDK"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/formbricks-sdk-boundary"


def _assert_no_default_dependency() -> None:
    for manifest in DEPENDENCY_MANIFESTS:
        assert manifest.is_file(), f"missing manifest: {manifest}"
        text = manifest.read_text(encoding="utf-8", errors="replace").lower()
        for token in FORBIDDEN_MANIFEST_TOKENS:
            assert token not in text, f"{token} appears in {manifest.name}"
    for source in RUNTIME_SOURCES:
        assert source.is_file(), f"missing runtime source: {source}"
        text = source.read_text(encoding="utf-8", errors="replace").lower()
        assert "import formbricks" not in text
        assert "from formbricks" not in text
        assert "require('formbricks')" not in text
        assert 'require("formbricks")' not in text
        assert "require('@formbricks/" not in text
        assert 'require("@formbricks/' not in text
    module_source = (
        REPO_ROOT / "apps" / "api" / "novara_core" / "modules" / "formbricks_sdk_boundary.py"
    ).read_text(encoding="utf-8", errors="replace")
    lowered = module_source.lower()
    assert "import formbricks" not in lowered
    assert "from formbricks" not in lowered
    assert "@formbricks/" not in lowered
    assert "agpl" not in lowered
    assert "enterprise" not in lowered
    vendored = REPO_ROOT / "apps" / "api" / "novara_core" / "skills" / "vendor" / "formbricks"
    assert not vendored.exists(), "Formbricks upstream source must not be vendored"


def _assert_notice_preserved() -> None:
    notice = notice_text(REPO_ROOT)
    assert "Formbricks SDK packages — Formbricks GmbH (MIT, per package `package.json`)" in notice
    assert "Required notice: the MIT copyright notice and permission notice" in notice
    assert "Status: license-text review complete" in notice
    assert "No third-party code has been copied" in notice


def _assert_boundary(client, ctx, row_id: str, *, name: str, source_path: str, replacement: str) -> None:
    listed = client.get(_base(ctx), headers=ctx["h"])
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == len(SDK_CATALOG)

    response = client.get(_base(ctx) + f"/{row_id}", headers=ctx["h"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_id"] == row_id
    assert data["name"] == name
    assert data["source_path"] == source_path
    assert data["replacement"] == replacement
    assert data["replacement"].startswith("novara_")
    assert data["attribution"] == ATTRIBUTION
    assert data["docs_reference"] == SDK_CATALOG[row_id]["docs_reference"]
    assert data["notice_file"] == "THIRD_PARTY_NOTICES.md"
    assert data["dependency_declared"] is False
    assert data["external_endpoint"] is None
    assert "clean-room replacement" in data["notes"]

    _assert_no_default_dependency()
    _assert_notice_preserved()

    cross = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/formbricks-sdk-boundary/{row_id}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 403, cross.text

    missing = client.get(_base(ctx) + "/FB-999", headers=ctx["h"])
    assert missing.status_code == 404, missing.text


def test_fb132_javascript_client_sdk_cleanroom_boundary(client, db_session):
    """FB-132: the JavaScript client SDK has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-132", name="JavaScript client SDK (packages/js)",
        source_path="packages/js", replacement="novara_survey_client_contract",
    )


def test_fb133_android_sdk_cleanroom_boundary(client, db_session):
    """FB-133: the Android SDK has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-133", name="Android SDK (packages/android)",
        source_path="packages/android", replacement="novara_survey_android_contract",
    )


def test_fb134_ios_sdk_cleanroom_boundary(client, db_session):
    """FB-134: the iOS SDK has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-134", name="iOS SDK (packages/ios)",
        source_path="packages/ios", replacement="novara_survey_ios_contract",
    )


def test_fb135_api_package_cleanroom_boundary(client, db_session):
    """FB-135: the API package has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-135", name="API package (packages/api)",
        source_path="packages/api", replacement="novara_survey_api_contract",
    )


def test_fb136_surveys_package_cleanroom_boundary(client, db_session):
    """FB-136: the surveys package has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-136", name="Surveys package (packages/surveys)",
        source_path="packages/surveys", replacement="novara_survey_core_contract",
    )


def test_fb137_survey_ui_package_cleanroom_boundary(client, db_session):
    """FB-137: the survey UI package has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-137", name="Survey UI package (packages/survey-ui)",
        source_path="packages/survey-ui", replacement="novara_survey_ui_contract",
    )


def test_fb138_js_core_mit_package_cleanroom_boundary(client, db_session):
    """FB-138: js-core has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-138", name="js-core MIT package",
        source_path="js-core", replacement="novara_survey_js_core_contract",
    )


def test_fb139_i18n_utils_mit_package_cleanroom_boundary(client, db_session):
    """FB-139: i18n-utils has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-139", name="i18n-utils MIT package",
        source_path="i18n-utils", replacement="novara_survey_i18n_contract",
    )


def test_fb140_logger_mit_package_cleanroom_boundary(client, db_session):
    """FB-140: logger has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-140", name="logger MIT package",
        source_path="logger", replacement="novara_survey_logger_contract",
    )


def test_fb141_vite_plugins_mit_package_cleanroom_boundary(client, db_session):
    """FB-141: vite-plugins has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-141", name="vite-plugins MIT package",
        source_path="vite-plugins", replacement="novara_survey_build_contract",
    )


def test_fb142_mobile_sdks_cleanroom_boundary(client, db_session):
    """FB-142: the mobile SDK set has a documented clean-room contract."""
    ctx = _setup(client)
    _assert_boundary(
        client, ctx, "FB-142", name="Mobile SDKs (React Native, iOS, Android, Flutter)",
        source_path="mobile-sdks", replacement="novara_survey_mobile_contract",
    )
