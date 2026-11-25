# Release readiness

Status: **not a release candidate.** No installer, package or public release exists.

Latest evidence: `docs/CHECKPOINT_2026-11-22.md` (security reverification, live
browser walkthrough, persistence, SQLite migration cycle and the unified workflow)
and `docs/QA_ROUNDS_2026-11-22.md` (all three QA rounds for the two new screens
complete: developer, independent and adversarial/recovery).

| Area | State | Evidence / gap |
|---|---|---|
| Research and licensing | Ready | `docs/research/`, `THIRD_PARTY_NOTICES.md`; no source copied |
| Core authentication and RBAC | Working locally | 99 passing full suite; four security areas reverified |
| Shared event spine and audit log | Working locally | 20 live events with correlation ids, append-only |
| CRM slice | Working locally | Contacts, companies, leads, tasks, notes, timeline; browser tested |
| Capability modules | Backend and UI done locally | Ten modules registered (82 API routes); agent center and integrations screens added and browser tested |
| Frontend | Working locally | Light theme wired to API; all screens browser tested, including the two added post-checkpoint |
| Module wiring into one app | Done | `include_all(app)` in `main.py`; production integration tests pass |
| Persistence | Verified locally | SQLite records and audit history survived a full server restart |
| PostgreSQL | Unverified | No PostgreSQL driver or container test run |
| Migrations | SQLite verified | Revision `6d610706f4ff`; upgrade/downgrade/re-upgrade and `alembic check` passed on SQLite only |
| Containers | Prepared, unverified | `Dockerfile`, `docker-compose.yml`; Docker unavailable |
| Installers / signing / stores | Not started | No binaries published, no credentials |
| External integrations | Not started | No provider credentials; no outbound delivery by design |
| NOVARA's own license | Owner decision open | `LICENSE` intentionally absent |
| Trademark/domain check | Owner decision open | Name availability unverified |

## Gate before any release

1. Every module and frontend file inspected by the orchestrator.
2. All module routers wired into the one app; full suite green.
3. Three testing rounds recorded in `docs/QA_ROUNDS_2026-11-22.md`: developer,
   independent and adversarial/recovery — all complete.
4. Alembic initial revision generated and applied to both SQLite and PostgreSQL.
5. Backup/restore verified with real data.
6. Dependency and secret scans clean; rate limiting added.
7. Container build and local install verified on at least one platform.
8. Owner decisions: NOVARA license, branding availability, signing credentials.
9. Explicit owner authorisation for Git operations and publishing.

No criterion is considered met on assertion alone.
