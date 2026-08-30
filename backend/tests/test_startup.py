import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from backend import main as backend_main
from backend.database import SQLALCHEMY_DATABASE_URL, SessionLocal
from backend.core.security import get_password_hash
from backend.scripts.seed import run_seeder
import models


# this file contains the small number of slow "integration" tests that
# exercise the application's lifespan and seeder logic.  most other tests
# should continue to use the lightweight ``client`` fixture.


@pytest.fixture(autouse=True)
def schema_ready_by_default(monkeypatch):
    """Keep lifespan tests focused unless a test explicitly simulates schema drift."""
    monkeypatch.setattr(
        backend_main.schema_readiness_service,
        "assert_schema_ready",
        lambda *_args, **_kwargs: None,
    )


def test_lifespan_requires_migrated_tables(integration_client):
    """The FastAPI lifespan manager should accept a migrated schema."""
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        assert "users" in inspector.get_table_names()
        assert "leagues" in inspector.get_table_names()
    finally:
        db.close()


def test_pytest_database_selection_is_deterministic():
    configured_url = make_url(SQLALCHEMY_DATABASE_URL)

    if os.getenv("FFPI_PYTEST_OWNS_DATABASE") == "1":
        assert configured_url.get_backend_name() == "sqlite"
        database_path = Path(configured_url.database)
        assert database_path.name == "backend.db"
        assert database_path.parent.name.startswith("ffpi-pytest-")
        assert database_path.is_file()


def test_seeder_populates_admin(integration_client):
    """Manually invoke the seeder and verify default admin is inserted."""
    db = SessionLocal()
    try:
        # Reset seed-sensitive tables across supported test dialects.
        if db.bind.dialect.name == "postgresql":
            db.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
            db.commit()
        else:
            db.query(models.User).delete()
            db.commit()

        run_seeder(db, get_password_hash)
        admin = db.query(models.User).filter(models.User.username == "Admin").first()
        assert admin is not None
        assert admin.is_commissioner
    finally:
        db.close()


def test_lifespan_teardown_and_restart():
    """Client teardown should release DB resources and allow a clean reboot."""
    # create then close a client to trigger shutdown
    from fastapi.testclient import TestClient
    from backend.main import app

    for i in range(2):
        with TestClient(app) as c:
            # performing a trivial call to ensure the app is running
            resp = c.get("/")
            assert resp.status_code == 200
        # after context exit, SQLAlchemy pool should have no active connections
        db = SessionLocal()
        try:
            # depending on dialect, pool status can be inspected
            pool = db.bind.pool
            assert pool.checkedout() == 0
        finally:
            db.close()


def test_lifespan_fails_when_database_probe_fails(monkeypatch):
    """The service must not start when its database is unreachable."""
    from fastapi.testclient import TestClient

    def fail_probe(_engine):
        raise ConnectionError("simulated unavailable database")

    monkeypatch.setattr(backend_main, "probe_database", fail_probe)

    with pytest.raises(RuntimeError, match="Database connectivity check failed during startup"):
        with TestClient(backend_main.app):
            pass


def test_lifespan_fails_when_schema_is_not_ready(monkeypatch):
    """The service must not start when required migrations are absent."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(backend_main, "probe_database", lambda _engine: None)

    def fail_readiness(*_args, **_kwargs):
        raise RuntimeError("simulated missing column")

    monkeypatch.setattr(
        backend_main.schema_readiness_service,
        "assert_schema_ready",
        fail_readiness,
    )

    with pytest.raises(RuntimeError, match="Database schema readiness check failed during startup"):
        with TestClient(backend_main.app):
            pass


def test_lifespan_stops_runtime_schedulers_when_context_raises(monkeypatch):
    events: list[str] = []

    class FakeSchedulerManager:
        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(backend_main, "_initialize_database", lambda: None)
    monkeypatch.setattr(
        backend_main,
        "_create_runtime_scheduler_manager",
        lambda: FakeSchedulerManager(),
    )
    monkeypatch.setattr(backend_main.live_scoring_event_bus, "set_event_loop", lambda _loop: None)

    async def fail_inside_lifespan():
        async with backend_main.lifespan(backend_main.app):
            raise RuntimeError("simulated application failure")

    with pytest.raises(RuntimeError, match="simulated application failure"):
        asyncio.run(fail_inside_lifespan())

    assert events == ["start", "stop"]
