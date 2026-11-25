"""Clean-room default-dependency boundary (MS-067/097, PL-068/149/150, CW-122, NV-058/059/094).

These rows are negative evidence claims: NOVARA must not install, vendor, or
advertise an unverified SDK, broker, cache connector or framework package as a
default dependency. The module serves a read-only, workspace-scoped catalogue
of those boundaries. It does not import any third-party SDK, create a network
client, or present a mock external result as product output.

There is no database table and no migration. Workspace scope is enforced by
``verify_workspace`` on every route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/dependency-boundary",
    tags=["dependency-boundary"],
)

NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NO_DEFAULT_NOTE = "No default dependency claim; no SDK import, vendored package, external endpoint or unverified result is created by this boundary."

# Values are NOVARA-local boundary descriptors. They record what is explicitly
# NOT part of the default product, not an installed or verified dependency.
BOUNDARY_CATALOG: dict[str, dict[str, str]] = {
    "MS-067": {
        "name": "Official client SDKs",
        "provider": "Meilisearch",
        "boundary": "no-meilisearch-sdk-dependency",
        "notice": "Meilisearch core — Meili SAS",
        "note": "Search results come from local NOVARA data; no Meilisearch SDK import or mock result is presented as search output.",
    },
    "MS-097": {
        "name": "LMDB storage connector and OpenLDAP license",
        "provider": "Meilisearch",
        "boundary": "no-lmdb-connector",
        "notice": "OpenLDAP license text must be preserved for the heed/LMDB connector",
        "note": "No LMDB file, connector or redistributed OpenLDAP notice obligation is created by this inventory row.",
    },
    "PL-068": {
        "name": "Slack SDK dependency",
        "provider": "Plane",
        "boundary": "no-slack-sdk-requirement",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "note": "The default install has no Slack SDK requirement and no outbound Slack call.",
    },
    "PL-149": {
        "name": "Redis cache and Channels backend",
        "provider": "Plane",
        "boundary": "no-unverified-redis-dependency",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "note": "No Redis service, cache connector or Channels backend is claimed as verified.",
    },
    "PL-150": {
        "name": "RabbitMQ message broker",
        "provider": "Plane",
        "boundary": "no-unverified-broker-dependency",
        "notice": "Plane — Plane Software, Inc. and contributors",
        "note": "No RabbitMQ broker dependency or verified broker claim is created by this row.",
    },
    "CW-122": {
        "name": "@chatwoot/* utility packages",
        "provider": "Chatwoot",
        "boundary": "no-unverified-chatwoot-package",
        "notice": "Chatwoot (community) — Chatwoot Inc.",
        "note": "No @chatwoot/* package is vendored or declared without a verified licence notice.",
    },
    "NV-058": {
        "name": "Server SDKs (@novu/api, Python, Go, PHP, .NET, Java)",
        "provider": "Novu",
        "boundary": "no-fabricated-server-sdk",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No Novu server SDK or external API endpoint is documented as verified or installed by default.",
    },
    "NV-059": {
        "name": "Client SDKs (@novu/js, @novu/react, @novu/react-native)",
        "provider": "Novu",
        "boundary": "no-verified-mobile-sdk-claim",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No mobile or external Novu SDK is claimed as verified in the default install.",
    },
    "NV-094": {
        "name": "@novu/nextjs SDK",
        "provider": "Novu",
        "boundary": "no-unverified-nextjs-sdk",
        "notice": "Novu (community) — Noti-fire Apps Ltd.",
        "note": "No framework-specific Novu SDK is claimed as verified without a named integration test.",
    },
}


class BoundaryOut(BaseModel):
    row_id: str
    name: str
    provider: str
    boundary: str
    notice: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    notes: str

    model_config = ConfigDict(from_attributes=True)


def _out(row_id: str, spec: dict[str, str]) -> BoundaryOut:
    return BoundaryOut(
        row_id=row_id,
        name=spec["name"],
        provider=spec["provider"],
        boundary=spec["boundary"],
        notice=spec["notice"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=NO_DEFAULT_NOTE + " " + spec["note"],
    )


@router.get("", response_model=list[BoundaryOut])
def list_dependency_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[BoundaryOut]:
    """List the immutable no-default-dependency boundaries for this workspace."""
    verify_workspace(principal, workspace_id)
    return [_out(row_id, spec) for row_id, spec in sorted(BOUNDARY_CATALOG.items())]


@router.get("/{row_id}", response_model=BoundaryOut)
def get_dependency_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> BoundaryOut:
    """Return one boundary, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = BOUNDARY_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dependency boundary not found",
        )
    return _out(row_id, spec)
