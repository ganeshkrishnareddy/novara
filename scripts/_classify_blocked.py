import csv, collections
rows = list(csv.DictReader(open(r"D:\NOVARA\docs\FEATURE_PARITY\MASTER_FEATURE_MATRIX.csv", encoding="utf-8")))
blocked = [r for r in rows if r["Current status"] == "EXTERNAL_DEPENDENCY_BLOCKED"]

# Rows whose AC requires a real verified external instance/deployment/send are excluded.
exclude_kw = [
    "verified sandbox", "verified external instance", "send and report delivery", "provider configuration",
    "verified provider configuration", "verified infrastructure evidence", "real postgresql connection",
    "verified redis-backed queue", "verified index returns", "retrievable from a verified provider",
    "real container run", "real ci logs", "verified heroku deployment", "verified cluster deployment",
    "verified compose stack", "verified chart install", "named test and ui evidence prove managed warehouse",
    "named test and ui evidence prove", "delivered: false", "provider response", "authenticates to the local instance",
]

def ok(r):
    a = r["Final acceptance criteria"].lower().strip()
    if any(k in a for k in exclude_kw):
        return False
    # must be a no-claim / no-default / design-review criterion
    pos = ["no ", "never ", "not ", "absent by default", "unavailable", "disabled by default",
           "labelled blocked", "design-constraint review", "docs/design review", "named test proves",
           "no new mandatory", "no cloud", "no environment variable", "no separate", "documented",
           "explicit state labels", "configuration", "opt-in"]
    return any(a.startswith(k) or k in a for k in pos)

sel = [r for r in blocked if ok(r)]
print("closable candidates", len(sel), "of", len(blocked))
print(collections.Counter(r["Source project"] for r in sel))
print("--- excluded ---")
for r in blocked:
    if not ok(r):
        print(r["ID"], "|", r["Final acceptance criteria"][:140].replace("\n", " "))
print("--- selected ids ---")
print(" ".join(r["ID"] for r in sel))
