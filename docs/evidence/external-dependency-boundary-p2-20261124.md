# External-dependency no-claim boundary (T-125) — 2026-11-24

Rows (94): FB-031, FB-077, FB-102, FB-103, FB-105, FB-106, FB-111, FB-112, FB-113, FB-114, FB-115, FB-116, FB-117, FB-118, FB-119, FB-120, FB-121, FB-122, FB-123, FB-150, FB-154, FB-163, FB-164, FB-165, FB-166, FB-169, FB-170, FB-171, FB-172, FB-173, FB-174, FB-175, FB-176, FB-178, FB-226, FB-227, FB-228, MS-083, MS-084, MS-085, MS-086, MS-087, MS-099, GB-119, GB-120, GB-121, GB-122, GB-123, GB-124, GB-125, GB-126, GB-127, GB-128, GB-129, GB-130, GB-131, GB-132, GB-133, PM-138, PM-140, MT-110, CW-033, CW-037, CW-038, CW-041, CW-045, CW-047, CW-073, CW-085, CW-107, CW-124, CW-127, CW-145, CW-161, CW-163, NV-080, NV-098, SB-001, SB-002, SB-004, SB-005, SB-006, SB-007, SB-025, SB-027, SB-029, SB-032, SB-045, SB-064, SB-073, SB-074, SB-075, SB-076, SB-077.

## Claim

Each row is an EXTERNAL_DEPENDENCY_BLOCKED inventory entry whose acceptance
criteria deny a default or fabricated external integration. NOVARA keeps each
capability blocked until a real provider is explicitly configured and verified.
A token scan confirmed that no precise capability token for any selected row
appears in active manifests and runtime sources.

## Implementation

- `apps/api/novara_core/modules/external_dependency_boundary.py`: read-only,
  workspace-scoped catalogue of no-claim decisions across Formbricks,
  Sellbird, GrowthBook, Chatwoot, Meilisearch, Papermark, Mautic and Novu.
  Every route requires `EVENT_READ` and calls `verify_workspace`.
- Each record carries a NOVARA-local claim, the preserved upstream notice,
  `dependency_declared = false`, `external_endpoint = null` and
  `delivery_claimed = false`.
- No table, no migration, no SDK import, no client, no socket and no endpoint.

## Verification

- `apps/api/tests/test_external_dependency_boundary_p2.py`: 94 named
  acceptance tests. Each proves the record, the preserved notice, absence of
  the capability token in active sources, no HTTP client import or URL in the
  boundary module, workspace isolation (403) and a closed 404 for unknown rows.
- Non-loopback network calls are banned in every test; boundary modules are
  excluded from token scans because they may name the claims they deny.
- Full suite result is recorded in `docs/evidence/t125-fullsuite-clean-20261124.txt`.

## Limits

No provider SDK, external call, credential field, fake delivery or unverified
infrastructure claim was introduced. No UI surface is claimed. 41 blocked rows
that require a real verified provider run, deployment or UI test were excluded.
