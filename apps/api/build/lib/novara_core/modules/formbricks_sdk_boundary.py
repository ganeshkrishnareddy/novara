"""Clean-room Formbricks SDK compatibility boundary (FB-132..FB-142).

The Formbricks SDK packages are MIT-licensed. NOVARA does not install them,
copy their source, call a Formbricks service or present a mock as survey output.
Instead it documents and serves a workspace-scoped replacement boundary: each
row names the advertised package path, the NOVARA-local replacement contract,
the public documentation reference, the preserved MIT notice and an explicit
marker that no SDK dependency or external endpoint is part of the default
product.

There is no database table and no migration. The catalogue is immutable,
permissioned through the shared workspace dependency, and identical for every
workspace; the workspace scope is enforced by ``verify_workspace`` on each
route.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import Principal, require, verify_workspace
from ..permissions import EVENT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/formbricks-sdk-boundary",
    tags=["formbricks-sdk-boundary"],
)

ATTRIBUTION = "Formbricks GmbH — MIT SDK-package notice preserved in THIRD_PARTY_NOTICES.md"
NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NO_DEFAULT_NOTE = "Documented clean-room replacement; no Formbricks SDK dependency, source copy or external call."

# Values are NOVARA-local replacement contracts derived from the public package
# paths in the feature catalogue. No upstream source, package name import or
# hosted endpoint is reproduced.
SDK_CATALOG: dict[str, dict[str, str]] = {
    "FB-132": {
        "name": "JavaScript client SDK (packages/js)",
        "source_path": "packages/js",
        "replacement": "novara_survey_client_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-133": {
        "name": "Android SDK (packages/android)",
        "source_path": "packages/android",
        "replacement": "novara_survey_android_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-134": {
        "name": "iOS SDK (packages/ios)",
        "source_path": "packages/ios",
        "replacement": "novara_survey_ios_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-135": {
        "name": "API package (packages/api)",
        "source_path": "packages/api",
        "replacement": "novara_survey_api_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-136": {
        "name": "Surveys package (packages/surveys)",
        "source_path": "packages/surveys",
        "replacement": "novara_survey_core_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-137": {
        "name": "Survey UI package (packages/survey-ui)",
        "source_path": "packages/survey-ui",
        "replacement": "novara_survey_ui_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-138": {
        "name": "js-core MIT package",
        "source_path": "js-core",
        "replacement": "novara_survey_js_core_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-139": {
        "name": "i18n-utils MIT package",
        "source_path": "i18n-utils",
        "replacement": "novara_survey_i18n_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-140": {
        "name": "logger MIT package",
        "source_path": "logger",
        "replacement": "novara_survey_logger_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-141": {
        "name": "vite-plugins MIT package",
        "source_path": "vite-plugins",
        "replacement": "novara_survey_build_contract",
        "docs_reference": "docs/research/repos/01-formbricks-meilisearch-growthbook.md S1.6",
    },
    "FB-142": {
        "name": "Mobile SDKs (React Native, iOS, Android, Flutter)",
        "source_path": "mobile-sdks",
        "replacement": "novara_survey_mobile_contract",
        "docs_reference": "docs surveys/embedded-data/mobile-sdks.md (web-verified)",
    },
}


class BoundaryOut(BaseModel):
    row_id: str
    name: str
    source_path: str
    replacement: str
    attribution: str
    docs_reference: str
    notice_file: str
    dependency_declared: bool
    external_endpoint: str | None
    notes: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[BoundaryOut])
def list_formbricks_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> list[BoundaryOut]:
    """List the immutable clean-room replacement contracts for this workspace."""
    verify_workspace(principal, workspace_id)
    return [
        BoundaryOut(
            row_id=row_id,
            name=spec["name"],
            source_path=spec["source_path"],
            replacement=spec["replacement"],
            attribution=ATTRIBUTION,
            docs_reference=spec["docs_reference"],
            notice_file=NOTICE_FILE,
            dependency_declared=False,
            external_endpoint=None,
            notes=NO_DEFAULT_NOTE,
        )
        for row_id, spec in sorted(SDK_CATALOG.items())
    ]


@router.get("/{row_id}", response_model=BoundaryOut)
def get_formbricks_boundary(
    workspace_id: str,
    row_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
) -> BoundaryOut:
    """Return one replacement contract, failing closed for unknown rows."""
    verify_workspace(principal, workspace_id)
    spec = SDK_CATALOG.get(row_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formbricks boundary not found")
    return BoundaryOut(
        row_id=row_id,
        name=spec["name"],
        source_path=spec["source_path"],
        replacement=spec["replacement"],
        attribution=ATTRIBUTION,
        docs_reference=spec["docs_reference"],
        notice_file=NOTICE_FILE,
        dependency_declared=False,
        external_endpoint=None,
        notes=NO_DEFAULT_NOTE,
    )


def notice_text(repo_root: Path) -> str:
    """Read the preserved third-party notice without altering it."""
    path = repo_root / NOTICE_FILE
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
