import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.security import check_is_commissioner
from ..database import get_db
from ..services import admin_audit_service

router = APIRouter(prefix="/admin/config", tags=["Admin Config"])


@router.post("/reload")
def reload_config(
    db: Session = Depends(get_db),
    current_user=Depends(check_is_commissioner),
):
    """Reload environment variables from the .env file."""
    from dotenv import load_dotenv

    dotenv_path = os.path.join(os.getcwd(), ".env")
    success = load_dotenv(dotenv_path=dotenv_path, override=True)
    admin_audit_service.record_privileged_action(
        db,
        current_user,
        "reload_config",
        "commissioner",
        metadata_json={"route": "admin_config.reload", "reloaded": bool(success)},
    )
    return {"reloaded": bool(success)}