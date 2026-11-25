import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
res = [r for r in rows if r["Current status"] == "LICENSING_RESTRICTED"]
print("total", len(res))
print("by project", collections.Counter(r["Source project"] for r in res))
for r in res:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:50], "||", r["Final acceptance criteria"][:180].replace("\n", " "))
