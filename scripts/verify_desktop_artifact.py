"""Verify that the expected native desktop artifact exists and has valid magic bytes.

This is a read-only CI sanity check. It does not sign, publish or upload
anything, and it does not claim that an installer was launched.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "desktop" / "dist"

EXPECTED = {
    "windows": ((".exe",),),
    "linux": ((".appimage",), (".deb",)),
    "macos": ((".dmg",),),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_ok(path: Path, platform: str) -> bool:
    suffix = path.suffix.lower()
    with path.open("rb") as stream:
        head = stream.read(8)
        stream.seek(0, 2)
        size = stream.tell()
        if suffix == ".exe":
            stream.seek(0)
            return stream.read(2) == b"MZ"
        if suffix == ".appimage":
            stream.seek(0)
            return stream.read(4) == b"\x7fELF"
        if suffix == ".deb":
            return head == b"!<arch>\n"
        if suffix == ".dmg":
            stream.seek(max(0, size - 512))
            return b"koly" in stream.read(512)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=sorted(EXPECTED))
    parser.add_argument("--arch", required=True)
    args = parser.parse_args()

    if not DIST.is_dir():
        print(f"FAIL: missing {DIST}", file=sys.stderr)
        return 1

    files = [p for p in DIST.iterdir() if p.is_file()]
    failures = []
    for group in EXPECTED[args.platform]:
        matches = sorted(p for p in files if p.name.lower().endswith(group))
        if not matches:
            failures.append(f"no artifact ending in {' or '.join(group)}")
            continue
        for path in matches:
            valid = format_ok(path, args.platform)
            print(
                f"{path.name} platform={args.platform} arch={args.arch} "
                f"size={path.stat().st_size} sha256={sha256(path)} format_ok={valid}"
            )
            if not valid:
                failures.append(f"invalid format: {path.name}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"PASS: expected {args.platform} {args.arch} artifact types verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
