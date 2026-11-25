import csv
from pathlib import Path
root = Path(r"D:\NOVARA")
rows = {r["ID"]: r for r in csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))}
parts = []
for m in [root / "apps/api/pyproject.toml", root / "Dockerfile", root / "docker-compose.yml"]:
    if m.is_file():
        parts += [l.strip().lower() for l in m.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip() and not l.strip().startswith("#")]
skip = {p.name for p in (root / "apps/api/novara_core/modules").glob("*boundary*.py")}
for s in (root / "apps/api/novara_core/modules").rglob("*.py"):
    if s.name in skip: continue
    parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
for s in [root / "apps/web/index.html", root / "apps/web/app.js"]:
    if s.is_file(): parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
text = "\n".join(parts)
for rid in "GB-194 GB-205 GB-213 GB-234 GB-239 GB-250".split():
    tok = rows[rid]["Exact source feature name"].strip().lower()
    print(rid, tok, "PRESENT" if tok in text else "absent", "|", rows[rid]["Current status"])
    if tok in text:
        i = text.find(tok)
        print("  context:", repr(text[max(0, i-80):i+80]))
