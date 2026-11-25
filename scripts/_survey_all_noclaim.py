import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
cand = [r for r in rows if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")]
strong = [
    "no claim", "no-claim", "not claimed", "do not claim", "any claim", "if claimed", "claims are limited",
    "no fake", "no fabricated", "never invent", "never replaces", "never auto-sent", "never depend",
    "never produces", "never enables", "stops at any external action", "refuses unverified", "no unverified",
    "no default", "disabled by default", "absent by default", "labelled unavailable", "clearly unavailable",
    "or the feature is labelled", "design-constraint review", "design decision", "explicit no-claim",
    "documented and accurate", "status is documented", "is documented", "documentation exists",
    "documented.", "guidance is documented", "provenance", "no hidden gating", "without claiming",
    "no copied", "original assets only", "no script injection", "does not depend on", "no delivery is claimed",
]
sel = [r for r in cand if any(k in r["Final acceptance criteria"].lower() for k in strong)]
print("candidates", len(sel), collections.Counter(r["Current status"] for r in sel))
print(collections.Counter(r["Source project"] for r in sel))
for r in sel:
    print(r["ID"], "|", r["Current status"][:4], "|", r["Source project"], "|", r["Exact source feature name"][:48], "||", r["Final acceptance criteria"][:150].replace("\n", " "))
