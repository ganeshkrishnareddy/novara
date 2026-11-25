import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
res = [r for r in rows if r["Current status"] == "LICENSING_RESTRICTED"]
print("restricted", len(res))
print("by project", collections.Counter(r["Source project"] for r in res))
sig = collections.Counter(r["Final acceptance criteria"] for r in res)
for k, v in sig.most_common(12):
    print(v, "::", k[:180].replace("\n", " "))
print("--- sample ---")
for r in res[:12]:
    print(r["ID"], "|", r["Exact source feature name"][:50], "||", r["Final acceptance criteria"][:150].replace("\n", " "))
