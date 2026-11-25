import csv
from pathlib import Path
import re
src = Path(r"D:\NOVARA\scripts\_gen_no_claim_evidence.py").read_text(encoding="utf-8")
m = re.search(r'IDS = """(.*?)"""', src, re.S)
ids = m.group(1).split()
ids = [i for i in ids if i not in ("CW-163", "PM-138", "PM-140")]
rows = {r["ID"]: r for r in csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))}
print("count", len(ids))
for rid in ids:
    r = rows[rid]
    print(f"{rid} | {r['Current status'][:4]} | {r['Exact source feature name'][:50]} || {r['Final acceptance criteria']}")
