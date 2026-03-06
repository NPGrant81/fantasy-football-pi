from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..core.security import get_current_user
from ..database import get_db
from ..services.division_balancing_service import (
    TeamStrengthInput,
    compute_imbalance_pct,
    compute_override_penalty,
    compute_team_strength,
    compute_confidence_score,
    deterministic_balanced_assignment,
    deterministic_random_assignment,
    format_balancing_response,
    validate_division_math,
    validate_division_name,
)

router = APIRouter(prefix="/leagues/{league_id}/divisions", tags=["Divisions"])


class DivisionNameItem(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    order_index: int = Field(ge=0)


class DivisionConfigUpsertRequest(BaseModel):
    season: int
    enabled: bool
    division_count: int | None = None
    assignment_method: str | None = None  # manual|random|heuristic
    random_seed: str | None = None
    names: list[DivisionNameItem] = []


class DivisionPreviewRequest(BaseModel):
    season: int
    assignment_method: str  # manual|random|heuristic
    random_seed: str | None = None
    manual_assignments: dict[int, list[int]] | None = None


class DivisionFinalizeRequest(BaseModel):
    season: int
    assignment_method: str
    random_seed: str | None = None


class DivisionReportNameRequest(BaseModel):
    season: int | None = None
    division_name: str
    reason: str | None = None


class DivisionUndoRequest(BaseModel):
    season: int


def _ensure_admin_for_league(current_user: models.User, league_id: int) -> None:
    if current_user.is_superuser:
        return
    if not current_user.is_commissioner:
        raise HTTPException(status_code=403, detail="Commissioner privileges required")
    if int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=403, detail="Commissioner can only modify their own league")


def _resolve_season(settings: models.LeagueSettings, explicit_season: int | None) -> int:
    if explicit_season is not None:
        return explicit_season
    if settings.draft_year:
        return int(settings.draft_year)
    return datetime.now(timezone.utc).year


def _league_strength_inputs(db: Session, league_id: int) -> list[TeamStrengthInput]:
    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    rows: list[TeamStrengthInput] = []

    for user in users:
        matches = db.query(models.Matchup).filter(
            (models.Matchup.home_team_id == user.id) | (models.Matchup.away_team_id == user.id)
        ).all()

        wins = 0
        completed = 0
        total_pf = 0.0

        for match in matches:
            if not match.is_completed:
                continue
            completed += 1
            if match.home_team_id == user.id:
                score = float(match.home_score or 0.0)
                opp = float(match.away_score or 0.0)
            else:
                score = float(match.away_score or 0.0)
                opp = float(match.home_score or 0.0)
            total_pf += score
            if score > opp:
                wins += 1

        avg_points = (total_pf / completed) if completed else 0.0
        win_pct = (wins / completed) if completed else 0.0

        roster_rows = (
            db.query(models.DraftPick, models.Player)
            .join(models.Player, models.Player.id == models.DraftPick.player_id)
            .filter(models.DraftPick.owner_id == user.id)
            .all()
        )
        projected = 0.0
        if roster_rows:
            projected = sum(float(player.projected_points or 0.0) for _, player in roster_rows) / len(roster_rows)

        rows.append(
            TeamStrengthInput(
                team_id=user.id,
                avg_points_for_last_season=avg_points,
                win_pct_last_season=win_pct,
                projected_roster_score=projected if roster_rows else None,
            )
        )

    return rows


def _get_or_create_settings(db: Session, league_id: int) -> models.LeagueSettings:
    settings = db.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league_id).first()
    if settings:
        return settings
    settings = models.LeagueSettings(league_id=league_id)
    db.add(settings)
    db.flush()
    return settings


def _get_divisions_for_season(db: Session, league_id: int, season: int) -> list[models.Division]:
    return (
        db.query(models.Division)
        .filter(models.Division.league_id == league_id, models.Division.season == season)
        .order_by(models.Division.order_index.asc(), models.Division.id.asc())
        .all()
    )


def _current_assignment(db: Session, league_id: int) -> dict[int, list[int]]:
    mapping: dict[int, list[int]] = {}
    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    for user in users:
        if user.division_id is None:
            continue
        mapping.setdefault(int(user.division_id), []).append(int(user.id))
    return mapping


@router.get("/config")
def get_division_config(
    league_id: int,
    season: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_admin_for_league(current_user, league_id)
    settings = _get_or_create_settings(db, league_id)
    effective_season = _resolve_season(settings, season)

    divisions = _get_divisions_for_season(db, league_id, effective_season)
    proposal_from_prev: list[dict[str, Any]] = []
    if not divisions:
        previous = _get_divisions_for_season(db, league_id, effective_season - 1)
        proposal_from_prev = [
            {"name": d.name, "order_index": d.order_index}
            for d in previous
        ]

    return {
        "league_id": league_id,
        "season": effective_season,
        "divisions_enabled": bool(settings.divisions_enabled),
        "division_count": settings.division_count,
        "division_config_status": settings.division_config_status,
        "division_assignment_method": settings.division_assignment_method,
        "division_random_seed": settings.division_random_seed,
        "division_needs_reseed": bool(settings.division_needs_reseed),
        "divisions": [
            {
                "id": d.id,
                "name": d.name,
                "order_index": d.order_index,
            }
            for d in divisions
        ],
        "proposal_from_previous_season": proposal_from_prev,
    }


@router.put("/config")
def upsert_division_config(
    league_id: int,
    payload: DivisionConfigUpsertRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_admin_for_league(current_user, league_id)
    settings = _get_or_create_settings(db, league_id)

    users = db.query(models.User).filter(models.User.league_id == league_id).all()
    team_count = len(users)

    if not payload.enabled:
        settings.divisions_enabled = False
        settings.division_count = None
        settings.division_config_status = "draft"
        settings.division_assignment_method = None
        settings.division_random_seed = None
        db.commit()
        return {"status": "ok", "divisions_enabled": False}

    if payload.division_count is None:
        raise HTTPException(status_code=400, detail="division_count is required when divisions are enabled")

    math_errors = validate_division_math(team_count=team_count, division_count=payload.division_count)
    if math_errors:
        raise HTTPException(status_code=400, detail={"division_count": math_errors})

    if len(payload.names) != payload.division_count:
        raise HTTPException(status_code=400, detail="division names must match division_count")

    existing_names: set[str] = set()
    name_errors: dict[str, list[str]] = {}
    for idx, row in enumerate(payload.names):
        errs = validate_division_name(row.name, existing_names)
        if errs:
            name_errors[f"names[{idx}]"] = errs
        existing_names.add(row.name.strip().casefold())

    if name_errors:
        raise HTTPException(status_code=400, detail=name_errors)

    db.query(models.Division).filter(
        models.Division.league_id == league_id,
        models.Division.season == payload.season,
    ).delete()

    for row in sorted(payload.names, key=lambda x: x.order_index):
        db.add(
            models.Division(
                league_id=league_id,
                season=payload.season,
                name=row.name.strip(),
                order_index=row.order_index,
            )
        )

    settings.divisions_enabled = True
    settings.division_count = payload.division_count
    settings.division_config_status = "draft"
    settings.division_assignment_method = payload.assignment_method
    settings.division_random_seed = payload.random_seed

    db.commit()
    return {"status": "ok", "divisions_enabled": True}


@router.post("/assignment-preview")
def preview_assignment(
    league_id: int,
    payload: DivisionPreviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_admin_for_league(current_user, league_id)
    settings = _get_or_create_settings(db, league_id)

    division_count = int(settings.division_count or 0)
    if division_count <= 0:
        raise HTTPException(status_code=400, detail="division_count must be configured before preview")

    team_inputs = _league_strength_inputs(db, league_id)
    strengths = [compute_team_strength(row) for row in team_inputs]
    previous = _current_assignment(db, league_id)

    method = payload.assignment_method.strip().lower()
    seed = payload.random_seed or settings.division_random_seed or secrets.token_hex(8)

    if method == "manual":
        if not payload.manual_assignments:
            raise HTTPException(status_code=400, detail="manual_assignments is required for manual previews")

        by_team = {item.team_id: item for item in strengths}
        assignment_rows: dict[int, list[Any]] = {}
        for key, team_ids in payload.manual_assignments.items():
            assignment_rows[int(key)] = [by_team[team_id] for team_id in team_ids if team_id in by_team]

        division_strengths = {
            idx: sum(t.strength_final for t in teams) / len(teams)
            for idx, teams in assignment_rows.items()
            if teams
        }
        imbalance_pct = compute_imbalance_pct(division_strengths)
        baseline_pct = 0.0
        if previous:
            prev_map = {item.team_id: item for item in strengths}
            prev_rows: dict[int, list[Any]] = {}
            for division_id, team_ids in previous.items():
                prev_rows[int(division_id)] = [prev_map[tid] for tid in team_ids if tid in prev_map]
            prev_strengths = {
                idx: sum(t.strength_final for t in teams) / len(teams)
                for idx, teams in prev_rows.items()
                if teams
            }
            baseline_pct = compute_imbalance_pct(prev_strengths)

        penalty = compute_override_penalty(baseline_pct, imbalance_pct)
        confidence = compute_confidence_score(imbalance_pct, penalty)
        return {
            "assignment_method": "manual",
            "seed": seed,
            "confidence_score": confidence,
            "imbalance_pct": imbalance_pct,
            "override_penalty": penalty,
            "assignments": [
                {
                    "division_index": idx,
                    "team_ids": [t.team_id for t in teams],
                    "strength_avg": round(sum(t.strength_final for t in teams) / len(teams), 4) if teams else 0.0,
                }
                for idx, teams in assignment_rows.items()
            ],
            "previous_assignments": previous,
            "team_strengths": [
                {
                    "team_id": t.team_id,
                    "strength_raw": t.strength_raw,
                    "strength_final": t.strength_final,
                }
                for t in strengths
            ],
        }

    if method == "random":
        idx_map = deterministic_random_assignment([item.team_id for item in strengths], division_count, seed)
        by_team = {item.team_id: item for item in strengths}
        assignment_rows = {
            idx: [by_team[team_id] for team_id in team_ids if team_id in by_team]
            for idx, team_ids in idx_map.items()
        }
    elif method == "heuristic":
        assignment_rows = deterministic_balanced_assignment(strengths, division_count, seed)
    else:
        raise HTTPException(status_code=400, detail="assignment_method must be one of: manual, random, heuristic")

    return format_balancing_response(
        assignment_method=method,
        assignments=assignment_rows,
        previous_assignments=previous,
        seed=seed,
    )


@router.post("/finalize")
def finalize_assignment(
    league_id: int,
    payload: DivisionFinalizeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_admin_for_league(current_user, league_id)

    settings = _get_or_create_settings(db, league_id)
    divisions = _get_divisions_for_season(db, league_id, payload.season)
    if not divisions:
        raise HTTPException(status_code=400, detail="division names must be configured before finalizing")

    preview = preview_assignment(
        league_id=league_id,
        payload=DivisionPreviewRequest(
            season=payload.season,
            assignment_method=payload.assignment_method,
            random_seed=payload.random_seed,
        ),
        db=db,
        current_user=current_user,
    )

    by_index = {idx: div for idx, div in enumerate(divisions)}
    users = {u.id: u for u in db.query(models.User).filter(models.User.league_id == league_id).all()}
    previous = _current_assignment(db, league_id)

    for row in preview.get("assignments", []):
        div = by_index.get(int(row["division_index"]))
        if not div:
            continue
        for team_id in row.get("team_ids", []):
            user = users.get(int(team_id))
            if user:
                user.division_id = div.id

    settings.division_config_status = "finalized"
    settings.division_assignment_method = payload.assignment_method
    settings.division_random_seed = preview.get("seed")
    settings.division_needs_reseed = False

    db.add(
        models.DivisionConfigSnapshot(
            league_id=league_id,
            season=payload.season,
            status="finalized",
            assignment_method=payload.assignment_method,
            random_seed=preview.get("seed"),
            confidence_score=float(preview.get("confidence_score", 0.0)),
            imbalance_pct=float(preview.get("imbalance_pct", 0.0)),
            config_json={
                "preview": preview,
                "previous_assignments": previous,
            },
            created_by_user_id=current_user.id,
        )
    )

    db.commit()
    return {"status": "finalized", "preview": preview}


@router.post("/undo-last")
def undo_last_assignment(
    league_id: int,
    payload: DivisionUndoRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_admin_for_league(current_user, league_id)

    latest = (
        db.query(models.DivisionConfigSnapshot)
        .filter(
            models.DivisionConfigSnapshot.league_id == league_id,
            models.DivisionConfigSnapshot.season == payload.season,
            models.DivisionConfigSnapshot.status == "finalized",
        )
        .order_by(models.DivisionConfigSnapshot.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No finalized division assignment to undo")

    previous = (latest.config_json or {}).get("previous_assignments") or {}
    users = {u.id: u for u in db.query(models.User).filter(models.User.league_id == league_id).all()}

    # Clear current assignment first.
    for user in users.values():
        user.division_id = None

    for division_id, team_ids in previous.items():
        for team_id in team_ids:
            user = users.get(int(team_id))
            if user:
                user.division_id = int(division_id)

    settings = _get_or_create_settings(db, league_id)
    settings.division_config_status = "draft"

    db.add(
        models.DivisionConfigSnapshot(
            league_id=league_id,
            season=payload.season,
            status="undo",
            assignment_method=settings.division_assignment_method,
            random_seed=settings.division_random_seed,
            confidence_score=None,
            imbalance_pct=None,
            config_json={"restored_assignments": previous, "undone_snapshot_id": latest.id},
            created_by_user_id=current_user.id,
        )
    )

    db.commit()
    return {"status": "undone"}


@router.post("/report-name")
def report_division_name(
    league_id: int,
    payload: DivisionReportNameRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    report = models.DivisionNameReport(
        league_id=league_id,
        season=payload.season,
        division_name=payload.division_name.strip(),
        reason=payload.reason,
        reported_by_user_id=current_user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "status": "queued",
        "report_id": report.id,
    }
