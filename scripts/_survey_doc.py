import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
open_rows = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED")]
kw = ["document", "design decision", "no-claim", "policy", "guidance", "release guidance", "provenance", "licence provenance", "status is documented", "hosting guidance"]
sel = [r for r in open_rows if any(k in r["Final acceptance criteria"].lower() for k in kw)]
print("doc-ish", len(sel))
print(collections.Counter(r["Source project"] for r in sel))
for r in sel:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:52], "||", r["Final acceptance criteria"][:160].replace("\n", " "))
