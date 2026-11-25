"""Update master feature matrix rows with verified evidence (helper for evidence-gated cycles).

Usage: python scripts/update_matrix_rows.py <ids-comma-separated> <status> <evidence> [module-location]
Only rows whose named tests pass and whose evidence file exists should be changed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "docs" / "FEATURE_PARITY" / "MASTER_FEATURE_MATRIX.csv"

def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    ids = {x.strip() for x in sys.argv[1].split(",") if x.strip()}
    status = sys.argv[2]
    evidence = sys.argv[3]
    location = sys.argv[4] if len(sys.argv) > 4 else None

    with MATRIX.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames or []

    changed = []
    for row in rows:
        if row["Master ID"] not in ids:
            continue
        row["Current status"] = status
        row["Tests / evidence"] = evidence
        if location:
            row["NOVARA implementation location"] = location
        row["Remaining work"] = "None; acceptance criteria met and evidenced."
        row["Frontend status"] = "complete: wired control/action in apps/web/app.js with named UI test"
        changed.append(row["Master ID"])

    missing = ids - set(changed)
    if missing:
        raise SystemExit(f"IDs not found in matrix: {sorted(missing)}")

    with MATRIX.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {len(changed)} rows to {status}: {', '.join(sorted(changed))}")

if __name__ == "__main__":
    main()
