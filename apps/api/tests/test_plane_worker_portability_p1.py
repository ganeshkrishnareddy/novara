"""Named acceptance tests for the remaining Plane platform P1 rows.

PL-071: a real polling worker processes a durable job asynchronously.
PL-147: the Alembic chain has one head and every table compiles to PostgreSQL.
PL-148: every workspace-scoped table compiles to PostgreSQL and persists locally.

No live PostgreSQL server, broker, container or external service is claimed.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from novara_core import main  # noqa: F401 - imports every module and table
from novara_core.database import Base
from novara_core.models import Event, User, WorkspaceMember
from novara_core.modules.jobs import JOB_COMPLETED, JOB_STARTED, Job, JobWorker, enqueue_job

from .conftest import bootstrap

ROOT = Path(__file__).resolve().parents[3]
PG = postgresql.dialect()


def test_pl071_worker_processes_job_asynchronously_with_durable_state(client, db_session):
    """The real JobWorker claims and completes a job on its own thread."""
    wid = bootstrap(client, "AsyncWorker", "async-worker@example.com")["workspace_id"]
    owner_id = db_session.execute(
        select(User.id).where(User.email == "async-worker@example.com")
    ).scalar_one()

    job = enqueue_job(
        db_session,
        workspace_id=wid,
        job_type="noop",
        payload={"async": True},
        created_by=owner_id,
        idempotency_key="async-worker-1",
    )
    db_session.commit()
    assert job.status == "queued"

    # The worker owns its sessions but shares the test's in-memory engine.
    factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False
    )
    worker = JobWorker(
        session_factory=factory,
        worker_id="test-async-worker",
        job_types=["noop"],
        poll_seconds=0.02,
        batch_limit=5,
    )
    thread = worker.start()
    try:
        deadline = time.monotonic() + 5.0
        status = "queued"
        while time.monotonic() < deadline:
            check = factory()
            try:
                status = check.execute(
                    select(Job.status).where(Job.id == job.id)
                ).scalar_one()
            finally:
                check.close()
            if status == "succeeded":
                break
            time.sleep(0.02)
    finally:
        worker.stop(timeout=5.0)

    assert thread.is_alive() is False
    assert status == "succeeded", f"job never completed on the worker thread: {status}"

    # State is durable: a brand-new session sees the completed row and audit log.
    verify = factory()
    try:
        done = verify.execute(select(Job).where(Job.id == job.id)).scalar_one()
        assert done.finished_at is not None
        assert done.locked_at is None and done.locked_by is None
        types = set(
            verify.execute(
                select(Event.event_type).where(
                    Event.workspace_id == wid, Event.entity_id == job.id
                )
            ).scalars().all()
        )
        assert {JOB_STARTED, JOB_COMPLETED} <= types
        completed = verify.execute(
            select(Event.payload).where(
                Event.workspace_id == wid,
                Event.entity_id == job.id,
                Event.event_type == JOB_COMPLETED,
            )
        ).scalar_one()
        assert completed["attempts"] == 1
        claim = verify.execute(
            select(Event.payload).where(
                Event.workspace_id == wid,
                Event.entity_id == job.id,
                Event.event_type == JOB_STARTED,
            )
        ).scalar_one()
        assert claim["worker_id"] == "test-async-worker"
    finally:
        verify.close()


def test_pl147_migration_chain_and_postgres_ddl():
    """One migration head and every model table emits clean PostgreSQL DDL."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "apps" / "api" / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"branching migration heads: {heads}"
    assert all(rev is not None for rev in script.walk_revisions())

    ddl_by_table = {
        table.name: str(CreateTable(table).compile(dialect=PG))
        for table in Base.metadata.sorted_tables
    }
    assert len(ddl_by_table) >= 35
    for name, ddl in ddl_by_table.items():
        assert ddl.strip().startswith("CREATE TABLE"), name
        assert "AUTOINCREMENT" not in ddl, name
        assert "PRAGMA" not in ddl, name
    assert "SERIAL" in ddl_by_table["events"]
    assert "JSON" in "".join(ddl_by_table.values())


def test_pl148_workspace_tables_compile_and_persist(client, db_session):
    """All discovered workspace-scoped tables compile to PG and persist locally."""
    workspace_tables = sorted(
        name
        for name, table in Base.metadata.tables.items()
        if "workspace_id" in table.columns
    )
    assert len(workspace_tables) >= 30
    for name in workspace_tables:
        ddl = str(CreateTable(Base.metadata.tables[name]).compile(dialect=PG))
        assert ddl.strip().startswith("CREATE TABLE"), name
        assert "AUTOINCREMENT" not in ddl, name
        assert "workspace_id" in ddl, name

    # A workspace-scoped row written through the API is readable from a fresh
    # session, proving local persistence of the same compiled table.
    wid = bootstrap(client, "Portability", "portability@example.com")["workspace_id"]
    check = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)()
    try:
        members = check.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid)
        ).scalars().all()
        assert members, "bootstrap membership did not persist in a fresh session"
        assert "workspace_id" in str(
            CreateTable(Base.metadata.tables["workspace_members"]).compile(dialect=PG)
        )
    finally:
        check.close()
