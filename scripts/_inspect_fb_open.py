import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
sigs = [
    "Full source capability covered by named passing tests, permissions, persistence and a UI route; row re-assessed as VERIFIED_COMPLETE.",
    "Real NOVARA behaviour with named passing tests, workspace isolation, permissions, persistence and a UI route; row re-assessed as VERIFIED_COMPLETE.",
]
sel = [r for r in rows if r["Final acceptance criteria"].strip() in sigs and r["Current status"] != "VERIFIED_COMPLETE"]
print("open", len(sel))
for r in sel:
    print("===", r["ID"], "|", r["Current status"], "|", r["Exact source feature name"])
    for k in ["NOVARA module", "NOVARA implementation location", "Backend status", "Frontend status", "API status", "Tests / evidence", "Remaining work"]:
        print("  ", k, ":", r[k][:220].replace("\n", " "))
