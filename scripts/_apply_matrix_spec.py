"""Apply evidence-gated, per-field matrix updates from a JSON spec.

Usage: python scripts/_apply_matrix_spec.py <spec.json>

The spec has the shape::

    {
      "defaults": {"evidence": "docs/evidence/...", "remaining": "..."},
      "rows": [
        {"id": "NV-003", "status": "VERIFIED_COMPLETE",
         "module": "...", "location": "...", "backend": "...",
         "frontend": "...", "database": "...", "api": "...",
         "permissions": "...", "integration": "...",
         "evidence": "...", "remaining": "..."}
      ]
    }

Every field is optional; only supplied fields are changed. This exists because
the simpler ``update_matrix_rows.py`` stamps a blanket frontend claim on every
row, which is not truthful for backend-only or design-constraint rows.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "docs" / "FEATURE_PARITY" / "MASTER_FEATURE_MATRIX.csv"

FIELDS = {
    "status": "Current status",
    "module": "NOVARA module",
    "location": "NOVARA implementation location",
    "backend": "Backend status",
    "frontend": "Frontend status",
    "database": "Database status",
    "api": "API status",
    "permissions": "Permissions / security status",
    "integration": "Integration status",
    "evidence": "Tests / evidence",
    "remaining": "Remaining work",
    "criteria": "Final acceptance criteria",
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    spec_path = Path(sys.argv[1]).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    defaults = spec.get("defaults", {})
    rows_in = spec.get("rows", [])
    if not rows_in:
        raise SystemExit("spec has no rows")

    with MATRIX.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames or []
    by_id = {row["Master ID"]: row for row in rows}

    unknown = [r["id"] for r in rows_in if r["id"] not in by_id]
    if unknown:
        raise SystemExit(f"IDs not found in matrix: {unknown}")

    for update in rows_in:
        row = by_id[update["id"]]
        merged = {**defaults, **update}
        for key, value in merged.items():
            if key == "id":
                continue
            if key not in FIELDS:
                raise SystemExit(f"Unknown field {key!r} for {update['id']}")
            if isinstance(value, str) and value.startswith("docs/evidence/"):
                for item in (part.strip() for part in value.split(";")):
                    if not item.startswith("docs/evidence/"):
                        continue
                    target = ROOT / item
                    if not target.exists():
                        raise SystemExit(f"Evidence file missing for {update['id']}: {item}")
            row[FIELDS[key]] = value

    with MATRIX.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Applied spec {spec_path.name} to {len(rows_in)} rows")


if __name__ == "__main__":
    main()
