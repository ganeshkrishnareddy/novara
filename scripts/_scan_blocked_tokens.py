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

ids = set("""FB-031 FB-077 FB-102 FB-103 FB-105 FB-106 FB-111 FB-112 FB-113 FB-114 FB-115 FB-116 FB-117 FB-118 FB-119 FB-120 FB-121 FB-122 FB-123 FB-150 FB-154 FB-163 FB-164 FB-165 FB-166 FB-169 FB-170 FB-171 FB-172 FB-173 FB-174 FB-175 FB-176 FB-178 FB-226 FB-227 FB-228 MS-083 MS-084 MS-085 MS-086 MS-087 MS-099 GB-119 GB-120 GB-121 GB-122 GB-123 GB-124 GB-125 GB-126 GB-127 GB-128 GB-129 GB-130 GB-131 GB-132 GB-133 PM-138 PM-140 MT-110 CW-033 CW-037 CW-038 CW-041 CW-045 CW-047 CW-073 CW-085 CW-107 CW-124 CW-127 CW-145 CW-161 CW-163 NV-080 NV-098 SB-001 SB-002 SB-004 SB-005 SB-006 SB-007 SB-025 SB-027 SB-029 SB-032 SB-045 SB-064 SB-073 SB-074 SB-075 SB-076 SB-077""".split())
rows = [r for r in csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8")) if r["ID"] in ids]
present, absent = [], []
for r in rows:
    tok = r["Exact source feature name"].strip().lower()
    if tok in text:
        present.append((r["ID"], r["Exact source feature name"], text.count(tok)))
    else:
        absent.append((r["ID"], r["Exact source feature name"]))
print("absent", len(absent), "present", len(present))
print("--- present ---")
for rid, name, cnt in present:
    print(rid, "|", name, "|", cnt)
