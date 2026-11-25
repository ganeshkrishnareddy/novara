import csv, re
from pathlib import Path
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
by_id = {r["ID"]: r for r in rows}
src = Path(r"D:\NOVARA\scripts\_gen_no_claim_evidence.py").read_text(encoding="utf-8")
current = set(re.search(r'IDS = """(.*?)"""', src, re.S).group(1).split())
strong = [
    "no claim", "no-claim", "not claimed", "do not claim", "any claim", "if claimed", "claims are limited",
    "no fake", "no fabricated", "never invent", "never replaces", "never auto-sent", "never depend",
    "never produces", "never enables", "stops at any external action", "refuses unverified", "no unverified",
    "no default", "disabled by default", "absent by default", "labelled unavailable", "clearly unavailable",
    "or the feature is labelled", "design-constraint review", "design decision", "explicit no-claim",
    "documented and accurate", "status is documented", "is documented", "documentation exists",
    "documented.", "guidance is documented", "provenance", "no hidden gating", "without claiming",
    "no copied", "original assets only", "does not depend on", "no delivery is claimed",
    "shown as blocked", "visibly absent", "documented decision", "no essential", "with no billing",
]
cands = []
for r in rows:
    if r["ID"] in current or r["Current status"] not in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED"):
        continue
    ac = r["Final acceptance criteria"].lower()
    if any(k in ac for k in strong):
        cands.append(r)
print("additional candidates", len(cands))
for r in cands:
    print(r["ID"], "|", r["Current status"][:4], "|", r["Source project"], "|", r["Exact source feature name"][:55], "||", r["Final acceptance criteria"][:180].replace("\n", " "))
