import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
sel = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED") and any(k in r["Final acceptance criteria"].lower() for k in ["never", "only ", "only with", "only when", "if ", "unless", "until", "no ", "not ", "without ", "absent", "stops", "refuse", "blocked", "unavailable", "optional"])]
print(len(sel), collections.Counter(r["Source project"] for r in sel))
for r in sel:
    print(r["ID"], "|", r["Current status"][:4], "|", r["Exact source feature name"][:48], "||", r["Final acceptance criteria"][:200].replace("\n", " "))
