# NOVARA Desktop Architecture Assessment

**Date:** 2026-11-25  
**Scope:** Desktop Client Edition packaging added to the existing NOVARA repository.  
**Outcome:** A thin Electron shell now wraps the existing FastAPI/SQLite application and its existing plain HTML/CSS/JavaScript client. No second frontend was created.

## Verified starting architecture

- `apps/api/novara_core/main.py` is a FastAPI modular monolith. Core and module routers register before a catch-all route that serves the web client.
- `apps/api/novara_core/database.py` defaults to a project-local SQLite file and honours `NOVARA_DB_PATH`.
- `apps/api/novara_core/modules/storage.py` honours `NOVARA_STORAGE_DIR`.
- `apps/web/index.html`, `apps/web/styles.css` and `apps/web/app.js` are a plain light-theme single-page client. `app.js` uses same-origin API calls when loaded over `http:` or `https:`.
- `GET /health` returns `{"status":"ok","product":"NOVARA"}`.
- The repository already had a static marketing site and a GitHub Pages workflow; neither was replaced.

## Why Electron

Electron was selected because the product already has a browser client. The shell loads that client from the existing backend instead of duplicating screens, state, auth or API calls. The result is one product codebase with a native launcher, not a parallel implementation.

Toolchain pinned in `desktop/package.json`:

| Component | Version |
| --- | --- |
| Electron | 45.5.0 |
| electron-builder | 26.18.0 |
| Application version | 0.1.0-desktop |
| Application id | `online.progvision.novara.desktop` |

## Runtime topology

### Local mode (default)

1. Electron starts a bundled CPython interpreter from `resources/backend/runtime`.
2. It chooses a free loopback port with `127.0.0.1:0`.
3. It launches `uvicorn novara_core.main:app --host 127.0.0.1 --port <port>` from the bundled dependency directory.
4. It polls `/health` before loading `http://127.0.0.1:<port>/`.
5. The existing frontend then calls the API same-origin, using the auth flow that already exists.

Per-user data is isolated through environment variables:

| Data | Location on Windows |
| --- | --- |
| SQLite database | `%APPDATA%\NOVARA\data\novara.sqlite3` |
| Document storage | `%APPDATA%\NOVARA\data\storage` |
| Backend log | `%APPDATA%\NOVARA\backend.log` |
| Settings | `%APPDATA%\NOVARA\settings.json` |

Uninstall deliberately does not delete this user data.

### Remote mode

The shell can instead connect to an operator-supplied `http:` or `https:` NOVARA backend. It validates the URL, rejects embedded credentials, waits for `/health`, and does not start a local Python process. This mode preserves the same client but requires a reachable server.

## Packaged payload

`scripts/prepare_desktop_backend.py` creates `desktop/backend-payload`, which electron-builder copies to `resources/backend`:

```text
resources/backend/
├── deps/          # novara_core plus Python dependencies for the build platform
├── runtime/       # trimmed CPython runtime; bin/python3 on POSIX, python.exe on Windows
├── web/           # existing apps/web client
└── manifest.json  # Python version, dependency folders, runtime flag
```

The `web/` copy is required because `main.py` resolves `WEB_ROOT` relative to `novara_core`. A first local build exposed this as a real defect (`web client is not installed`); the payload script was corrected and the rebuilt installer was re-verified.

## Shell security boundaries

- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`.
- A minimal preload exposes only named IPC methods; no filesystem or Node API is exposed to renderer code.
- Navigation is restricted to the local app files and the selected backend origin. Other http(s) links open in the system browser.
- IPC validates setting keys and URL schemes before use.
- A restrictive CSP is applied to loaded responses.
- Single-instance locking prevents duplicate local backends from competing.
- The backend binds only to loopback and uses an ephemeral port.

See `SECURITY_REVIEW.md` for residual risks.

## Build and CI design

`desktop/package.json` defines real targets:

| Platform | Target | Notes |
| --- | --- | --- |
| Windows x64 | NSIS `.exe` | Per-user by default, optional install directory |
| Linux x64 | AppImage and `.deb` | CI target only in this workspace |
| macOS universal | `.dmg` | Unsigned/ad-hoc in this configuration |

`.github/workflows/desktop-build.yml` runs one backend/client test job, then a Windows/Linux/macOS build matrix. Each matrix leg prepares the backend payload, smoke-tests the bundled interpreter against `/health`, builds the installer, writes `build-manifest.json`, SHA-256 sidecar files and a CSV manifest, then uploads workflow artifacts. It contains no tag, Release, publish, upload-to-external or download-link step.

## Verification position

Windows was built, installed, launched and exercised locally, including first-run setup, navigation, a real CRM write, restart persistence, settings behaviour, uninstall and reinstall. The final installer checksum and size are recorded in `PLATFORM_BUILD_MATRIX.csv` and `DESKTOP_READINESS_REPORT.md`.

Linux and macOS CI is configured, but no artifact for those platforms exists in this workspace. Those platforms remain `UNVERIFIED` until the workflow runs and its artifacts are inspected. Desktop packaging progress does not change NOVARA's product release verdict.
