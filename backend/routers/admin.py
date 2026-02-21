# backend/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from core import security 
from services import admin_service

router = APIRouter(prefix="/admin", tags=["League Admin"])

# --- 2.1 COMMISSIONER ENDPOINTS ---

@router.post("/finalize-draft")
def finalize_draft(
    db: Session = Depends(get_db),
    # 2.1.1 Only the Commissioner of THIS league can do this
    admin: models.User = Depends(security.get_current_active_admin)
):
    return admin_service.finalize_league_draft(db, admin.league_id)

@router.post("/reset-league")
def reset_league(
    db: Session = Depends(get_db),
    admin: models.User = Depends(security.get_current_active_admin)
):
    return admin_service.reset_league_rosters(db, admin.league_id)

