"""Throwaway-DB migration round-trip check with existing-data preservation.

Usage (from D:\\NOVARA):
  .venv\\Scripts\\python.exe scripts\\migration_roundtrip_check.py <previous_revision>

Creates a fresh SQLite DB, stamps/upgrades to head, inserts a workspace row,
downgrades to <previous_revision>, upgrades back to head, and asserts the row
survived. No token, secret or production data is touched.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "apps" / "api"
PY = ROOT / ".venv" / "Scripts" / "python.exe"


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    previous = sys.argv[1]
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "roundtrip.sqlite3"
        # The app resolves its DSN from NOVARA_DATABASE_URL (see
        # novara_core.database.database_url). Set both so Alembic and the
        # runtime model sessions use the same throwaway database.
        url = f"sqlite:///{db.as_posix()}"
        env = dict(os.environ, NOVARA_DATABASE_URL=url, DATABASE_URL=url, PYTHONPATH=str(API))
        alembic = [str(PY), "-m", "alembic", "-c", str(API / "alembic.ini")]

        def run(*args: str) -> None:
            result = subprocess.run(alembic + list(args), cwd=API, env=env,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                print(result.stdout[-2000:])
                print(result.stderr[-2000:])
                raise SystemExit(f"alembic {' '.join(args)} failed")

        run("upgrade", "head")
        # Insert a pre-existing row using the real model, then verify it survives.
        sys.path.insert(0, str(API))
        from novara_core.database import SessionLocal
        from novara_core.models import Workspace, new_id
        session = SessionLocal()
        wid = new_id()
        session.add(Workspace(id=wid, name="Roundtrip"))
        session.commit()
        session.close()

        run("downgrade", previous)
        run("upgrade", "head")
        # Strict check: migrations alone must reproduce the full model schema.
        # Do not call init_db()/create_all() here, or a missing table could hide
        # behind the runtime startup path and this check would pass falsely.
        run("check")

        session = SessionLocal()
        row = session.query(Workspace).filter(Workspace.id == wid).first()
        session.close()
        if row is None:
            raise SystemExit("ROUND TRIP FAIL: pre-existing workspace was lost")
        print("ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
