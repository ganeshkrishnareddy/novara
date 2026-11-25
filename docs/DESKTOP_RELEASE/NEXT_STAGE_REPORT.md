# NOVARA Next-Stage Engineering Verification — 2026-11-25

**Scope:** cross-platform build verification, security hardening, regression, evidence and release verdicts for the existing NOVARA repository.  
**Working tree:** branch `main`, HEAD `f1dcfef`. All files created or changed in this stage are unstaged; most new engineering files are untracked. Nothing was committed, pushed, tagged, published or uploaded. `README.md` was not edited. Video, narration, thumbnail and promotional assets were not touched.

This report is an addendum. Earlier milestone reports and evidence are retained as history; values that changed after the next-stage fixes are explicitly marked as superseded.

## A. Cross-platform build verification

### Windows x64 — local artifact verified

Command from `desktop/`:

```powershell
npm run build:win
python scripts/write_desktop_build_manifest.py --platform windows --arch x64
```

Exit codes: build `0`, manifest `0`.

Current final artifact:

| Field | Value |
| --- | --- |
| Path | `desktop/dist/NOVARA-Setup-0.1.0-desktop-x64.exe` |
| Size | `146465197` bytes |
| SHA-256 | `b291e32ec0e02db640aa1e837fe8f396a4920cc2e75f9517d556c7c8cc05f6d6` |
| Signed | No |
| Published | No |
| Manifest | `desktop/dist/build-manifest.json`, generated `2026-11-25T14:17:56.606073+00:00` |

`build-manifest.json`, `build-manifest.csv` and the installer `.sha256` sidecar all match the on-disk artifact. There is no `build-manifest.json.sha256` sidecar; the script only writes checksum files for installer/package artifacts.

The earlier hardened milestone checksum `4FEF61F2968746A664535F4280E504A044523BE640B399E50E0CC859C8574858` (146,465,056 bytes) and an intermediate post-fix checksum `9c4cf82ba703626549329cf3a644e908496583f45f9b38a8d88b3f32e6efd068` (146,465,241 bytes) are both superseded. The intermediate build predates making the permission deny-list platform-independent on Windows.

Fresh install/launch/uninstall verification was performed against the exact current installer with deliberately poisoned inherited environment variables (`NOVARA_DEV_MODE=1`, `NOVARA_DATABASE_URL=sqlite:///D:/NOVARA/artifacts/stage2-qa/poison-final2.sqlite3`, `NOVARA_S3_SECRET_KEY=stage2-poison-final2`):

- install exit `0`; executable, bundled web client and uninstaller present;
- log recorded: `removed inherited backend overrides: NOVARA_DATABASE_URL, NOVARA_DEV_MODE, NOVARA_S3_SECRET_KEY`;
- backend started on loopback port `49741`; `/health` returned `status=ok product=NOVARA`;
- poisoned database was not created;
- app stopped cleanly; uninstall exit `0`; executable removed.

Evidence: `docs/evidence/stage2-windows-final2-build-20261125.txt`, `stage2-windows-final2-build-exit-20261125.txt`, `stage2-windows-final2-manifest-20261125.txt`, `stage2-windows-final2-qa-20261125.txt`.

### Linux x64 — real local attempts failed; CI unverified

Commands and results:

| Command | Exit | Concrete result |
| --- | --- | --- |
| `npm run build:linux` | `1` | Unpacked Electron directory was produced, but AppImage creation failed on Windows with `EPERM ... symlink 'usr\share\icons\hicolor\512x512\apps\novara-desktop.png'` |
| `npx electron-builder --linux deb --x64` | `1` | First attempt failed for missing homepage/maintainer metadata; after adding that metadata, retry failed with `fpm process failed ENOENT` / `spawn fpm ENOENT` |

The initial metadata defect was real and was fixed in `desktop/package.json`: `homepage`, `author`, Linux `maintainer`, `desktopName` and `syncDesktopName`. The CI workflow was updated to install `ruby`, `ruby-dev`, `build-essential` and `fpm` before the Linux build.

No Linux `.deb`, AppImage, checksum or CI run ID exists. Native session launch and package-manager installation remain unverified.

Evidence: `docs/evidence/stage2-linux-build-attempt-20261125.txt`, `stage2-linux-build-exit-20261125.txt`, `stage2-linux-deb-attempt-20261125.txt`, `stage2-linux-deb-retry-20261125.txt`, `stage2-linux-deb-retry-exit-20261125.txt`.

### macOS universal — real local attempt failed; CI unverified

`npm run build:mac` exited `1` with:

```text
Build for macOS is supported only on macOS, please see https://electron.build/multi-platform-build
```

No `.dmg`, checksum, CI run ID, native launch, Gatekeeper or notarization test exists. The ad-hoc/unsigned configuration remains unchanged.

Evidence: `docs/evidence/stage2-macos-build-attempt-20261125.txt`, `stage2-macos-build-exit-20261125.txt`.

### Remote CI state

`gh` is unavailable locally, so the public GitHub API was used read-only. Remote `origin` HEAD and `refs/heads/main` are both `f1dcfefe162faac644e974f075a411eb0975f4cb`. The remote contains only `.github/workflows/pages.yml` and one workflow run, ID `45556726447` (`Deploy NOVARA public site to Pages`, success). `.github/workflows/desktop-build.yml` is present locally but untracked and absent on the remote. Because pushing is not authorized, no desktop CI run was triggered.

## B. Security hardening

Four additional real issues were fixed beyond the earlier `SECURITY_REVIEW.md` findings:

1. **Inherited backend environment (HIGH).** `desktop/src/main.js` previously passed `process.env` into the bundled backend. A developer shell with `NOVARA_DEV_MODE`, `NOVARA_DATABASE_URL`, `NOVARA_CORS_ORIGINS`, `NOVARA_STORAGE_BACKEND` or `NOVARA_S3_*` set could expose one-time tokens, break per-user data isolation or redirect storage. `desktop/src/security-helpers.js` now strips those keys and forces local storage. Only the names of removed overrides are logged. Verified by the poisoned-environment install test above.
2. **Remote HTTPS health check (HIGH).** `waitForHealth` used `http.get` for every URL, so an `https://` remote threw `ERR_INVALID_PROTOCOL` and left the UI at "starting". `healthClientFor`/`healthGet` now select `http` or `https` by parsed protocol and fail closed on unsupported protocols.
3. **Known presign key outside dev mode (HIGH).** `apps/api/novara_core/modules/storage.py` no longer falls back to `novara-dev-presign-secret` unless `NOVARA_DEV_MODE` is explicitly enabled. Other runs use an unpredictable per-process key. Explicit `NOVARA_PRESIGN_SECRET` still wins. `.env.example` documents it and `docker-compose.yml` passes it through without a default.
4. **POSIX directory permissions (MEDIUM).** The previous `0600` chmod on the storage directory removes search permission on Linux/macOS. Modes are now `0700` for directories and `0600` for files, applied recursively with `umask 077` before backend spawn. This is unit-tested but not yet executed on a native POSIX host.

Additional defence in depth: subframe navigation uses the same allow-list as top-level navigation; external links are validated before `shell.openExternal`; media, geolocation, MIDI-sysex and pointer-lock permission requests are denied.

Focused evidence:

| Check | Exit/result | Evidence |
| --- | --- | --- |
| `node --test desktop/tests/security-helpers.test.js` | `0`; 5 tests passed | `stage2-shell-security-tests-20261125.txt` |
| Presign + existing security tests | `0`; `9 passed, 1 warning in 5.62s` | `stage2-presign-tests-20261125.txt` |
| Bundled backend payload smoke | `PASS: /health {"status":"ok","product":"NOVARA"}` | `stage2-payload-smoke-20261125.txt` |
| `node --check` on `main.js`, `security-helpers.js`, `apps/web/app.js` | `0` for each | shell output in this stage |
| `npm audit --omit=dev --json` | exit `0`, `0` production vulnerabilities | `stage2-npm-audit-prod-20261125.json` |
| `npm audit --json` | exit `1`, `6 moderate`, `0 high`, `0 critical`, all dev build toolchain; offered fix is an unjustified major downgrade of electron-builder | `stage2-npm-audit-all-20261125.json` |
| `python -m pip_audit --path=desktop/backend-payload/deps --format json` | exit `0`, 18 audited dependencies, 0 vulnerabilities, local `novara-core` skipped | earlier evidence `desktop-python-audit-payload-20261125.json` (dependency versions unchanged by this stage) |
| Final packaged-source verification | backend payload hash matches source; packaged `app.asar` contains the final `main.js` and byte-identical `security-helpers.js`; no embedded `secrets.json` or credential-like keys | `stage2-final-payload-asar-verification-20261125.txt` |

The package contains the development-only literal presign fallback in `storage.py`; it is active only under explicit `NOVARA_DEV_MODE` and is not a production credential. The desktop shell removes inherited `NOVARA_DEV_MODE` and generates a unique per-install signing secret.

Residual risks remain: `localStorage` tokens, no application-level encryption, `'unsafe-inline'` styles in CSP, no code signing, no notarization, no auto-update, and no independent penetration test. Details are in `SECURITY_REVIEW.md`.

## C. Release engineering blockers

Confirmed blockers and required owner actions:

- Sign Windows installer and establish SmartScreen reputation. Current artifact is unsigned.
- Provide macOS signing identity, hardened runtime and notarization; current config has `identity: null`, `hardenedRuntime: false`, `gatekeeperAssess: false`.
- Authorize commit/push so `.github/workflows/desktop-build.yml` exists on the remote; then run the workflow and capture all three run IDs, artifact names, sizes and checksums.
- Verify the new Linux `fpm` install step and Debian metadata on a real Ubuntu runner.
- Run native Linux session/package installation and macOS launch/Gatekeeper checks.
- Decide on token persistence UX and signed auto-update before public distribution.
- Re-verify POSIX permission tightening on native Linux/macOS runners.
- Review the 6 moderate electron-builder/minimatch advisories when a non-downgrade upstream fix exists.

## D. Regression and validation

Full backend suite command against the patched source:

```powershell
PYTHONPATH=D:\NOVARA\apps\api
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests -q
```

Evidence: `docs/evidence/stage2-fullsuite-final-20261125.txt`; exit file `stage2-fullsuite-final-exit-20261125.txt`.

**Final full-suite result:** exit `0`; **1,652 passed, 0 failed, 4 warnings in 1205.76s (0:20:05)**. This run was executed after all security and packaging source changes. The four warnings are the same inherited deprecations: Starlette/httpx test client, two `HTTP_422_UNPROCESSABLE_ENTITY` uses in marketing local capabilities, and one Alembic `path_separator` warning. The earlier `nextstage-fullsuite-20261125.txt` stopped at 65% and the first `stage2-fullsuite-final-20261125.txt` attempt stopped at 43%, both with no exit file; neither is used as evidence. The complete log was regenerated in UTF-8 with the final result above.

Other validation:

| Check | Command | Result | Evidence |
| --- | --- | --- | --- |
| Site validator | `python scripts/validate_site.py` | `0`; `35 passed, 0 failed, 0 warnings, 15 informational` | `stage2-site-validator-final-20261125.txt`, `stage2-site-validator-final-exit-20261125.txt` |
| Alembic head | `cd apps/api; python -m alembic -c alembic.ini heads` | `0`; single head `b5c6d7e8f9a0 (head)` | `stage2-alembic-heads-final-retry-20261125.txt`, `stage2-alembic-heads-final-retry-exit-20261125.txt` |
| Bundled payload preparation | `python scripts/prepare_desktop_backend.py` | `0` | `stage2-payload-prepare-20261125.txt` |
| Bundled payload health | `python scripts/smoke_desktop_payload.py` | `0`; `/health` ok | `stage2-payload-smoke-20261125.txt` |

The first Alembic attempt from the repository root failed with `Path doesn't exist: migrations`; that failure is retained in `stage2-alembic-heads-final-20261125.txt`. The correct working directory is `apps/api`, and the retry passed.

The backend suite covers the product's auth/session, CRM, projects, search/analytics, notifications/automation, marketing, support/documents and other previously implemented areas through the existing test modules; no test file was deleted or bypassed.

## E. Documentation and evidence updates

Updated in place without overwriting historical sections:

- `docs/DESKTOP_RELEASE/DESKTOP_READINESS_REPORT.md` — next-stage addendum with current artifact, install evidence and cross-platform attempts.
- `docs/DESKTOP_RELEASE/SECURITY_REVIEW.md` — addendum documenting the four new fixes and residual risks.
- `docs/DESKTOP_RELEASE/KNOWN_LIMITATIONS.md` — next-stage addendum and pointer to this report.
- `docs/DESKTOP_RELEASE/OWNER_ACTION_CHECKLIST.md` — current verified state and remaining owner actions.
- `docs/DESKTOP_RELEASE/INSTALLATION_GUIDE.md` — current checksum, with the old checksum explicitly marked superseded.
- `docs/DESKTOP_RELEASE/PLATFORM_BUILD_MATRIX.csv` — appended current Windows/Linux/macOS rows; earlier rows retained as history.
- New evidence under `docs/evidence/stage2-*`, listed throughout this report.

`README.md` was not edited.

## F. Verdicts

| Area | Verdict | Basis |
| --- | --- | --- |
| Windows | `PARTIALLY VERIFIED` | Current installer built, checksummed, installed, launched, health-checked, environment-sanitization checked and uninstalled; full dashboard/contact UI evidence belongs to the earlier hardened artifact; unsigned and unpublished |
| Linux | `UNVERIFIED` | Real local attempts failed for host limitations; no artifact, no CI run ID, no native smoke |
| macOS | `UNVERIFIED` | electron-builder refuses macOS builds off macOS; no artifact, no CI run ID, no native/Gatekeeper test |
| Security | `PARTIALLY VERIFIED` | Four high/medium issues fixed with focused tests; packaged-source verification and clean production scans; no native POSIX runtime test, penetration test, signing or update service |
| Full NOVARA product readiness | `RELEASE BLOCKED` | Installer success alone is insufficient: cross-platform CI artifacts, signing/notarization, update path and clean-machine native verification are absent |

**Release owner decision required:** do not publish or link a public download until the blocker list in section C is closed and a fresh cross-platform CI run is recorded.

## G. Recommended next engineering milestone

**Objective:** run the existing cross-platform desktop workflow on native GitHub runners and close Linux/macOS build verification without touching product code.

**Scope:** authorize commit/push of the intended working tree, trigger `.github/workflows/desktop-build.yml` once, and record Windows/Linux/macOS run IDs, artifact names, sizes, SHA-256 checksums, logs and smoke results. Do not publish a Release or change the marketing site download statuses until artifacts are reviewed.

**Dependencies:** explicit owner authorization to commit and push; repository runner availability; no secret or credential is required for unsigned preview builds. Signing/notarization remains a separate owner-controlled milestone.

**Acceptance criteria:** one workflow run ID per platform; each build exits `0`; Linux AppImage and `.deb` exist with checksums; macOS `.dmg` exists with checksum; payload smoke passes on each runner; POSIX permission and data-path checks execute natively; all artifacts and logs are attached to the run. Windows existing local evidence remains preserved.

**Verification commands evidence to capture:** workflow run URL and job IDs; exact build commands from the workflow; `sha256sum`/`Get-FileHash` output; `scripts/smoke_desktop_payload.py` output; `node --test desktop/tests/security-helpers.test.js` output; installer/launch output where the runner supports it.

**Evidence required:** workflow run IDs and URLs, artifact filenames/sizes/checksums, job logs showing exit codes, native smoke logs, and an updated `PLATFORM_BUILD_MATRIX.csv` with no unverified platform promoted.
