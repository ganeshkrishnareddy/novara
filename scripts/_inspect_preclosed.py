import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
sigs = [
    "Full source capability covered by named passing tests, permissions, persistence and a UI route; row re-assessed as VERIFIED_COMPLETE.",
    "Real NOVARA behaviour with named passing tests, workspace isolation, permissions, persistence and a UI route; row re-assessed as VERIFIED_COMPLETE.",
]
sel = [r for r in rows if r["Final acceptance criteria"].strip() in sigs]
print("total", len(sel), "statuses", collections.Counter(r["Current status"] for r in sel))
print("by project", collections.Counter(r["Source project"] for r in sel))
for r in sel:
    print(r["ID"], "|", r["Current status"], "|", r["Source project"], "|", r["Exact source feature name"][:55], "|| tests:", r["Tests / evidence"][:150].replace("\n", " "))
