import csv, collections
from pathlib import Path
root = Path(r"D:\NOVARA")
rows = [r for r in csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))
        if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")]
mods = (root / "apps/api/novara_core/modules")
skip = {p.name for p in mods.glob("*boundary*.py")}
src_parts = []
for p in mods.rglob("*.py"):
    if p.name in skip: continue
    src_parts.append(p.read_text(encoding="utf-8", errors="replace").lower())
for p in [root/"apps/api/pyproject.toml", root/"Dockerfile", root/"docker-compose.yml", root/"apps/web/index.html", root/"apps/web/app.js"]:
    if p.is_file(): src_parts.append(p.read_text(encoding="utf-8", errors="replace").lower())
src = "\n".join(src_parts)
test_text = "\n".join(p.read_text(encoding="utf-8", errors="replace").lower() for p in (root/"apps/api/tests").glob("*.py"))
present = []
for r in rows:
    tok = r["Exact source feature name"].strip().lower()
    if tok and tok in src:
        named = f"test_{r['ID'].lower().replace('-','_')}" in test_text
        present.append((r, named))
print("remaining", len(rows), "token present in active sources", len(present), "with named test", sum(1 for _,n in present if n))
for r, n in present:
    print(("NAMED " if n else "      "), r["ID"], r["Current status"][:4], r["Source project"], "|", r["Exact source feature name"], "||", r["Final acceptance criteria"][:120].replace("\n"," "))
