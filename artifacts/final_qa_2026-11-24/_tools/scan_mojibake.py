"""Find mojibake / non-English artefacts in the NOVARA web assets."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"D:\NOVARA\apps\web")
SUSPECT = ("Ã", "Â", "â€", "Ãƒ", "Â¬", "Â", "ï¿½", "\ufffd")

for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in {".js", ".html", ".css", ".json", ".md"}:
        continue
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"[NOT UTF-8] {path}: {exc}")
        continue
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(tag in line for tag in SUSPECT):
            hits.append((i, line[:200]))
    if hits:
        print(f"\n=== {path} ({len(hits)} suspect lines)")
        for i, line in hits[:40]:
            print(f"  {i}: {line}")
