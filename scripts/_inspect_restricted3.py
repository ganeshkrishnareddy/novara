import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
res = [r for r in rows if r["Current status"] == "LICENSING_RESTRICTED"]
negkw = ["no ee code", "absent from", "no ", "not ", "out-of-scope", "never", "without licensed source", "no claim"]
poskw = ["named test and ui evidence prove", "full source capability", "real novara behaviour"]
for r in res:
    ac = r["Final acceptance criteria"].lower().strip()
    if any(k in ac for k in poskw) or any(ac.startswith(k) for k in negkw):
        continue
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:45], "||", r["Final acceptance criteria"][:160].replace("\n", " "))
