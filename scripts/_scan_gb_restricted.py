import csv
from pathlib import Path

root = Path(r"D:\NOVARA")
parts = []
for m in [root / "apps/api/pyproject.toml", root / "Dockerfile", root / "docker-compose.yml"]:
    if m.is_file():
        parts += [l.strip().lower() for l in m.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip() and not l.strip().startswith("#")]
skip = {p.name for p in (root / "apps/api/novara_core/modules").glob("*boundary*.py")}
for s in (root / "apps/api/novara_core/modules").rglob("*.py"):
    if s.name in skip:
        continue
    parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
for s in [root / "apps/web/index.html", root / "apps/web/app.js"]:
    if s.is_file():
        parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
text = "\n".join(parts)

rows = list(csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
gb = [r for r in rows if r["Source project"] == "GrowthBook" and r["Current status"] == "LICENSING_RESTRICTED"]
absent, present = [], []
for r in gb:
    name = r["Exact source feature name"].strip()
    token = name.lower()
    if token in text:
        present.append((r["ID"], name, text.count(token)))
    else:
        absent.append((r["ID"], name))
print("GB restricted", len(gb), "absent", len(absent), "present", len(present))
print("--- present ---")
for rid, name, cnt in present:
    print(rid, "|", name, "|", cnt)
print("--- absent ids ---")
print(" ".join(rid for rid, _ in absent))
