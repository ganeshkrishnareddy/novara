"""Pinned, MIT-licensed Marketing Skills content with runtime integrity checks.

This module does not interpret, execute or evaluate the vendored skills. It
serves them as attributed reference content on NOVARA's one workspace-scoped,
permissioned API surface. Every request re-validates the pinned bundle:
the manifest's own SHA-256 is anchored in this file, and every listed file's
SHA-256, byte length and upstream Git blob SHA are recomputed on load.

The upstream `evals/` files are bundled for provenance only. Upstream evals spend
paid model requests and are never run here. Upstream scripts (only the
conversion-tracking skill has them) are never executed either.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..permissions import CONTACT_READ

PINNED_COMMIT = "5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1"
PLUGIN_VERSION = "2.14.25"
LICENSE_SPDX = "MIT"
FETCHED_ON = "2026-11-23"
UPSTREAM_REPOSITORY = "https://github.com/coreyhaines31/marketingskills"

# Anchor for the manifest itself. Without this, an edited manifest could simply
# rewrite the SHA-256 values of the files it describes and hide a tampered copy.
EXPECTED_MANIFEST_SHA256 = "50592552106d00ae88e81dab91fe63173f272f0387d30d89602b81536e3293c4"

BUNDLE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vendor"
    / "marketingskills"
    / PLUGIN_VERSION
)

INTEGRITY_NOTE = (
    "Vendored reference content at a pinned MIT-licensed upstream commit. "
    "NOVARA does not execute skills, run upstream evals or spend model requests here."
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/skills",
    tags=["marketing-skills"],
)


class BundleIntegrityError(RuntimeError):
    """Raised when the pinned bundle or its manifest fails verification."""


@dataclass(frozen=True)
class VerifiedFile:
    path: str
    sha256: str
    bytes: int
    upstream_blob_sha: str


@dataclass(frozen=True)
class VerifiedSkill:
    row_id: str
    name: str
    version: str
    description: str
    skill_md: str
    skill_path: str
    files: tuple[VerifiedFile, ...]


@dataclass(frozen=True)
class VerifiedBundle:
    root: Path
    repository: str
    pinned_commit: str
    plugin_version: str
    fetched_on: str
    license_spdx: str
    license_file: VerifiedFile
    manifest_sha256: str
    skills: tuple[VerifiedSkill, ...]
    file_count: int
    vendored_bytes: int


class FileOut(BaseModel):
    path: str
    sha256: str
    bytes: int
    upstream_blob_sha: str


class SkillSummaryOut(BaseModel):
    row_id: str
    name: str
    version: str
    description: str
    file_count: int


class ProvenanceOut(BaseModel):
    repository: str
    pinned_commit: str
    plugin_version: str
    fetched_on: str
    license_spdx: str
    license_file: str
    license_sha256: str
    manifest_sha256: str
    verified: bool
    checked_files: int
    vendored_bytes: int
    skill_count: int
    note: str


class SkillOut(BaseModel):
    row_id: str
    name: str
    version: str
    description: str
    skill_path: str
    skill_md: str
    files: list[FileOut]
    provenance: ProvenanceOut


class SkillsListOut(BaseModel):
    skills: list[SkillSummaryOut]
    provenance: ProvenanceOut


def _digests(path: Path) -> tuple[str, str, int]:
    """Return SHA-256, Git blob SHA-1 and byte length for one file."""
    data = path.read_bytes()
    git_header = f"blob {len(data)}\0".encode("ascii")
    sha1 = hashlib.sha1(git_header + data).hexdigest()
    return hashlib.sha256(data).hexdigest(), sha1, len(data)


def _file_entry(root: Path, entry: dict) -> VerifiedFile:
    relative = entry["path"]
    if not isinstance(relative, str) or relative.startswith("/") or ".." in relative.split("/"):
        raise BundleIntegrityError(f"unsafe manifest path: {relative!r}")
    target = root.joinpath(*relative.split("/"))
    if not target.is_file():
        raise BundleIntegrityError(f"bundled file is missing: {relative}")
    sha256, blob_sha, size = _digests(target)
    if sha256 != entry.get("sha256"):
        raise BundleIntegrityError(f"SHA-256 mismatch: {relative}")
    if size != entry.get("bytes"):
        raise BundleIntegrityError(f"byte length mismatch: {relative}")
    if blob_sha != entry.get("upstream_blob_sha"):
        raise BundleIntegrityError(f"upstream blob SHA mismatch: {relative}")
    return VerifiedFile(
        path=relative,
        sha256=sha256,
        bytes=size,
        upstream_blob_sha=blob_sha,
    )


def verify_bundle(root: Path | str | None = None) -> VerifiedBundle:
    """Verify and describe the pinned bundle. Uncached; safe for tamper tests."""
    root_path = Path(root).resolve() if root is not None else BUNDLE_ROOT.resolve()
    manifest_path = root_path / "MANIFEST.json"
    if not manifest_path.is_file():
        raise BundleIntegrityError("MANIFEST.json is missing")
    raw_manifest = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise BundleIntegrityError(
            f"manifest SHA-256 mismatch: expected {EXPECTED_MANIFEST_SHA256}, got {manifest_sha256}"
        )
    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleIntegrityError(f"manifest is not valid UTF-8 JSON: {exc}") from exc

    upstream = manifest.get("upstream", {})
    expected_upstream = {
        "repository": UPSTREAM_REPOSITORY,
        "pinned_commit": PINNED_COMMIT,
        "plugin_version": PLUGIN_VERSION,
        "fetched_on": FETCHED_ON,
        "license_spdx": LICENSE_SPDX,
    }
    for key, expected in expected_upstream.items():
        if upstream.get(key) != expected:
            raise BundleIntegrityError(f"manifest {key} does not match the pinned bundle")

    license_entry = manifest.get("license", {})
    if license_entry.get("path") != "LICENSE" or license_entry.get("spdx") != LICENSE_SPDX:
        raise BundleIntegrityError("manifest license metadata is invalid")
    verified_license = _file_entry(root_path, license_entry)

    skills: list[VerifiedSkill] = []
    all_paths = {verified_license.path}
    for raw_skill in manifest.get("skills", []):
        name = raw_skill["skill"]
        frontmatter = raw_skill["frontmatter"]
        files = tuple(_file_entry(root_path, entry) for entry in raw_skill["files"])
        if not files:
            raise BundleIntegrityError(f"skill {name} has no bundled files")
        all_paths.update(file.path for file in files)
        skill_rel = f"skills/{name}/SKILL.md"
        skill_file = next((file for file in files if file.path == skill_rel), None)
        if skill_file is None:
            raise BundleIntegrityError(f"skill {name} has no pinned SKILL.md")
        skill_md = (root_path / skill_file.path).read_text(encoding="utf-8")
        if not skill_md.startswith("---\n") or "\n---\n" not in skill_md[4:]:
            raise BundleIntegrityError(f"skill {name} lost its YAML frontmatter")
        if frontmatter.get("name") != name:
            raise BundleIntegrityError(f"skill {name} frontmatter name mismatch")
        if f"version: {frontmatter.get('version')}" not in skill_md:
            raise BundleIntegrityError(f"skill {name} frontmatter version mismatch")
        skills.append(
            VerifiedSkill(
                row_id=raw_skill["row_id"],
                name=name,
                version=frontmatter["version"],
                description=frontmatter["description"],
                skill_md=skill_md,
                skill_path=skill_file.path,
                files=files,
            )
        )

    if len(skills) != 53:
        raise BundleIntegrityError(f"expected 53 pinned skills, found {len(skills)}")

    actual_paths = {
        path.relative_to(root_path).as_posix()
        for path in root_path.rglob("*")
        if path.is_file()
        and (
            path.relative_to(root_path).as_posix().startswith("skills/")
            or path.relative_to(root_path).as_posix() == "LICENSE"
        )
    }
    if actual_paths != all_paths:
        raise BundleIntegrityError(
            f"bundle file set changed: missing={sorted(all_paths - actual_paths)}, "
            f"unexpected={sorted(actual_paths - all_paths)}"
        )
    skill_prefixes = tuple(f"skills/{skill.name}/" for skill in skills)
    if not all(path == "LICENSE" or path.startswith(skill_prefixes) for path in all_paths):
        raise BundleIntegrityError("bundle contains a path outside the pinned skill set")

    declared_count = manifest.get("bundle", {}).get("file_count")
    declared_bytes = manifest.get("bundle", {}).get("vendored_bytes")
    all_files = (verified_license, *(file for skill in skills for file in skill.files))
    total_bytes = sum(file.bytes for file in all_files)
    if declared_count != len(all_paths) or declared_bytes != total_bytes:
        raise BundleIntegrityError("manifest bundle totals do not match the verified files")

    return VerifiedBundle(
        root=root_path,
        repository=UPSTREAM_REPOSITORY,
        pinned_commit=PINNED_COMMIT,
        plugin_version=PLUGIN_VERSION,
        fetched_on=FETCHED_ON,
        license_spdx=LICENSE_SPDX,
        license_file=verified_license,
        manifest_sha256=manifest_sha256,
        skills=tuple(skills),
        file_count=len(all_paths),
        vendored_bytes=total_bytes,
    )


@lru_cache(maxsize=8)
def load_bundle(root: Path | str | None = None) -> VerifiedBundle:
    """Cached view of the verified bundle used by the API endpoints."""
    return verify_bundle(root)


def _provenance(bundle: VerifiedBundle) -> ProvenanceOut:
    return ProvenanceOut(
        repository=bundle.repository,
        pinned_commit=bundle.pinned_commit,
        plugin_version=bundle.plugin_version,
        fetched_on=bundle.fetched_on,
        license_spdx=bundle.license_spdx,
        license_file=bundle.license_file.path,
        license_sha256=bundle.license_file.sha256,
        manifest_sha256=bundle.manifest_sha256,
        verified=True,
        checked_files=bundle.file_count,
        vendored_bytes=bundle.vendored_bytes,
        skill_count=len(bundle.skills),
        note=INTEGRITY_NOTE,
    )


def _bundle_or_503() -> VerifiedBundle:
    try:
        return load_bundle()
    except (BundleIntegrityError, OSError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"vendored marketing skills bundle failed integrity verification: {exc}",
        ) from exc


@router.get("", response_model=SkillsListOut)
def list_bundled_skills(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db=Depends(get_db),
) -> SkillsListOut:
    """List all pinned skills with their exact upstream frontmatter."""
    verify_workspace(principal, workspace_id)
    bundle = _bundle_or_503()
    return SkillsListOut(
        skills=[
            SkillSummaryOut(
                row_id=skill.row_id,
                name=skill.name,
                version=skill.version,
                description=skill.description,
                file_count=len(skill.files),
            )
            for skill in bundle.skills
        ],
        provenance=_provenance(bundle),
    )


@router.get("/provenance", response_model=ProvenanceOut)
def skills_provenance(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db=Depends(get_db),
) -> ProvenanceOut:
    """Pin, license and live hash-verification result for the vendored bundle."""
    verify_workspace(principal, workspace_id)
    return _provenance(_bundle_or_503())


@router.get("/{skill_name}", response_model=SkillOut)
def get_bundled_skill(
    workspace_id: str,
    skill_name: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db=Depends(get_db),
) -> SkillOut:
    """Return one SKILL.md verbatim, with its pinned file hashes and provenance."""
    verify_workspace(principal, workspace_id)
    bundle = _bundle_or_503()
    skill = next((item for item in bundle.skills if item.name == skill_name), None)
    if skill is None:
        raise HTTPException(status_code=404, detail="marketing skill not found in pinned bundle")
    return SkillOut(
        row_id=skill.row_id,
        name=skill.name,
        version=skill.version,
        description=skill.description,
        skill_path=skill.skill_path,
        skill_md=skill.skill_md,
        files=[
            FileOut(
                path=file.path,
                sha256=file.sha256,
                bytes=file.bytes,
                upstream_blob_sha=file.upstream_blob_sha,
            )
            for file in skill.files
        ],
        provenance=_provenance(bundle),
    )
