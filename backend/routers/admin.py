# backend/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..core import security
from ..services import admin_service
from ..services import admin_audit_service

router = APIRouter(prefix="/admin", tags=["League Admin"])

# --- 2.1 COMMISSIONER ENDPOINTS ---

@router.post("/finalize-draft")
def finalize_draft(
    db: Session = Depends(get_db),
    # 2.1.1 Only the Commissioner of THIS league can do this
    admin: models.User = Depends(security.get_current_active_admin)
):
    result = admin_service.finalize_league_draft(db, admin.league_id)
    admin_audit_service.record_privileged_action(
        db,
        admin,
        "finalize_draft",
        "commissioner",
        league_id=admin.league_id,
    )
    return result

@router.post("/reset-league")
def reset_league(
    db: Session = Depends(get_db),
    admin: models.User = Depends(security.get_current_active_admin)
):
    result = admin_service.reset_league_rosters(db, admin.league_id)
    admin_audit_service.record_privileged_action(
        db,
        admin,
        "reset_league",
        "commissioner",
        league_id=admin.league_id,
    )
    return result


@router.post("/reset-draft")
def reset_draft(
    db: Session = Depends(get_db),
    admin: models.User = Depends(security.get_current_active_admin)
):
    result = admin_service.reset_league_rosters(db, admin.league_id)
    admin_audit_service.record_privileged_action(
        db,
        admin,
        "reset_draft",
        "commissioner",
        league_id=admin.league_id,
    )
    return result


@router.post("/create-test-league")
def create_test_league(
    db: Session = Depends(get_db),
    _superuser: models.User = Depends(security.get_current_active_superuser)
):
    league = admin_service.create_full_test_league(db)
    admin_audit_service.record_privileged_action(
        db,
        _superuser,
        "create_test_league",
        "superuser",
        target_type="league",
        target_id=str(league.id),
        league_id=league.id,
    )
    return {
        "message": "Test league created.",
        "league": {
            "id": league.id,
            "name": league.name,
        },
    }

