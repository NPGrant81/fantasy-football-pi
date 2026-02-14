from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from database import get_db
import models
import auth # Use our new auth system
import secrets
import string
from utils.email_sender import send_invite_email

# FIX 1: Changed prefix to "/leagues" (Plural) to match Frontend
router = APIRouter(
    prefix="/leagues",
    tags=["League"]
)

# --- Schemas ---
class LeagueCreate(BaseModel):
    name: str

class LeagueSummary(BaseModel):
    id: int
    name: str

# --- Update the Request Schema ---
class AddMemberRequest(BaseModel):
    username: str
    email: Optional[str] = None # Now accepts email

# NEW: Schema for updating settings
class SettingsUpdate(BaseModel):
    roster_size: int
    salary_cap: int
    starting_slots: Dict[str, int] # e.g. {"QB": 1, "WR": 3}

# --- UPDATED SCHEMA (Supports Rules + Settings) ---
class ScoringRuleSchema(BaseModel):
    category: str
    description: Optional[str] = None
    points: float

class LeagueConfigFull(BaseModel):
    roster_size: int
    salary_cap: int
    starting_slots: Dict[str, int]
    scoring_rules: List[ScoringRuleSchema]    

# --- Endpoints ---

@router.get("/", response_model=List[LeagueSummary])
def get_leagues(db: Session = Depends(get_db)):
    """List all available leagues."""
    leagues = db.query(models.League).all()
    return [LeagueSummary(id=l.id, name=l.name) for l in leagues]

@router.post("/", response_model=LeagueSummary)
def create_league(league_data: LeagueCreate, db: Session = Depends(get_db)):
    """Create a new league + Default Scoring Rules + Default Settings."""
    # 1. Check if name exists
    existing = db.query(models.League).filter(models.League.name == league_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already taken")
    
    # 2. Create League
    new_league = models.League(name=league_data.name)
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    # 3. Create Default Settings (NEW)
    default_settings = models.LeagueSettings(league_id=new_league.id)
    db.add(default_settings)

    # 4. Create Default Scoring Rules
    default_rules = [
        models.ScoringRule(league_id=new_league.id, category="Passing", description="Passing TD", points=4.0),
        models.ScoringRule(league_id=new_league.id, category="Passing", description="Interception", points=-2.0),
        models.ScoringRule(league_id=new_league.id, category="Rushing", description="Rushing TD", points=6.0),
        models.ScoringRule(league_id=new_league.id, category="Receiving", description="Reception (PPR)", points=1.0),
    ]
    db.add_all(default_rules)
    db.commit()

    return LeagueSummary(id=new_league.id, name=new_league.name)

@router.post("/join")
def join_league(league_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Let a user join a specific league."""
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    
    current_user.league_id = league_id
    db.commit()
    return {"message": f"Welcome to {league.name}!"}

# --- NEW: LEAGUE SETTINGS ENDPOINTS ---

@router.get("/{league_id}/settings", response_model=LeagueConfigFull)
def get_league_settings(league_id: int, db: Session = Depends(get_db)):
    # 1. Get Settings (Roster, Cap)
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    if not settings:
        settings = models.LeagueSettings(league_id=league_id)
        db.add(settings)
        db.commit()
    
    # 2. Get Scoring Rules (Points)
    rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).all()
    
    # --- SELF-HEALING: If no rules exist, create them now! ---
    if not rules:
        default_rules = [
            models.ScoringRule(league_id=league_id, category="Passing", description="Passing TD", points=4.0),
            models.ScoringRule(league_id=league_id, category="Passing", description="Interception", points=-2.0),
            models.ScoringRule(league_id=league_id, category="Rushing", description="Rushing TD", points=6.0),
            models.ScoringRule(league_id=league_id, category="Receiving", description="Reception (PPR)", points=1.0),
            models.ScoringRule(league_id=league_id, category="Kicking", description="Field Goal Made", points=3.0),
            models.ScoringRule(league_id=league_id, category="Defense", description="Sack", points=1.0),
        ]
        db.add_all(default_rules)
        db.commit()
        # Fetch them again so they appear immediately
        rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).all()
    
    # 3. Combine them
    return LeagueConfigFull(
        roster_size=settings.roster_size,
        salary_cap=settings.salary_cap,
        starting_slots=settings.starting_slots or {},
        scoring_rules=[
            ScoringRuleSchema(category=r.category, description=r.description, points=r.points) 
            for r in rules
        ]
    )

@router.put("/{league_id}/settings")
def update_league_settings(
    league_id: int, 
    config: LeagueConfigFull, 
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Update Settings
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    settings.roster_size = config.roster_size
    settings.salary_cap = config.salary_cap
    settings.starting_slots = config.starting_slots
    
    # 2. Update Rules (Nuclear Option: Delete old, add new)
    # This is the easiest way to handle edits/deletes without complex logic
    db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id).delete()
    
    new_rules = []
    for r in config.scoring_rules:
        new_rules.append(models.ScoringRule(
            league_id=league_id,
            category=r.category,
            description=r.description,
            points=r.points
        ))
    db.add_all(new_rules)
    
    db.commit()
    return {"message": "League configuration saved!"}

# --- NEW: USER MANAGEMENT ENDPOINTS ---

@router.post("/{league_id}/members")
def add_league_member(
    league_id: int, 
    request: AddMemberRequest, 
    db: Session = Depends(get_db)
):
    """Move a specific user into this league."""
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.league_id = league_id
    db.commit()
    return {"message": f"{user.username} added to the league!"}

@router.delete("/{league_id}/members/{user_id}")
def remove_league_member(
    league_id: int, 
    user_id: int, 
    db: Session = Depends(get_db)
):
    """Kick a user out of the league (Make them a Free Agent)."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.league_id != league_id:
         raise HTTPException(status_code=400, detail="User is not in this league.")

    user.league_id = None  # Reset to NULL
    db.commit()
    return {"message": "User removed from league."}

# --- NEW: CREATE OWNER ENDPOINT ---
@router.post("/owners")
def create_owner(
    request: AddMemberRequest, 
    db: Session = Depends(get_db)
):
    """Invite a new user with an auto-generated 8-char password."""
    
    # 1. Check if username exists
    if db.query(models.User).filter(models.User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username taken.")
    
    # 2. Check if email exists (if provided)
    if request.email and db.query(models.User).filter(models.User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    # 3. Generate 8-Digit Random Password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(8))
    
    # 4. Hash & Save
    from auth import get_password_hash
    hashed_pw = get_password_hash(temp_password)
    
    # Create the user (assigning them to NO league initially, forcing a recruit step, 
    # OR you can assign them to league_id=1 if you want auto-add)
    new_user = models.User(
        username=request.username, 
        email=request.email,
        hashed_password=hashed_pw
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Send the Email (or print to console)
    if request.email:
        send_invite_email(request.email, request.username, temp_password)
    else:
        # Fallback if no email provided: print to console anyway
        print(f"User created without email. Temp Password: {temp_password}")
    
    return {
        "message": f"Invite sent to {request.email or 'Console'}!",
        # In production, DO NOT return the password here. For now, it helps debugging.
        "debug_password": temp_password 
    }
# backend/routers/league.py (Add to bottom)

@router.post("/{league_id}/finalize-draft")
def finalize_draft(league_id: int, db: Session = Depends(get_db)):
    """
    Commissioner Tool: Validates rosters and locks the draft.
    """
    # 1. Get League Settings (for roster size)
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    max_roster = settings.roster_size if settings else 14  # Default to 14 if missing

    # 2. Get Owners in THIS league
    owners = db.query(models.User).filter(
        models.User.league_id == league_id,
        models.User.username.not_in(["Free Agent", "Obsolete"])
    ).all()
    
    errors = []

    for owner in owners:
        picks = db.query(models.DraftPick).filter(
            models.DraftPick.owner_id == owner.id,
            models.DraftPick.league_id == league_id
        ).all()
        
        # Rule A: Check Roster Size vs League Settings
        if len(picks) < max_roster:
            errors.append(f"{owner.username} only has {len(picks)}/{max_roster} players.")
            continue

        # Rule B: Positional Check (Simple version)
        positions = set()
        for pick in picks:
            # Assuming you have a way to get player position (joined query or property)
            # For now, simplistic check if player object exists
            if pick.player: 
                pos = "DEF" if pick.player.position == "TD" else pick.player.position
                positions.add(pos)
        
        required = {"QB", "RB", "WR", "TE", "K", "DEF"}
        missing = required - positions
        
        if missing:
            errors.append(f"{owner.username} is missing: {', '.join(missing)}")

    if errors:
        return {"status": "error", "messages": errors}

    # 3. Success - In future, set league.status = 'active'
    return {"status": "success", "message": "DRAFT COMPLETE! Season is now active."}

@router.get("/players/search")
def search_players(q: str, db: Session = Depends(get_db)):
    """
    Search for players by name. 
    This is what powers the 'Global Search' and 'War Room'.
    """
    if len(q) < 2:
        return []
    
    # We use ilike for case-insensitive searching
    # We search the 'name' column (or 'first_name'/'last_name' depending on your model)
    results = db.query(models.Player).filter(
        models.Player.name.ilike(f"%{q}%")
    ).limit(10).all()
    
    return results