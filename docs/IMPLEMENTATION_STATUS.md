# Implementation status

Verified local state at the latest checkpoint. "Done" means code exists and a
named test or command was run; it does not mean released.

## Done

- `apps/api/novara_core/models.py` — workspace, global user, membership,
  invitations, sessions, reset/verification tokens, single Contact identity,
  Company, Lead, Note, append-only Event, Task, Notification, OutreachDraft.
- `apps/api/novara_core/security.py` — bcrypt password hashing with SHA-256
  pre-hash, hashed random tokens, session creation/rotation/revocation,
  one-time token issue/consume.
- `apps/api/novara_core/dependencies.py` — server-side principal resolution,
  `require(permission)` and `verify_workspace()`.
- `apps/api/novara_core/permissions.py` — seven workspace-scoped roles.
- `apps/api/novara_core/events.py` — one event envelope, idempotency, central
  registry extensible by modules via `register_event_types()`.
- `apps/api/novara_core/workflow.py` — intake fan-out and approval gate; no send.
- `apps/api/novara_core/main.py` — authenticated, workspace-scoped API for
  auth, workspaces, members, invitations, CRM, tasks, notifications, audit log
  and unified customer timeline.
- `apps/api/novara_core/modules/` — all ten capability modules; their routers
  are registered in `main.py` via `include_all(app)` (82 API routes).
- `apps/web/styles.css`, `apps/web/app.js` — unified light-theme frontend wired
  to the same process, live browser tested on every screen. The post-checkpoint
  `agents` screen covers governed configuration, runs, progress and approvals;
  the `integrations` screen covers the capability catalog and non-sensitive
  settings. Both reject secrets and state that no external call is made.
- `apps/api/migrations/versions/6d610706f4ff_initial_schema.py` — initial
  Alembic revision (35 tables). Upgrade/downgrade/re-upgrade and `alembic check`
  verified on a clean SQLite database.
- `scripts/start-local.ps1` / `.sh` — local startup; PowerShell stderr handling
  corrected earlier in this work stream.

## In progress / incomplete

- Real provider adapters, outbound delivery and executable AI output — absent
  by design; the UI records and governs activity instead of fabricating results.
- PostgreSQL/containers, installers/signing and owner decisions — see
  `docs/BLOCKERS.md`; not touched by this UI work.

## Not started / unverified

- PostgreSQL migration execution and container build/run (Docker unavailable).
- Installers, signing, store publication.
- Real external provider adapters and any outbound delivery.
- Rate limiting, dependency and secret scanning.

Update this file only with verifiable evidence.
