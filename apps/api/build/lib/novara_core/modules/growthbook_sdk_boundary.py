"""Clean-room GrowthBook SDK compatibility boundary (GB-148..GB-173).

These rows describe advertised SDK/provider paths. NOVARA does not install any
GrowthBook SDK package, contact a GrowthBook service, or copy enterprise code.
Instead it publishes an explicit, workspace-scoped compatibility boundary: each
catalogued SDK has a documented local adapter name, its public documentation
reference, the preserved MIT notice, and an honest ``no default dependency``
marker. A caller can therefore discover the boundary and attribute the upstream
project without importing a paid or unverified dependency.

All new state lives in the additive ``gbsdk_*`` table. No existing experiment,
flag, SDK or event row is altered.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import EVENT_READ, WORKSPACE_MANAGE

BOUNDARY_EVENT = "growthbook_sdk_boundary.changed"
register_event_types(BOUNDARY_EVENT)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/sdk-boundaries",
    tags=["growthbook-sdk-boundary"],
)

ATTRIBUTION = "Copyright (c) 2025 GrowthBook, Inc. | MIT license"
NOTICE_FILE = "THIRD_PARTY_NOTICES.md"
NO_DEFAULT_NOTE = "Compatibility boundary only; no default SDK dependency and no outbound call."

# Values are derived only from the public documentation references recorded in
# the feature catalogue. ``adapter`` names are NOVARA-local boundary names; they
# are deliberately not package imports and no upstream source is reproduced.
SDK_CATALOG: dict[str, dict[str, str]] = {
    "GB-148": {
        "name": "JavaScript SDK",
        "ecosystem": "browser",
        "boundary": "browser-bridge",
        "adapter": "novara_js_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/js.md",
    },
    "GB-149": {
        "name": "React SDK",
        "ecosystem": "react",
        "boundary": "react-hook-boundary",
        "adapter": "novara_react_hook_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/react.md",
    },
    "GB-150": {
        "name": "Next.js SDK",
        "ecosystem": "nextjs",
        "boundary": "server-safe-boundary",
        "adapter": "novara_nextjs_server_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/nextjs.md",
    },
    "GB-151": {
        "name": "Vue SDK",
        "ecosystem": "vue",
        "boundary": "vue-composable-boundary",
        "adapter": "novara_vue_composable_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/vue.md",
    },
    "GB-152": {
        "name": "Node.js SDK",
        "ecosystem": "node",
        "boundary": "server-bridge",
        "adapter": "novara_node_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/node.md",
    },
    "GB-153": {
        "name": "Python SDK",
        "ecosystem": "python",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_python_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/python.md",
    },
    "GB-154": {
        "name": "Ruby SDK",
        "ecosystem": "ruby",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_ruby_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/ruby.md",
    },
    "GB-155": {
        "name": "PHP SDK",
        "ecosystem": "php",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_php_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/php.md",
    },
    "GB-156": {
        "name": "Java SDK",
        "ecosystem": "java",
        "boundary": "jvm-evaluator-boundary",
        "adapter": "novara_jvm_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/java.md",
    },
    "GB-157": {
        "name": "Go SDK",
        "ecosystem": "go",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_go_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/go.md",
    },
    "GB-158": {
        "name": "C# SDK",
        "ecosystem": "dotnet",
        "boundary": "dotnet-evaluator-boundary",
        "adapter": "novara_csharp_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/csharp.md",
    },
    "GB-159": {
        "name": "Elixir SDK",
        "ecosystem": "elixir",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_elixir_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/elixir.md",
    },
    "GB-160": {
        "name": "Rust SDK",
        "ecosystem": "rust",
        "boundary": "local-evaluator-boundary",
        "adapter": "novara_rust_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/rust.md",
    },
    "GB-161": {
        "name": "Kotlin JVM SDK",
        "ecosystem": "kotlin-jvm",
        "boundary": "jvm-evaluator-boundary",
        "adapter": "novara_kotlin_jvm_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/kotlin.md",
    },
    "GB-162": {
        "name": "Kotlin Android SDK",
        "ecosystem": "kotlin-android",
        "boundary": "android-evaluator-boundary",
        "adapter": "novara_kotlin_android_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/kotlin.md",
    },
    "GB-163": {
        "name": "Swift SDK",
        "ecosystem": "swift",
        "boundary": "apple-evaluator-boundary",
        "adapter": "novara_swift_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/swift.md",
    },
    "GB-164": {
        "name": "Flutter SDK",
        "ecosystem": "flutter",
        "boundary": "dart-evaluator-boundary",
        "adapter": "novara_flutter_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/flutter.md",
    },
    "GB-165": {
        "name": "React Native SDK",
        "ecosystem": "react-native",
        "boundary": "react-native-boundary",
        "adapter": "novara_react_native_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/react-native.md",
    },
    "GB-166": {
        "name": "Roku SDK",
        "ecosystem": "roku",
        "boundary": "roku-evaluator-boundary",
        "adapter": "novara_roku_bridge",
        "docs_reference": "https://docs.growthbook.io/lib.md",
    },
    "GB-167": {
        "name": "HTML script tag",
        "ecosystem": "html-script",
        "boundary": "script-tag-boundary",
        "adapter": "novara_script_tag_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/script-tag.md",
    },
    "GB-168": {
        "name": "OpenFeature provider",
        "ecosystem": "openfeature",
        "boundary": "provider-boundary",
        "adapter": "novara_openfeature_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/openfeature.md",
    },
    "GB-169": {
        "name": "Cloudflare Workers SDK",
        "ecosystem": "cloudflare-workers",
        "boundary": "edge-boundary",
        "adapter": "novara_cloudflare_workers_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/edge/cloudflare.md",
    },
    "GB-170": {
        "name": "Fastly Compute SDK",
        "ecosystem": "fastly-compute",
        "boundary": "edge-boundary",
        "adapter": "novara_fastly_compute_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/edge/fastly.md",
    },
    "GB-171": {
        "name": "Lambda@Edge SDK",
        "ecosystem": "lambda-edge",
        "boundary": "edge-boundary",
        "adapter": "novara_lambda_edge_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/edge/lambda.md",
    },
    "GB-172": {
        "name": "Vercel Flags SDK",
        "ecosystem": "vercel-flags",
        "boundary": "flags-provider-boundary",
        "adapter": "novara_vercel_flags_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/nextjs.md",
    },
    "GB-173": {
        "name": "Build your own SDK spec",
        "ecosystem": "sdk-spec",
        "boundary": "specification-boundary",
        "adapter": "novara_sdk_spec_bridge",
        "docs_reference": "https://docs.growthbook.io/lib/build-your-own.md",
    },
}


class SdkBoundary(Base):
    __tablename__ = "gbsdk_boundaries"
    __table_args__ = (UniqueConstraint("workspace_id", "sdk_id", name="uq_gbsdk_workspace_sdk"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    sdk_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(40), nullable=False)
    boundary: Mapped[str] = mapped_column(String(80), nullable=False)
    adapter: Mapped[str] = mapped_column(String(120), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    docs_reference: Mapped[str] = mapped_column(Text, nullable=False)
    notice_file: Mapped[str] = mapped_column(String(120), nullable=False)
    default_dependency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_endpoint: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BoundaryOut(BaseModel):
    sdk_id: str
    name: str
    ecosystem: str
    boundary: str
    adapter: str
    attribution: str
    docs_reference: str
    notice_file: str
    default_dependency: bool
    external_endpoint: str | None
    notes: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SeedOut(BaseModel):
    created: list[str] = Field(default_factory=list)
    total: int
    notes: str = NO_DEFAULT_NOTE


class SeedIn(BaseModel):
    sdk_ids: list[str] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("sdk_ids")
    @classmethod
    def known_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = sorted(set(value) - set(SDK_CATALOG))
        if unknown:
            raise ValueError(f"unknown SDK ids: {', '.join(unknown)}")
        return sorted(set(value))


@router.post("/seed", response_model=SeedOut, status_code=status.HTTP_201_CREATED)
def seed_sdk_boundaries(
    workspace_id: str,
    body: SeedIn,
    principal: Principal = Depends(require(WORKSPACE_MANAGE)),
    db: Session = Depends(get_db),
) -> SeedOut:
    verify_workspace(principal, workspace_id)
    wanted = body.sdk_ids or sorted(SDK_CATALOG)
    existing = set(
        db.execute(
            select(SdkBoundary.sdk_id).where(SdkBoundary.workspace_id == workspace_id)
        ).scalars().all()
    )
    created: list[str] = []
    for sdk_id in wanted:
        if sdk_id in existing:
            continue
        spec = SDK_CATALOG[sdk_id]
        db.add(
            SdkBoundary(
                id=new_id(),
                workspace_id=workspace_id,
                sdk_id=sdk_id,
                name=spec["name"],
                ecosystem=spec["ecosystem"],
                boundary=spec["boundary"],
                adapter=spec["adapter"],
                attribution=ATTRIBUTION,
                docs_reference=spec["docs_reference"],
                notice_file=NOTICE_FILE,
                default_dependency=False,
                external_endpoint=None,
                notes=NO_DEFAULT_NOTE,
                created_by=principal.user.id,
                created_at=now(),
            )
        )
        created.append(sdk_id)
    db.flush()
    if created:
        publish_event(
            db,
            workspace_id=workspace_id,
            event_type=BOUNDARY_EVENT,
            entity_id=workspace_id,
            payload={"action": "seed", "created": created},
            actor_id=principal.user.id,
        )
    db.commit()
    total = len(
        db.execute(
            select(SdkBoundary.sdk_id).where(SdkBoundary.workspace_id == workspace_id)
        ).scalars().all()
    )
    return SeedOut(created=created, total=total)


@router.get("", response_model=list[BoundaryOut])
def list_sdk_boundaries(
    workspace_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> list[SdkBoundary]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(SdkBoundary)
        .where(SdkBoundary.workspace_id == workspace_id)
        .order_by(SdkBoundary.sdk_id)
    ).scalars().all()


@router.get("/{sdk_id}", response_model=BoundaryOut)
def get_sdk_boundary(
    workspace_id: str,
    sdk_id: str,
    principal: Principal = Depends(require(EVENT_READ)),
    db: Session = Depends(get_db),
) -> SdkBoundary:
    verify_workspace(principal, workspace_id)
    row = db.execute(
        select(SdkBoundary).where(
            SdkBoundary.workspace_id == workspace_id,
            SdkBoundary.sdk_id == sdk_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="SDK boundary not found")
    return row


def notice_text(repo_root: Path) -> str:
    """Read the preserved third-party notice without altering it."""
    path = repo_root / NOTICE_FILE
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
