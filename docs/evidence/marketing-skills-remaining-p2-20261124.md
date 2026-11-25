# Remaining Marketing Skills vendoring (T-128) — 2026-11-24

Rows (46): MK-002, MK-003, MK-004, MK-006, MK-007, MK-008, MK-009, MK-010, MK-011, MK-012, MK-013, MK-014, MK-016, MK-019, MK-020, MK-021, MK-022, MK-023, MK-024, MK-025, MK-026, MK-027, MK-028, MK-029, MK-030, MK-031, MK-032, MK-033, MK-034, MK-035, MK-036, MK-037, MK-038, MK-040, MK-041, MK-042, MK-043, MK-044, MK-045, MK-046, MK-047, MK-049, MK-050, MK-051, MK-052, MK-053.

## Claim

The 46 SKILL.md artifacts, all referenced files, their exact frontmatter
and versions, and the MIT notice were fetched from the SAME upstream Git
commit (`5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`, plugin 2.14.25) already
used for the seven originally vendored rows. Nothing was authored or
fabricated: SHA-256, byte length and Git blob SHA are computed from the
received bytes and anchored through the manifest hash in the module.

## Verification

- 357 pinned upstream files across 46 skills, 53 skills in total.
- `apps/api/tests/test_marketing_skills_remaining_p2.py`: 46 named tests.
- Each named test checks exact frontmatter/version, verbatim SKILL.md,
  live per-file digests, 401/403 isolation, a closed 404 and the preserved
  MIT provenance. Skills are served, never executed; upstream evals and
  scripts are not run and no model request is spent.
- Full-suite evidence: `docs/evidence/t128-fullsuite-clean-20261124.txt`.

## Limits

This proves exact pinned vendoring and integrity only. It does not claim
skill execution, provider delivery, publication or any external action.
