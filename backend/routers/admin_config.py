import os

from fastapi import APIRouter, Depends

from ..core.security import check_is_commissioner

router = APIRouter(prefix="/admin/config", tags=["Admin Config"])


@router.post("/reload")
def reload_config(current_user=Depends(check_is_commissioner)):
    """Reload environment variables from the .env file."""
    from dotenv import load_dotenv

    dotenv_path = os.path.join(os.getcwd(), ".env")
    success = load_dotenv(dotenv_path=dotenv_path, override=True)
    return {"reloaded": bool(success)}