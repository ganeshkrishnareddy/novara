"""Phase 2 P2-7: verified SQLite backup and restore."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backup_restore.py"


def _create_source(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT);
        CREATE TABLE events (seq INTEGER PRIMARY KEY, event_type TEXT);
        CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);
        INSERT INTO users VALUES ('u1', 'backup@example.test');
        INSERT INTO events VALUES (1, 'contact.identified');
        INSERT INTO events VALUES (2, 'lead.created');
        INSERT INTO alembic_version VALUES ('9951aadc14c8');
        """
    )
    connection.commit()
    connection.close()


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_backup_verify_and_restore(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    _create_source(source)
    out_dir = tmp_path / "backups"

    created = _run("backup", "--db", str(source), "--out", str(out_dir))
    assert created.returncode == 0, created.stderr
    assert "integrity: ok" in created.stdout
    backups = list(out_dir.glob("novara-*.sqlite3"))
    assert len(backups) == 1
    backup = backups[0]

    checked = _run("verify", "--db", str(backup))
    assert checked.returncode == 0, checked.stderr
    assert "'users': 1" in checked.stdout
    assert "'events': 2" in checked.stdout
    assert "9951aadc14c8" in checked.stdout

    # Simulate data loss in the live database, then restore from the backup.
    connection = sqlite3.connect(source)
    connection.execute("DELETE FROM events")
    connection.commit()
    connection.close()

    restored_path = tmp_path / "restored.sqlite3"
    restored = _run(
        "restore", "--from", str(backup), "--to", str(restored_path)
    )
    assert restored.returncode == 0, restored.stderr
    assert "counts_verified" in restored.stdout

    connection = sqlite3.connect(restored_path)
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
    assert connection.execute(
        "SELECT version_num FROM alembic_version"
    ).fetchone()[0] == "9951aadc14c8"
    connection.close()


def test_restore_refuses_to_overwrite_without_force(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    _create_source(source)
    created = _run("backup", "--db", str(source), "--out", str(tmp_path / "backups"))
    backup = next((tmp_path / "backups").glob("novara-*.sqlite3"))

    target = tmp_path / "existing.sqlite3"
    target.write_text("do not overwrite")
    refused = _run("restore", "--from", str(backup), "--to", str(target))
    assert refused.returncode == 1
    assert "use --force" in refused.stderr
    assert target.read_text() == "do not overwrite"

    overwritten = _run(
        "restore", "--from", str(backup), "--to", str(target), "--force"
    )
    assert overwritten.returncode == 0, overwritten.stderr
    assert target.read_bytes()[:15] == b"SQLite format 3"
