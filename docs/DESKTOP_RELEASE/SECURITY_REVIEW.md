# NOVARA Desktop Security Review

**Date:** 2026-11-25  
**Verdict:** Suitable as a controlled local preview. **Not** suitable for public production distribution until signing, update verification and the remaining inherited client/backend risks are addressed.

This review covers the Electron shell and the backend payload exactly as configured in `desktop/` and `scripts/prepare_desktop_backend.py`. It does not claim a penetration test or independent security audit.

## Controls implemented and verified

| Control | Implementation | Status |
| --- | --- | --- |
| Renderer isolation | `contextIsolation: true`, `nodeIntegration: false` | Verified in `desktop/src/main.js` |
| Sandboxed renderer | `sandbox: true`, `webSecurity: true` | Verified for main and utility windows |
| Minimal bridge | `preload.js` exposes only named methods through `contextBridge` | Verified |
| Navigation allow-list | Local shell files plus the selected backend origin only | Verified |
| External links | Routed through validated `shell.openExternal`, never loaded in the app window | Verified |
| IPC validation | Settings keys restricted; remote URLs validated before save and connection; external URLs must parse as http(s) and contain no credentials | Verified |
| HTTPS-default remote mode | Non-loopback `http://` remote URLs rejected; loopback HTTP allowed for development and local QA | Verified in built app |
| CSP | Scripts self-only; `connect-src` limited to self plus active backend origin; objects, frames and base-uri blocked; forms restricted to self | Verified |
| Backend exposure | Loopback-only bind on an ephemeral port | Verified in code and local runtime log |
| Local data isolation | `NOVARA_DB_PATH` and `NOVARA_STORAGE_DIR` point inside the per-user application data folder | Verified |
| Generated presign secret | Unique 43-character secret in userData `secrets.json`, passed as `NOVARA_PRESIGN_SECRET`; absent from packaged bundle | Verified on final Windows build |
| Log redaction | Bearer tokens, `token`/`signature`/`sig`/`key` query values and the generated secret are redacted from newly appended lines | Verified in code and runtime QA |
| POSIX permissions | Application data directory and generated secret use restrictive modes where supported; SQLite/storage tightened after startup | Implemented, not natively executed on this host |
| Single instance | `requestSingleInstanceLock` prevents duplicate shell instances | Verified |

## Findings and residual risks

### F-01 — No code signing or notarization (Medium)

Both the local Windows installer and the bundled runtime executables report `no code signing certificate configured, signing is skipped` during electron-builder. macOS is configured with `identity: null`, `hardenedRuntime: false` and `gatekeeperAssess: false`.

**Impact:** Windows SmartScreen and macOS Gatekeeper will warn or block untrusted users. Unsigned binaries cannot prove provenance.

**Owner action:** Sign the Windows executable/installer with a trusted certificate; enable hardened runtime and notarize the macOS build before public distribution.

### F-02 — No update service (Medium)

The About panel states that no update service is configured. Electron's auto-updater is not wired.

**Impact:** Users would need to manually replace the app; there is no signed update manifest or rollback path.

**Owner action:** Add a signed update feed with checksum/signature verification before calling any build production-ready.

### F-03 — Long-lived tokens in localStorage (Medium, inherited)

The existing client stores access and refresh tokens in `localStorage` under `novara.access_token`, `novara.refresh_token` and the workspace key. Electron's isolation reduces immediate exposure, but any future renderer script compromise could read them. A shell-only storage replacement was evaluated and deliberately not introduced because it would require changing the shared web client and its auth flow.

**Impact:** Token theft is possible if renderer code is later compromised.

**Owner action:** Move tokens to a safer store or shorten token lifetime; keep dependency review and CSP enforcement in place.

### F-04 — Default presign secret outside the desktop default (Medium, inherited)

`storage.py` still falls back to `novara-dev-presign-secret` when `NOVARA_PRESIGN_SECRET` is unset. The desktop shell now generates a unique per-install secret and supplies it to the bundled backend; the generated value is not in the app bundle.

**Impact:** Deployed or standalone backend instances that do not set their own secret would still use a publicly known signing key. Desktop local mode is mitigated, but the inherited backend default remains.

**Owner action:** Set a unique `NOVARA_PRESIGN_SECRET` for every non-preview deployment. Treat `secrets.json` in userData as sensitive.

### F-05 — Data at rest is not application-encrypted (Medium)

SQLite and uploaded files are stored in the user's application data folder. Access is scoped by the app and the local OS account, with tighter POSIX modes where supported, but there is no app-level encryption.

**Impact:** Anyone with the user's OS account or a copied backup can read local data.

**Owner action:** Require OS-level full-disk encryption and document backup handling; add application encryption only if the threat model requires it.

### F-06 — Remote mode previously permitted arbitrary http URLs (Mitigated in desktop shell)

`validRemoteUrl` now rejects non-loopback `http://` addresses both when settings are saved and when a connection is attempted. Local mode continues to use loopback HTTP. The settings page states this rule.

**Impact:** The remaining risk is a deliberate loopback exception or a user-supplied HTTPS server with an untrusted certificate; standard TLS validation applies.

**Owner action:** Keep the HTTPS requirement and review any future exception before shipping.

### F-07 — CSP tightened; inline styles remain (Low)

The earlier broad `ws:`/`wss:` connect allowance was removed. `connect-src` now permits only `'self'` and the active backend origin. The current client uses streaming `fetch`, not WebSockets. Inline styles remain allowed because the existing client uses them; scripts remain self-only and object/frame loading is blocked.

**Impact:** A narrow residual weakening of defence in depth; not an active exploit by itself.

**Owner action:** Remove `'unsafe-inline'` styles after a frontend DOM audit.

### F-08 — Local backend log (Low, mitigated for new lines)

`backend.log` contains startup and error text in the user data folder and is not uploaded anywhere by the shell. New lines now redact bearer tokens, signed-link query values and the generated presign secret. Existing log lines written before this change are not rewritten.

**Impact:** Older or future backend changes could still place sensitive text in the log.

**Owner action:** Treat the application data folder as sensitive and verify redaction after future backend logging changes.

### F-09 — Dependency findings (Low, build/dev only)

`npm audit --omit=dev --json` reports **0** vulnerabilities for the packaged runtime tree; the app carries no runtime Node dependencies. A full `npm audit --json` reports **6 moderate**, 0 high and 0 critical findings in the electron-builder development toolchain (`minimatch` via `@electron/universal`, `app-builder-lib`, `dmg-builder`, `electron-builder`, and `electron-builder-squirrel-windows`). Evidence: `docs/evidence/desktop-npm-audit-final-prod-20261125.json` and `desktop-npm-audit-final-all-20261125.json`.

`pip-audit` scanned the packaged Python dependency directory: **18 dependencies audited, 0 vulnerabilities, 0 fixes, 1 local package skipped** (`novara-core` is not published on PyPI). Evidence: `docs/evidence/desktop-python-audit-payload-20261125.json`.

**Impact:** The npm findings affect the build machine, not the shipped renderer bundle. Python scan coverage excludes only the locally built first-party package, which was separately imported and smoke-tested.

**Owner action:** Review the upstream electron-builder/minimatch fix before the next toolchain upgrade; rescan first-party code when a suitable source-level scanner is available.

## Dependency scan scope

- Node production: `npm audit --omit=dev --json`, exit `0`, 0 vulnerabilities.
- Node full/dev: `npm audit --json`, exit `1` from findings, 6 moderate, 0 high, 0 critical.
- Python packaged deps: `python -m pip_audit --path=D:\NOVARA\desktop\backend-payload\deps --format json`, exit `0`, 18 audited, 0 vulnerable, 1 skipped local package.
- No SAST, DAST, dependency-confusion audit or independent penetration test was performed.

## Explicitly not claimed

- No code signature, notarization, hardened runtime or trusted timestamp.
- No auto-update or signed update manifest.
- No public download link, GitHub Release asset or published binary.
- No Linux or macOS build artifact or workflow run ID.
- No external network call by the Electron shell itself beyond links the user opens in the system browser and an explicitly configured remote backend.
- No independent penetration test or formal compliance certification.

## Conclusion

The desktop shell applies standard Electron hardening plus a generated presign secret, HTTPS-default remote mode, log redaction and an origin-scoped CSP. The remaining risks are inheritance from the existing client/backend plus the expected pre-release gaps around signing, updates and deployment. Those gaps must be closed before public production distribution.

## Next-stage hardening pass — 2026-11-25 (addendum, history above preserved)

Four additional real issues were found and fixed after the review above:

- **Inherited backend environment (HIGH).** The shell previously passed `process.env` into the bundled backend. A developer shell with `NOVARA_DEV_MODE=1`, `NOVARA_DATABASE_URL` or `NOVARA_S3_*` set could silently expose one-time tokens, break per-user data isolation or redirect storage. `desktop/src/security-helpers.js` now strips those keys and forces local storage; the shell logs only the *names* of removed overrides. Verified by a fresh install/launch with poisoned variables: the log recorded `NOVARA_DATABASE_URL, NOVARA_DEV_MODE, NOVARA_S3_SECRET_KEY`, the poisoned database was never created and `/health` returned ok. Evidence: `docs/evidence/stage2-windows-final2-qa-20261125.txt`.
- **Remote HTTPS health check (HIGH).** `waitForHealth` used `http.get`, which throws on an `https://` remote URL and left the UI stuck at "starting". Protocol-aware `healthClientFor`/`healthGet` now select the correct client and invalid protocols fail closed. Five Node unit tests pass; evidence `docs/evidence/stage2-shell-security-tests-20261125.txt`.
- **Known presign key outside dev mode (HIGH).** `apps/api/novara_core/modules/storage.py` no longer falls back to `novara-dev-presign-secret` unless `NOVARA_DEV_MODE` is explicitly on; other runs use an unpredictable per-process key. Explicit `NOVARA_PRESIGN_SECRET` still wins, and the compose file and `.env.example` now document/pass it. Three new tests plus the existing tamper test pass (9 total); evidence `docs/evidence/stage2-presign-tests-20261125.txt`.
- **POSIX directory permissions (MEDIUM).** The previous `0600` chmod on the storage *directory* removes search permission on Linux/macOS. Permissions are now mode `0700` for directories and `0600` for files, applied recursively, with `umask 077` before backend spawn. Verified by unit test but **not** on a native POSIX host; native smoke remains a CI blocker.

Also added: subframe navigation is guarded by the same allow-list, external links pass URL validation before opening, and media/geolocation/midi/pointer-lock permission requests are denied. No use of those capabilities exists in the current client.

Still open and unchanged: localStorage tokens (F-03), no application-level encryption (F-05), `'unsafe-inline'` styles in CSP (F-07), unsigned artifacts and no update service (F-01/F-02), and 6 moderate npm **build-toolchain** advisories whose only offered fix is a semver-major downgrade of electron-builder (not applied). Production dependency scans remain clean (npm runtime 0, Python payload 18 audited / 0 vulnerable). No independent penetration test was performed.

Final package verification: the current installer's bundled backend source hash matches the working tree, the packaged `app.asar` contains the final `main.js` and a byte-identical `security-helpers.js`, and no `secrets.json` or credential-like key was found in the packaged shell. The only presign literal in the payload is the documented development-only fallback, inactive under the desktop shell's sanitized environment. Evidence: `docs/evidence/stage2-final-payload-asar-verification-20261125.txt`.
