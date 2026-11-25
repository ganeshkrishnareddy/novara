import csv, collections, re
from pathlib import Path
root = Path(r"D:\NOVARA")
rows = [r for r in csv.DictReader(open(root / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv", encoding="utf-8"))
        if r["Current status"] in ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")]
parts = []
for m in [root / "apps/api/pyproject.toml", root / "Dockerfile", root / "docker-compose.yml"]:
    if m.is_file():
        parts += [l.strip().lower() for l in m.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip() and not l.strip().startswith("#")]
skip = {p.name for p in (root / "apps/api/novara_core/modules").glob("*boundary*.py")}
for s in (root / "apps/api/novara_core/modules").rglob("*.py"):
    if s.name in skip: continue
    parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
for s in [root / "apps/web/index.html", root / "apps/web/app.js"]:
    if s.is_file(): parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
text = "\n".join(parts)
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
    "absent from the default", "or the feature is not advertised", "never sent", "no send", "no external message",
    "blocked until", "only with verified", "only when a verified", "only from a verified", "never depends",
    "no copied source", "no script injection", "no menu item", "no placeholder", "no external action",
]
sel = []
for r in rows:
    ac = r["Final acceptance criteria"].lower()
    if any(k in ac for k in strong):
        tok = r["Exact source feature name"].strip().lower()
        sel.append((r, tok, tok not in text))
print("remaining", len(rows), "strong candidates", len(sel), "tokens absent", sum(1 for _, _, ok in sel if ok))
print("by status", collections.Counter(r["Current status"] for r, _, _ in sel if _))
print("by project", collections.Counter(r["Source project"] for r, _, _ in sel if _))
for r, tok, ok in sel:
    print(("absent " if ok else "PRESENT"), r["ID"], "|", r["Current status"][:4], "|", r["Source project"], "|", r["Exact source feature name"][:50], "||", r["Final acceptance criteria"][:160].replace("\n", " "))
