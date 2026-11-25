import csv
from pathlib import Path

IDS = """MS-101 GB-118 PL-075 PL-143 PL-152 MT-002 MT-005 MT-006 MT-038 MT-061 MT-071 MT-081 MT-084 MT-085 MT-087 MT-088 MT-090 MT-091 MT-103 MT-104 MT-119 MT-120 MT-125 MT-128 MT-129 MT-130 MT-131 MT-132 MT-133 CW-026 CW-046 CW-061 CW-062 CW-063 CW-068 CW-069 CW-071 CW-080 CW-103 CW-128 CW-150 CW-154 CW-156 CW-157 CW-165 NV-016 NV-021 NV-049 NV-050 NV-064 NV-117 SB-044 SB-052 SB-059 SB-068 PM-103 PM-130""".split()
root = Path(r"D:\NOVARA")
rows = {r["ID"]: r for r in csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))}
print("count", len(IDS))
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
for rid in IDS:
    r = rows[rid]
    tok = r["Exact source feature name"].strip().lower()
    print(("PRESENT" if tok in text else "absent "), rid, "|", r["Current status"], "|", tok, "|", r["Exact source feature name"][:50])
