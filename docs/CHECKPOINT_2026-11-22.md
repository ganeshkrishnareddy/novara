# NOVARA checkpoint report — 2026-11-22

Scope: Phase 1 security reverification, live application validation, persistence,
migrations and the unified workflow. All work local; no commits or pushes.
Git HEAD remained `73e9f76` throughout.

> Point-in-time report. The two screens listed as absent in section 5 were added
> later the same day, and all three QA rounds are now complete; see
> `docs/QA_ROUNDS_2026-11-22.md` and `docs/PROJECT_STATUS.md` for current state.

## 1. Test results

| Stage | Command | Result |
|---|---|---|
| Baseline at start of checkpoint | `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'` | 96 passed |
| After security regression coverage | same | 97 passed, then 99 passed |
| Final run after all changes | same | **99 passed, 1 warning in 36.32s** |

The single remaining warning is a `StarletteDeprecationWarning` from
`fastapi/testclient.py` recommending `httpx2`. It is upstream, not a failure.

## 2. Security reverification

| Area | Evidence | Result |
|---|---|---|
| A — Workspace bootstrap | `test_invalid_emails_empty_workspace_names_and_bad_roles_are_rejected` | Empty and whitespace-only names rejected with 422; valid name accepted |
| B — Email validation | same test plus `test_email_normalization_and_legitimate_addresses` | Malformed and embedded-whitespace addresses rejected; case normalised; legitimate addresses preserved |
| C — Owner assignment | `test_owner_assignment_requires_active_same_workspace_member` | Company, lead, contact and task owners must be active members of the same workspace; other-workspace, inactive and nonexistent users rejected |
| D — Workspace authorisation | `test_cross_workspace_access_is_denied_for_every_scoped_resource`, `test_cross_workspace_write_is_denied`, `test_integration.py::test_module_routes_enforce_workspace_isolation`; code inspection of `dependencies.py` and `main.py` | One shared `verify_workspace()` helper in `dependencies.py`; the duplicate in `main.py` is gone; all scoped routes use the shared helper |

No new security defect was found in this checkpoint.

## 3. Files changed in this checkpoint

- `apps/web/app.js` — company list now shows a stored website value even when it
  has no URL scheme, instead of rendering a dash. Verified live in a fresh tab.
- `apps/api/migrations/versions/6d610706f4ff_initial_schema.py` — generated
  initial Alembic revision covering 35 tables and all workspace indexes.
- `docs/PROJECT_STATUS.md`, `IMPLEMENTATION_STATUS.md`, `TEST_RESULTS.md`,
  `SECURITY_REPORT.md`, `BLOCKERS.md`, `RELEASE_READINESS.md`, this report.

No Git commit, push, tag, force-push or history rewrite was performed.

## 4. Live browser walkthrough

The app was served from `http://localhost:8000` by its existing local uvicorn
startup command. `/health` returned `{"status":"ok","product":"NOVARA"}`.
Database engine in use: **SQLite** at `D:\NOVARA\novara_dev.sqlite3`.

| Screen / journey | Result |
|---|---|
| Open app, session restore | Pass — token refresh then authenticated dashboard |
| Register new user | Pass — local `qa.owner@example.com` account with workspace |
| Log in / log out / log in again | Pass (earlier pass, confirmed in server log) |
| Create workspace | Pass — two workspaces exist |
| Dashboard | Pass — live counts, audit events, recent contacts, open tasks |
| Create contact | Pass |
| Contact detail | Pass — profile, company, phone, tags, notes, unified timeline with correlation IDs |
| Edit contact | Pass — `Browser Contact Updated` record shows edited fields and an audit event |
| Create company | Pass — `Novara QA Holdings` created; empty-required-field validation also confirmed |
| Create and assign lead | Pass |
| Create task | Pass |
| View notifications | Pass — unread counts, individual and bulk mark-read |
| Open outreach drafts | Pass — draft and approved states |
| Agent activity | Pass — 20 append-only events with correlation IDs and type filter |
| Profile | Pass — identity, role, permissions, account actions |
| Settings | Pass — workspace info, password change, verification, sign out, members |
| Workspaces and workspace switching | Pass — switched to `QA Second Workspace` and back, each with password confirmation; second workspace showed correct isolated empty states |
| Validation and loading states | Pass — required fields block submit; `Working…` shown during actions; empty states render |
| Console / network | Clean on reload — no failed requests or page errors |

### Not implemented in the UI

- **AI agent center** — no screen exists. Backend module `novara_core/modules/agents.py`
  and its routes are registered, but there is no frontend route or link.
- **Integrations** — same: backend module exists, no frontend screen.

These are reported as incomplete rather than tested as working.

### Responsive layouts

The built-in browser surface has no viewport emulation, so live desktop/tablet/
mobile resizing could not be performed. Static inspection confirmed breakpoints
at 1180, 980, 900, 680 and 480px, including an off-canvas sidebar with scrim
below 900px and single-column stats/forms on small screens. Actual device-width
rendering remains unverified.

## 5. Persistence and migrations

**Persistence (SQLite):** before the restart the database held 1 user, 2 workspaces,
3 contacts, 2 companies, 2 leads, 3 tasks, 1 notification, 1 draft and 14 events.
The server was stopped and started again; the browser session refreshed and the
same records and audit events were still present. Workspace isolation remained
enforced after restart. No audit or timeline history was lost.

**Migrations:** the Alembic extra (`pip install -e "apps/api[migrate]"`, alembic
1.20.1) was installed into the project virtual environment and an initial
revision generated. On a separate clean SQLite database:

- `alembic upgrade head` → revision `6d610706f4ff`, 35 tables, core tables present
- `alembic downgrade base` → revision cleared, only `alembic_version` remains
- `alembic upgrade head` again → 35 tables restored
- `alembic check` → "No new upgrade operations detected" (no model/schema drift)

Only SQLite was exercised. PostgreSQL and container behaviour remain unverified.

## 6. Unified workflow (live, post-restart)

"Record intake" was run through the UI with a fresh submission. One workflow run
created a contact (`cb21620a`), lead (`6238c8ed`), task (`b707561b`), notification
(`b6b3b7d5`) and outreach draft (`7a983f97`) under correlation id
`d9904afd-62ee-470a-b668-f85edee17548`. The draft was then approved; the app
reported "Draft approved. Nothing was sent externally." Notifications were marked
read. Final counts: 4 contacts, 3 leads, 4 tasks, 2 notifications, 2 drafts,
20 events. No outbound delivery adapter exists or was invoked.

## 7. Evidence

- Screenshots: `novara-dashboard.png`, `novara-agent-activity.png`,
  `novara-companies.png` (working folder).
- Server request log: `novara-server.log` (working folder) and the live console log.
- Command outputs recorded in sections 1, 5 and 6.

## 8. Remaining blockers

- AI agent center and integrations frontend screens absent.
- Three independent QA rounds with written evidence are not complete; this
  checkpoint is developer verification plus a live browser walkthrough.
- Docker unavailable, so container build/run and PostgreSQL remain unverified.
- Installers, signing, store publication not built.
- External provider credentials absent; no outbound delivery by design.
- Rate limiting, dependency and secret scans not done.
- Owner decisions open: NOVARA license, trademark/domain availability.

## 9. Next milestone

Build the missing agent-center and integrations UI screens against the already
registered backend routes, then run the three documented QA rounds and verify
PostgreSQL with a real container. Keep all work local until the owner authorises
Git operations.
