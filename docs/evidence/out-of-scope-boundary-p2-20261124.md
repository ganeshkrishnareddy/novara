# Enterprise out-of-scope clean-room boundary (T-124) — 2026-11-24

Rows (49): FB-155, FB-156, FB-205, FB-206, FB-207, FB-208, FB-209, FB-210, FB-211, FB-212, FB-213, FB-214, FB-215, FB-216, FB-217, FB-218, FB-219, FB-220, FB-221, FB-222, FB-223, FB-224, FB-225, FB-234, MS-088, MS-089, MS-090, MS-091, MS-092, MS-093, CW-164, CW-167, CW-168, NV-067, NV-074, NV-077, NV-078, NV-079, NV-084, NV-093, NV-109, NV-116, PL-110, PL-111, PL-112, PL-121, PL-122, PL-127, PM-094.

## Claim

Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria
permit an explicit out-of-scope decision backed by named evidence: no enterprise
source, entitlement, paid asset or unverified claim is present in NOVARA.

## Implementation

- `apps/api/novara_core/modules/out_of_scope_boundary.py`: read-only,
  workspace-scoped catalogue of out-of-scope decisions across Formbricks,
  Meilisearch, Chatwoot, Novu, Plane and Papermark. Every route requires
  `EVENT_READ` and calls `verify_workspace`.
- Each record carries the capability name, provider, preserved notice, no
  declared dependency and no external endpoint.
- No table, no migration, no enterprise source, no entitlement, no external call.

## Verification

- `apps/api/tests/test_out_of_scope_boundary_p2.py`: 49 named
  acceptance tests. Each proves the record, the preserved notice, the absence
  of capability-specific tokens in active sources, workspace isolation (403)
  and a closed 404 for unknown rows. Boundary modules are excluded from scans.
- External network is patched to fail for non-loopback addresses in every test.
- Full suite result is recorded in `docs/evidence/t124-fullsuite-clean-20261124.txt`.

## Limits

No enterprise source, entitlement, paid asset or unverified certification was
introduced. No UI surface is claimed. Restricted rows whose acceptance requires
a positive clean-room feature were deliberately excluded from this cluster.
