# NOVARA Desktop Known Limitations

**Date:** 2026-11-25

## Publication and trust

- No public download link, GitHub Release asset or published binary exists.
- Windows, Linux and macOS builds are unsigned; macOS is not hardened-runtime enabled or notarized.
- No auto-update service or signed update manifest exists.
- The Windows artifact is an NSIS `.exe` only. An `.msi` was once listed as a planned format but was not built.
- Desktop packaging progress does not change NOVARA's product release verdict.

## Platform evidence

- Windows x64 was built, installed, launched and exercised locally on this machine.
- Linux and macOS CI is configured, but no Linux or macOS artifact was produced in this workspace. Both platforms are `UNVERIFIED` until a workflow run completes and its artifacts are inspected.
- The bundled POSIX runtime layout is implemented in the payload script but could not be executed locally from Windows. CI smoke-tests it on each native runner.

## Runtime and packaging

- The installer is large (about 146 MB) because it carries CPython, the API dependencies, the existing web client and Electron.
- The bundled Python runtime matches the build host's Python version and platform. Rebuild on each target platform; do not copy a Windows payload to Linux or macOS.
- Local mode requires a reachable loopback backend; the app is not offline-first.
- Remote mode requires an `https://` NOVARA backend; plain `http://` is accepted only for loopback development addresses.
- A stale or damaged `resources/backend/web` copy will cause the first page to return `web client is not installed`; this was found and fixed during local QA.
- The shell does not migrate data from an existing development SQLite file automatically. First run creates a fresh workspace in the per-user data folder.

## Security

- Access and refresh tokens remain in `localStorage`, inherited from the existing client; a shell-only replacement was deliberately not introduced.
- SQLite data and uploaded files are not application-encrypted, though POSIX permissions are tightened where supported.
- The backend still falls back to a development presign secret outside the desktop shell; desktop local mode supplies a generated per-install secret instead.
- The CSP retains `'unsafe-inline'` for styles because of existing client requirements. The earlier broad websocket allowance was removed; `connect-src` is now scoped to the active backend origin.
- New local backend log lines redact bearer tokens, signed-link query values and the generated secret; older lines are not rewritten.
- Python packaged dependencies were scanned with `pip-audit`: 18 audited, 0 vulnerabilities, 1 locally built package skipped. Node audits reported 0 runtime and 6 moderate build-toolchain findings.

## Operational checks not yet performed

- Clean-machine Windows install with corporate endpoint protection enabled.
- Windows signing and SmartScreen reputation.
- Native Linux desktop session launch and package-manager installation.
- Native macOS launch, Gatekeeper approval and notarization.
- Upgrade path from one desktop version to the next.

Items in this file are deliberate, evidence-based limits, not silent omissions. Owner actions are tracked in `OWNER_ACTION_CHECKLIST.md`.

## Next-stage addendum — 2026-11-25

- The desktop now strips inherited backend overrides, uses protocol-aware HTTPS health checks and no longer has a known presign default outside dev mode. The rows above that describe those older behaviours are historical and superseded.
- Native Linux and macOS builds were attempted on this Windows host and genuinely failed: AppImage cannot create POSIX symlinks (`EPERM`), `.deb` needs `fpm`, and electron-builder refuses macOS builds off macOS. The CI workflow was updated with an `fpm` install step and Linux desktop metadata, but the workflow file is still untracked on the remote, so no CI run exists.
- The rebuilt Windows installer is unsigned and unpublished; its checksum changed after the security fixes. See `NEXT_STAGE_REPORT.md` (created in this stage) for the current checksum and exact evidence.
- POSIX permission tightening is implemented and unit-tested but has not been executed on a native Linux or macOS filesystem.
