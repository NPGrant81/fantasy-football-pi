from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from ..database import get_db
from .. import models
from ..routers.league import fetch_league_owners_data
from ..services.standings_service import owner_standings_sort_key
from ..services.validation_service import (
    validate_playoff_settings_boundary,
    validate_playoff_settings_dynamic_rules,
)
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
    playoff_qualifiers: Optional[int] = None
    playoff_reseed: Optional[bool] = None
    playoff_consolation: Optional[bool] = None
    playoff_tiebreakers: Optional[List[str]] = None

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
    team_1_seed: Optional[int] = None
    team_2_seed: Optional[int] = None
    team_1_is_division_winner: Optional[bool] = None
    team_2_is_division_winner: Optional[bool] = None
    team_1_division_name: Optional[str] = None
    team_2_division_name: Optional[str] = None

class BracketSchema(BaseModel):
    championship: List[MatchSchema]
    consolation: Optional[List[MatchSchema]] = []


def _should_use_division_seeding(settings: models.LeagueSettings, owners_data: List[Dict[str, Any]]) -> bool:
    return bool(
        getattr(settings, "divisions_enabled", False)
        and any(bool(owner.get("division_id")) for owner in owners_data)
    )


def _ranked_division_winner_rows(owners_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for owner in owners_data:
        division_id = owner.get("division_id")
        if not division_id:
            continue
        grouped.setdefault(int(division_id), []).append(owner)

    winners: List[Dict[str, Any]] = []
    for rows in grouped.values():
        ranked = sorted(rows, key=owner_standings_sort_key)
        if ranked:
            winners.append(ranked[0])

    winners.sort(key=owner_standings_sort_key)
    return winners


def _build_playoff_context(
    owners_data: List[Dict[str, Any]],
    settings: models.LeagueSettings,
    qualifiers: int,
) -> Dict[str, Any]:
    ordered_owners = sorted(owners_data, key=owner_standings_sort_key)
    uses_division_seeding = _should_use_division_seeding(settings, ordered_owners)

    division_winner_rows = _ranked_division_winner_rows(ordered_owners) if uses_division_seeding else []
    selected_division_winner_rows = division_winner_rows[:qualifiers]
    division_winner_ids = {int(row["id"]) for row in selected_division_winner_rows}

    wildcard_slots = max(0, qualifiers - len(selected_division_winner_rows))
    wildcard_rows = [row for row in ordered_owners if int(row["id"]) not in division_winner_ids][:wildcard_slots]
    playoff_rows = selected_division_winner_rows + wildcard_rows

    # If division winners do not fully populate the field, fall back to overall standings.
    if len(playoff_rows) < qualifiers:
        already_selected = {int(row["id"]) for row in playoff_rows}
        needed = qualifiers - len(playoff_rows)
        playoff_rows.extend(
            row for row in ordered_owners if int(row["id"]) not in already_selected
        )
        playoff_rows = playoff_rows[:qualifiers]

    playoff_team_ids = {int(row["id"]) for row in playoff_rows}
    playoff_teams = [
        {
            "id": int(row["id"]),
            "seed": index + 1,
            "division_id": row.get("division_id"),
            "division_name": row.get("division_name"),
            "is_division_winner": int(row["id"]) in division_winner_ids,
        }
        for index, row in enumerate(playoff_rows)
    ]

    return {
        "ordered_owners": ordered_owners,
        "playoff_rows": playoff_rows,
        "playoff_teams": playoff_teams,
        "playoff_team_ids": playoff_team_ids,
        "division_winner_ids": division_winner_ids,
        "uses_division_seeding": uses_division_seeding,
        "wildcard_count": len([row for row in playoff_rows if int(row["id"]) not in division_winner_ids]),
    }


def _build_seeding_policy_payload(
    *,
    settings: models.LeagueSettings,
    playoff_context: Dict[str, Any],
    championship_matches: List[Dict[str, Any]],
    consolation_matches: List[Dict[str, Any]],
    qualifiers: int,
) -> Dict[str, Any]:
    round_labels = _build_round_labels(championship_matches, consolation_matches, qualifiers)
    return {
        "divisions_enabled": bool(getattr(settings, "divisions_enabled", False)),
        "division_count": getattr(settings, "division_count", None),
        "division_winners_top_seeds": playoff_context["uses_division_seeding"],
        "division_winner_count": len(playoff_context["division_winner_ids"]),
        "wildcards_by_overall_record": playoff_context["wildcard_count"] > 0,
        "seed_source": "division_winners_then_wildcards"
        if playoff_context["uses_division_seeding"]
        else "overall_record",
        "tiebreak_chain": settings.playoff_tiebreakers,
        "playoff_qualifiers": qualifiers,
        "playoff_reseed": settings.playoff_reseed,
        "playoff_consolation": bool(settings.playoff_consolation),
        "playoff_week_count": len(round_labels.get("championship") or {}),
        "round_labels": round_labels,
    }


def _build_meta_payload(
    *,
    league_id: int,
    season: int,
    current_year: int,
    source: str,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    warning_list = [warning for warning in (warnings or []) if warning]
    return {
        "league_id": league_id,
        "season": season,
        "is_historical": season != current_year,
        "source": source,
        "warnings": warning_list,
        "is_partial": bool(warning_list),
    }


def _effective_playoff_qualifiers(configured: int, owner_count: int) -> int:
    """Normalize qualifier count to a valid, even value for current league size."""
    if owner_count < 2:
        raise HTTPException(status_code=400, detail="Need at least two owners to generate bracket")

    desired = int(configured or 0)
    desired = max(2, desired)
    desired = min(desired, owner_count)

    # Keep qualifiers even for deterministic pairing.
    if desired % 2 != 0:
        desired -= 1

    if desired < 2:
        raise HTTPException(status_code=400, detail="Unable to derive a valid playoff qualifier count")

    return desired


def _build_round_labels(
    championship_matches: List[Dict[str, Any]],
    consolation_matches: List[Dict[str, Any]],
    qualifiers: int,
) -> Dict[str, Dict[str, str]]:
    """Build user-friendly labels for rounds currently present in payload."""
    championship_rounds = sorted(
        {int(m.get("round") or 1) for m in championship_matches}
    )
    consolation_rounds = sorted(
        {int(m.get("round") or 1) for m in consolation_matches}
    )

    championship_labels: Dict[str, str] = {}
    if championship_rounds:
        for index, round_num in enumerate(championship_rounds, start=1):
            rounds_remaining = len(championship_rounds) - index + 1
            if rounds_remaining == 1:
                label = "Championship Final"
            elif rounds_remaining == 2:
                label = "Semifinal"
            elif qualifiers == 6 and index == 1:
                label = "Wildcard Round"
            elif rounds_remaining == 3:
                label = "Quarterfinal"
            else:
                label = f"Round {round_num}"
            championship_labels[str(round_num)] = label

    consolation_labels: Dict[str, str] = {}
    if consolation_rounds:
        for index, round_num in enumerate(consolation_rounds, start=1):
            rounds_remaining = len(consolation_rounds) - index + 1
            if rounds_remaining == 1:
                label = "Toilet Bowl Final"
            else:
                label = f"Consolation Round {index}"
            consolation_labels[str(round_num)] = label

    return {
        "championship": championship_labels,
        "consolation": consolation_labels,
    }


def _division_winner_owner_ids(owners_data: List[Dict[str, Any]]) -> set[int]:
    winners: set[int] = set()
    grouped: dict[int, List[Dict[str, Any]]] = {}
    for row in owners_data:
        division_id = row.get("division_id")
        if not division_id:
            continue
        grouped.setdefault(int(division_id), []).append(row)

    for rows in grouped.values():
        rows.sort(key=lambda o: (-o.get("wins", 0), -float(o.get("pf", 0.0)), o.get("id", 0)))
        winners.add(int(rows[0]["id"]))
    return winners

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


def _resolve_match_winner_id(match: Dict[str, Any]) -> Optional[int]:
    """Resolve a winner id from a bracket match payload when possible."""
    if match.get("is_bye"):
        return match.get("team_1_id")

    team_1_id = match.get("team_1_id")
    team_2_id = match.get("team_2_id")
    score_1 = match.get("team_1_score")
    score_2 = match.get("team_2_score")

    if team_1_id is None:
        return team_2_id
    if team_2_id is None:
        return team_1_id
    if score_1 is None or score_2 is None:
        return None
    if score_1 > score_2:
        return team_1_id
    if score_2 > score_1:
        return team_2_id

    seed_1 = match.get("team_1_seed") or 999
    seed_2 = match.get("team_2_seed") or 999
    return team_1_id if seed_1 <= seed_2 else team_2_id


def _build_winner_summary(matches: List[Dict[str, Any]], owner_by_id: Dict[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return winner metadata for the final round when scores are available."""
    if not matches:
        return None

    finals = [m for m in matches if not m.get("winner_to")]
    if not finals:
        max_round = max((m.get("round") or 0 for m in matches), default=0)
        finals = [m for m in matches if (m.get("round") or 0) == max_round]

    if not finals:
        return None

    final_match = sorted(finals, key=lambda m: m.get("match_id") or "")[0]
    winner_id = _resolve_match_winner_id(final_match)
    if not winner_id:
        return None

    owner = owner_by_id.get(int(winner_id), {})
    return {
        "owner_id": int(winner_id),
        "team_name": owner.get("team_name") or owner.get("username") or f"Team {winner_id}",
    }


def _build_consolation_payload(
    ordered_owners: List[Dict[str, Any]],
    playoff_team_ids: set[int],
    playoff_consolation: bool,
    division_winners: set[int],
) -> List[Dict[str, Any]]:
    """Build toilet-bowl bracket payload from standings when enabled."""
    if not playoff_consolation:
        return []

    all_teams = [{"id": o["id"], "seed": idx + 1} for idx, o in enumerate(ordered_owners)]
    playoff_teams = [team for team in all_teams if int(team["id"]) in playoff_team_ids]
    generated = playoff_logic.generate_consolation_bracket(all_teams, playoff_teams)
    payload: List[Dict[str, Any]] = []

    for m in generated:
        payload.append(
            {
                "match_id": m.get("match_id"),
                "round": m.get("round", 1),
                "is_bye": m.get("is_bye", False),
                "team_1_id": m.get("team_1", {}).get("id") if m.get("team_1") else None,
                "team_2_id": m.get("team_2", {}).get("id") if m.get("team_2") else None,
                "winner_to": m.get("winner_to"),
                "team_1_seed": m.get("team_1", {}).get("seed") if m.get("team_1") else None,
                "team_2_seed": m.get("team_2", {}).get("seed") if m.get("team_2") else None,
                "team_1_is_division_winner": (m.get("team_1", {}).get("id") in division_winners)
                if m.get("team_1")
                else False,
                "team_2_is_division_winner": (m.get("team_2", {}).get("id") in division_winners)
                if m.get("team_2")
                else False,
                "team_1_division_name": None,
                "team_2_division_name": None,
                "team_1_score": None,
                "team_2_score": None,
            }
        )

    return payload

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
    patch_payload = payload.model_dump(exclude_unset=True)
    boundary_report = validate_playoff_settings_boundary(patch_payload)
    if not boundary_report.valid:
        raise HTTPException(status_code=400, detail=boundary_report.errors)

    dynamic_report = validate_playoff_settings_dynamic_rules(patch_payload)
    if not dynamic_report.valid:
        raise HTTPException(status_code=400, detail=dynamic_report.errors)

    settings = _load_settings(db, league_id)
    for field, val in patch_payload.items():
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
    owners_data = fetch_league_owners_data(league_id=league.id, db=db)
    effective_qualifiers = _effective_playoff_qualifiers(
        settings.playoff_qualifiers,
        len(owners_data),
    )
    playoff_context = _build_playoff_context(owners_data, settings, effective_qualifiers)
    division_winners = playoff_context["division_winner_ids"]

    # create bracket structure using helper
    bracket = playoff_logic.build_initial_bracket(
        playoff_context["playoff_teams"], effective_qualifiers, settings.playoff_reseed
    )
    consolation = _build_consolation_payload(
        playoff_context["ordered_owners"],
        playoff_context["playoff_team_ids"],
        bool(settings.playoff_consolation),
        division_winners,
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
            team_1_seed=m.get("team_1", {}).get("seed") if m.get("team_1") else None,
            team_2_seed=m.get("team_2", {}).get("seed") if m.get("team_2") else None,
            team_1_is_division_winner=(m.get("team_1", {}).get("id") in division_winners) if m.get("team_1") else False,
            team_2_is_division_winner=(m.get("team_2", {}).get("id") in division_winners) if m.get("team_2") else False,
        )
        db.add(pm)

    for m in consolation:
        pm = models.PlayoffMatch(
            league_id=league.id,
            season=req.season,
            match_id=m.get("match_id"),
            round=m.get("round", 1),
            is_bye=m.get("is_bye", False),
            team_1_id=m.get("team_1_id"),
            team_2_id=m.get("team_2_id"),
            winner_to=m.get("winner_to"),
            team_1_seed=m.get("team_1_seed"),
            team_2_seed=m.get("team_2_seed"),
            team_1_is_division_winner=m.get("team_1_is_division_winner", False),
            team_2_is_division_winner=m.get("team_2_is_division_winner", False),
        )
        db.add(pm)
    db.commit()

    snapshot_payload = {
        "championship": [
            {
                "match_id": m.match_id,
                "round": m.round,
                "is_bye": m.is_bye,
                "team_1_id": m.team_1_id,
                "team_2_id": m.team_2_id,
                "winner_to": m.winner_to,
                "team_1_seed": m.team_1_seed,
                "team_2_seed": m.team_2_seed,
                "team_1_is_division_winner": m.team_1_is_division_winner,
                "team_2_is_division_winner": m.team_2_is_division_winner,
                "team_1_division_name": None,
                "team_2_division_name": None,
                "team_1_score": m.team_1_score,
                "team_2_score": m.team_2_score,
            }
            for m in db.query(models.PlayoffMatch)
            .filter(
                models.PlayoffMatch.league_id == league.id,
                models.PlayoffMatch.season == req.season,
                ~models.PlayoffMatch.match_id.like("con_%"),
            )
            .order_by(models.PlayoffMatch.round.asc(), models.PlayoffMatch.match_id.asc())
            .all()
        ],
        "consolation": [
            {
                "match_id": m.match_id,
                "round": m.round,
                "is_bye": m.is_bye,
                "team_1_id": m.team_1_id,
                "team_2_id": m.team_2_id,
                "winner_to": m.winner_to,
                "team_1_seed": m.team_1_seed,
                "team_2_seed": m.team_2_seed,
                "team_1_is_division_winner": m.team_1_is_division_winner,
                "team_2_is_division_winner": m.team_2_is_division_winner,
                "team_1_division_name": None,
                "team_2_division_name": None,
                "team_1_score": m.team_1_score,
                "team_2_score": m.team_2_score,
            }
            for m in db.query(models.PlayoffMatch)
            .filter(
                models.PlayoffMatch.league_id == league.id,
                models.PlayoffMatch.season == req.season,
                models.PlayoffMatch.match_id.like("con_%"),
            )
            .order_by(models.PlayoffMatch.round.asc(), models.PlayoffMatch.match_id.asc())
            .all()
        ],
        "seeding_policy": _build_seeding_policy_payload(
            settings=settings,
            playoff_context=playoff_context,
            championship_matches=bracket.get("championship", []),
            consolation_matches=consolation,
            qualifiers=effective_qualifiers,
        ),
        "meta": _build_meta_payload(
            league_id=req.league_id,
            season=req.season,
            current_year=datetime.now(timezone.utc).year,
            source="snapshot",
        ),
    }
    db.add(
        models.PlayoffSnapshot(
            league_id=req.league_id,
            season=req.season,
            data=snapshot_payload,
        )
    )
    db.commit()
    return {"status": "ok"}

@router.get("/seasons")
def get_seasons(league_id: int = Query(...), db: Session = Depends(get_db)) -> List[int]:
    """Return a list of seasons for which a bracket exists for a given league.

    This is used by the UI to populate an archive dropdown.
    """
    results = (
        db.query(models.PlayoffMatch.season)
        .filter(models.PlayoffMatch.league_id == league_id)
        .distinct()
        .order_by(models.PlayoffMatch.season.desc())
        .all()
    )
    # results is list of tuples
    seasons = [row[0] for row in results]
    # also include any snapshot seasons not already present
    snap_seasons = (
        db.query(models.PlayoffSnapshot.season)
        .filter(models.PlayoffSnapshot.league_id == league_id)
        .distinct()
        .all()
    )
    for row in snap_seasons:
        if row[0] not in seasons:
            seasons.append(row[0])
    seasons.sort(reverse=True)
    return seasons


@router.get("/bracket")
def get_bracket(league_id: int = Query(...), season: int = Query(...), db: Session = Depends(get_db)) -> Dict[str, Any]:
    current_year = datetime.now(timezone.utc).year
    snap = (
        db.query(models.PlayoffSnapshot)
        .filter(
            models.PlayoffSnapshot.league_id == league_id,
            models.PlayoffSnapshot.season == season,
        )
        .order_by(models.PlayoffSnapshot.id.desc())
        .first()
    )

    # Historical seasons should prefer season-specific snapshots when available.
    if season != current_year and snap and isinstance(snap.data, dict):
        snap_data = dict(snap.data)
        snap_data["meta"] = _build_meta_payload(
            league_id=league_id,
            season=season,
            current_year=current_year,
            source="snapshot",
        )
        return snap_data

    matches = db.query(models.PlayoffMatch).filter(
        models.PlayoffMatch.league_id == league_id,
        models.PlayoffMatch.season == season,
    ).all()
    if not matches:
        if snap and isinstance(snap.data, dict):
            snap_data = dict(snap.data)
            snap_data["meta"] = _build_meta_payload(
                league_id=league_id,
                season=season,
                current_year=current_year,
                source="snapshot_fallback",
                warnings=[
                    "Using saved bracket snapshot because live playoff match rows are unavailable for this season.",
                ],
            )
            return snap_data
        raise HTTPException(status_code=404, detail="Bracket not found")

    # convert to JSON structure
    champ: List[Dict[str, Any]] = []
    stored_consolation: List[Dict[str, Any]] = []
    owners_data = fetch_league_owners_data(league_id=league_id, db=db)
    owner_by_id = {int(o["id"]): o for o in owners_data}
    settings = _load_settings(db, league_id)
    effective_qualifiers = _effective_playoff_qualifiers(
        settings.playoff_qualifiers,
        len(owners_data),
    )
    playoff_context = _build_playoff_context(owners_data, settings, effective_qualifiers)
    division_winners = playoff_context["division_winner_ids"]
    for m in matches:
        team_1 = owner_by_id.get(int(m.team_1_id)) if m.team_1_id else None
        team_2 = owner_by_id.get(int(m.team_2_id)) if m.team_2_id else None
        match_payload = {
            "match_id": m.match_id,
            "round": m.round,
            "is_bye": m.is_bye,
            "team_1_id": m.team_1_id,
            "team_2_id": m.team_2_id,
            "winner_to": m.winner_to,
            "team_1_seed": m.team_1_seed,
            "team_2_seed": m.team_2_seed,
            "team_1_is_division_winner": m.team_1_is_division_winner,
            "team_2_is_division_winner": m.team_2_is_division_winner,
            "team_1_division_name": team_1.get("division_name") if team_1 else None,
            "team_2_division_name": team_2.get("division_name") if team_2 else None,
            "team_1_score": m.team_1_score,
            "team_2_score": m.team_2_score,
        }

        if str(m.match_id or "").startswith("con_"):
            stored_consolation.append(match_payload)
        else:
            champ.append(match_payload)

    if stored_consolation:
        consolation = stored_consolation
    else:
        consolation = _build_consolation_payload(
            playoff_context["ordered_owners"],
            playoff_context["playoff_team_ids"],
            bool(settings.playoff_consolation),
            division_winners,
        )
        for match in consolation:
            team_1 = owner_by_id.get(int(match["team_1_id"])) if match.get("team_1_id") else None
            team_2 = owner_by_id.get(int(match["team_2_id"])) if match.get("team_2_id") else None
            match["team_1_division_name"] = team_1.get("division_name") if team_1 else None
            match["team_2_division_name"] = team_2.get("division_name") if team_2 else None

    warnings: List[str] = []
    source = "matches"
    if season != current_year and not snap:
        source = "matches_fallback"
        warnings.append(
            "Historical season snapshot is unavailable; bracket rendered from playoff match rows and current league settings where season-specific settings were not captured."
        )
    return {
        "championship": champ,
        "consolation": consolation,
        "champion": _build_winner_summary(champ, owner_by_id),
        "toilet_bowl_winner": _build_winner_summary(consolation, owner_by_id),
        "seeding_policy": _build_seeding_policy_payload(
            settings=settings,
            playoff_context=playoff_context,
            championship_matches=champ,
            consolation_matches=consolation,
            qualifiers=effective_qualifiers,
        ),
        "meta": _build_meta_payload(
            league_id=league_id,
            season=season,
            current_year=current_year,
            source=source,
            warnings=warnings,
        ),
    }


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
