import csv
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
mt = [r for r in rows if r["Source project"] == "Mautic" and r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED")]
print(len(mt))
for r in mt:
    print("===", r["ID"], "|", r["Current status"], "|", r["Exact source feature name"][:58])
    print("  LOC:", r["NOVARA implementation location"][:140].replace("\n", " "))
    print("  AC:", r["Final acceptance criteria"][:170].replace("\n", " "))
    print("  REM:", r["Remaining work"][:150].replace("\n", " "))
