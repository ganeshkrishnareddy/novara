import csv, collections
from pathlib import Path
IDS = """MS-101 PL-075 PL-143 PL-152 MT-005 MT-006 MT-038 MT-061 MT-084 MT-085 MT-087 MT-088 MT-090 MT-091 MT-103 MT-104 MT-119 MT-120 MT-125 MT-128 MT-131 MT-132 MT-133 CW-026 CW-034 CW-044 CW-046 CW-058 CW-061 CW-062 CW-063 CW-064 CW-068 CW-069 CW-070 CW-071 CW-072 CW-079 CW-080 CW-082 CW-103 CW-125 CW-126 CW-128 CW-136 CW-147 CW-150 CW-154 CW-156 CW-157 CW-165 NV-016 NV-021 NV-037 NV-049 NV-050 NV-064 NV-076 NV-083 NV-117 PL-126 PL-131 PL-155 SB-034 SB-039 SB-040 SB-041 SB-044 SB-047 SB-049 SB-050 SB-058 SB-059 SB-063 SB-065 SB-066 SB-068 GB-194 GB-205 GB-213 GB-234 GB-239 GB-250 MK-038 MT-056 FB-193 NV-075""".split()
OVERRIDES = {rid: "growthbook " + rid_name for rid, rid_name in {
    "GB-194": "simulate", "GB-205": "teams", "GB-213": "custom-roles", "GB-234": "holdouts", "GB-239": "dashboards", "GB-250": "releases",
}.items()}
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
present = []
print("count", len(IDS), "unique", len(set(IDS)))
for rid in IDS:
    r = rows[rid]
    tok = OVERRIDES.get(rid, r["Exact source feature name"].strip().lower())
    ok = tok not in text
    print(("absent " if ok else "PRESENT"), rid, "|", r["Current status"][:4], "|", tok)
    if not ok:
        present.append(rid)
print("present ids", present)
