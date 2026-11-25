import re
from pathlib import Path
root = Path(r"D:\NOVARA")
tests_src = (root / "apps/api/tests/test_no_claim_evidence_boundary_p2.py").read_text(encoding="utf-8")
tests = set(re.findall(r"^def (test_\w+)", tests_src, re.M))
script = (root / "docs/FEATURE_PARITY/_close_no_claim_evidence.py").read_text(encoding="utf-8")
names = set(re.findall(r"[\"'](test_\w+)[\"']", script))
print("tests", len(tests), "closure names", len(names))
print("missing in tests:", sorted(names - tests))
print("extra in tests:", sorted(tests - names))
# Recreate the source scan used by the generated tests and verify each token is absent.
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
block = re.search(r"FORBIDDEN_TOKENS[^=]*=\s*\{(.*?)\n\}", tests_src, re.S).group(1)
pairs = re.findall(r'"([^"]+)": \(\s*"([^"]+)",', block)
present = [(rid, tok) for rid, tok in pairs if tok.lower() in text]
print("token pairs", len(pairs), "present", present)
