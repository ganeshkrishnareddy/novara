from pathlib import Path

root = Path("docs")
for p in sorted(root.rglob("*.md")):
    text = p.read_text(encoding="utf-8", errors="replace")
    bad = text.count("\ufffd")
    plus = text.count("?+")
    if bad or plus:
        print(f"{p}: U+FFFD={bad}, '?+'={plus}")
