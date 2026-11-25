import csv, collections, re
from pathlib import Path
rows = [r for r in csv.DictReader(open(Path(r"D:\NOVARA\docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv"), encoding="utf-8"))
        if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")]
buckets = collections.defaultdict(list)
for r in rows:
    ac = r["Final acceptance criteria"].lower()
    if "inventory row retained" in ac or "audit-only" in ac:
        buckets["audit_only"].append(r)
    elif ("named test" in ac or "named passing test" in ac) and not any(k in ac for k in ("browser", "ui route", "real provider", "verified provider", "container", "deployment", "signed webhook", "delivery receipt", "published", "oauth callback")):
        if any(k in ac for k in ("workspace", "permission", "persist", "isolation", "stored", "evaluated", "computed", "renders", "round-trip", "rejects secrets", "fires once", "matches", "hooks", "documented and tested")):
            buckets["named_test_local"].append(r)
        else:
            buckets["named_test_weak"].append(r)
    elif any(k in ac for k in ("browser", "ui route", "ui evidence", "rendering", "frontend")):
        buckets["ui_required"].append(r)
    elif any(k in ac for k in ("provider", "delivery", "webhook", "oauth", "sso", "deployment", "container", "signed", "receipt", "quota", "verified instance")):
        buckets["external_required"].append(r)
    else:
        buckets["other"].append(r)
print({k: len(v) for k, v in buckets.items()})
for k in ("named_test_local", "named_test_weak"):
    print("\n===", k, len(buckets[k]), "===")
    for r in buckets[k]:
        print(r["ID"], "|", r["Source project"], "|", r["Exact source feature name"][:35], "||", r["Final acceptance criteria"][:130].replace("\n", " "))
