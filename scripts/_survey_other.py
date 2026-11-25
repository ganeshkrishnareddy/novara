import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
open_rows = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED")]
def classify(ac):
    a = ac.lower().strip()
    if "absent from" in a or "is not claimed" in a or "no " in a[:20] or "never " in a[:20] or "out-of-scope" in a[:30] or "not advertised" in a[:40]:
        return "negative"
    if "named test" in a or "browser evidence" in a or "verified" in a:
        return "positive-test"
    return "other"
other = [r for r in open_rows if classify(r["Final acceptance criteria"]) == "other"]
print("other", len(other))
print(collections.Counter(r["Source project"] for r in other))
sig = collections.Counter(r["Final acceptance criteria"].strip() for r in other)
for k, v in sig.most_common(20):
    print(v, "::", k[:170])
for r in other:
    print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:48], "||", r["Final acceptance criteria"][:150].replace("\n", " "))
