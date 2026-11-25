import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
res = [r for r in rows if r["Current status"] == "LICENSING_RESTRICTED"]
negkw = ["no ee code", "absent from", "no ", "not ", "out-of-scope", "never", "without licensed source", "no claim"]
poskw = ["named test and ui evidence prove", "full source capability", "real novara behaviour"]
groups = collections.Counter()
for r in res:
    ac = r["Final acceptance criteria"].lower().strip()
    if any(k in ac for k in poskw):
        groups["positive"] += 1
    elif any(ac.startswith(k) for k in negkw):
        groups["negative"] += 1
    else:
        groups["other"] += 1
print(groups)
sig = collections.Counter(r["Final acceptance criteria"] for r in res)
for k, v in sig.most_common(40):
    print(v, "::", k[:170].replace("\n", " "))
