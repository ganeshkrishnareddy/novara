"""One-off validator for the ten source inventories. Read-only; prints a report."""
from pathlib import Path
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY\SOURCES")
PREFIXES = {
    "01-formbricks.md": "FB",
    "02-meilisearch.md": "MS",
    "03-growthbook.md": "GB",
    "04-papermark.md": "PM",
    "05-plane.md": "PL",
    "06-mautic.md": "MT",
    "07-chatwoot.md": "CW",
    "08-novu.md": "NV",
    "09-marketingskills.md": "MK",
    "10-sellbird.md": "SB",
}
STATUSES = {
    "VERIFIED_COMPLETE", "IMPLEMENTED_UNVERIFIED", "PARTIALLY_IMPLEMENTED",
    "BACKEND_ONLY", "FRONTEND_ONLY", "NOT_IMPLEMENTED",
    "EXTERNAL_DEPENDENCY_BLOCKED", "LICENSING_RESTRICTED",
    "INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION",
}
AVAILABILITY = {"AVAILABLE", "GATED", "ADVERTISED_UNVERIFIED", "PAID_HOSTED_ONLY"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
EXPECTED_HEADER = [
    "ID", "Source repository", "Exact source feature name", "Description",
    "Source location / documentation reference", "Community availability",
    "Current status", "NOVARA module", "NOVARA implementation location",
    "Backend status", "Frontend status", "Database status", "API status",
    "Permissions / security status", "Integration status", "Tests / evidence",
    "Licensing constraint", "Priority", "Dependencies", "Remaining work",
    "Final acceptance criteria",
]

all_ok = True
total_rows = 0
status_counts = {s: 0 for s in STATUSES}
prefix_counts = {}

for fname, prefix in PREFIXES.items():
    path = BASE / fname
    if not path.exists():
        print(f"MISSING: {fname}")
        all_ok = False
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| ID |") or line.strip().startswith("|ID|"):
            header_idx = i
            break
    problems = []
    if header_idx is None:
        problems.append("no table header found")
        rows = []
    else:
        cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
        if cells != EXPECTED_HEADER:
            problems.append(f"header mismatch ({len(cells)} cols): {cells}")
        rows = []
        for line in lines[header_idx + 2:]:
            stripped = line.strip()
            if stripped == "":
                continue
            if not stripped.startswith("|"):
                break
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) != len(EXPECTED_HEADER):
                problems.append(f"row has {len(cells)} cols, expected 21: {cells[:2]}")
                continue
            rows.append(cells)
    ids = [r[0] for r in rows]
    expected_ids = [f"{prefix}-{n:03d}" for n in range(1, len(rows) + 1)]
    if ids != expected_ids:
        bad = [(i + 1, a, b) for i, (a, b) in enumerate(zip(ids, expected_ids)) if a != b]
        if len(ids) != len(expected_ids):
            problems.append(f"count {len(ids)} vs expected {len(expected_ids)}")
        if bad:
            problems.append(f"ID sequence mismatch first: {bad[:3]}")
    for idx, r in enumerate(rows, 1):
        if r[6] not in STATUSES:
            problems.append(f"row {idx} bad Current status: {r[6]!r}")
        else:
            status_counts[r[6]] += 1
        if r[5] not in AVAILABILITY:
            problems.append(f"row {idx} bad Community availability: {r[5]!r}")
        if r[17] not in PRIORITIES:
            problems.append(f"row {idx} bad Priority: {r[17]!r}")
    prefix_counts[prefix] = len(rows)
    total_rows += len(rows)
    if problems:
        all_ok = False
        print(f"FAIL {fname} ({len(rows)} rows)")
        for p in problems[:12]:
            print(f"   - {p}")
    else:
        print(f"OK   {fname} - {len(rows)} rows, {ids[0]}..{ids[-1]}" if ids else f"OK   {fname} - 0 rows")

print()
print("PREFIX COUNTS:", prefix_counts)
print("TOTAL ROWS:", total_rows)
print("STATUS COUNTS:")
for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"   {s}: {c}")
print("ALL VALID:", all_ok)
