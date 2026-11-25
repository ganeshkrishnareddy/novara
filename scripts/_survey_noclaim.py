import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
open_rows = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED")]
kw = [
    "do not claim", "no claim", "not claimed", "any claim", "if claimed", "claims are limited",
    "unverified", "absent", "without claiming", "no fake", "only descriptive", "explicit no-claim",
    "decision plus", "documented and accurate", "status is documented", "documented", "documentation",
    "design-constraint", "no hidden gating", "provenance", "release guidance", "hosting guidance",
]
sel = [r for r in open_rows if any(k in r["Final acceptance criteria"].lower() for k in kw)]
print("no-claim/doc candidates", len(sel))
print(collections.Counter(r["Source project"] for r in sel))
print(" ".join(r["ID"] for r in sel))
