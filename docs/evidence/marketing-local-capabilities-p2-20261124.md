# Mautic local capabilities (T-129) — 2026-11-24

Rows (19): MT-002, MT-034, MT-041, MT-043, MT-049, MT-056, MT-063, MT-064, MT-066, MT-067, MT-071, MT-073, MT-077, MT-121, MT-124, MT-126, MT-127, MT-130, MT-123.

## Claim

NOVARA implements local, deterministic capability records and evaluators
for 19 Mautic acceptance criteria. Every record is a real workspace-scoped
row in the existing event spine. Evaluators compute results from stored
records and caller input; no provider is contacted and no message sent.

## Verification

- 19 named acceptance tests, each checking real auth (401), workspace
  isolation (403), persistence, evaluation and the computed result.
- No new table or migration; no non-loopback network call in any test.
- Full-suite evidence: `docs/evidence/t129-fullsuite-clean-20261124.txt`.

## Limits

This proves local behaviour only. No provider delivery, external action,
browser rendering or deployment claim is made.
