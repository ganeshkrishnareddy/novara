"""Write a truthful manifest and SHA-256 files for desktop build artifacts.

Only files electron-builder actually produced in desktop/dist are recorded.
No remote release assets, signatures, links or installers are invented.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "desktop" / "dist"
PACKAGE = ROOT / "desktop" / "package.json"
SUFFIXES = (".exe", ".msi", ".appimage", ".deb", ".rpm", ".dmg", ".tar.gz", ".zip")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default=os.getenv("NOVARA_BUILD_PLATFORM", "unknown"))
    parser.add_argument("--arch", default=os.getenv("NOVARA_BUILD_ARCH", "unknown"))
    args = parser.parse_args()

    if not DIST.is_dir():
        print(f"FAIL: missing {DIST}", file=sys.stderr)
        return 1

    artifacts = []
    for path in sorted(DIST.iterdir()):
        if not path.is_file() or not path.name.lower().endswith(SUFFIXES):
            continue
        checksum = sha256(path)
        artifacts.append({
            "name": path.name,
            "sizeBytes": path.stat().st_size,
            "sha256": checksum,
        })
        (DIST / f"{path.name}.sha256").write_text(f"{checksum}  {path.name}\n", encoding="ascii")

    if not artifacts:
        print(f"FAIL: no desktop artifacts found in {DIST}", file=sys.stderr)
        return 1

    version = json.loads(PACKAGE.read_text(encoding="utf-8")).get("version", "unknown")
    manifest = {
        "version": version,
        "platform": args.platform,
        "arch": args.arch,
        "runner": os.getenv("RUNNER_OS") or "local",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "signed": False,
        "published": False,
        "artifacts": artifacts,
    }
    (DIST / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    with (DIST / "build-manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["name", "platform", "arch", "size_bytes", "sha256"])
        for item in artifacts:
            writer.writerow([item["name"], args.platform, args.arch, item["sizeBytes"], item["sha256"]])

    for item in artifacts:
        print(f"{item['sha256']}  {item['name']}  ({item['sizeBytes']} bytes)")
    print(f"wrote {DIST / 'build-manifest.json'} and build-manifest.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
