# NOVARA project status

Last updated: 2026-11-22 (post-checkpoint UI work). Source of truth for what is
actually done.

## Verdict

Research and licensing are complete. A real, runnable application exists locally:
first-run setup, registration, sessions, RBAC, workspace isolation, the shared
event spine, a CRM slice, a connected intake workflow and a light-theme frontend
wired to the same process. The full backend suite is **99 passed** and a live
browser walkthrough covers every screen, including the two added after the
checkpoint: **AI agent center** and **integrations**. All three QA rounds
(developer, independent, adversarial/recovery) are complete with written
evidence. It is **not yet a release candidate**: PostgreSQL/containers,
installers, outbound delivery and owner decisions remain unverified. See
`docs/CHECKPOINT_2026-11-22.md` and `docs/QA_ROUNDS_2026-11-22.md` for evidence.

## Phase 0 — Environment inspection: DONE

- Workspace `D:\NOVARA` created and connected to `https://github.com/ganeshkrishnareddy/novara` (`main`).
- Python 3.12, Node.js, Git available. Docker is still unavailable.
- All ten source repositories verified; metadata in `docs/research/REPOSITORY_AUDIT.md`.

## Phase 1 — Research and licensing: DONE

- Per-repository license texts read; decisions in `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`.
- Four deep audit reports cover all ten repositories in `docs/research/repos/`.
- No source code was copied from the ten repositories.

## Phase 2 — Architecture and shared contracts: DONE

- `apps/api/novara_core/`: one `Contact` identity, append-only `Event` log,
  workspace-scoped models, Pydantic contracts, RBAC.
- `docs/architecture/CONTRACTS.md` documents implemented contracts and gaps.
- `docs/architecture/MODULE_CONTRACT.md` fixes the contract all capability
  modules must follow, with `modules/feedback.py` as the reference implementation.
- SQLite is the local-first default; `NOVARA_DATABASE_URL` switches the same
  models to PostgreSQL. Alembic scaffolding added in `apps/api/migrations/`.

## Phase 3 — Authentication and foundation: DONE (locally verified)

Implemented: first-run bootstrap, registration, login/logout, bcrypt password
hashing with SHA-256 pre-hash, server-side revocable sessions, refresh rotation,
password reset, email-verification token flow, workspace creation/membership,
invitations, seven workspace-scoped roles, permission checks and cross-workspace
denial. Client-supplied user ids are never accepted as identity.

## Phase 4 — Capability modules: DONE in backend and UI

All ten capability modules exist under `novara_core/modules/` and their routers
are registered through `include_all(app)` (82 API routes in the production app).
The frontend now covers the CRM/operations screens plus the **agent center**
(governed configuration, runs, progress and approvals) and **integrations**
(capability catalog and non-sensitive settings). Both were live browser tested;
no external AI provider is called and no outbound adapter is active in this build.

## Phase 5 — Integration and cross-module workflows: DONE for one workflow

The website-form workflow was re-run live after a server restart: one submission
created a contact, lead, task, notification and outreach draft under a shared
correlation id; approval was confirmed in the UI with no external delivery.
Audit events and the unified customer timeline reflect the whole chain.

## Phase 6 — Testing: backend green, QA rounds complete

- Latest full suite: **99 passed, 2 upstream warnings in 35.00s**.
  Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'`
- Four security areas reverified independently with regression tests.
- Live browser walkthrough completed on the main screens; see
  `docs/CHECKPOINT_2026-11-22.md`.
- All three QA rounds for the two new screens are complete in
  `docs/QA_ROUNDS_2026-11-22.md`: developer, independent (Panko, isolated
  workspace, 14/14 pass) and adversarial/recovery. One cosmetic error-display
  defect found in the rounds was fixed and re-verified; no blocking defect
  remains in the new screens.

## Phase 7 — Packaging, installers, distribution: NOT STARTED

Dockerfile, `docker-compose.yml` (PostgreSQL opt-in profile) and local start
scripts were prepared but cannot be executed here because container tooling is
absent. Container deployment is **not verified**. A first Alembic revision now
exists and its upgrade/downgrade cycle was verified on SQLite only.

## Owner priorities

1. Product correctness 2. Security/privacy 3. Cross-module integration
4. Functional completeness 5. Ease of installation 6. UX 7. Performance
8. Documentation 9. Cross-platform distribution 10. Marketing/adoption.

## Git policy

No commits, pushes, tags or history rewrites. All product code stays in the
local working tree until the owner authorises final Git operations.
