"""Report forbidden tokens from existing boundary tests that appear in the new module."""
import re
from pathlib import Path

tests = Path(r"D:\NOVARA\apps\api\tests")
new_text = Path(r"D:\NOVARA\apps\api\novara_core\modules\extended_claim_boundary.py").read_text(encoding="utf-8").lower()
for p in tests.glob("test_*boundary*p2.py"):
    if p.name == "test_extended_claim_boundary_p2.py":
        continue
    text = p.read_text(encoding="utf-8")
    m = re.search(r"FORBIDDEN_TOKENS[^=]*=\s*\{(.*?)\n\}", text, re.S)
    if not m:
        continue
    toks = re.findall(r'"([^"]+)"', m.group(1))
    hits = sorted({t for t in toks if t.lower() in new_text})
    if hits:
        print(p.name, "->", hits)
