import sqlite3

c = sqlite3.connect("novara_dev.sqlite3")
print("version:", c.execute("select version_num from alembic_version").fetchall())
print("tmp tables:", [r[0] for r in c.execute(
    "select name from sqlite_master where name like '_alembic_tmp%'").fetchall()])
for table in ("users", "workspaces", "contacts", "support_tickets", "feature_flags", "projects"):
    try:
        print(table, c.execute(f"select count(1) from {table}").fetchone()[0])
    except Exception as exc:
        print(table, "ERROR", exc)
