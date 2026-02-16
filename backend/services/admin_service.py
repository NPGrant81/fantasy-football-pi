# backend/services/admin_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
from core import security

# --- 1.1 LEAGUE MANAGEMENT (COMMISSIONER) ---

def finalize_league_draft(db: Session, league_id: int):
    # 1.1.1 Logic to lock the draft
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league: raise HTTPException(status_code=404, detail="League not found")
    league.draft_status = "COMPLETED"
    db.commit()
    return league

def reset_league_rosters(db: Session, league_id: int):
    # 1.1.2 Nuclear reset for a specific league
    db.query(models.DraftPick).filter(models.DraftPick.league_id == league_id).delete()
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if league: league.draft_status = "PRE_DRAFT"
    db.commit()
    return {"status": "success"}

# --- 1.2 PLATFORM TOOLS (SUPERUSER) ---

def create_full_test_league(db: Session):
    # 1.2.1 Logic moved from your router's "create-test-league"
    league_name = "Test League 2026"
    league = models.League(name=league_name)
    db.add(league)
    db.commit()
    db.refresh(league)
    
    # 1.2.2 Add dummy owners logic... (omitted for brevity but keep your code here!)
    return league

def sync_initial_nfl_data(db: Session):
    # 1.2.3 Your NFL sync logic moved here
    if db.query(models.Player).count() > 0:
        return False
    # ... add players logic ...
    db.commit()
    return True