# No-claim and documentation evidence boundary (T-126) — 2026-11-24

Rows (81): MS-101, PL-075, PL-143, PL-152, MT-005, MT-006, MT-038, MT-061, MT-084, MT-085, MT-087, MT-088, MT-090, MT-091, MT-103, MT-104, MT-119, MT-120, MT-125, MT-128, MT-131, MT-132, MT-133, CW-026, CW-034, CW-044, CW-046, CW-058, CW-061, CW-062, CW-063, CW-064, CW-068, CW-069, CW-070, CW-071, CW-072, CW-080, CW-103, CW-125, CW-126, CW-128, CW-136, CW-147, CW-150, CW-154, CW-156, CW-157, CW-165, NV-016, NV-021, NV-037, NV-049, NV-050, NV-064, NV-083, NV-117, PL-126, PL-131, PL-155, SB-039, SB-040, SB-041, SB-044, SB-047, SB-049, SB-050, SB-058, SB-059, SB-063, SB-065, SB-066, SB-068, GB-194, GB-205, GB-213, GB-234, GB-239, GB-250, FB-193, NV-075.

## Claim

Each row has a no-claim, documentation-only, design-decision or conditional
("if claimed") acceptance criterion. NOVARA records a conservative, accurate
decision in `docs/NOVARA_NO_CLAIM_POLICY.md`; it does not assert that a source
project capability was copied or that an external provider was verified.

## Implementation

- `docs/NOVARA_NO_CLAIM_POLICY.md`: one statement per row, written from
  verified local facts (README, INSTALL, THIRD_PARTY_NOTICES, test suite).
- `apps/api/novara_core/modules/no_claim_evidence_boundary.py`: read-only,
  workspace-scoped catalogue of those decisions. Every route requires
  `EVENT_READ` and calls `verify_workspace`.
- No table, migration, SDK, external endpoint or fabricated result.

## Verification

- `apps/api/tests/test_no_claim_evidence_boundary_p2.py`: 81 named
  acceptance tests. Each proves the policy statement is present, the record
  is correct and workspace-scoped, the upstream notice is preserved, the
  capability token is absent from active sources, no HTTP client is imported,
  cross-workspace access is 403 and unknown rows are 404.
- Non-loopback network calls are banned in every test.
- Full suite result is recorded in `docs/evidence/t126-fullsuite-clean-20261124.txt`.

## Limits

No source-project code or asset was copied. No external provider, deployment,
container build, CI service or enterprise entitlement is claimed. Rows whose
acceptance requires a positive implementation were excluded.
