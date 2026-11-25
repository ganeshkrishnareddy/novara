# Extended clean-room claims boundary (T-122) — 2026-11-24

Rows (26): MS-005, MS-009, MS-010, MS-050, MS-051, MS-059, MS-096, MS-098,
CW-119, PM-067, PM-136, PM-155, NV-041, NV-053, NV-055, NV-060, NV-061,
NV-063, NV-066, NV-090, NV-091, NV-095, NV-108, NV-110, NV-114, SB-043.

## Claim

Each row is negative evidence: NOVARA must not advertise an unverified engine
capability, legacy auth header, hosted-provider default, certification,
analytics metric, CLI, foreign dashboard, MCP bridge, AI adapter or public-post
route. The acceptance criteria deny a claim; they do not assert a feature.

## Implementation

- `apps/api/novara_core/modules/extended_claim_boundary.py`: read-only,
  workspace-scoped catalogue of 26 boundary records across Meilisearch,
  Chatwoot, Papermark, Novu and Sellbird. Every route requires `EVENT_READ`
  and calls `verify_workspace`.
- Each record carries a NOVARA-local boundary, the preserved upstream notice,
  `dependency_declared = false`, `external_endpoint = null` and an explicit
  note of what is not claimed.
- No table, no migration, no SDK import, no network client and no mocked
  external result.

## Verification

- `apps/api/tests/test_extended_claim_boundary_p2.py`: 26 named acceptance
  tests. Each proves the record, the preserved notice, the absence of precise
  capability tokens in active manifests and runtime sources, workspace
  isolation (403 cross-workspace) and a closed 404 for unknown rows.
  Forbidden tokens were scanned against active sources before selection and
  only tokens with zero occurrences were used. Boundary modules are excluded
  from the scan because they are allowed to name the claims they deny.
- Combined targeted suite with T-121: **34 passed, 1 warning in 21.32s**
  (`docs/evidence/t122-targeted-20261124.txt`).
- Single Alembic head unchanged at `e0f1a2b3c4d5`; fresh-DB `upgrade head`
  exit 0 and `alembic check` = "No new upgrade operations detected" (exit 0).
- External network is patched to fail for non-loopback addresses in every test.

## Limits

No external SDK, connector, warehouse, CLI, foreign dashboard, MCP bridge,
AI model call, certification or public-post route was introduced. No UI
surface is claimed because the acceptance criteria are negative evidence.
