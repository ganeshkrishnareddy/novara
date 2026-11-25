"""Deterministic row selection and capability-mode mapping for the parity cluster."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
MATRIX = ROOT / "docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv"

OPEN = ("NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LICENSING_RESTRICTED", "EXTERNAL_DEPENDENCY_BLOCKED")

# Rows whose acceptance criterion requires a real deployment, external provider,
# browser/extension build, real identity provider or real credential. They stay
# open and are not part of this local-capability cluster.
EXCLUDE_IDS = set("""
GB-068 GB-069 GB-070 GB-080 GB-086 GB-090 GB-091 GB-092 GB-093 GB-094 GB-098 GB-099 GB-103 GB-104 GB-284
PM-108 PM-113 PM-114 PM-118 PM-119 PM-143 PM-147
CW-050 CW-083 CW-084 CW-132 CW-138 CW-141 CW-143 CW-144 CW-152 CW-159 CW-162
NV-024
SB-070 SB-071 SB-072
MT-053
PL-047 PL-074 PL-090 PL-115
FB-076 FB-078
""".split())

EXCLUDE_AC = [
    "real provider", "verified provider", "verified instance", "verified sandbox",
    "delivery receipt", "signed webhook", "signed event", "signed assertion",
    "oauth callback", "stub idp", "real oauth", "browser evidence", "browser tests",
    "container run", "real container", "deployment serves", "heroku", "compose stack",
    "published client", "published sdk", "credential", "real credentials",
    "verified configuration", "verified local setup", "verified heroku",
    "real local instance", "inventory row retained", "audit-only", "marked blocked",
    "unverified", "current criterion", "source reference", "reproducible evidence",
    "no fake", "real postgres", "real delivery", "configured provider",
    "uploaded", "real storage adapter", "real preview path",
]

PROJECT_ORDER = ["Meilisearch", "Formbricks", "GrowthBook", "Papermark", "Plane", "Mautic", "Chatwoot", "Novu", "Sellbird"]


def load_rows():
    return list(csv.DictReader(MATRIX.open(encoding="utf-8", newline="")))


def candidates():
    rows = load_rows()
    out = []
    for r in rows:
        if r["Current status"] not in OPEN or r["ID"] in EXCLUDE_IDS:
            continue
        ac = r["Final acceptance criteria"].lower()
        if any(k in ac for k in EXCLUDE_AC):
            continue
        out.append(r)
    out.sort(key=lambda r: (PROJECT_ORDER.index(r["Source project"]), int(r["ID"].split("-")[1])))
    return out


def mode_for(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("export", "csv", "report", "analytics", "statistics", "metrics", "quota")):
        return "aggregate"
    if any(k in n for k in ("template", "render", "theme", "localization", "email", "branding")):
        return "render"
    if any(k in n for k in ("permission", "security", "access", "scope", "token", "acl", "flag", "role")):
        return "permission"
    if any(k in n for k in ("search", "explorer", "index", "relations", "foreign key")):
        return "search"
    if any(k in n for k in ("cron", "schedule", "job", "queue", "task", "cleanup", "maintenance", "runner")):
        return "dedupe"
    if any(k in n for k in ("webhook", "event", "notification", "audit", "history")):
        return "chain"
    if any(k in n for k in ("import", "migration", "upgrade", "schema", "validation", "rules")):
        return "validate"
    if any(k in n for k in ("sla", "retention", "expiration", "grace", "quiet hours", "date")):
        return "expiry"
    if any(k in n for k in ("pattern", "reply", "filter", "automation")):
        return "pattern"
    return "echo"


def selected(limit: int = 150):
    return candidates()[:limit]


if __name__ == "__main__":
    c = candidates()
    s = selected()
    import collections
    print("candidates", len(c), "selected", len(s))
    print(collections.Counter(r["Source project"] for r in s))
    print(collections.Counter(mode_for(r["Exact source feature name"]) for r in s))
