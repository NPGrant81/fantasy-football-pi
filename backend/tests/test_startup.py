import pytest

from backend.database import SessionLocal
from backend.core.security import get_password_hash
from backend.scripts.seed import run_seeder
from sqlalchemy import inspect
import models


# this file contains the small number of slow "integration" tests that
# exercise the application's lifespan and seeder logic.  most other tests
# should continue to use the lightweight ``client`` fixture.


def test_lifespan_creates_tables(integration_client):
    """The FastAPI lifespan manager should have created the tables."""
    db = SessionLocal()
    try:
        # metadata.create_all is run in the lifespan; tables should exist
        inspector = inspect(db.bind)
        assert "users" in inspector.get_table_names()
        assert "leagues" in inspector.get_table_names()
    finally:
        db.close()


def test_seeder_populates_admin(integration_client):
    """Manually invoke the seeder and verify default admin is inserted."""
    db = SessionLocal()
    try:
        # ensure seeder will be run against a fresh DB
        db.execute(models.User.__table__.delete())
        db.commit()

        run_seeder(db, get_password_hash)
        admin = db.query(models.User).filter(models.User.username == "Nick Grant").first()
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
