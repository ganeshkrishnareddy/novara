import re
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
MODULE = ROOT / "apps/api/novara_core/modules/parity_capabilities.py"
TOKENS = [line.strip() for line in (ROOT / "scripts/_boundary_tokens.txt").read_text(encoding="utf-8").splitlines() if line.strip()]

text = MODULE.read_text(encoding="utf-8")
# Only inspect the SPECS table descriptions (inside the SPECS dict).
start = text.index("SPECS = {")
end = text.index("\n}\n", start)
block = text[start:end]

hits = {}
for tok in TOKENS:
    if len(tok) < 4:
        continue
    found = [line for line in block.splitlines() if tok in line.lower()]
    if found:
        hits[tok] = found
print("tokens present in SPECS:", len(hits))
for tok, found in sorted(hits.items()):
    print(repr(tok), len(found), found[0].strip()[:130])
