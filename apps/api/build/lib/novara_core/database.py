"""Database setup.

SQLite is the local-first default for development and isolated tests. Set
NOVARA_DATABASE_URL to a PostgreSQL DSN to run the same SQLAlchemy models against
PostgreSQL. No module code depends on the engine choice.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Resolve the default database relative to the project root, not the caller's
# working directory. Starting uvicorn from apps/ used to silently pick up an
# older, incompatible SQLite file with a different users schema.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = os.getenv(
    "NOVARA_DB_PATH", str(PROJECT_ROOT / "novara_dev.sqlite3")
)


def database_url() -> str:
    configured = os.getenv("NOVARA_DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{DEFAULT_DB_PATH}"


def make_engine(url: str | None = None):
    url = url or database_url()
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db(target=None) -> None:
    """Create tables. For deployed installations use Alembic migrations instead."""
    Base.metadata.create_all(target or engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
