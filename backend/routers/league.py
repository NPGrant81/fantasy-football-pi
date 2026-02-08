from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any 
from database import get_db
import models

router = APIRouter(
    prefix="/league",
    tags=["League Settings"]
)

# --- Schemas ---
class LeagueSettingsSchema(BaseModel):
    league_name: str
    roster_size: int
    salary_cap: int
    starting_slots: Dict[str, int]
    scoring_rules: List[Dict[str, Any]] 

class UpdateSettingsSchema(BaseModel):
    league_name: str | None = None
    roster_size: int | None = None
    salary_cap: int | None = None
    starting_slots: Dict[str, int] | None = None
    scoring_rules: List[Dict[str, Any]] | None = None 

class LeagueSummary(BaseModel):
    id: int
    name: str

class LeagueCreate(BaseModel):
    name: str    

class UserSummary(BaseModel):
    id: int
    username: str
    league_id: int | None

class AddMemberRequest(BaseModel):
    user_id: int

# --- Endpoints ---

@router.get("/", response_model=List[LeagueSummary])
def get_leagues(db: Session = Depends(get_db)):
    """List all available leagues."""
    leagues = db.query(models.League).all()
    return [LeagueSummary(id=l.id, name=l.name) for l in leagues]

@router.post("/", response_model=LeagueSummary)
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db)):
    """Create a new league."""
    # Check if exists
    existing = db.query(models.League).filter(models.League.name == league_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already taken")
    
    # Create League
    new_league = models.League(name=league_data.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    # Create Default Settings
    default_settings = models.LeagueSettings(
        league_name=new_league.name,
        roster_size=14,
        salary_cap=200,
        starting_slots={"QB":1, "RB":2, "WR":2, "TE":1, "K":1, "DEF":1, "FLEX":1},
        scoring_rules=[{"cat": "Passing", "event": "Passing TD", "min": 0, "max": 99, "pts": 4, "type": "per_unit", "desc": "Default"}]
    )
    db.add(default_settings)
    db.commit()

    return LeagueSummary(id=new_league.id, name=new_league.name)

@router.get("/settings", response_model=LeagueSettingsSchema)
def get_league_settings(db: Session = Depends(get_db)):
    """Fetch the current league rules."""
    settings = db.query(models.LeagueSettings).first()
    
    if not settings:
        return LeagueSettingsSchema(
            league_name="Default League",
            roster_size=14,
            salary_cap=200,
            starting_slots={"QB":1, "RB":2, "WR":2, "TE":1, "K":1, "DEF":1, "FLEX":1},
            scoring_rules=[
                {"cat": "Passing", "event": "Passing TD", "min": 0, "max": 99, "pts": 4, "type": "per_unit", "desc": "Default Rule"}
            ]
        )
    return settings

@router.put("/settings")
def update_league_settings(
    updates: UpdateSettingsSchema, 
    user_id: int, 
    db: Session = Depends(get_db)
):
    """Update league rules. RESTRICTED TO COMMISSIONER."""
    # 1. Check Authority
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_commissioner:
        raise HTTPException(status_code=403, detail="Only the Commissioner can update league rules.")

    # 2. Get Settings (or create if missing)
    settings = db.query(models.LeagueSettings).first()
    if not settings:
        settings = models.LeagueSettings()
        db.add(settings)

    # 3. Apply Updates
    if updates.league_name: settings.league_name = updates.league_name
    if updates.roster_size: settings.roster_size = updates.roster_size
    if updates.salary_cap: settings.salary_cap = updates.salary_cap
    if updates.starting_slots: settings.starting_slots = updates.starting_slots
    if updates.scoring_rules: settings.scoring_rules = updates.scoring_rules

    db.commit()
    return {"status": "success", "message": "League settings updated.", "settings": settings.league_name}

@router.get("/users", response_model=List[UserSummary])
def get_all_users(db: Session = Depends(get_db)):
    """List all users so the Commissioner can see who to recruit."""
    users = db.query(models.User).all()
    return [UserSummary(id=u.id, username=u.username, league_id=u.league_id) for u in users]

@router.post("/add-member")
def add_member_to_league(
    request: AddMemberRequest, 
    current_user_id: int, 
    db: Session = Depends(get_db)
):
    """Move a specific user into the Commissioner's current league."""
    # 1. Get the Commissioner
    admin = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not admin or not admin.is_commissioner:
        raise HTTPException(status_code=403, detail="Only Commissioners can recruit users.")
    
    if not admin.league_id:
        raise HTTPException(status_code=400, detail="You are not in a league yourself!")

    # 2. Get the Target User
    target_user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 3. The Switch
    previous_league = target_user.league_id
    target_user.league_id = admin.league_id
    db.commit()

    return {
        "status": "success", 
        "message": f"Moved {target_user.username} from League {previous_league} to League {admin.league_id}"
    }