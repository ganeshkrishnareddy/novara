# NOVARA Desktop Owner Action Checklist

**Date:** 2026-11-25  
**Rule:** Nothing here has been committed, pushed, tagged, released, signed or published.

## Before any public distribution

- [ ] Decide explicitly whether the product release verdict should change. Desktop packaging alone does **not** change it.
- [ ] Authorize pushing the intended commit so `.github/workflows/desktop-build.yml` can run; no run was triggered in this track.
- [ ] Confirm all three matrix legs pass and record every workflow run ID/URL.
- [ ] Download the workflow artifacts and independently verify every SHA-256 checksum.
- [ ] Inspect each `build-manifest.json` and confirm `signed: false` and `published: false` before treating a build as preview-only.
- [ ] Sign the Windows executable/installer with a trusted certificate and establish SmartScreen reputation.
- [ ] Enable macOS hardened runtime and notarization for the `.dmg`.
- [ ] Add a signed auto-update feed with checksum/signature verification.
- [ ] Keep the desktop-generated per-install presign secret; set a separate unique `NOVARA_PRESIGN_SECRET` in any deployed server environment.
- [ ] Review token storage (`localStorage`) and decide whether preview lifetime is acceptable.
- [ ] Confirm OS-level full-disk encryption is required in the deployment guidance.
- [ ] Do not add a website download link until an artifact is actually published and this checklist is complete.
- [ ] Obtain explicit authorization before committing, pushing, tagging, creating a Release, or uploading binaries.

## Platform validation

- [ ] Install the Windows artifact on a clean machine with endpoint protection enabled.
- [ ] Test AppImage and `.deb` in a native Linux desktop session; document FUSE requirements.
- [ ] Test the unsigned universal `.dmg` on Apple Silicon and Intel macOS.
- [ ] Verify first-run setup, a real CRM write, restart persistence and uninstall on each platform.
- [ ] Verify that a non-loopback `http://` remote URL is rejected on each platform after the hardening change.
- [ ] Define and test an upgrade path between desktop versions.

## Repository hygiene

- [ ] Keep `README.md` unchanged unless separately approved; it was already modified by earlier work and was not touched in this track.
- [ ] Preserve the existing frontend, backend, auth, workspace and feature modules; no duplicate frontend was introduced.
- [ ] Keep the site copy honest: no binary, Release asset or download link is claimed.
- [ ] Archive the evidence files under `docs/evidence/` with the chosen release commit.
- [ ] Node audits were rerun after hardening: `npm audit --omit=dev` exit `0` with 0 vulnerabilities; full `npm audit` exit `1` with 6 moderate, 0 high and 0 critical findings in the electron-builder dev chain only. Before sign-off, review the upstream fix.
- [ ] Python packaged dependencies were scanned with `pip-audit`: exit `0`, 18 audited, 0 vulnerabilities, 1 locally built first-party package skipped. Consider a source-level scanner if first-party dependency review is required.

## Current state at hand-off

- Windows local preview: hardened build completed, installed, launched and exercised; unsigned; not published.
- Linux: CI configured; no workflow run ID, artifact or checksum; unverified.
- macOS: CI configured; no workflow run ID, artifact or checksum; unsigned; unverified.
- Final hardened full backend suite: exit `0`, 1,649 passed, 0 failed, 4 warnings in 1,480.05s; evidence `docs/evidence/desktop-hardened-fullsuite-20261125.txt` and `desktop-hardened-fullsuite-exit.txt`.
- Earlier hardened Windows SHA-256 (superseded): `4FEF61F2968746A664535F4280E504A044523BE640B399E50E0CC859C8574858`; size 146,465,056 bytes. The current post-security-fix values are in the next-stage section below.
- Site validator: exit `0`, 35 passed, 0 failed, 0 warnings, 15 informational notes.
- Desktop readiness verdict: `PARTIALLY VERIFIED`; no platform is published, signed or install-ready for public distribution.

## Next-stage actions — 2026-11-25

Current verified state after the security fixes:

- Current Windows installer SHA-256: `B291E32EC0E02DB640AA1E837FE8F396A4920CC2E75F9517D556C7C8CC05F6D6`; size 146,465,197 bytes; unsigned, unpublished; evidence `docs/evidence/stage2-windows-final2-manifest-20261125.txt`. An intermediate post-fix hash `9C4CF82BA703626549329CF3A644E908496583F45F9B38A8D88B3F32E6EFD068` is superseded.
- Fresh install/launch with poisoned inherited backend variables: install exit `0`, `/health` ok, override names logged, poisoned database not created, uninstall exit `0`; evidence `docs/evidence/stage2-windows-final2-qa-20261125.txt`.
- Focused verification: shell helpers `5 passed`; presign/backend security `9 passed`; site validator `35 passed, 0 failed`; Alembic single head `b5c6d7e8f9a0`.
- Full backend suite against the final patched source: exit `0`, 1,652 passed, 0 failed, 4 warnings in 1205.76s; evidence `docs/evidence/stage2-fullsuite-final-20261125.txt` and `stage2-fullsuite-final-exit-20261125.txt`.
- Linux and macOS local builds exited `1` for host limitations documented in `NEXT_STAGE_REPORT.md`; no CI run IDs or artifacts exist.

- [ ] Authorize committing and pushing the intended tree so `.github/workflows/desktop-build.yml` exists on the remote. The remote currently has only `.github/workflows/pages.yml` and one successful Pages run (`45556726447`); no desktop run ID or artifact exists.
- [ ] After the push, run the desktop workflow and record all three run IDs, artifact names, sizes and SHA-256 checksums. Verify the Linux `fpm` install step and the Debian maintainer metadata on the runner.
- [ ] Sign the Windows installer and enable macOS hardened runtime/notarization before any public download link.
- [ ] Decide whether to move tokens out of `localStorage` (safe shell-only alternatives require re-login after restart) and whether to add signed auto-update.
- [ ] Re-verify POSIX permission tightening on native Linux/macOS runners; the code and unit test are ready but unexecuted there.
- [ ] Review the 6 moderate electron-builder/minimatch dev-toolchain advisories when a non-downgrade upstream fix is available. No production runtime or Python payload vulnerability is outstanding.
