"""Prepare the payload bundled into NOVARA desktop installers.

Creates desktop/backend-payload/deps with the NOVARA API and its Python
dependencies, and desktop/backend-payload/runtime with a trimmed CPython
runtime. The Electron shell prefers this runtime, so a packaged app can start
its own backend without a separate Python installation.

This script never touches the application source or the Git index.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "desktop" / "backend-payload"
DEPS = PAYLOAD / "deps"
RUNTIME = PAYLOAD / "runtime"
WEB = PAYLOAD / "web"


def install_deps() -> None:
    if DEPS.exists():
        shutil.rmtree(DEPS)
    DEPS.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--target", str(DEPS), str(ROOT / "apps" / "api")],
        cwd=str(ROOT),
    )


def copy_runtime() -> None:
    base = Path(sys.base_prefix)
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        for name in ("python.exe", "python3.dll", f"python{sys.version_info.major}{sys.version_info.minor}.dll",
                     "vcruntime140.dll", "vcruntime140_1.dll"):
            source = base / name
            if source.exists():
                shutil.copy2(source, RUNTIME / name)
        for folder in ("DLLs", "libs"):
            source = base / folder
            if source.exists():
                shutil.copytree(source, RUNTIME / folder)
        shutil.copytree(
            base / "Lib", RUNTIME / "Lib",
            ignore=shutil.ignore_patterns("site-packages", "test", "idlelib", "tkinter", "__pycache__"),
        )
    else:
        # Electron's main process expects <runtime>/bin/python3 on POSIX and
        # CPython expects <runtime>/lib/pythonX.Y. Copy the whole interpreter
        # prefix so framework builds keep their relative symlink targets;
        # copying only bin/lib broke setup-python's macOS framework runtime.
        ignore = shutil.ignore_patterns(
            "site-packages", "test", "idlelib", "tkinter", "__pycache__"
        )
        shutil.copytree(base, RUNTIME, symlinks=True, ignore=ignore, dirs_exist_ok=True)
        bin_dir = RUNTIME / "bin"
        versioned = bin_dir / f"python{sys.version_info.major}.{sys.version_info.minor}"
        alias = bin_dir / "python3"
        if versioned.exists() and not alias.exists():
            shutil.copy2(versioned, alias, follow_symlinks=True)
        for executable in bin_dir.iterdir():
            if executable.is_file() and executable.name.startswith("python"):
                executable.chmod(
                    executable.stat().st_mode
                    | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                )


def copy_web_client() -> None:
    """FastAPI resolves WEB_ROOT relative to novara_core, so ship that layout."""
    if WEB.exists():
        shutil.rmtree(WEB)
    shutil.copytree(ROOT / "apps" / "web", WEB)


def main() -> None:
    PAYLOAD.mkdir(parents=True, exist_ok=True)
    install_deps()
    copy_runtime()
    copy_web_client()
    manifest = {
        "python": sys.version.split()[0],
        "dependencies": sorted(p.name for p in DEPS.iterdir() if p.is_dir()),
        "runtimeBundled": (RUNTIME / ("python.exe" if os.name == "nt" else "bin/python3")).exists(),
    }
    (PAYLOAD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {PAYLOAD}: {len(manifest['dependencies'])} dependency folders, runtime={manifest['runtimeBundled']}")


if __name__ == "__main__":
    main()
