from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novara_core.database import Base
from novara_core.main import app, get_db


@pytest.fixture(autouse=True)
def restore_global_app_state():
    """Snapshot and restore the shared FastAPI app around every test.

    Module tests attach routers or rewrite paths on the global app; without
    this guard those changes leak into unrelated tests and the production app
    object used later in the same process.
    """
    original_routes = list(app.routes)
    original_overrides = dict(app.dependency_overrides)
    original_openapi = getattr(app, "openapi_schema", None)
    yield
    app.routes[:] = original_routes
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)
    app.openapi_schema = original_openapi


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def bootstrap(client, workspace_name="Acme", email="owner@example.com", password="Password123!"):
    response = client.post(
        "/api/v1/setup/bootstrap",
        json={
            "workspace_name": workspace_name,
            "email": email,
            "password": password,
            "display_name": "Owner",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}
