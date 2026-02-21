# backend/routers/platform_tools.py
"""
Platform-level tools that don't require commissioner status.
These are system-wide operations available to admins/superusers.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from core.security import get_current_active_superuser
from services import admin_service

router = APIRouter(prefix="/admin/tools", tags=["Platform Tools"])


@router.post("/sync-nfl")
def sync_nfl(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser)
):
    """
    Sync NFL player data from ESPN API.
    Imports active roster players with position filtering (QB, RB, WR, TE, K, DEF).
    Requires superuser/platform admin status.
    """
    try:
        admin_service.sync_initial_nfl_data(db)
        return {
            "message": "NFL player data synced successfully!",
            "detail": "Players, positions, and defenses updated from ESPN API."
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
