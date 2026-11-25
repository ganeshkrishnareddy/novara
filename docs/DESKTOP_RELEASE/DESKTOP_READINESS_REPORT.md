# NOVARA Desktop Release Readiness Report

**Date:** 2026-11-25  
**Repository state:** branch `main`, working tree already dirty before this work; all new changes remain uncommitted. No commit, push, tag, GitHub Release, signature, publication or binary upload was performed.  
**Product verdict:** unchanged. Desktop packaging is not a product release decision.

## Executive summary

- The Electron desktop client is implemented around the **existing** FastAPI backend and plain HTML/CSS/JavaScript web client. No second frontend was created.
- Windows x64: the final hardened NSIS installer was built, installed, launched and exercised locally. It is unsigned and unpublished.
- Linux and macOS: CI is configured with real build targets, payload smoke tests, checksums, manifests and workflow-artifact upload. **No workflow run, run ID, URL, artifact or checksum exists in this workspace**, so both platforms are `CI_CONFIGURED_UNVERIFIED`.
- The fresh full backend suite was rerun after the hardening changes: **1,649 passed, 0 failed, 4 warnings in 1,480.05s (0:24:40), exit 0**.
- No platform is install-ready for public distribution on the evidence currently available.

## Scope decisions

Electron 45.5.0 with electron-builder 26.18.0 was selected because it reuses the existing client. The shell starts the existing API on a loopback-only port, waits for `/health`, and loads `http://127.0.0.1:<port>/` so the client continues to make same-origin API calls. Remote-backend mode remains available through validated settings and now requires HTTPS except for loopback development addresses.

Hardening added after the earlier preview build:

- A unique 43-character presign secret is generated per installed application-data directory and passed to the bundled backend as `NOVARA_PRESIGN_SECRET`; the generated value is not embedded in the app bundle.
- Remote mode rejects non-loopback `http://` URLs at both save time and connection time.
- Logs redact bearer tokens, query-string secrets and the generated presign secret.
- CSP `connect-src` is limited to `'self'` plus the active backend origin; broad `ws:`/`wss:` allowances were removed because the current client uses streaming `fetch`, not WebSockets.
- On POSIX hosts, the application data directory, secret file, SQLite database and storage directory use restrictive permissions where supported.

## Files added or changed by this track

- `desktop/package.json`, `desktop/package-lock.json`
- `desktop/src/main.js`, `preload.js`, `ui.js`, `styles.css`
- `desktop/src/loading.html`, `settings.html`, `about.html`
- `desktop/build/generate_icon.py`, `icon.png`, `icon.ico`
- `scripts/prepare_desktop_backend.py`
- `scripts/smoke_desktop_payload.py`
- `scripts/write_desktop_build_manifest.py`
- `.github/workflows/desktop-build.yml`
- `apps/api/tests/test_cw035_visitor_conversation_p1.py` (narrowed a stale global string assertion to the ticket views it protects)
- `site/index.html` (download section updated to state the real Windows build status; still no download links)
- `docs/DESKTOP_RELEASE/*.md`, `PLATFORM_BUILD_MATRIX.csv`
- `docs/evidence/desktop-*`

`README.md` was **not** edited in this track.

## Verification evidence

Exact commands and outcomes observed on 2026-11-25:

| Check | Command | Exit / result |
| --- | --- | --- |
| Icon generation | `python -m pip install Pillow --quiet; python desktop/build/generate_icon.py` | 0; wrote `icon.png` (4,846 bytes) and `icon.ico` (23,749 bytes) |
| Electron install | `npm install --no-audit --no-fund` in `desktop/` | 0; 283 packages; deprecation warnings and one `allow-scripts` notice for `electron-winstaller` |
| Backend payload | `python scripts/prepare_desktop_backend.py` | 0; created `deps`, trimmed `runtime`, `web`, `manifest.json` |
| Payload smoke, hardened build | `python scripts/smoke_desktop_payload.py` | 0; `PASS: /health {"status":"ok","product":"NOVARA"}`; evidence `desktop-payload-smoke-hardened-20261125.txt` |
| Client syntax | `node --check apps/web/app.js` | 0 |
| Shell syntax, final | `node --check desktop/src/main.js`; `node --check desktop/src/preload.js`; `node --check desktop/src/ui.js` | 0 for each; evidence `desktop-hardening-final-verification-20261125.txt` |
| Python script syntax | `python -m py_compile scripts/prepare_desktop_backend.py scripts/smoke_desktop_payload.py scripts/write_desktop_build_manifest.py` | 0 |
| Windows build, final | `npm run build:win` in `desktop/` | 0; warnings: missing `author`, no code-signing certificate configured; evidence `desktop-windows-build-hardened-final-20261125.txt` |
| Build manifest, final | `python scripts/write_desktop_build_manifest.py --platform windows --arch x64` | 0; wrote JSON, CSV and installer `.sha256` (no separate manifest checksum sidecar is produced); evidence `desktop-windows-manifest-hardened-final-20261125.txt` |
| CI workflow parse | Python `yaml.safe_load` on `.github/workflows/desktop-build.yml` | 0; jobs `backend-tests,desktop-build`; matrix `windows,linux,macos` |
| Alembic head | `cd apps/api; python -m alembic -c alembic.ini heads` | 0; single head `b5c6d7e8f9a0 (head)` |
| Site validator, final | `python scripts/validate_site.py` | 0; 35 passed, 0 failed, 0 warnings, 15 informational notes; evidence `desktop-site-validator-hardened-20261125.txt` |
| Full backend suite, earlier fresh run after migration | `PYTHONPATH=D:\NOVARA\apps\api; D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests -q` | **1**; 1 failed, 1,648 passed, 4 warnings in 1,251.00s. Failure was the stale `whatsapp`-anywhere assertion in `test_cw035_visitor_conversation_p1.py`; the later marketing migration legitimately added WhatsApp as a local delivery channel. |
| Targeted regression after narrowing assertion | `python -m pytest apps/api/tests/test_cw035_visitor_conversation_p1.py -q` | 0; 1 passed, 1 warning in 1.42s |
| Full backend suite, pre-hardening rerun | same command; `desktop-fullsuite-final-20261125.txt` | **0**; 1,649 passed, 0 failed, 4 warnings in 1,247.14s (0:20:47) |
| Full backend suite, final after hardening | same command; `desktop-hardened-fullsuite-20261125.txt`, exit file `desktop-hardened-fullsuite-exit.txt` | **0**; 1,649 passed, 0 failed, 4 warnings in 1,480.05s (0:24:40) |
| npm audit, packaged runtime, final | `npm audit --omit=dev --json` in `desktop/` | 0; 0 vulnerabilities; evidence `desktop-npm-audit-final-prod-20261125.json` |
| npm audit, build toolchain, final | `npm audit --json` in `desktop/` | 1 from audit findings; 6 moderate, 0 high, 0 critical in the electron-builder dev chain only; evidence `desktop-npm-audit-final-all-20261125.json` |
| Python dependency scan | `python -m pip_audit --path=D:\NOVARA\desktop\backend-payload\deps --format json -o docs/evidence/desktop-python-audit-payload-20261125.json` | 0; 18 audited dependencies with 0 vulnerabilities; local `novara-core` skipped because it is not on PyPI; 0 fixes; evidence `desktop-python-audit-payload-20261125.json` |
| Cross-platform payload review | `python -m py_compile ...` plus payload inspection | 0; POSIX executable bits, layout, deps, userData write paths and shutdown handling reviewed; native POSIX smoke remains CI-only |
| Environment capability check | `wsl.exe -l -v`, `Get-Command gh` | WSL class not registered / no distro; `gh` unavailable. Native Linux/macOS builds and read-only CI-run inspection could not be performed from this host. |

The full-suite warnings were the existing Starlette/httpx test-client deprecation, two `HTTP_422_UNPROCESSABLE_ENTITY` deprecations in marketing local capabilities, and one Alembic `path_separator` deprecation. None is introduced by the desktop shell.

## Windows artifact evidence — earlier hardened milestone (superseded)

The values in this section belong to the earlier hardened milestone and are retained only as history. The current post-security-fix values are in the next-stage addendum below and in `NEXT_STAGE_REPORT.md`.

| Field | Value |
| --- | --- |
| Path | `desktop/dist/NOVARA-Setup-0.1.0-desktop-x64.exe` |
| Name | `NOVARA-Setup-0.1.0-desktop-x64.exe` |
| Size | 146,465,056 bytes |
| SHA-256 | `4FEF61F2968746A664535F4280E504A044523BE640B399E50E0CC859C8574858` |
| Signed | No |
| Published | No |
| Manifest | `signed: false`, `published: false`; checksum matches the exact installer |

This final hardened artifact supersedes the earlier pre-hardening checksum `8563435A3FE795548D3F2F93DEED06FC5D03E5D278BECE9596D30603FD5A5077`. Do not use the earlier hash.

Install/launch verification on the exact final artifact (`docs/evidence/desktop-windows-hardened-qa-20261125.txt` and `desktop-windows-hardened-mode-qa-20261125.txt`):

- Silent install exit `0`; `resources/backend/web/index.html` and `resources/app.asar` present.
- Window title reached `NOVARA - Everything Connected. Everything Under Control.`
- Bundled backend on `http://127.0.0.1:53232` returned `{"status":"ok","product":"NOVARA"}`; `GET /` returned `200` with the real client title.
- Built-in browser sign-in loaded the dashboard; Contacts navigation worked and a real contact (`hardened.qa@novara.local` / `Hardened QA Contact`) was created and read back.
- `secrets.json` was created outside the app bundle with a 43-character secret; the generated value was absent from `app.asar` and was never printed in evidence.
- A non-loopback `http://` remote setting did not connect or start a backend; a loopback plain-HTTP setting reached the connection screen without backend startup, as expected for a refused port; local mode restored the dashboard and backend.
- Uninstall exit `0` removed the executable; reinstall exit `0` restored it. The SQLite database and secret file remained in the user data folder; an explicit recheck is in `desktop-windows-hardened-data-retention-20261125.txt`.
- For that earlier hardened build, the checksum remained `4FEF61F2968746A664535F4280E504A044523BE640B399E50E0CC859C8574858` after reinstall.

## Platform readiness

| Platform | Configured | Workflow run ID/URL | Build | Artifact + checksum | Install/launch tested | Signed/notarized | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Windows x64 | Yes | No (local npm build instead) | Succeeded locally | Yes, matched manifest | Yes, on exact final artifact | No | `desktop-windows-hardened-qa-20261125.txt`, `desktop-windows-hardened-mode-qa-20261125.txt` |
| Linux x64 | Yes | None | Not verified | No artifact | No | No | Workflow inspected only; no CI run |
| macOS universal | Yes | None | Not verified | No artifact | No | No | Workflow inspected only; no CI run |

See `PLATFORM_BUILD_MATRIX.csv` for the machine-readable matrix. No download link was added to the website; its download section says the Windows preview was built locally and nothing is published, while Linux/macOS show CI-configured status.

## Security position

The shell uses context isolation, no Node integration, a sandboxed preload, strict navigation allow-listing, validated IPC, a restrictive origin-scoped CSP, loopback-only local backend binding, a generated per-install presign secret, log redaction and per-user data isolation. Residual items are documented in `SECURITY_REVIEW.md`: unsigned artifacts, no auto-update, `localStorage` tokens, unencrypted local data, deployment secrets outside the desktop default, and inherited backend/client behaviour.

## Readiness conclusion

The desktop **preview** is implemented and the Windows build is genuinely verified on this machine. It is not a public release: no platform has a signed, notarized, auto-updating, published artifact. Linux and macOS remain unverified until the configured workflow runs. Owner actions required before distribution are listed in `OWNER_ACTION_CHECKLIST.md`.

**Desktop readiness verdict:** `PARTIALLY VERIFIED` — Windows local evidence is complete; Linux and macOS are CI-configured only, and no platform is signed, published or install-ready for public distribution. This verdict is separate from, and does not alter, the NOVARA product release gate.

## Next-stage verification addendum — 2026-11-25

The table above records the earlier hardened milestone and is retained as history. After additional security fixes, the bundled backend payload was regenerated and the Windows installer rebuilt from the current source. An intermediate post-fix build (`9c4cf82b...068`, 146465241 bytes) was superseded after the permission deny-list was made platform-independent. The current final artifact is `NOVARA-Setup-0.1.0-desktop-x64.exe`, size `146465197` bytes, SHA-256 `b291e32ec0e02db640aa1e837fe8f396a4920cc2e75f9517d556c7c8cc05f6d6`; `desktop/dist/build-manifest.json` and the `.sha256` file match. Evidence: `docs/evidence/stage2-windows-final2-build-20261125.txt` and `stage2-windows-final2-manifest-20261125.txt`.

A fresh local install/launch test with poisoned inherited environment variables succeeded: install exit `0`, executable/web/uninstaller present, `/health` ok, removed override names logged, and the poisoned external database was not created. Evidence: `docs/evidence/stage2-windows-final2-qa-20261125.txt`. The installer remains unsigned and unpublished.

The final full backend suite was rerun after all security and packaging source changes: exit `0`, **1,652 passed, 0 failed, 4 warnings in 1205.76s**. Evidence: `docs/evidence/stage2-fullsuite-final-20261125.txt` and `stage2-fullsuite-final-exit-20261125.txt`. The earlier 1,649-test run remains historical.

Native cross-platform attempts were made, not merely inferred from workflow files:

- Linux `npm run build:linux` produced an unpacked Electron directory but failed to create the AppImage on Windows (`EPERM` on POSIX symlink creation); evidence `stage2-linux-build-attempt-20261125.txt`, exit `1`.
- Linux `npx electron-builder --linux deb --x64` initially failed for missing homepage/maintainer metadata; after adding that metadata it failed because `fpm` is unavailable on the Windows host; evidence `stage2-linux-deb-attempt-20261125.txt` and `stage2-linux-deb-retry-20261125.txt`, exit `1`. The CI workflow was updated to install `ruby`/`fpm`, and Linux desktop metadata was added, but the workflow remains untracked on the remote.
- macOS `npm run build:mac` failed exactly as electron-builder documents off macOS: `Build for macOS is supported only on macOS`; evidence `stage2-macos-build-attempt-20261125.txt`, exit `1`.

The readiness verdict remains `PARTIALLY VERIFIED`: Windows has current local artifact evidence, while Linux and macOS have documented failed local attempts and no CI run IDs or published artifacts.
