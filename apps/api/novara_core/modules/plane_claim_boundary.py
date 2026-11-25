"""Clean-room Plane "no unverified default" boundary (PL-067..PL-156).

These rows are negative evidence claims: NOVARA must not claim a default external
AI model call, embedded Plane edition/licence logic, a desktop or mobile build,
required external object storage, verified Docker/container deployment,
Kubernetes/Helm capability, or an internal @plane/* monorepo package. This
module serves a read-only, workspace-scoped catalogue of those boundaries. It
does not install a Plane package, read a Plane edition, build an app, require an
external object store or assert a deployment verification.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/plane-claim-boundary",
    tags=["plane-claim-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NOTICE_TEXT = "Plane — Plane Software, Inc. and contributors"
NO_DEFAULT_NOTE = (
    "Negative evidence boundary: NOVARA makes no such claim; no dependency, "
    "external endpoint, build artifact or unverified deployment is created here."
)

# Values are NOVARA-local boundary descriptors. They record what is explicitly
# NOT claimed by the default product, not an installed or verified dependency.
CLAIM_CATALOG: dict[str, dict[str, str]] = {
    "PL-067": {
        "name": "Optional OpenAI SDK",
        "claim": "no-external-ai-model-default",
        "note": "No default install calls an external AI model; the local agent provider is the only default.",
    },
    "PL-109": {
        "name": "Instance edition and license model",
        "claim": "no-plane-edition-logic",
        "note": "No Plane edition logic, licence tier or edition gate is embedded in NOVARA.",
    },
    "PL-133": {
        "name": "Desktop app",
        "claim": "no-desktop-build-claim",
        "note": "No NOVARA desktop build, installer or electron/tauri shell is claimed.",
    },
    "PL-134": {
        "name": "Mobile app",
        "claim": "no-mobile-build-claim",
        "note": "No NOVARA mobile build, APK or IPA is claimed.",
    },
    "PL-151": {
        "name": "MinIO/S3 object storage",
        "claim": "no-external-object-storage-default",
        "note": "No default install requires external object storage; local file storage is used.",
    },
    "PL-153": {
        "name": "Docker Compose deployment",
        "claim": "no-container-verification-claim",
        "note": "No Docker/container deployment verification is asserted in the acceptance evidence.",
    },
    "PL-154": {
        "name": "Kubernetes/Helm deployment",
        "claim": "no-kubernetes-helm-claim",
        "note": "No Kubernetes, Helm or kubectl capability is claimed.",
    },
    "PL-156": {
        "name": "Internal @plane/* monorepo packages",
        "claim": "no-plane-monorepo-package",
        "note": "No @plane/* package appears in NOVARA manifests or runtime imports.",
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
def list_plane_claim_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[ClaimBoundaryOut]:
    """List the immutable no-unverified-default boundaries for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(CLAIM_CATALOG.items())]


@router.get("/{row_id}", response_model=ClaimBoundaryOut)
def get_plane_claim_boundary(
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
            detail="Plane claim boundary not found",
        )
    return _out(row_id, spec)
