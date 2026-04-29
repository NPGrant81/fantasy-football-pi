"""
Tests for the ETL router (backend/routers/etl.py).

Asserts:
- POST /api/etl/run returns 202 Accepted immediately without blocking.
- Response contains a run_id.
- GET /api/etl/status/{run_id} returns the queued/running state.
- GET /api/etl/status/<unknown> returns 404.
- Invalid token returns 401.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ETL_API_TOKEN", "test-token")

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.routers import etl as etl_module

AUTH = {"Authorization": "Bearer test-token"}
BAD_AUTH = {"Authorization": "Bearer wrong-token"}


@pytest.fixture(autouse=True)
def clear_run_registry():
    """Wipe the in-process run registry and patch the token between tests."""
    # API_TOKEN is captured at import time; patch the module-level variable
    # so tests do not depend on the process environment at startup.
    original_token = etl_module.API_TOKEN
    etl_module.API_TOKEN = "test-token"
    etl_module._etl_runs.clear()
    yield
    etl_module._etl_runs.clear()
    etl_module.API_TOKEN = original_token


@pytest.fixture
def client():
    from contextlib import asynccontextmanager

    original = app.router.lifespan_context

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.lifespan_context = original


# ---------------------------------------------------------------------------
# POST /api/etl/run
# ---------------------------------------------------------------------------

def test_run_etl_returns_202_immediately(client):
    """Endpoint must return 202 without executing the subprocess."""
    with patch.object(etl_module, "_run_etl_pipeline") as mock_task:
        response = client.post("/api/etl/run", headers=AUTH)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert "run_id" in body
    assert len(body["run_id"]) == 36  # UUID4 string


def test_run_etl_does_not_call_subprocess_synchronously(client):
    """The endpoint must delegate work to _run_etl_pipeline, not call
    subprocess.run directly inside the request handler."""
    with patch.object(etl_module, "_run_etl_pipeline") as mock_pipeline:
        response = client.post("/api/etl/run", headers=AUTH)

    assert response.status_code == 202
    # The pipeline function (not subprocess.run) is what the handler invokes
    mock_pipeline.assert_called_once()


def test_run_etl_stores_queued_state(client):
    """After a POST the run registry must contain the new run in queued state."""
    with patch.object(etl_module, "_run_etl_pipeline"):
        response = client.post("/api/etl/run", headers=AUTH)

    run_id = response.json()["run_id"]
    assert run_id in etl_module._etl_runs
    assert etl_module._etl_runs[run_id]["status"] == "queued"


def test_run_etl_rejects_invalid_token(client):
    response = client.post("/api/etl/run", headers=BAD_AUTH)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/etl/status/{run_id}
# ---------------------------------------------------------------------------

def test_status_returns_run_info(client):
    """GET /api/etl/status/{run_id} returns the stored run state."""
    with patch.object(etl_module, "_run_etl_pipeline"):
        post_resp = client.post("/api/etl/run", headers=AUTH)

    run_id = post_resp.json()["run_id"]
    status_resp = client.get(f"/api/etl/status/{run_id}", headers=AUTH)

    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["run_id"] == run_id
    assert "status" in body
    assert "started_at" in body


def test_status_returns_404_for_unknown_run(client):
    response = client.get("/api/etl/status/nonexistent-run-id", headers=AUTH)
    assert response.status_code == 404


def test_status_rejects_invalid_token(client):
    etl_module._etl_runs["some-id"] = {"run_id": "some-id", "status": "queued"}
    response = client.get("/api/etl/status/some-id", headers=BAD_AUTH)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Background task execution (unit-level)
# ---------------------------------------------------------------------------

def test_background_task_records_success():
    """_run_etl_pipeline updates status to 'success' on returncode 0."""
    import subprocess

    etl_module._etl_runs["test-run"] = {
        "run_id": "test-run",
        "status": "queued",
        "output": None,
        "started_at": "",
        "completed_at": None,
    }

    fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="done", stderr="")
    with patch("subprocess.run", return_value=fake_result):
        etl_module._run_etl_pipeline("test-run")

    assert etl_module._etl_runs["test-run"]["status"] == "success"
    assert etl_module._etl_runs["test-run"]["output"] == "done"
    assert etl_module._etl_runs["test-run"]["completed_at"] is not None


def test_background_task_records_error_on_nonzero_returncode():
    """_run_etl_pipeline updates status to 'error' on non-zero returncode."""
    import subprocess

    etl_module._etl_runs["test-run"] = {
        "run_id": "test-run",
        "status": "queued",
        "output": None,
        "started_at": "",
        "completed_at": None,
    }

    fake_result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="pipeline failed")
    with patch("subprocess.run", return_value=fake_result):
        etl_module._run_etl_pipeline("test-run")

    assert etl_module._etl_runs["test-run"]["status"] == "error"
    assert etl_module._etl_runs["test-run"]["output"] == "pipeline failed"


def test_background_task_records_error_on_exception():
    """_run_etl_pipeline captures unexpected exceptions as error status."""
    etl_module._etl_runs["test-run"] = {
        "run_id": "test-run",
        "status": "queued",
        "output": None,
        "started_at": "",
        "completed_at": None,
    }

    with patch("subprocess.run", side_effect=RuntimeError("disk full")):
        etl_module._run_etl_pipeline("test-run")

    assert etl_module._etl_runs["test-run"]["status"] == "error"
    assert "disk full" in etl_module._etl_runs["test-run"]["output"]
