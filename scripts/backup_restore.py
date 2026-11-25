#!/usr/bin/env python3
"""Local SQLite backup and restore for NOVARA.

Uses sqlite3's online backup API so a consistent copy is taken without stopping
the application. No network, cloud upload or external service is involved.

Examples:
    python scripts/backup_restore.py backup --db novara_dev.sqlite3 --out backups/
    python scripts/backup_restore.py verify --db backups/novara-20260101T120000.sqlite3
    python scripts/backup_restore.py restore --from <backup> --to <target-db>
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDIT_TABLES = (
    "users",
    "workspaces",
    "contacts",
    "leads",
    "tasks",
    "events",
    "jobs",
    "adapter_calls",
)


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {path}")
    return sqlite3.connect(path)


def _integrity(connection: sqlite3.Connection) -> str:
    return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    existing = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in AUDIT_TABLES
        if table in existing
    }


def _revision(connection: sqlite3.Connection) -> str | None:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "alembic_version" not in tables:
        return None
    row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    return str(row[0]) if row else None


def backup(db_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    target = out_dir / f"novara-{stamp}.sqlite3"
    if target.exists():
        target = out_dir / f"novara-{stamp}-{datetime.now().timestamp():.0f}.sqlite3"

    source = _connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()

    check = _connect(target)
    try:
        result = _integrity(check)
        if result != "ok":
            raise RuntimeError(f"backup failed integrity check: {result}")
        print(f"backup_created: {target}")
        print(f"integrity: {result}")
        print(f"revision: {_revision(check)}")
        print(f"counts: {_counts(check)}")
    finally:
        check.close()
    return target


def verify(db_path: Path) -> None:
    connection = _connect(db_path)
    try:
        print(f"database: {db_path}")
        print(f"integrity: {_integrity(connection)}")
        print(f"revision: {_revision(connection)}")
        print(f"counts: {_counts(connection)}")
    finally:
        connection.close()


def restore(from_path: Path, to_path: Path, force: bool) -> None:
    if to_path.exists() and not force:
        raise FileExistsError(f"target already exists: {to_path} (use --force to overwrite)")

    source = _connect(from_path)
    integrity = _integrity(source)
    if integrity != "ok":
        source.close()
        raise RuntimeError(f"backup failed integrity check: {integrity}")
    counts = _counts(source)
    revision = _revision(source)
    to_path.parent.mkdir(parents=True, exist_ok=True)

    # Restore into a temporary file, verify, then atomically replace the target.
    temporary = to_path.with_suffix(to_path.suffix + ".restore-tmp")
    if temporary.exists():
        temporary.unlink()
    destination = sqlite3.connect(temporary)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()

    restored = _connect(temporary)
    try:
        if _integrity(restored) != "ok":
            raise RuntimeError("restored database failed integrity check")
        if _counts(restored) != counts:
            raise RuntimeError("restored row counts differ from backup")
        if _revision(restored) != revision:
            raise RuntimeError("restored Alembic revision differs from backup")
    finally:
        restored.close()

    temporary.replace(to_path)
    print(f"restored_to: {to_path}")
    print(f"counts_verified: {counts}")
    print(f"revision_verified: {revision}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    backup_parser = sub.add_parser("backup", help="create a verified backup")
    backup_parser.add_argument("--db", required=True, type=Path)
    backup_parser.add_argument("--out", required=True, type=Path)

    verify_parser = sub.add_parser("verify", help="check integrity and counts")
    verify_parser.add_argument("--db", required=True, type=Path)

    restore_parser = sub.add_parser("restore", help="restore into a new database file")
    restore_parser.add_argument("--from", dest="source", required=True, type=Path)
    restore_parser.add_argument("--to", dest="target", required=True, type=Path)
    restore_parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "backup":
            backup(args.db, args.out)
        elif args.command == "verify":
            verify(args.db)
        elif args.command == "restore":
            restore(args.source, args.target, args.force)
    except (FileNotFoundError, FileExistsError, RuntimeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
