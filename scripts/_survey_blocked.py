import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
blocked = [r for r in rows if r["Current status"] == "EXTERNAL_DEPENDENCY_BLOCKED"]
print("blocked", len(blocked))
print("by project", collections.Counter(r["Source project"] for r in blocked))
sig = collections.Counter(r["Final acceptance criteria"].strip() for r in blocked)
for k, v in sig.most_common(15):
    print(v, "::", k[:180].replace("\n", " "))
for r in blocked:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:52], "||", r["Final acceptance criteria"][:150].replace("\n", " "))
