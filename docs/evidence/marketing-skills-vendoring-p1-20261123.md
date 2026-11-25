# Evidence — vendored Marketing Skills P1 (2026-11-23)

## Scope

Seven P1 rows (`MK-001`, `MK-005`, `MK-015`, `MK-017`, `MK-018`, `MK-039`,
`MK-048`) are served as attributed, pinned, read-only reference content on
NOVARA's one native API surface. Upstream source is `coreyhaines31/marketingskills`
at the immutable commit `5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`
(plugin `2.14.25`), licensed MIT with the full notice in `THIRD_PARTY_NOTICES.md`.
No upstream script or eval was executed; no network fetch was required at
runtime.

## What is real

- `apps/api/novara_core/modules/marketing_skills.py` registers three
  workspace-scoped routes under `/api/v1/workspaces/{workspace_id}/skills`:
  the skill index, provenance/health, and per-skill detail.
- The loader recomputes the SHA-256 of the manifest (anchored in code), then the
  SHA-256, byte length and upstream Git blob SHA of every one of the 44 vendored
  files on every load. A mismatch raises `BundleIntegrityError` and the API
  returns a real `503`.
- Content is served verbatim; it is never interpreted, executed or evaluated.
- Enforcement is shared with the rest of the app: real bearer sessions,
  `CONTACT_READ`, `verify_workspace`. Anonymous requests get `401`; a valid
  principal from another workspace gets `403` on all three routes.

## Named acceptance tests

`apps/api/tests/test_marketing_skills_p1.py` — 8 named tests:

- `test_mk001_ab_testing_skill_is_pinned_verified_and_isolated`
- `test_mk005_analytics_skill_is_pinned_verified_and_isolated`
- `test_mk015_conversion_tracking_skill_is_pinned_verified_and_isolated`
- `test_mk017_copywriting_skill_is_pinned_verified_and_isolated`
- `test_mk018_cro_skill_is_pinned_verified_and_isolated`
- `test_mk039_product_marketing_skill_is_pinned_verified_and_isolated`
- `test_mk048_seo_audit_skill_is_pinned_verified_and_isolated`
- `test_manifest_tamper_is_detected`

Each row test drives a real FastAPI `TestClient`: it asserts `401` without a
token, the manifest-declared version/description/file count, `verified: true`
provenance with the pinned commit/plugin/licence, verbatim `SKILL.md`, a
per-file recomputed SHA-256/byte-length/upstream-blob match, all three paths in
the live OpenAPI document, and `403` cross-workspace denial. The tamper test
corrupts a copy, proves the loader refuses it with a `SHA-256 mismatch`, proves
the real bundle still verifies, proves a real `503` from the app when the
corrupt copy is served, and proves a rewritten manifest cannot self-anchor.

## Verification

- Targeted: `pytest apps/api/tests/test_marketing_skills_p1.py -q` — 8 passed.
- Full API suite: 423 passed, 2 warnings (upstream Starlette/httpx deprecation).

## Honest limits

These rows are VERIFIED as *pinned, integrity-checked, permissioned serving of
the upstream reference skills*. The vendor's paid/eval scripts are not run and
no claim is made that the upstream marketing outcomes were independently
reproduced; the skills are advisory content, not executable workflows.
