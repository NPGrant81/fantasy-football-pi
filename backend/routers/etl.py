import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()

API_TOKEN = os.environ.get("ETL_API_TOKEN", "supersecret")
security = HTTPBearer()

# In-process run-status registry. Survives the request lifetime; reset on
# server restart (acceptable for an infrequent admin-only operation).
_etl_runs: dict[str, dict] = {}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token.",
        )


def _run_etl_pipeline(run_id: str) -> None:
    """Background task: execute the ETL pipeline script and record the result."""
    _etl_runs[run_id]["status"] = "running"
    try:
        result = subprocess.run(
            [sys.executable, "etl/test_etl_pipeline.py"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            _etl_runs[run_id].update({"status": "success", "output": result.stdout})
        else:
            _etl_runs[run_id].update({"status": "error", "output": result.stderr})
    except Exception as exc:
        _etl_runs[run_id].update({"status": "error", "output": str(exc)})
    finally:
        _etl_runs[run_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/api/etl/run", status_code=202, dependencies=[Depends(verify_token)])
def run_etl(background_tasks: BackgroundTasks):
    """
    Trigger the ETL pipeline as a background task.

    Returns 202 Accepted immediately with a run_id.
    Poll GET /api/etl/status/{run_id} for completion status.
    """
    run_id = str(uuid.uuid4())
    _etl_runs[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "output": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    background_tasks.add_task(_run_etl_pipeline, run_id)
    return {"status": "accepted", "run_id": run_id}


@router.get("/api/etl/status/{run_id}", dependencies=[Depends(verify_token)])
def etl_run_status(run_id: str):
    """Return the current status and output of an ETL run."""
    run = _etl_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ETL run not found.")
    return run
