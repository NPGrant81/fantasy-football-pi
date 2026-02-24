from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from database import get_db
import models
from routers.league import get_league_owners
from utils import playoff_logic

router = APIRouter(
    prefix="/playoffs",
    tags=["Playoffs"]
)

# --- Schemas ---
class PlayoffSettingsSchema(BaseModel):
    playoff_qualifiers: int
    playoff_reseed: bool
    playoff_consolation: bool
    playoff_tiebreakers: List[str]

class SettingsUpdateRequest(BaseModel):
    playoff_qualifiers: Optional[int]
    playoff_reseed: Optional[bool]
    playoff_consolation: Optional[bool]
    playoff_tiebreakers: Optional[List[str]]

class GenerateRequest(BaseModel):
    league_id: int
    season: int

class MatchSchema(BaseModel):
    match_id: str
    round: int
    is_bye: bool = False
    team_1_id: Optional[int]
    team_2_id: Optional[int]
    winner_to: Optional[str]

class BracketSchema(BaseModel):
    championship: List[MatchSchema]
    consolation: Optional[List[MatchSchema]] = []

# --- Helpers ---
def _load_settings(db: Session, league_id: int) -> models.LeagueSettings:
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if not league.settings:
        # lazily create default settings
        league.settings = models.LeagueSettings(league_id=league.id)
        db.add(league.settings)
        db.commit()
        db.refresh(league.settings)
    return league.settings

# --- Endpoints ---
@router.get("/settings", response_model=PlayoffSettingsSchema)
def get_settings(league_id: int = Query(...), db: Session = Depends(get_db)):
    settings = _load_settings(db, league_id)
    return PlayoffSettingsSchema(
        playoff_qualifiers=settings.playoff_qualifiers,
        playoff_reseed=settings.playoff_reseed,
        playoff_consolation=settings.playoff_consolation,
        playoff_tiebreakers=settings.playoff_tiebreakers,
    )

@router.patch("/settings", response_model=PlayoffSettingsSchema)
def update_settings(payload: SettingsUpdateRequest, league_id: int = Query(...), db: Session = Depends(get_db)):
    settings = _load_settings(db, league_id)
    for field, val in payload.dict(exclude_unset=True).items():
        setattr(settings, field, val)
    db.commit()
    db.refresh(settings)
    return PlayoffSettingsSchema(
        playoff_qualifiers=settings.playoff_qualifiers,
        playoff_reseed=settings.playoff_reseed,
        playoff_consolation=settings.playoff_consolation,
        playoff_tiebreakers=settings.playoff_tiebreakers,
    )

@router.post("/generate")
def generate_bracket(req: GenerateRequest, db: Session = Depends(get_db)):
    league = db.query(models.League).filter(models.League.id == req.league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    settings = _load_settings(db, league.id)
    # build team list from owners using the league endpoint which already
    # computes and sorts by wins/pf etc.
    owners_data = get_league_owners(league_id=league.id, db=db)
    teams = [{"id": o["id"], "seed": idx + 1} for idx, o in enumerate(owners_data)]

    # create bracket structure using helper
    bracket = playoff_logic.build_initial_bracket(
        teams, settings.playoff_qualifiers, settings.playoff_reseed
    )

    # clear any existing matches for this league/season
    db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == league.id,
        models.PlayoffMatch.season == req.season,
    ).delete()

    # persist championship matches
    for m in bracket.get("championship", []):
        pm = models.PlayoffMatch(
            league_id=league.id,
            season=req.season,
            match_id=m["match_id"],
            round=m["round"],
            is_bye=m.get("is_bye", False),
            team_1_id=m.get("team_1", {}).get("id") if m.get("team_1") else None,
            team_2_id=m.get("team_2", {}).get("id") if m.get("team_2") else None,
            winner_to=m.get("winner_to"),
        )
        db.add(pm)
    db.commit()
    return {"status": "ok"}

@router.get("/bracket")
def get_bracket(league_id: int = Query(...), season: int = Query(...), db: Session = Depends(get_db)) -> Dict[str, Any]:
    matches = db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == league_id,
        models.PlayoffMatch.season == season,
    ).all()
    if not matches:
        raise HTTPException(status_code=404, detail="Bracket not found")

    # convert to JSON structure
    champ: List[Dict[str, Any]] = []
    for m in matches:
        champ.append({
            "match_id": m.match_id,
            "round": m.round,
            "is_bye": m.is_bye,
            "team_1_id": m.team_1_id,
            "team_2_id": m.team_2_id,
            "winner_to": m.winner_to,
        })
    # we currently do not generate consolation data here
    return {"championship": champ, "consolation": []}


class SnapshotRequest(BaseModel):
    league_id: int
    season: int

@router.post("/snapshot")
def snapshot(req: SnapshotRequest, db: Session = Depends(get_db)):
    """Save the current bracket structure as a historical snapshot."""
    bracket = get_bracket(req.league_id, req.season, db)
    snap = models.PlayoffSnapshot(
        league_id=req.league_id,
        season=req.season,
        data=bracket,
    )
    db.add(snap)
    db.commit()
    return {"status": "snapped", "id": snap.id}


class ReSeedRequest(BaseModel):
    league_id: int
    season: int

class MatchOverrideRequest(BaseModel):
    winner_team_id: int
    team_1_score: Optional[float] = None
    team_2_score: Optional[float] = None

@router.post("/reseed")
def reseed(req: ReSeedRequest, db: Session = Depends(get_db)):
    """Re-calculate round-two matchups after round-one is complete."""
    settings = _load_settings(db, req.league_id)
    matches = db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == req.league_id,
        models.PlayoffMatch.season == req.season,
        models.PlayoffMatch.round == 1,
    ).all()
    # convert to simple dicts for helper
    simple = []
    for m in matches:
        simple.append({
            "team_1": {"id": m.team_1_id, "seed": None},
            "team_2": {"id": m.team_2_id, "seed": None},
            "team_1_score": m.team_1_score,
            "team_2_score": m.team_2_score,
            "is_bye": m.is_bye,
        })
    new_matches = playoff_logic.reseed_bracket(simple, settings.playoff_tiebreakers)
    # delete any existing round2 entries
    db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == req.league_id,
        models.PlayoffMatch.season == req.season,
        models.PlayoffMatch.round == 2,
    ).delete()
    # persist
    for nm in new_matches:
        pm = models.PlayoffMatch(
            league_id=req.league_id,
            season=req.season,
            match_id=nm["match_id"],
            round=2,
            team_1_id=nm.get("home_team", {}).get("id"),
            team_2_id=nm.get("away_team", {}).get("id"),
        )
        db.add(pm)
    db.commit()
    return {"status": "reseeded"}

@router.put("/match/{match_id}/override")
def override_match(match_id: str,
                   payload: MatchOverrideRequest,
                   league_id: int = Query(...),
                   season: int = Query(...),
                   db: Session = Depends(get_db)):
    """Commissioner manually sets winner and optionally scores."""
    m = db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == league_id,
        models.PlayoffMatch.season == season,
        models.PlayoffMatch.match_id == match_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    # assign scores if provided
    if payload.team_1_score is not None:
        m.team_1_score = payload.team_1_score
    if payload.team_2_score is not None:
        m.team_2_score = payload.team_2_score
    # determine winner
    if m.team_1_id == payload.winner_team_id or m.team_2_id == payload.winner_team_id:
        # nothing else to do but save
        pass
    else:
        raise HTTPException(status_code=400, detail="Winner ID not part of match")
    db.commit()
    return {"status": "overridden"}
