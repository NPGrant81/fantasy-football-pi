from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import subprocess
import os

router = APIRouter()

# Simple token-based security (replace with your real auth logic)
API_TOKEN = os.environ.get("ETL_API_TOKEN", "supersecret")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token.")

@router.post("/api/etl/run", dependencies=[Depends(verify_token)])
def run_etl():
    """
    Trigger the ETL pipeline (runs etl/test_etl_pipeline.py).
    Returns output or error message.
    """
    try:
        result = subprocess.run([
            "python", "etl/test_etl_pipeline.py"
        ], capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout}
        else:
            return {"status": "error", "output": result.stderr}
    except Exception as e:
        return {"status": "error", "output": str(e)}
