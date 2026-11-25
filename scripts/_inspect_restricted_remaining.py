import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
res = [r for r in rows if r["Current status"] == "LICENSING_RESTRICTED"]
print("total", len(res))
print("by project", collections.Counter(r["Source project"] for r in res))
sig = collections.Counter(r["Final acceptance criteria"] for r in res)
for k, v in sig.most_common(20):
    print(v, "::", k[:190].replace("\n", " "))
print("--- all ---")
for r in res:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:45], "||", r["Final acceptance criteria"][:130].replace("\n", " "))
