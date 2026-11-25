<div align="center">
  <img src="site/assets/img/novara-logo.svg" alt="NOVARA" width="260" />
  <h1>NOVARA</h1>
  <p><strong>Everything Connected. Everything Under Control.</strong></p>
  <p>
    <a href="https://ganeshkrishnareddy.github.io/novara/">Project site</a> ·
    <a href="https://github.com/ganeshkrishnareddy/novara/releases/tag/v0.1.0-desktop-ci-preview">Desktop CI preview</a> ·
    <a href="https://github.com/ganeshkrishnareddy/novara/actions/workflows/desktop-build.yml">Build workflow</a>
  </p>
</div>

---

## At a glance

| | |
| --- | --- |
| Status | Active development; not a release candidate |
| Deployment | Local-first SQLite install; container and PostgreSQL paths are prepared but unverified |
| Verified locally | Backend suite, browser walkthrough, and a Windows desktop preview installer |
| Not verified | Linux/macOS CI artifacts, signed installers, hosted deployment, and live provider integrations |
| Repository licence | Pending owner decision |

## What NOVARA is

NOVARA is a self-hostable business operating system being built as one connected application rather than a stack of separate tools. It provides a shared customer identity, workspace and permission model, event spine, and analytics stream for CRM, sales, marketing, support, feedback, projects, documents, automation, and governed local AI agents.

The project is local-first by design. A default install needs no hosted account, API key, Redis, PostgreSQL, or Docker. Data stays in a SQLite file in the project folder unless another database is configured explicitly.

## What works today

- **Shared foundation:** first-run setup, registration, login/logout, bcrypt password hashing, revocable sessions, refresh rotation, password reset, workspace membership and invitations, seven workspace roles, and cross-workspace denial.
- **Connected customer record:** contacts, companies, notes, lead lifecycle, tasks, notifications, audit events, and a unified customer timeline built on one append-only event log.
- **Capability modules:** CRM, sales, marketing, support, feedback, projects, documents, analytics and experimentation, search, notifications, automation, integrations, and a governed AI agent centre, all registered through one FastAPI application.
- **One observed end-to-end workflow:** website form → contact → lead → task → notification → outreach draft → authorised approval → audit trail. NOVARA does not send external messages from the core service.
- **Local intelligence:** universal search, local feature flags and experiments, durable jobs, and agent runs with step limits and human approval.
- **Developer surface:** FastAPI with generated OpenAPI documentation, SQLAlchemy models, Alembic migrations, and a documented module contract.

Provider-backed capabilities remain explicitly blocked until a real provider is configured and verified. No delivery is simulated as successful.

## Quick start

Requires Python 3.11 or newer (3.12 recommended) and a modern browser.

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "./apps/api"
.\.venv\Scripts\python -m uvicorn novara_core.main:app --host 127.0.0.1 --port 8000
```

```sh
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -e "./apps/api"
.venv/bin/python -m uvicorn novara_core.main:app --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000> and complete first-run setup. The API documentation is at <http://localhost:8000/docs>. A local SQLite database is created in the project folder; no hosted service or licence key is required.

To run the backend suite:

```sh
python -m pip install -e "./apps/api[dev]"
python -m pytest apps/api/tests -q
```

Container definitions and PostgreSQL configuration are present in the project history, but container builds and live PostgreSQL deployment have **not** been verified in this environment.

## Desktop preview

The `desktop/` folder contains an Electron shell that starts the bundled NOVARA backend and serves the existing web client from the same process. `.github/workflows/desktop-build.yml` defines a four-leg native build matrix: Windows x64, Linux x64, macOS x64, and macOS arm64, with backend checks, payload smoke tests, checksums, manifests, and run-scoped artifact uploads.

A Windows x64 installer was built and install-tested locally. Linux and macOS native artifacts are **CI-configured only**; no successful runner result, artifact, or checksum exists for them yet.

The native CI scope is published as a [prerelease](https://github.com/ganeshkrishnareddy/novara/releases/tag/v0.1.0-desktop-ci-preview) from commit `c6e68da`. It is unsigned, attaches no binaries, and is not a production release.

## Documentation

- [Public project site](https://ganeshkrishnareddy.github.io/novara/) — product overview, workflows, FAQ, and local-install guidance
- [Project status](docs/PROJECT_STATUS.md) — phase-by-phase implementation state
- [Test results](docs/TEST_RESULTS.md) — commands actually run and their recorded results
- [Blockers and decisions](docs/BLOCKERS.md) — what remains open
- [Native CI preparation review](docs/DESKTOP_RELEASE/CI_NATIVE_PREP_REVIEW.md) — desktop workflow scope and remaining gates
- [Third-party notices](THIRD_PARTY_NOTICES.md) and [licence compliance review](docs/research/LICENSE_COMPLIANCE.md)

## Known boundaries

NOVARA is not production-ready. The repository licence is still an owner decision; external provider credentials, signing identities, notarisation, container verification, live PostgreSQL, and non-Chromium browser testing remain open. There is no hosted SaaS, managed backup service, native mobile installer, or outbound notification delivery in this build. Capability descriptions reflect local implementation and parity evidence, not claims of upstream integrations.

## Reference projects

Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu, Marketing Skills, and Sellbird informed the capability scope. Their licences and NOVARA's clean-room replacements are documented in the files linked above. No source code from those projects was copied into NOVARA.

## Contributing

Issues and pull requests are welcome. Review is based on reproducible work, not stars or follows, and no feature is locked behind social engagement. Contribution criteria are described on the [project site](https://ganeshkrishnareddy.github.io/novara/#contribute).

## Git and release policy

The native desktop CI scope was merged into `main` on 25 November 2026. A public prerelease tag, `v0.1.0-desktop-ci-preview`, identifies that commit. No full production release, signed binary, force-push, or history rewrite was performed. Product code is published only with owner authorisation.
