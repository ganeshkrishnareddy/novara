import re
from pathlib import Path
tests = set(re.findall(r"^def (test_\w+)", Path(r"D:\NOVARA\apps\api\tests\test_external_dependency_boundary_p2.py").read_text(encoding="utf-8"), re.M))
script = Path(r"D:\NOVARA\docs\FEATURE_PARITY\_close_external_dependency_boundary.py").read_text(encoding="utf-8")
names = set(re.findall(r"[\"'](test_\w+)[\"']", script))
print("tests", len(tests), "closure names", len(names))
print("missing in tests:", sorted(names - tests))
print("extra in tests:", sorted(tests - names))
