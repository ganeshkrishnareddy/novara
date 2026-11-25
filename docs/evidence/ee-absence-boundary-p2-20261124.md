# GrowthBook EE-absence clean-room boundary (T-123) — 2026-11-24

Rows (82): GB-108, GB-109, GB-174, GB-175, GB-176, GB-177, GB-178, GB-179, GB-180, GB-181, GB-182, GB-184, GB-185, GB-186, GB-190, GB-191, GB-192, GB-193, GB-195, GB-197, GB-198, GB-199, GB-200, GB-201, GB-202, GB-203, GB-204, GB-207, GB-208, GB-212, GB-216, GB-218, GB-219, GB-220, GB-221, GB-223, GB-226, GB-227, GB-228, GB-229, GB-230, GB-235, GB-236, GB-238, GB-240, GB-241, GB-242, GB-243, GB-244, GB-245, GB-246, GB-251, GB-252, GB-253, GB-254, GB-255, GB-256, GB-257, GB-258, GB-259, GB-260, GB-261, GB-262, GB-263, GB-264, GB-265, GB-266, GB-267, GB-268, GB-269, GB-270, GB-271, GB-272, GB-273, GB-274, GB-275, GB-276, GB-277, GB-278, GB-279, GB-280, GB-281.

## Claim

Each row is a LICENSING_RESTRICTED inventory entry whose acceptance criteria
allow closure when the proprietary enterprise capability is absent from the
default install and no licensed source is used. A capability token scan over
active manifests, runtime modules and web sources confirmed the absence of
every selected token before the row was included.

## Implementation

- `apps/api/novara_core/modules/ee_absence_boundary.py`: read-only,
  workspace-scoped catalogue of absence decisions. Every route requires
  `EVENT_READ` and calls `verify_workspace`.
- Each record carries the capability name, a NOVARA-local claim, the preserved
  GrowthBook community notice, `dependency_declared = false` and no endpoint.
- No table, no migration, no enterprise source, no entitlement, no external call.

## Verification

- `apps/api/tests/test_ee_absence_boundary_p2.py`: 82 named acceptance
  tests. Each proves the record, the preserved notice, the absence of the
  capability token in active sources, workspace isolation (403) and a closed
  404 for unknown rows. Boundary modules are excluded from token scans.
- External network is patched to fail for non-loopback addresses in every test.
- Full suite result is recorded in `docs/evidence/t123-fullsuite-clean-20261124.txt`.

## Limits

No GrowthBook enterprise source, entitlement, provider endpoint or licensed
capability was introduced. No UI surface is claimed. Six restricted rows whose
tokens are already present in the codebase were deliberately excluded.
