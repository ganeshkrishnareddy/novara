# Plane no-unverified-default boundary (T-121) — 2026-11-24

Rows: PL-067, PL-109, PL-133, PL-134, PL-151, PL-153, PL-154, PL-156.

## Claim

Each row is negative evidence: NOVARA must not advertise a default external
AI-model call, embedded Plane edition/licence logic, a desktop or mobile build,
a required external object store, a verified container/Kubernetes deployment,
or an internal `@plane/*` monorepo package.

## Implementation

- `apps/api/novara_core/modules/plane_claim_boundary.py`: read-only,
  workspace-scoped catalogue of eight boundary records. Every route requires
  `EVENT_READ` and calls `verify_workspace`.
- Each record states a NOVARA-local boundary, preserves the Plane
  AGPL-3.0-only notice, sets `dependency_declared = false` and
  `external_endpoint = null`, and records why no such claim is made.
- No table, no migration, no package, no build artifact, no external call.

## Verification

- `apps/api/tests/test_plane_claim_boundary_p2.py`: eight named acceptance
  tests. Each proves the record, the preserved notice, the absence of precise
  capability tokens in active manifests and runtime sources, workspace
  isolation (403 cross-workspace) and a closed 404 for unknown rows.
- Targeted suite: **8 passed, 1 warning in 6.78s**
  (`docs/evidence/t121-targeted-20261124.txt`).
- Single Alembic head unchanged at `e0f1a2b3c4d5`; fresh-DB `upgrade head`
  exit 0 and `alembic check` = "No new upgrade operations detected" (exit 0).
- External network is patched to fail for non-loopback addresses in every test.

## Limits

No Plane source copy, edition logic, SDK, desktop/mobile build, object-storage
dependency, container verification or `@plane/*` package was introduced. No UI
surface is claimed because the acceptance criteria are negative evidence.
