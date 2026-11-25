# NOVARA native CI preparation review — 2026-11-25

**Scope:** prepare `.github/workflows/desktop-build.yml` for native Windows, Linux and macOS verification of the existing Electron desktop shell. This is a static-preparation report only: **no commit, push, tag, release, upload or CI run was performed**, and no Linux/macOS result is claimed.

**Snapshot:** branch `main`, HEAD `f1dcfef` (`f1dcfefe162faac644e974f075a411eb0975f4cb`). Working tree remains dirty; no staged diff. `README.md` was not edited. The verified Windows installer was not overwritten and still hashes to `b291e32ec0e02db640aa1e837fe8f396a4920cc2e75f9517d556c7c8cc05f6d6`.

## 1. Required files

All files below exist locally. Only `apps/web/app.js` is tracked in HEAD; every other workflow input is untracked and must be included in the authorized commit before the remote workflow can build from them.

| File | State |
| --- | --- |
| `.github/workflows/desktop-build.yml` | exists, untracked |
| `desktop/package.json` | exists, untracked |
| `desktop/package-lock.json` | exists, untracked |
| `desktop/build/icon.png` | exists, untracked |
| `desktop/src/main.js` | exists, untracked |
| `desktop/src/security-helpers.js` | exists, untracked |
| `desktop/tests/security-helpers.test.js` | exists, untracked |
| `desktop/tests/posix-permissions.test.js` | new, untracked |
| `scripts/prepare_desktop_backend.py` | exists, untracked |
| `scripts/smoke_desktop_payload.py` | exists, untracked |
| `scripts/verify_desktop_artifact.py` | new, untracked |
| `scripts/write_desktop_build_manifest.py` | exists, untracked |
| `apps/api/pyproject.toml` | exists, untracked |
| `apps/api/alembic.ini` | exists, untracked |
| `apps/api/novara_core/modules/storage.py` | exists, untracked |
| `apps/api/tests/test_presign_secret_hardening.py` | exists, untracked |
| `apps/web/app.js` | tracked, pre-existing modification |
| `docs/DESKTOP_RELEASE/NEXT_STAGE_REPORT.md` | exists, untracked |

The workflow triggers on `workflow_dispatch`, push to `main` and pull requests touching `apps/api/**`, `apps/web/**`, `desktop/**`, the four desktop scripts, or the workflow itself. It has `contents: read` and no release/tag/publish step.

## 2. Workflow issues found and resolved

| Issue found | Fix applied |
| --- | --- |
| Backend job installed only the base API, so `pytest`, `httpx` and `alembic` were not guaranteed. | Install `-e "./apps/api[dev,migrate]"`. |
| Build output was streamed only to the live log; nothing was attached for later review, and failures lost logs. | All prepare/smoke/build/manifest commands now `tee` into `desktop/build-logs/*.log`; log upload uses `if: always()`; a `SHA256SUMS.txt` is written. Backend check logs are also uploaded. |
| macOS used `--universal` while the bundled Python runtime is built for the host architecture; the Intel half of a universal DMG could not launch its own backend. | Replaced the universal leg with two native legs: `macos-15-intel` → `x64` and `macos-latest` → `arm64`. `build:mac` is now `electron-builder --mac` and the DMG target is plain `dmg`; each leg passes its own `--x64`/`--arm64`. |
| POSIX payload preparation copied only `bin`/`lib`, which can break setup-python's macOS framework symlinks. | Copy the whole interpreter prefix with symlinks preserved, excluding `site-packages`, tests, Tk and bytecode. |
| No CI step exercised the POSIX permission change on a native POSIX host. | Added `desktop/tests/posix-permissions.test.js`; it chmods a temporary directory/file and is skipped on Windows, so it runs on both macOS legs and Linux. |
| Artifact presence was inferred from filename suffixes only. | Added `scripts/verify_desktop_artifact.py`, which checks PE/ELF/ar/DMG magic bytes and prints size and SHA-256 before manifest generation. |
| Linux `fpm` and Debian metadata were previously identified as failure causes. | Retained `libfuse2`, `ruby`, `ruby-dev`, `build-essential` and `fpm` installation; retained `homepage`, `author`, `maintainer`, `desktopName` and `syncDesktopName` metadata. Not yet runner-verified. |

## 3. Native build matrix and expected outputs

| Runner | Leg | Expected artifact(s) |
| --- | --- | --- |
| `windows-latest` | Windows x64 | `desktop/dist/NOVARA-Setup-0.1.0-desktop-x64.exe` |
| `ubuntu-latest` | Linux x64 | `desktop/dist/NOVARA-0.1.0-desktop-x64.AppImage` and `desktop/dist/NOVARA-0.1.0-desktop-x64.deb` |
| `macos-15-intel` | macOS x64 | `desktop/dist/NOVARA-0.1.0-desktop-x64.dmg` |
| `macos-latest` | macOS arm64 | `desktop/dist/NOVARA-0.1.0-desktop-arm64.dmg` |

Every leg runs payload preparation, payload `/health` smoke, desktop shell tests, the native build, artifact format verification, SHA-256 sidecars, `build-manifest.json`/`.csv`, log checksums and artifact/log uploads. These are **expected**, not produced: no workflow has run and no Linux/macOS artifact exists.

Full GUI/installer launch is not automated on headless runners. Native macOS/Linux launch, Gatekeeper, package-manager installation and first-run UI checks remain owner-reported items; the workflow deliberately does not claim them.

## 4. Local validation performed

Exact commands and outputs are preserved in `docs/evidence/ci-native-prep-static-validation-20261125.txt`.

| Command | Result |
| --- | --- |
| `python -` PyYAML `BaseLoader` structural parse and matrix/package assertions | `YAML_OK: 2 jobs, 4 native matrix legs, 11 build steps, bash shell`; `PACKAGE_OK`; recheck `YAML_RECHECK_OK 2 4 15` |
| `python -m py_compile scripts/prepare_desktop_backend.py scripts/smoke_desktop_payload.py scripts/verify_desktop_artifact.py scripts/write_desktop_build_manifest.py` | exit `0`, 4 scripts compiled |
| `node --check` on `main.js`, `security-helpers.js`, both test files | exit `0`, 4 files checked |
| `node --test desktop/tests/security-helpers.test.js desktop/tests/posix-permissions.test.js` | 6 tests, 5 passed, 0 failed, 1 skipped (POSIX test intentionally skipped on Windows) |
| `python scripts/verify_desktop_artifact.py --platform windows --arch x64` | existing installer `format_ok=True`, size `146465197`, SHA-256 `b291e32e…f6d6`, exit `0` |
| Read-only hash of existing installer | size and SHA-256 unchanged; `build-manifest.json` still says `signed: false`, `published: false` |
| Git snapshot | `f1dcfef`, `main`, no staged diff |

`python -m pytest apps/api/tests -q` was **not rerun** in this preparation step; the final existing result remains `1652 passed, 4 warnings` from `docs/evidence/stage2-fullsuite-final-20261125.txt`. No Linux/macOS build, install or launch was attempted locally in this step.

## 5. Approval required before anything is pushed

- [ ] Approve the exact file set to commit. The tree has hundreds of pre-existing unstaged/untracked files; none should be assumed authorized.
- [ ] Authorize the commit and push to `main` (or an agreed branch/PR). The workflow's push trigger will start CI immediately after the push reaches the remote.
- [ ] Confirm unsigned preview artifacts and read-only `contents: read` permissions are acceptable for this run. No secret is needed for this milestone.
- [ ] Accept runner usage for four matrix legs plus the backend suite; `macos-15-intel` and `macos-latest` are the two macOS runners.
- [ ] After results, separately approve any documentation/matrix promotion, site download change, Release creation or artifact publication.
- [ ] Signing identity, hardened runtime, notarization and auto-update credentials remain a separate owner-controlled milestone; none are configured or requested here.

**Stopping for review. No Git commit or push will be made without explicit approval.**
