import csv
from pathlib import Path

rows = [r for r in csv.DictReader(open(Path(r"D:\NOVARA\docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv"), encoding="utf-8"))
        if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")]

EXCLUDE = [
    "real provider", "verified provider", "verified instance", "verified sandbox",
    "delivery receipt", "signed webhook", "signed event", "signed assertion",
    "oauth callback", "stub idp", "real oauth", "browser evidence", "browser tests",
    "container run", "real container", "deployment serves", "heroku", "compose stack",
    "published client", "published sdk", "credential", "real credentials",
    "verified configuration", "verified local setup", "verified heroku", "real local instance",
    "inventory row retained", "audit-only", "marked blocked", "unverified",
    "current criterion", "source reference", "reproducible evidence",
    "no fake", "real postgres", "real delivery", "configured provider",
    "uploaded", "real storage adapter", "real preview path",
]

local = []
for r in rows:
    ac = r["Final acceptance criteria"].lower()
    if any(k in ac for k in EXCLUDE):
        continue
    local.append(r)

print("candidates", len(local))
for r in local:
    print(r["ID"], "|", r["Current status"][:4], "|", r["Source project"], "|", r["Exact source feature name"][:38], "||", r["Final acceptance criteria"][:95].replace("\n", " "))
