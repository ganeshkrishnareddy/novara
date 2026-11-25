"""Named acceptance tests for the originally vendored Marketing Skills P1 rows.

Every test drives the real FastAPI app through the ``client`` fixture: real
bootstrap identity, real bearer sessions, real CONTACT_READ enforcement, real
``verify_workspace`` isolation and the real OpenAPI document. The vendored
content is served, never executed; upstream evals and scripts are never run.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from novara_core.modules import marketing_skills as skills_module

from .conftest import auth, bootstrap

BUNDLE_ROOT = skills_module.BUNDLE_ROOT
MANIFEST = json.loads((BUNDLE_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
ROWS = {skill["row_id"]: skill for skill in MANIFEST["skills"]}

OPENAPI_PATHS = (
    "/api/v1/workspaces/{workspace_id}/skills",
    "/api/v1/workspaces/{workspace_id}/skills/provenance",
    "/api/v1/workspaces/{workspace_id}/skills/{skill_name}",
)


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _assert_pinned_row(client, row_id: str, skill_name: str) -> None:
    """Shared acceptance path for one MK row; called only by named tests."""
    tokens = bootstrap(client, "Marketing", f"{skill_name}-owner@example.com")
    workspace_id = tokens["workspace_id"]
    headers = auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{workspace_id}/skills"

    # Real auth and CONTACT_READ, not a client-supplied identity.
    assert client.get(base).status_code == 401
    assert client.get(base + "/provenance").status_code == 401
    assert client.get(f"{base}/{skill_name}").status_code == 401

    listed = client.get(base, headers=headers)
    assert listed.status_code == 200, listed.text
    listing = listed.json()
    assert len(listing["skills"]) == len(MANIFEST["skills"])
    skill_row = ROWS[row_id]
    summary = next(item for item in listing["skills"] if item["row_id"] == row_id)
    assert summary["name"] == skill_name
    assert summary["version"] == skill_row["frontmatter"]["version"]
    assert summary["description"] == skill_row["frontmatter"]["description"]
    assert summary["file_count"] == skill_row["file_count"]

    health = client.get(base + "/provenance", headers=headers)
    assert health.status_code == 200, health.text
    provenance = health.json()
    assert provenance["verified"] is True
    assert provenance["pinned_commit"] == skills_module.PINNED_COMMIT
    assert provenance["plugin_version"] == "2.14.25"
    assert provenance["license_spdx"] == "MIT"
    assert provenance["manifest_sha256"] == skills_module.EXPECTED_MANIFEST_SHA256
    assert provenance["checked_files"] == MANIFEST["bundle"]["file_count"]
    assert provenance["vendored_bytes"] == MANIFEST["bundle"]["vendored_bytes"]
    assert "does not execute skills" in provenance["note"]
    assert "upstream evals" in provenance["note"].lower()

    detail = client.get(f"{base}/{skill_name}", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()

    verbatim_path = BUNDLE_ROOT / f"skills/{skill_name}/SKILL.md"
    verbatim = verbatim_path.read_text(encoding="utf-8")
    assert payload["skill_md"] == verbatim
    assert payload["skill_path"] == f"skills/{skill_name}/SKILL.md"
    assert verbatim.startswith("---\n")
    frontmatter = verbatim.split("---", 2)[1]
    assert f"name: {skill_name}" in frontmatter
    assert f"version: {skill_row['frontmatter']['version']}" in frontmatter
    assert payload["version"] == skill_row["frontmatter"]["version"]
    assert payload["description"] == skill_row["frontmatter"]["description"]
    assert payload["provenance"]["verified"] is True

    # Every file listed for this skill verifies against its pinned SHA-256,
    # byte length and upstream Git blob SHA (not merely a 200 response).
    expected_files = skill_row["files"]
    assert [entry["path"] for entry in payload["files"]] == [
        entry["path"] for entry in expected_files
    ]
    for declared, served in zip(expected_files, payload["files"]):
        path = BUNDLE_ROOT / declared["path"]
        data = path.read_bytes()
        assert served["sha256"] == declared["sha256"]
        assert served["sha256"] == hashlib.sha256(data).hexdigest()
        assert served["bytes"] == declared["bytes"] == len(data)
        assert served["upstream_blob_sha"] == declared["upstream_blob_sha"]
        assert served["upstream_blob_sha"] == _blob_sha(data)

    # The endpoints are documented on the one native API surface.
    schema = client.get("/openapi.json").json()
    for path in OPENAPI_PATHS:
        assert path in schema["paths"]

    # A valid principal for a different workspace is denied on all three routes.
    foreign = client.post("/api/v1/workspaces", headers=headers, json={"name": "Foreign"})
    assert foreign.status_code == 200, foreign.text
    foreign_headers = auth(foreign.json()["access_token"])
    assert foreign.json()["workspace_id"] != workspace_id
    for path in (base, base + "/provenance", f"{base}/{skill_name}"):
        denied = client.get(path, headers=foreign_headers)
        assert denied.status_code == 403, denied.text


def test_mk001_ab_testing_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-001", "ab-testing")


def test_mk005_analytics_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-005", "analytics")


def test_mk015_conversion_tracking_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-015", "conversion-tracking")


def test_mk017_copywriting_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-017", "copywriting")


def test_mk018_cro_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-018", "cro")


def test_mk039_product_marketing_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-039", "product-marketing")


def test_mk048_seo_audit_skill_is_pinned_verified_and_isolated(client):
    _assert_pinned_row(client, "MK-048", "seo-audit")


def test_manifest_tamper_is_detected(client, tmp_path, monkeypatch):
    """A corrupted copy is refused by the loader and by the real API."""
    corrupted = tmp_path / "tampered-bundle"
    shutil.copytree(BUNDLE_ROOT, corrupted)
    skill_file = corrupted / "skills" / "conversion-tracking" / "SKILL.md"
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8") + "\nTAMPERED CONTENT\n",
        encoding="utf-8",
    )
    with pytest.raises(skills_module.BundleIntegrityError, match="SHA-256 mismatch"):
        skills_module.verify_bundle(corrupted)

    # The real bundle is untouched: it still verifies after the corrupted copy.
    assert skills_module.verify_bundle(skills_module.BUNDLE_ROOT).file_count == MANIFEST["bundle"]["file_count"]

    # Serving from the corrupted copy yields a real 503 from the FastAPI app.
    monkeypatch.setattr(skills_module, "BUNDLE_ROOT", corrupted)
    skills_module.load_bundle.cache_clear()
    try:
        tokens = bootstrap(client, "Tamper", "tamper-owner@example.com")
        headers = auth(tokens["access_token"])
        base = f"/api/v1/workspaces/{tokens['workspace_id']}/skills"
        response = client.get(base, headers=headers)
        assert response.status_code == 503, response.text
        assert "integrity verification" in response.json()["detail"]
    finally:
        skills_module.load_bundle.cache_clear()

    # A rewritten manifest cannot re-anchor its own hashes either.
    manifest_path = corrupted / "MANIFEST.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["upstream"]["plugin_version"] = "9.9.9"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(skills_module.BundleIntegrityError, match="manifest SHA-256 mismatch"):
        skills_module.verify_bundle(corrupted)
