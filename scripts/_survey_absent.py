import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
sel = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED") and ("absent" in r["Final acceptance criteria"].lower() or "not enabled" in r["Final acceptance criteria"].lower() or "not claimed" in r["Final acceptance criteria"].lower())]
print(len(sel), collections.Counter(r["Source project"] for r in sel))
for r in sel:
    print(r["ID"], "|", r["Current status"][:4], "|", r["Exact source feature name"][:52], "||", r["Final acceptance criteria"][:180].replace("\n", " "))
