import csv
from pathlib import Path
IDS = """MT-039 MT-054 MT-057 MT-058 MT-059 MT-060 MT-067 MT-073 MT-074 MT-076 MT-092 MT-094 CW-031 CW-079 CW-082 CW-109 CW-163 NV-022 NV-065 PL-069 PL-126 PL-131 PL-155 PM-138 PM-140""".split()
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
print("count", len(IDS))
for rid in IDS:
    r = rows[rid]
    tok = r["Exact source feature name"].strip().lower()
    print(("PRESENT" if tok in text else "absent "), rid, "|", r["Current status"], "|", tok, "|", r["Final acceptance criteria"][:100].replace("\n", " "))
