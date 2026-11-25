"""Report forbidden tokens from existing boundary tests that appear in a named module."""
import re
import sys
from pathlib import Path

tests = Path(r"D:\NOVARA\apps\api\tests")
target_name = sys.argv[1]
new_text = Path(r"D:\NOVARA\apps\api\novara_core\modules") / target_name
new_text = new_text.read_text(encoding="utf-8").lower()
for p in sorted(tests.glob("test_*boundary*p2.py")):
    if p.name.startswith("test_" + target_name.replace(".py", "").replace("_boundary", "_boundary")):
        continue
    text = p.read_text(encoding="utf-8")
    m = re.search(r"FORBIDDEN_TOKENS[^=]*=\s*\{(.*?)\n\}", text, re.S)
    if not m:
        continue
    toks = re.findall(r'"([^"]+)"', m.group(1))
    hits = sorted({t for t in toks if t.lower() in new_text})
    if hits:
        print(p.name, "->", hits)
