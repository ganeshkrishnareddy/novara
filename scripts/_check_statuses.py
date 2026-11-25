import csv
import collections
ids = "MS-005 MS-009 MS-010 MS-050 MS-051 MS-059 MS-096 MS-098 CW-119 PM-067 PM-136 PM-155 NV-041 NV-053 NV-055 NV-060 NV-061 NV-063 NV-066 NV-090 NV-091 NV-095 NV-108 NV-110 NV-114 SB-043".split()
rows = {r["ID"]: r for r in csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))}
print(collections.Counter(rows[i]["Current status"] for i in ids))
for i in ids:
    if rows[i]["Current status"] != "NOT_IMPLEMENTED":
        print(i, rows[i]["Current status"])
