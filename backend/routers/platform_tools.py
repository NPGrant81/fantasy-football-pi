# backend/routers/platform_tools.py
"""
Platform-level tools that don't require commissioner status.
These are system-wide operations available to admins/superusers.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import secrets
import string
from database import get_db
from core.security import get_current_active_superuser, get_password_hash
import models
from services import admin_service
from utils.email_sender import send_invite_email

router = APIRouter(prefix="/admin/tools", tags=["Platform Tools"])


class CommissionerRequest(BaseModel):
    username: str
    email: Optional[str] = None
    league_id: Optional[int] = None


@router.get("/commissioners")
def list_commissioners(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser),
):
    commissioners = (
        db.query(models.User)
        .filter(models.User.is_commissioner == True)
        .order_by(models.User.id.asc())
        .all()
    )
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "league_id": user.league_id,
            "is_superuser": user.is_superuser,
        }
        for user in commissioners
    ]


@router.post("/commissioners")
def create_commissioner(
    request: CommissionerRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser),
):
    if db.query(models.User).filter(models.User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username taken.")

    if request.email and db.query(models.User).filter(models.User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    if request.league_id:
        league = db.query(models.League).filter(models.League.id == request.league_id).first()
        if not league:
            raise HTTPException(status_code=404, detail="League not found")

    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(8))

    new_commissioner = models.User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(temp_password),
        is_commissioner=True,
        league_id=request.league_id,
    )
    db.add(new_commissioner)
    db.commit()
    db.refresh(new_commissioner)

    if request.email:
        send_invite_email(
            request.email,
            request.username,
            temp_password,
            request.league_id,
        )

    return {
        "message": "Commissioner invited.",
        "league_id": request.league_id,
        "commissioner": {
            "id": new_commissioner.id,
            "username": new_commissioner.username,
            "email": new_commissioner.email,
            "league_id": new_commissioner.league_id,
            "is_superuser": new_commissioner.is_superuser,
        },
        "debug_password": temp_password,
    }


@router.put("/commissioners/{commissioner_id}")
def update_commissioner(
    commissioner_id: int,
    request: CommissionerRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser),
):
    commissioner = db.query(models.User).filter(models.User.id == commissioner_id).first()
    if not commissioner or not commissioner.is_commissioner:
        raise HTTPException(status_code=404, detail="Commissioner not found")

    if request.username != commissioner.username:
        existing_user = db.query(models.User).filter(models.User.username == request.username).first()
        if existing_user and existing_user.id != commissioner.id:
            raise HTTPException(status_code=400, detail="Username taken.")
        commissioner.username = request.username

    if request.email != commissioner.email:
        if request.email:
            existing_email = db.query(models.User).filter(models.User.email == request.email).first()
            if existing_email and existing_email.id != commissioner.id:
                raise HTTPException(status_code=400, detail="Email already in use.")
        commissioner.email = request.email

    if request.league_id != commissioner.league_id:
        if request.league_id:
            league = db.query(models.League).filter(models.League.id == request.league_id).first()
            if not league:
                raise HTTPException(status_code=404, detail="League not found")
        commissioner.league_id = request.league_id

    db.commit()
    db.refresh(commissioner)

    return {
        "message": "Commissioner updated.",
        "commissioner": {
            "id": commissioner.id,
            "username": commissioner.username,
            "email": commissioner.email,
            "league_id": commissioner.league_id,
            "is_superuser": commissioner.is_superuser,
        },
    }


@router.delete("/commissioners/{commissioner_id}")
def remove_commissioner(
    commissioner_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser),
):
    commissioner = db.query(models.User).filter(models.User.id == commissioner_id).first()
    if not commissioner or not commissioner.is_commissioner:
        raise HTTPException(status_code=404, detail="Commissioner not found")

    if commissioner.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot remove commissioner access from a superuser.")

    commissioner.is_commissioner = False
    db.commit()

    return {"message": "Commissioner access removed."}


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


@router.post("/uat-draft-reset")
def uat_draft_reset(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser)
):
    try:
        result = admin_service.uat_draft_reset(db)
        return {
            "message": "UAT Draft Reset complete",
            "detail": f"Draft cleared for {result['league']} ({result['draft_picks_deleted']} picks removed).",
            "stats": result,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/uat-team-reset")
def uat_team_reset(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_active_superuser)
):
    try:
        result = admin_service.uat_team_reset(db)
        return {
            "message": "UAT Team Reset complete",
            "detail": f"Teams reseeded for {result['league']} with {result['seed']['picks_created']} draft picks.",
            "stats": result,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
