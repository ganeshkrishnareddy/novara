# NOVARA

**Everything Connected. Everything Under Control.**

NOVARA is being built as one open-source, self-hostable business operating
system: a shared customer identity, workspace, permission model, event spine and
analytics stream for CRM, sales, marketing, support, feedback, projects,
documents, automation and governed AI agents — not ten separate apps linked
together.

## Current status

**Active development. This is not a release candidate.**

- The authenticated core is implemented and locally tested: first-run setup,
  registration, login/logout, bcrypt hashing, revocable sessions, refresh
  rotation, password reset, workspace membership/invitations, seven
  workspace-scoped roles, CRM, tasks, notifications, audit log and a unified
  customer timeline.
- One connected workflow runs end to end: website form → one contact → lead →
  task → notification → outreach **draft** → authorised approval → audit events.
  NOVARA never sends an external message from the core service.
- Capability modules and the light-theme web app are being built in parallel
  against `docs/architecture/MODULE_CONTRACT.md`.
- Research and licensing are complete; no source was copied from the ten
  reference repositories.

See `docs/PROJECT_STATUS.md` for the honest phase state,
`docs/TEST_RESULTS.md` for commands and results, and `docs/BLOCKERS.md` for what
is still missing.

## Run locally (no Docker, no database setup)

Windows PowerShell:

```powershell
.\scripts\start-local.ps1
```

macOS / Linux / Termux:

```sh
sh scripts/start-local.sh
```

Then open <http://localhost:8000>. The installed API docs are at
<http://localhost:8000/docs>. A private NOVARA license, hosted account or API
key is not required.

Container definitions are provided in `Dockerfile` and `docker-compose.yml`,
but container builds have not been verified in this environment. See
`docs/INSTALL.md`.

## Ten reference projects

Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu,
Marketing Skills and Sellbird. Metadata is in
`docs/research/REPOSITORY_AUDIT.md`; license decisions are in
`docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`. No source
code from these projects has been copied into NOVARA.

## Git policy

Product code is kept local until the full product is complete and the owner
authorises commit and push. No release tags or binaries are published.
