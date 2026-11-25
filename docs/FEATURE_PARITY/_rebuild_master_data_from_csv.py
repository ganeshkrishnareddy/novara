"""Rebuild _master_data.json aggregates from the live matrix CSV (never from SOURCES)."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
with (BASE / "MASTER_FEATURE_MATRIX.csv").open(encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))

status_all = Counter(r["Current status"] for r in rows)
verified = status_all.get("VERIFIED_COMPLETE", 0)
replaced = status_all.get("INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION", 0)
accounted = verified + replaced
total = len(rows)
summary = {
    "source": "MASTER_FEATURE_MATRIX.csv (live)",
    "total": total,
    "status_all": dict(status_all),
    "accounting": {
        "verified_complete": verified,
        "intentionally_replaced": replaced,
        "complete_or_equivalent_or_code_exists": accounted,
        "complete_pct_of_total": round(100.0 * accounted / total, 2),
        "remaining_not_implemented": status_all.get("NOT_IMPLEMENTED", 0),
        "remaining_partial": status_all.get("PARTIALLY_IMPLEMENTED", 0),
        "remaining_restricted": status_all.get("LICENSING_RESTRICTED", 0),
        "remaining_blocked": status_all.get("EXTERNAL_DEPENDENCY_BLOCKED", 0),
    },
}
(BASE / "_master_data.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("rebuilt _master_data.json from live CSV:", summary["accounting"])
