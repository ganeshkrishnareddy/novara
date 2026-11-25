"""Discover module tables not yet covered by any Alembic migration.

Read-only: imports all modules, compares Base.metadata against tables named in
migration files (op.create_table plus idempotent TABLES tuples).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))

from novara_core.database import Base
from novara_core.modules import import_all

import_all()

module_tables = set(Base.metadata.tables)

covered: set[str] = set()
for path in sorted((API / "migrations" / "versions").glob("*.py")):
    text = path.read_text(encoding="utf-8")
    covered.update(re.findall(r"op\.create_table\(\s*['\"]([a-z0-9_]+)['\"]", text))
    # Idempotent generator writes quoted names one per line inside TABLES tuple.
    for m in re.finditer(r"TABLES\s*=\s*\((.*?)\)", text, re.S):
        covered.update(re.findall(r"['\"]([a-z0-9_]+)['\"]", m.group(1)))
    covered.update(re.findall(r'op\.drop_table\(["\']([a-z0-9_]+)["\']\)', text))

missing = sorted(module_tables - covered)
print(f"module tables: {len(module_tables)}")
print(f"covered by migrations: {len(covered & module_tables)}")
print(f"MISSING ({len(missing)}):")
for name in missing:
    print("  ", name)
