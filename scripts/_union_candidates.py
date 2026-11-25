import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
by_id = {r["ID"]: r for r in rows}
a = set("""MS-101 PL-075 PL-143 PL-152 MT-002 MT-005 MT-010 MT-038 MT-056 MT-061 MT-063 MT-071 MT-081 MT-084 MT-085 MT-087 MT-088 MT-090 MT-091 MT-103 MT-104 MT-119 MT-120 MT-125 MT-128 MT-129 MT-130 MT-131 MT-132 MT-133 CW-026 CW-094 CW-128 CW-150 CW-152 NV-016 NV-029 NV-064 NV-097 NV-102 MK-024 MK-053 SB-052 SB-059 SB-068""".split())
b = set("""MS-101 GB-118 PM-070 PL-075 PL-143 PL-152 MT-005 MT-038 MT-056 MT-061 MT-081 MT-084 MT-087 MT-088 MT-090 MT-091 MT-103 MT-104 MT-119 MT-120 MT-125 MT-128 MT-129 MT-131 MT-132 MT-133 CW-046 CW-058 CW-061 CW-062 CW-063 CW-068 CW-069 CW-071 CW-146 CW-148 CW-149 CW-153 CW-154 CW-157 NV-049 NV-075 NV-100 NV-117 SB-044 SB-068""".split())
u = sorted(a | b)
print("union", len(u))
print(collections.Counter(by_id[i]["Source project"] for i in u))
print(collections.Counter(by_id[i]["Current status"] for i in u))
for i in u:
    print(i, "|", by_id[i]["Current status"][:4], "|", by_id[i]["Exact source feature name"][:52], "||", by_id[i]["Final acceptance criteria"][:140].replace("\n", " "))
