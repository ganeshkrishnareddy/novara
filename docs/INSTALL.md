# Installing NOVARA locally

NOVARA is local-first. Basic use needs no hosted account, license key,
PostgreSQL, Redis or Docker. All data stays in a single SQLite file in the
project unless you deliberately configure PostgreSQL.

## What you need

- Python 3.11 or newer (3.12 recommended)
- A modern browser

Nothing else is required for the default local install.

## Windows 10/11

1. Install Python from <https://www.python.org/downloads/> and tick **Add Python to PATH**.
2. Open PowerShell in the `NOVARA` folder.
3. Run:

   ```powershell
   .\scripts\start-local.ps1
   ```

4. Open <http://localhost:8000> and complete the first-run setup.
5. Stop the server with `Ctrl+C`.

If PowerShell blocks the script, run
`powershell -ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -File .\scripts\start-local.ps1`.

## macOS

1. Install Python 3.12 with `brew install python@3.12` or from python.org.
2. Open Terminal in the `NOVARA` folder.
3. Run:

   ```sh
   sh scripts/start-local.sh
   ```

4. Open <http://localhost:8000> and complete first-run setup.

## Linux

1. Install `python3` and `python3-venv` with your package manager.
2. Open a terminal in the `NOVARA` folder.
3. Run `sh scripts/start-local.sh`.
4. Open <http://localhost:8000>.

## Android / iOS

There are no native mobile apps in this build. On the same Wi-Fi network you
can open the web app in a mobile browser using the computer's LAN address,
for example `http://192.168.1.20:8000`. The local server binds to
`127.0.0.1` by default, so change the host in `scripts/start-local.sh` or run
`uvicorn novara_core.main:app --host 0.0.0.0 --port 8000` explicitly to allow
LAN access. Only do this on a trusted network; authentication tokens are sent
in HTTP headers and TLS is not configured by default.

## Optional: Docker

`Dockerfile` and `docker-compose.yml` are provided:

```sh
docker compose up --build
```

The default compose service uses a named SQLite volume and needs no database
container. PostgreSQL is opt-in with `docker compose --profile postgres up`.
Docker builds and container runs are **not verified** in the development
environment; treat this path as preparatory until tested.

## Optional: PostgreSQL

The same SQLAlchemy models run on PostgreSQL. Install the driver and set the
URL before starting:

```sh
pip install 'psycopg[binary]>=3.1'
export NOVARA_DATABASE_URL='postgresql+psycopg://user:password@host:5432/novara'
alembic -c apps/api/alembic.ini upgrade head
```

Alembic is configured; the migration head is `e0f1a2b3c4d5` (single head). Run
`python -m alembic upgrade head` from `apps/api` (the Alembic script location is
relative). PostgreSQL compilation of all tables is verified, but a **live**
PostgreSQL server has not been tested here. See `docs/DEPLOYMENT_RUNBOOK.md`.

## Where data lives

- Default database: `<PROJECT_ROOT>/novara_dev.sqlite3` (for this checkout,
  `D:\NOVARA\novara_dev.sqlite3`) or the path in `NOVARA_DB_PATH`. The path is
  resolved from the installed package, not the working directory, so starting
  uvicorn from `apps/api` uses the same file.
- Passwords are stored as salted bcrypt hashes; tokens are stored as SHA-256 hashes.
- Never commit the SQLite file or `.env`; both are ignored by Git.

## Document metadata quickstart

Documents in NOVARA are **metadata records**, not file storage. You register a
title, type and an opaque storage reference that only you understand (for
example `metadata://local/proposal.pdf`). NOVARA never opens, uploads, serves or
emails the underlying file. Share links carry policy and record engagement;
they do not deliver file bytes.

This walkthrough works on a fresh local install with no external services. It is
also exercised end to end by `tests/test_documents_p0.py`.

1. Sign in and open **Documents** in the sidebar (Revenue group). Your role
   needs `document:read`; creating records additionally needs `document:write`.
2. Click **New room** and name it, for example `Sales collateral`. Rooms group
   related records; you can leave a document unfiled.
3. Click **Add document**. Enter a title such as `Overview.pdf`, choose a type,
   and set a storage reference you control. The size in bytes is optional.
   Nothing is uploaded.
4. Open the document and click **New share link**. Choose your controls:
   - **Password** — visitors must unlock the link before viewing.
   - **Expires in hours** — the link stops working after that time.
   - **Maximum views** — a hard cap on recorded visits.
   - **View only** — the record is presented as read-only.
   - **Allow recorded downloads** — permits a download *event*. NOVARA still
     serves no file bytes.
5. After the link is created, copy the share token once. It is shown only once
   and is not kept in the browser. Store it wherever you keep local secrets.
6. Record a visit with `POST
   /api/v1/workspaces/{workspace_id}/documents/links/resolve/{token}/visits`.
   Supply a `visitor_email` if you know it. NOVARA reuses an existing CRM
   contact with that email, or creates one, so the visitor has a single
   identity. The visit publishes a `document.viewed` event; if the visitor is
   known, that event also appears on the customer's contact timeline and
   creates an in-app notification for the person who shared the link.
7. Optionally record a page view with `.../visits/{visit_id}/page-views`, and a
   download with `.../visits/{visit_id}/download`. A download is rejected with
   HTTP 403 when **Allow recorded downloads** is off.
8. Return to the document detail page to see share links, view caps, revocation
   and aggregated page engagement. The sharing user sees the document
   notification in **Notifications**.

Revoking a link immediately blocks new visits even if it has not expired.
Deleting a data room that still contains documents is refused; delete or move
the records first. All of these actions are local and produce only local events
and notifications — no email, SMS or other external message is sent.

## Troubleshooting

- **`python: command not found` on Windows** — reinstall Python with “Add Python to PATH”.
- **Port 8000 already in use** — stop the other service or pass a different
  port to `uvicorn`.
- **ModuleNotFoundError: novara_core** — the start scripts set `PYTHONPATH`;
  if starting manually, run from `apps/api` or use `--app-dir apps/api`.
- **First-run setup says setup already completed** — the local database already
  has an owner. Use the login screen instead, or remove the SQLite file only
  if you intentionally want to discard all local data.

## Privacy

NOVARA does not phone home. No telemetry, activation check, hosted account or
mandatory subscription exists. Optional external integrations require your own
credentials and are disabled unless you configure them.
