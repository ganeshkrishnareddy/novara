# NOVARA feature-parity inventory contract

This file is the shared contract for the ten source-project inventories. It is owned by the principal agent. Source inventory agents **read** it and write **only** their own file under `docs/FEATURE_PARITY/SOURCES/`.

## Zero-omission rule

Every capability mentioned in a source audit, source README/docs, feature directory, API surface, schema, UI, worker, SDK, configuration or enterprise boundary must receive its own row and its own permanent feature ID. A feature may be marked restricted, blocked or not implemented, but it may never be silently dropped, merged invisibly into another row, or relabelled as "not applicable" to avoid accounting for it. When a capability is only advertised (not verified in source), it still gets a row with the source evidence marked `ADVERTISED_UNVERIFIED`.

## Permanent ID prefixes

| Source | Prefix | Owned inventory file |
|---|---|---|
| Formbricks | `FB` | `SOURCES/01-formbricks.md` |
| Meilisearch | `MS` | `SOURCES/02-meilisearch.md` |
| GrowthBook | `GB` | `SOURCES/03-growthbook.md` |
| Papermark | `PM` | `SOURCES/04-papermark.md` |
| Plane | `PL` | `SOURCES/05-plane.md` |
| Mautic | `MT` | `SOURCES/06-mautic.md` |
| Chatwoot | `CW` | `SOURCES/07-chatwoot.md` |
| Novu | `NV` | `SOURCES/08-novu.md` |
| Marketing Skills | `MK` | `SOURCES/09-marketingskills.md` |
| Sellbird | `SB` | `SOURCES/10-sellbird.md` |

IDs are sequential with three digits (`FB-001`, `MS-001`, …). An ID is never reused, renumbered or deleted once published. Newly discovered features get the next free number for that prefix.

## Required row schema

Each inventory is a GitHub-flavoured markdown table with **exactly these 20 columns**, in this order, followed by a short notes section:

1. `ID`
2. `Source repository`
3. `Exact source feature name`
4. `Description`
5. `Source location / documentation reference`
6. `Community availability` — `AVAILABLE`, `GATED`, `ADVERTISED_UNVERIFIED` or `PAID_HOSTED_ONLY`
7. `Current status` — exactly one of the nine labels below
8. `NOVARA module`
9. `NOVARA implementation location`
10. `Backend status`
11. `Frontend status`
12. `Database status`
13. `API status`
14. `Permissions / security status`
15. `Integration status`
16. `Tests / evidence`
17. `Licensing constraint`
18. `Priority` — `P0`, `P1`, `P2` or `P3`
19. `Dependencies`
20. `Remaining work`
21. `Final acceptance criteria`

(The last column makes 21 columns; use all of them. Do not add or reorder columns.)

## Allowed `Current status` values

`VERIFIED_COMPLETE`, `IMPLEMENTED_UNVERIFIED`, `PARTIALLY_IMPLEMENTED`, `BACKEND_ONLY`, `FRONTEND_ONLY`, `NOT_IMPLEMENTED`, `EXTERNAL_DEPENDENCY_BLOCKED`, `LICENSING_RESTRICTED`, `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`.

Definitions:
- `VERIFIED_COMPLETE`: real user-facing behaviour, persistence, permissions, validation and a passing named test/browser evidence.
- `IMPLEMENTED_UNVERIFIED`: code and tests exist locally but no browser/end-to-end evidence was captured.
- `PARTIALLY_IMPLEMENTED`: a real slice exists; the rest of the source capability is absent and listed in Remaining work.
- `BACKEND_ONLY`: API/model exists, no UI route.
- `FRONTEND_ONLY`: UI exists without its own backend behaviour (caution: do not claim this if it merely calls a shared API).
- `NOT_IMPLEMENTED`: no real implementation found.
- `EXTERNAL_DEPENDENCY_BLOCKED`: needs credentials, provider verification, Docker/PostgreSQL or unavailable infrastructure.
- `LICENSING_RESTRICTED`: source feature cannot be copied (EE/proprietary/AGPL-incompatible); Remaining work must describe the lawful alternative.
- `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`: NOVARA has a clean-room equivalent; name it and explain the compatibility boundary.

## Evidence rules

- Primary evidence is `docs/research/repos/01…04` (source-verified audits) and `docs/research/LICENSE_COMPLIANCE.md`. Verify against public docs/README where reachable; if a web check fails, say `audit-only` in the evidence cell rather than implying live verification.
- NOVARA-side evidence must cite real paths and named tests under `apps/api/tests/`, real routes in `apps/api/novara_core/`, and real routes/actions in `apps/web/app.js`. If none exists, write `none found`.
- Never count a menu item, table, 200 response, placeholder button or local mock as a completed feature.
- Never claim Docker, PostgreSQL, real outbound providers, mobile/desktop builds or AI models are verified. They are not.

## Licensing rules

- Formbricks AGPL community + EE; Meilisearch MIT/OpenLDAP core + BUSL EE; GrowthBook MIT + EE; Papermark AGPL + commercial EE; Plane AGPL-only; Mautic GPL; Chatwoot MIT + EE; Novu MIT + proprietary; Marketing Skills MIT; Sellbird AGPL v0.4.0+ / MIT ≤0.3.x.
- Enterprise-only and proprietary paths are `LICENSING_RESTRICTED`, never silently omitted. Describe a clean-room alternative where lawful.
- No source code copying from incompatible licences; clean-room implementations only.

## File ownership and prohibited actions

Each assigned agent owns **exactly one** file in `docs/FEATURE_PARITY/SOURCES/`. It must not edit any other file, including shared code, tests, this contract, the master catalog, the master CSV, the task board or git state. No commits, pushes, tags, deployment, installs or outbound messages. Agents must not claim completion based on another agent's summary.
