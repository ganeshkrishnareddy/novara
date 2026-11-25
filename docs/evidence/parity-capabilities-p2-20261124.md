# Parity local capabilities (T-130) — 2026-11-24

Rows: 150, one named test each.

## Claim

NOVARA implements local, deterministic capability records and evaluators
for the listed feature-parity rows. Every record is a real workspace-scoped
row in the existing event spine. Evaluators compute results from stored
records and caller input; no provider is contacted, no deployment is claimed
and nothing is sent externally.

## Verification

- 150 named backend tests: real auth (401), workspace isolation (403),
  persistence, evaluation and mode-specific computed results.
- SPA route, loader, forms and dispatch handlers verified by a static UI
  wiring contract test (no dead controls).
- No new table or migration; no non-loopback network call in any test.
- Full-suite evidence: `docs/evidence/t130-fullsuite-clean-20261124.txt`.

## Limits

Local behaviour only. No provider delivery, external event, browser extension,
deployment, real identity provider or external send is claimed. Rows whose
acceptance criteria require any of those remain open.
