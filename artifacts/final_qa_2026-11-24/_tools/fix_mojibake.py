"""Repair layered UTF-8 mis-decoding in the NOVARA web application copy.

The source file is valid UTF-8, but many English strings were decoded through
cp1252/latin-1 several times, so em dashes, ellipses and middle dots appear as
"ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â" etc. This reverses those layers and leaves identifiers and
ASCII code untouched. A byte-for-byte backup is kept as evidence.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

TARGET = Path(r"D:\NOVARA\apps\web\app.js")
BACKUP = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\app.js.before_language_fix")
SUSPECT_RE = re.compile(r"[\u00c0-\u00ff\u0192\u20ac\u201a\u201e\u2026\u0080-\u009f]")


def mixed_encode(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            out += ch.encode("latin-1")
    return bytes(out)


def undo_layer(text: str) -> str:
    return mixed_encode(text).decode("utf-8")


def repair_line(line: str) -> str:
    bom = "\ufeff" if line.startswith("\ufeff") else ""
    current = line[len(bom):]
    for _ in range(8):
        if not SUSPECT_RE.search(current):
            break
        try:
            nxt = undo_layer(current)
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if nxt == current:
            break
        current = nxt
    return bom + current


def main():
    original = TARGET.read_bytes()
    if not BACKUP.exists():
        BACKUP.write_bytes(original)
    text = original.decode("utf-8")
    lines = text.splitlines(keepends=True)
    fixed = [repair_line(line) for line in lines]
    result = "".join(fixed)
    changed = sum(1 for a, b in zip(lines, fixed) if a != b)
    TARGET.write_text(result, encoding="utf-8", newline="")
    remaining = sum(1 for line in result.splitlines() if SUSPECT_RE.search(line))
    print(f"lines changed: {changed}")
    print(f"remaining suspect lines: {remaining}")
    print(f"backup: {BACKUP}")
    for i, (a, b) in enumerate(zip(lines, fixed), 1):
        if a != b:
            print(f"\nline {i}\n  before: {a.rstrip()[:180]!r}\n  after : {b.rstrip()[:180]!r}")
            if i > 40:
                break


if __name__ == "__main__":
    main()
