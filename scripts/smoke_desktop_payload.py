"""Smoke-test the Python runtime and payload bundled into NOVARA desktop.

Starts the bundled interpreter against the bundled NOVARA API on a free
loopback port, waits for GET /health, then stops it and removes temporary
state. This is used by local verification and by the desktop CI workflow.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "desktop" / "backend-payload"
TIMEOUT_SECONDS = 45


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> int:
    manifest_path = PAYLOAD / "manifest.json"
    if not manifest_path.is_file():
        print(f"FAIL: missing {manifest_path}; run prepare_desktop_backend.py first", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("runtimeBundled"):
        print("FAIL: payload manifest reports no bundled runtime", file=sys.stderr)
        return 1

    executable = PAYLOAD / "runtime" / (
        "python.exe" if os.name == "nt" else "bin/python3"
    )
    deps = PAYLOAD / "deps"
    web = PAYLOAD / "web"
    for required in (executable, deps / "novara_core" / "main.py", web / "index.html"):
        if not required.exists():
            print(f"FAIL: missing payload path {required}", file=sys.stderr)
            return 1

    port = free_port()
    with tempfile.TemporaryDirectory(prefix="novara-desktop-smoke-") as temp:
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(deps),
            "NOVARA_DB_PATH": str(Path(temp) / "novara.sqlite3"),
            "NOVARA_STORAGE_DIR": str(Path(temp) / "storage"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        })
        command = [
            str(executable), "-m", "uvicorn", "novara_core.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log",
        ]
        print("starting:", " ".join(command), flush=True)
        process = subprocess.Popen(
            command, cwd=temp, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        started = time.monotonic()
        try:
            while time.monotonic() - started < TIMEOUT_SECONDS:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health", timeout=2
                    ) as response:
                        body = response.read().decode("utf-8")
                        if response.status == 200:
                            print(f"PASS: /health {body}", flush=True)
                            return 0
                except (urllib.error.URLError, TimeoutError, OSError):
                    time.sleep(0.4)
            output = ""
            if process.poll() is not None and process.stdout is not None:
                output = process.stdout.read()
            print(f"FAIL: bundled backend did not become healthy in {TIMEOUT_SECONDS}s", file=sys.stderr)
            if output:
                print(output[-4000:], file=sys.stderr)
            return 1
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    raise SystemExit(main())
