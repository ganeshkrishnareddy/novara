# NOVARA deployment runbook (preparation only)

Date: 2026-11-22. This document prepares a repeatable local deployment. It does
**not** record a real deployment: nothing was published, registered, purchased
or exposed to the internet. Every step below was exercised against a local
uvicorn process and the local SQLite file unless explicitly marked unverified.

## 1. Scope and honest status

| Item | Status |
|---|---|
| Local uvicorn start + login + full UI walkthrough | Verified locally 2026-11-22 |
| Config template (`.env.example`) | Provided; all settings optional locally |
| Schema management (Alembic head `9951aadc14c8`) | Verified on SQLite; `alembic check` clean |
| Backup / verify / restore drill | Verified on isolated SQLite files in Phase 2 |
| Production web host, TLS, domain | **Not done** — owner decision pending |
| PostgreSQL live server | **Not verified** — no driver/server installed |
| Docker image build / container run | **Not verified** — Docker unavailable |
| Installer, code signing, app store | **Not done** — credentials/authority absent |
| Outbound email / WhatsApp / SMS / AI providers | Intentionally disabled — local mocks only |

## 2. Prerequisites

- Python 3.11+ (3.12 used in verification).
- A modern browser for the web UI.
- For PostgreSQL only: `pip install 'psycopg[binary]>=3.1'` and a reachable server.

## 3. Configuration

1. Copy `.env.example` to `.env` in the project root.
2. Leave every value unset for the default local install. The API reads these
   variables:

   | Variable | Purpose | Default |
   |---|---|---|
   | `NOVARA_DB_PATH` | SQLite file path | `<PROJECT_ROOT>/novara_dev.sqlite3` |
   | `NOVARA_DATABASE_URL` | Optional PostgreSQL DSN | unset (SQLite) |
   | `NOVARA_CORS_ORIGINS` | Comma-separated cross-origin allow-list | same-origin only |
   | `NOVARA_AUTH_RATE_LIMIT` | Auth attempts per client per window | 10 |
   | `NOVARA_DEV_MODE` | Local seed/setup convenience endpoints | off |

3. Keep `NOVARA_DEV_MODE` off for anything but local development.
4. Do not put provider credentials in `.env`; adapters are local mocks in this
   build and no credential is used.

## 4. Start (local, verified)

```powershell
$env:PYTHONPATH='D:\NOVARA\apps\api'
python -m uvicorn novara_core.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The API serves the SPA on the same origin, so the
frontend makes same-origin API calls (no hardcoded `localhost`, no CORS needed).

For schema changes, run migrations first from `apps/api` (the Alembic script
location is relative):

```powershell
$env:PYTHONPATH='D:\NOVARA\apps\api'
python -m alembic upgrade head
python -m alembic check
```

The container image carries `alembic.ini` and `migrations/`, installs the
`migrate` extra, and its startup command runs `alembic upgrade head` before
uvicorn, so a fresh container receives a version-stamped schema rather than an
unstamped `create_all()` database. This change is **inspection-verified only**:
Docker is unavailable here (B-01), so no image build or container run confirmed
it. Do not treat the container path as tested.

## 5. Readiness checks (local)

- `GET /health` → `200 {"status":"ok","product":"NOVARA"}`.
- Security headers present on responses: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive
  `Content-Security-Policy`.
- Login with a local account, then confirm the Overview, Insights, Job queue,
  Adapters and System health views load with real stored counts.
- System health must still report adapters as **Local Mock**, AI providers and
  containers as **Blocked**, and database/job queue as **Local**.

## 6. Backup before any change

```powershell
python D:\NOVARA\scripts\backup_restore.py backup `
  --db D:\NOVARA\novara_dev.sqlite3 --out D:\NOVARA\backups
python D:\NOVARA\scripts\backup_restore.py verify `
  --db D:\NOVARA\backups\<backup-file>.sqlite3
```

The backup uses SQLite's online API, so the app need not be stopped. It prints
integrity, Alembic revision and audited row counts. `backups/` is outside the
tracked product code; store it somewhere durable for anything you care about.

## 7. Rollback (local, verified procedure)

1. Stop the running server (`Ctrl+C`).
2. Restore **into a new file** first; the tool refuses to overwrite by default:

   ```powershell
   python D:\NOVARA\scripts\backup_restore.py restore `
     --from D:\NOVARA\backups\<backup-file>.sqlite3 `
     --to   D:\NOVARA\novara_restored.sqlite3
   ```

3. Verify the printed counts and revision match the backup.
4. To make the restored file the active one, point config at it explicitly:

   ```powershell
   $env:NOVARA_DB_PATH='D:\NOVARA\novara_restored.sqlite3'
   ```

   Only replace the original file directly (`--force`) after a separate verified
   copy exists and you intend to discard newer data.

5. Restart the server and repeat the readiness checks in section 5.

For a **code** rollback, no Git history was rewritten: the original HEAD is
`73e9f76`. All Phase 2/3 work is local and uncommitted, so a code rollback means
stashing or removing those uncommitted changes deliberately — it is not an
automated step in this runbook, and it was not performed.

## 8. Known limits to resolve before a real deployment

- Choose production infrastructure, domain and TLS; bind to a trusted network.
- Run the untested Docker/PostgreSQL paths on target infrastructure. In
  particular, confirm the container's startup `alembic upgrade head` against a
  fresh `/data` volume and against a volume restored from an older backup.
- Re-run the full backend suite and this runbook on the target host.
- Decide licence, trademark and domain availability.
- Add real provider credentials only through a documented secret process; keep
  mock/blocked distinctions visible in the UI.
