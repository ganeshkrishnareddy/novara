# NOVARA — P0 exit report (2026-11-23)

This is the defensible baseline for closing Cycle 1 P0. It is computed from
`docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv`, the single source of truth, and
backed by named tests and runtime evidence. It does **not** claim the whole
1,488-feature catalogue is complete.

## 1. P0 inventory

| Measure | Count |
| --- | --- |
| P0 rows in the permanent catalogue | 111 |
| VERIFIED_COMPLETE | 70 |
| INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | 32 |
| LICENSING_RESTRICTED (lawful alternative recorded) | 9 |
| PARTIALLY_IMPLEMENTED | 0 |
| NOT_IMPLEMENTED / IMPLEMENTED_UNVERIFIED / BACKEND_ONLY | 0 |

Every P0 row now has a disposition and its original acceptance criterion is
preserved in the matrix. No row was removed, renamed or silently downgraded.

## 2. How the 70 verified rows were proved

Each verified cluster has named acceptance tests, a UI wiring guard where the
feature has a visible control, a real-server runtime-smoke section and an
evidence document under `docs/evidence/`. The final suites cover, among others:

- auth, sessions, RBAC and cross-workspace denial
- CRM, sales, support inbox, customer profile and feedback lifecycle
- notifications centre, work items, documents and document links
- campaigns, scheduling, local journey steps and lifecycle analytics
- workspace administration, opt-in adapters, native API contexts and the
  generated OpenAPI document

Final regression: **244 passed, 1 warning** (the known Starlette/httpx
TestClient deprecation notice); `node --check` and `compileall` clean; runtime
smoke **PASS, sections [1]–[14]** over a real uvicorn server; migration
`9b7c4e2a1d63` round-tripped with existing data preserved; all 1,488 rows pass
`validate_inventories.py`; all seven FEATURE_PARITY deliverables regenerated.

## 3. The 32 compatible replacements

These rows are recorded as `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`,
not as verified copies of a source feature. A NOVARA-native mechanism supplies
the same user outcome (for example, local deterministic flags instead of an
external flag service, one native API surface instead of re-hosted controllers).
Their documented acceptance criteria remain in the matrix; none of them claims
to be the upstream product or to contact it.

## 4. The 9 licensing-restricted rows

These rows are `LICENSING_RESTRICTED` with the governing licence and a lawful
clean-room disposition in `LICENSING_EXCEPTION_REGISTER.md`. No restricted
source code, schema, trademarked asset or proprietary bundle was copied. They
are excluded from code-level completion counts and are not reopened as work
items without a fresh licence decision.

## 5. Explicitly not claimed

- No Docker/PostgreSQL stack was exercised; container work remains inspection-only.
- No outbound email, SMS, notification, webhook, landing page or adapter delivery.
- No live third-party instance, credential, SDK or re-hosted controller.
- No desktop/mobile installer, store approval or signed release.
- No commit, push, tag, deployment or public publishing. Git HEAD is `73e9f76`.
- The full catalogue remains 10.89% complete-like (162 / 1,488); 820 rows are
  still NOT_IMPLEMENTED and belong to P1–P3.

## 6. Decision

P0 is closed for Cycle 1: zero partial or unimplemented P0 rows remain, with the
three allowed dispositions above fully accounted for. The next milestone is the
P1 implementation cycle (218 rows), staged in dependency order with the same
tests-first, evidence-gated rule. No P1 row may be marked complete on assertion
alone.
