"""Remove artifacts left by the earlier buggy round-trip script run."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "novara_dev.sqlite3"

c = sqlite3.connect(DB)
tmp = [r[0] for r in c.execute(
    "select name from sqlite_master where name like '_alembic_tmp%'").fetchall()]
for name in tmp:
    c.execute(f"drop table {name}")
    print("dropped", name)
cur = c.execute("delete from workspaces where name = 'Roundtrip'")
print("removed synthetic workspaces:", cur.rowcount)
c.commit()
c.close()

env = dict(os.environ,
           NOVARA_DATABASE_URL=f"sqlite:///{DB.as_posix()}",
           PYTHONPATH=str(ROOT / "apps" / "api"))
subprocess.run([sys.executable, "-m", "alembic", "stamp", "head"],
               cwd=ROOT / "apps" / "api", env=env, check=True)
print("stamped head")
