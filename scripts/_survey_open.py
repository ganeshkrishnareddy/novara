import csv, collections, re
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
open_rows = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED")]
print("open", len(open_rows))
print("by project", collections.Counter(r["Source project"] for r in open_rows))
print("by status", collections.Counter(r["Current status"] for r in open_rows))

def classify(ac):
    a = ac.lower().strip()
    if "absent from" in a or "is not claimed" in a or "no " in a[:20] or "never " in a[:20] or "out-of-scope" in a[:30] or "not advertised" in a[:40]:
        return "negative"
    if "named test" in a or "browser evidence" in a or "verified" in a:
        return "positive-test"
    return "other"

print("AC classes", collections.Counter(classify(r["Final acceptance criteria"]) for r in open_rows))
print("--- repeated AC signatures (top 25) ---")
sig = collections.Counter(r["Final acceptance criteria"].strip() for r in open_rows)
for k, v in sig.most_common(25):
    print(v, "::", k[:170].replace("\n", " "))
print("--- negative rows by project ---")
neg = [r for r in open_rows if classify(r["Final acceptance criteria"]) == "negative"]
print(collections.Counter(r["Source project"] for r in neg))
for r in neg[:120]:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:48], "||", r["Final acceptance criteria"][:130].replace("\n", " "))
