"""Phase 2 P2-1: database portability preparation.

These tests verify that the shared models and queries compile against the
PostgreSQL dialect and that DSN selection works. They do NOT claim a live
PostgreSQL connection: no driver or server is available in this workspace.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from novara_core import main  # noqa: F401 - imports every module and table
from novara_core.database import Base, database_url, make_engine
from novara_core.modules.jobs import Job

PG = postgresql.dialect()


def test_all_tables_compile_to_postgresql_ddl():
    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=PG))
        for table in Base.metadata.sorted_tables
    )
    assert len(Base.metadata.sorted_tables) >= 35
    assert "AUTOINCREMENT" not in ddl  # SQLite-only syntax
    assert "PRAGMA" not in ddl
    assert "SERIAL" in ddl  # the append-only event sequence
    assert "JSON" in ddl
    assert "TIMESTAMP" in ddl


def test_tenant_tables_carry_workspace_id():
    tenant_tables = {
        "contacts",
        "companies",
        "leads",
        "tasks",
        "notes",
        "events",
        "notifications",
        "outreach_drafts",
        "integrations",
        "agent_configs",
        "agent_runs",
        "experiments",
        "jobs",
        "adapter_calls",
    }
    missing = {
        name
        for name in tenant_tables
        if "workspace_id" not in Base.metadata.tables[name].columns
    }
    assert missing == set(), f"tenant tables without workspace_id: {sorted(missing)}"


def test_skip_locked_claim_compiles_on_postgres_and_sqlite():
    statement = (
        select(Job)
        .where(Job.status == "queued")
        .with_for_update(skip_locked=True)
    )
    postgres_sql = str(statement.compile(dialect=PG))
    assert "FOR UPDATE SKIP LOCKED" in postgres_sql
    sqlite_sql = str(statement.compile(dialect=sqlite.dialect()))
    assert "FOR UPDATE" not in sqlite_sql  # ignored, not an error


def test_postgres_dsn_is_selected_without_connecting(monkeypatch):
    dsn = "postgresql+psycopg2://novara@localhost/novara_test"
    monkeypatch.setenv("NOVARA_DATABASE_URL", dsn)
    assert database_url() == dsn
    monkeypatch.delenv("NOVARA_DATABASE_URL")
    assert database_url().startswith("sqlite:///")
    # The local engine still constructs cleanly; no external connection is made.
    engine = make_engine("sqlite://")
    assert engine.dialect.name == "sqlite"
    engine.dispose()
