import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
b = [r for r in rows if r["Current status"] == "EXTERNAL_DEPENDENCY_BLOCKED"]
print(len(b), collections.Counter(r["Source project"] for r in b))
for r in b:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:55], "||", r["Final acceptance criteria"])
