# NOVARA Desktop Installation Guide

**Status:** Preview. A Windows x64 installer was built and verified locally. No installer is published, linked or attached to a GitHub Release. Linux and macOS CI is configured but has produced no artifact in this workspace.

## Windows x64 (local preview artifact)

Artifact: `desktop/dist/NOVARA-Setup-0.1.0-desktop-x64.exe`  
Size: **146,465,197 bytes**  
SHA-256: **`B291E32EC0E02DB640AA1E837FE8F396A4920CC2E75F9517D556C7C8CC05F6D6`**

The checksum above identifies the exact current local build after the next-stage security fixes. It changes when the app is rebuilt. The earlier hardened preview hash `4FEF61F2968746A664535F4280E504A044523BE640B399E50E0CC859C8574858` (146,465,056 bytes) and the intermediate post-fix hash `9C4CF82BA703626549329CF3A644E908496583F45F9B38A8D88B3F32E6EFD068` (146,465,241 bytes) are superseded and must not be used for the current file. Evidence: `docs/evidence/stage2-windows-final2-manifest-20261125.txt`.

### Verify before installing

```powershell
Get-FileHash '.\NOVARA-Setup-0.1.0-desktop-x64.exe' -Algorithm SHA256
```

Compare the hash with the value above. Do not install a file whose hash differs unless the owner has published a new checksum through a trusted channel.

### Install

1. Obtain the artifact directly from the repository owner. There is no public download.
2. Run the NSIS installer. It installs per user by default and permits changing the install directory.
3. Because the build is unsigned, Windows may show a SmartScreen warning. Do not bypass that warning unless the checksum matches and you trust the source.
4. Launch **NOVARA** from the Start menu or desktop shortcut.
5. On first run, complete the local setup form to create the workspace and owner account.

### Connect to a backend

- **Bundled local backend (default):** the app starts its own Python backend on a free loopback port. No separate Python installation or cloud account is required.
- **Existing NOVARA server:** open **File → Settings…**, choose the remote mode and enter an `https://` URL. Plain `http://` is accepted only for loopback development addresses such as `127.0.0.1`; then save and restart.

### Where data is stored

| Item | Location |
| --- | --- |
| SQLite database | `%APPDATA%\NOVARA\data\novara.sqlite3` |
| Uploaded files | `%APPDATA%\NOVARA\data\storage` |
| Settings | `%APPDATA%\NOVARA\settings.json` |
| Generated presign secret | `%APPDATA%\NOVARA\secrets.json` |
| Backend log | `%APPDATA%\NOVARA\backend.log` |

The presign secret is generated per installation and is not embedded in the installer. Treat the application data folder as sensitive.

If the window says **NOVARA — Connecting**, open `backend.log` for the exact startup error. The client retries automatically through **Retry** on the connection screen.

### Uninstall

Run `Uninstall NOVARA.exe` from the install folder or use Windows app removal. The uninstaller removes the application files but deliberately keeps the user data folder so a later reinstall restores the workspace.

## Linux and macOS

No local artifact exists for these platforms. CI is configured to build:

| Platform | Target |
| --- | --- |
| Linux x64 | AppImage and `.deb` |
| macOS universal | `.dmg` (unsigned/ad-hoc) |

Use the workflow artifacts and their SHA-256 sidecars only after a successful CI run. Do not invent a download URL. On macOS, Gatekeeper will require explicit approval for an unsigned app until notarization is configured. AppImage may require FUSE (`libfuse2`) on newer Linux distributions.

## Build from source

From the repository root:

```powershell
python -m pip install Pillow
python desktop/build/generate_icon.py
python scripts/prepare_desktop_backend.py
python scripts/smoke_desktop_payload.py
cd desktop
npm ci --no-audit --no-fund
npm run build:win
cd ..
python scripts/write_desktop_build_manifest.py --platform windows --arch x64
```

Substitute `npm run build:linux` or `npm run build:mac` on the corresponding host. The payload smoke test must pass before building; it starts the bundled interpreter and checks `/health`.

## Security note

This preview is unsigned and has no auto-update service. Verify checksums, install only from a trusted source, and review `SECURITY_REVIEW.md` before any wider rollout.
