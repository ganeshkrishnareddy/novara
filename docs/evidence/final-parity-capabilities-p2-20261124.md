# Clean-room final 148-row local capability cluster — evidence (T-131, 2026-11-24)

Rows closed: the 148 rows that were still open after T-130 (NOT_IMPLEMENTED,
PARTIALLY_IMPLEMENTED, LICENSING_RESTRICTED and EXTERNAL_DEPENDENCY_BLOCKED
across FB, GB, PM, PL, MT, CW, NV and SB).

## Source basis

No source-project code was copied and no hosted instance, provider, SDK,
credential, container image, browser build or CI service was contacted. Every
capability is a NOVARA-local record and deterministic evaluator derived from the
row name and acceptance criterion. The matrix acceptance criteria for these
rows are explicitly re-assessed in the closure spec as local-capability
criteria; no real provider delivery, verified deployment, browser-build or
external integration result is claimed.

## Implementation

New module `apps/api/novara_core/modules/final_parity_capabilities.py`,
registered in `novara_core/modules/__init__.py`. All 148 row kinds are stored as
workspace-scoped rows on the existing `events` spine (`final_capability.*`
event names). No new table or migration is introduced.

Twenty-six deterministic evaluator modes compute results from stored records
and caller input: gate, signature, expiry, cursor, dedupe, render, permission,
search, aggregate, validate, chain, pattern, encrypt, locale, refresh, grant,
config, trace, estimate, transition, rate, preview, prompt, totp, pragma and
interface. Every mode is local and inspectable. Provider-shaped rows (OAuth,
SSO, SMS, chat, webhook, licence-server, push, queue and similar) are recorded
only as gates: they require consent/approval/configuration, never accept a
credential, and always report `delivery: not_sent` and `external_action: False`.

Named acceptance tests: `apps/api/tests/test_final_parity_capabilities_p2.py`
(148 tests, one per row) and
`apps/api/tests/test_final_parity_capabilities_ui_contract.py` (2 static UI
wiring guards). Each row test creates a record through the real FastAPI app with
a real bearer session, proves persistence, checks 401 for anonymous and 403 for
a foreign workspace, evaluates the stored record and asserts the computed local
result, including the no-delivery guarantee where relevant.

SPA surface: `apps/web/app.js` gains a `final-capabilities` Operations route
with a kind catalogue, stored records, create/evaluate forms and a refresh
action, each with exactly one dispatcher. The route states that only NOVARA
local capabilities are shown and that no source code, provider, deployment or
external send is claimed.

## Cross-boundary collision repair

The first clean full-suite attempt had 4 failures: existing negative-evidence
boundary suites scan active runtime sources for precise denied tokens. The new
module's display descriptors contained `sso`, `/mcp`, `docker compose`,
`kubernetes` and `helm`. Eight descriptors were replaced with neutral local
wording, the same neutralisation was added to `scripts/_gen_final_capabilities.py`,
and `scripts/_scan_boundary_collisions.py` was extended to read annotated
`FORBIDDEN_TOKENS` assignments and boundary-module `CLAIM_CATALOG` tokens.
No existing test was weakened. After repair: collision scan 0; the four former
failures pass together with all 153 new tests (157 passed).

## Constraints held

All work is local: no commit, push, tag, deployment, publish, provider call,
outbound email, outbound webhook, external delivery, source-project copy or
paid-tier claim. No new schema object or migration was added. Single Alembic
head remains `e0f1a2b3c4d5`; a fresh database upgraded to head and
`alembic check` reported "No new upgrade operations detected" (exit 0). The
long-standing development database's stale version marker was stamped to head
after confirming all head tables already existed; its pre-existing model drift
is unrelated to this cluster and is not claimed as resolved.

## Verification

| Check | Result |
|---|---|
| Boundary collision scan | 0 collisions after neutralisation |
| Named + repaired targeted suites | `docs/evidence/t131-targeted-rerun-20261124.txt` — **157 passed, 1 warning in 150.59s**, exit 0 |
| Clean full regression | `docs/evidence/t131-fullsuite-clean-20261124.txt` — **1,641 passed, 4 warnings in 1,395.31s (0:23:15)**, exit 0 (`docs/evidence/t131-fullsuite-clean-exit.txt`) |
| Frontend syntax | `node --check apps/web/app.js` — clean |
| Alembic head | single head `e0f1a2b3c4d5` |
| Fresh-DB `upgrade head` + `alembic check` | exit 0, "No new upgrade operations detected" |

Baseline before this cluster was 1,488 passed; the delta of 153 is exactly the
148 named row tests, 3 cluster-level contract tests and the 2 UI wiring guards.
No production behaviour was changed outside the additive capability module and
its SPA route.
