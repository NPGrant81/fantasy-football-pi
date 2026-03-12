"""Audit and optionally clean invalid placeholder players.

Usage examples (from repo root):
  python -m backend.manage audit-invalid-players
  python -m backend.manage audit-invalid-players --league-id 1
  python -m backend.manage audit-invalid-players --league-id 1 --owner-team-name "The Big Show" --allow-reset-draft-picks
  python -m backend.manage audit-invalid-players --apply --allow-reset-draft-picks
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.database import SessionLocal
from backend.services import player_service


def _query_invalid_players(db: Session) -> list[models.Player]:
    players = db.query(models.Player).order_by(models.Player.id.asc()).all()
    return [row for row in players if not player_service.is_valid_player_row(row)]


def _resolve_owner_ids(db: Session, *, owner_id: int | None, owner_team_name: str | None) -> set[int]:
    if owner_id is not None:
        return {int(owner_id)}

    normalized_team_name = (owner_team_name or "").strip()
    if not normalized_team_name:
        return set()

    rows = (
        db.query(models.User.id)
        .filter(func.lower(models.User.team_name) == normalized_team_name.lower())
        .all()
    )
    return {int(row[0]) for row in rows}


def _reference_counts(
    db: Session,
    *,
    player_id: int,
    league_id: int | None,
    owner_ids: set[int],
) -> dict[str, int]:
    draft_pick_query = db.query(models.DraftPick).filter(models.DraftPick.player_id == player_id)
    keeper_query = db.query(models.Keeper).filter(models.Keeper.player_id == player_id)
    waiver_query = db.query(models.WaiverClaim).filter(models.WaiverClaim.player_id == player_id)

    if league_id is not None:
        draft_pick_query = draft_pick_query.filter(models.DraftPick.league_id == league_id)
        keeper_query = keeper_query.filter(models.Keeper.league_id == league_id)
        waiver_query = waiver_query.filter(models.WaiverClaim.league_id == league_id)

    if owner_ids:
        draft_pick_query = draft_pick_query.filter(models.DraftPick.owner_id.in_(owner_ids))
        keeper_query = keeper_query.filter(models.Keeper.owner_id.in_(owner_ids))

    counts = {
        "draft_picks.player_id": int(draft_pick_query.count()),
        "keepers.player_id": int(keeper_query.count()),
        "waiver_claims.player_id": int(waiver_query.count()),
    }
    counts["total_scoped_references"] = sum(counts.values())
    return counts


def _find_replacement_player(db: Session, player: models.Player) -> models.Player | None:
    replacement = player_service.find_existing_player(
        db,
        gsis_id=player.gsis_id,
        espn_id=player.espn_id,
        name=player.name,
        position=player.position,
        nfl_team=player.nfl_team,
    )
    if replacement is None:
        return None
    if replacement.id == player.id:
        return None
    if not player_service.is_valid_player_row(replacement):
        return None
    return replacement


def _apply_scoped_cleanup(
    db: Session,
    *,
    player_id: int,
    replacement_id: int | None,
    allow_reset_draft_picks: bool,
    league_id: int | None,
    owner_ids: set[int],
) -> dict[str, int]:
    updates = {
        "draft_picks.player_id": 0,
        "keepers.player_id": 0,
        "waiver_claims.player_id": 0,
        "players.deleted": 0,
    }

    draft_pick_query = db.query(models.DraftPick).filter(models.DraftPick.player_id == player_id)
    keeper_query = db.query(models.Keeper).filter(models.Keeper.player_id == player_id)
    waiver_query = db.query(models.WaiverClaim).filter(models.WaiverClaim.player_id == player_id)

    if league_id is not None:
        draft_pick_query = draft_pick_query.filter(models.DraftPick.league_id == league_id)
        keeper_query = keeper_query.filter(models.Keeper.league_id == league_id)
        waiver_query = waiver_query.filter(models.WaiverClaim.league_id == league_id)

    if owner_ids:
        draft_pick_query = draft_pick_query.filter(models.DraftPick.owner_id.in_(owner_ids))
        keeper_query = keeper_query.filter(models.Keeper.owner_id.in_(owner_ids))

    if replacement_id is not None:
        updates["draft_picks.player_id"] = int(
            draft_pick_query.update({models.DraftPick.player_id: replacement_id}, synchronize_session=False) or 0
        )
        updates["keepers.player_id"] = int(
            keeper_query.update({models.Keeper.player_id: replacement_id}, synchronize_session=False) or 0
        )
        updates["waiver_claims.player_id"] = int(
            waiver_query.update({models.WaiverClaim.player_id: replacement_id}, synchronize_session=False) or 0
        )
    elif allow_reset_draft_picks:
        updates["draft_picks.player_id"] = int(
            draft_pick_query.update({models.DraftPick.player_id: None}, synchronize_session=False) or 0
        )

    # Delete only when the player has no remaining references anywhere.
    remaining_refs = {
        "draft_picks": int(db.query(models.DraftPick).filter(models.DraftPick.player_id == player_id).count()),
        "keepers": int(db.query(models.Keeper).filter(models.Keeper.player_id == player_id).count()),
        "waiver_claims": int(db.query(models.WaiverClaim).filter(models.WaiverClaim.player_id == player_id).count()),
    }
    if sum(remaining_refs.values()) == 0:
        updates["players.deleted"] = int(
            db.query(models.Player)
            .filter(models.Player.id == player_id)
            .delete(synchronize_session=False)
            or 0
        )

    return updates


def run_invalid_player_audit(
    *,
    apply_changes: bool = False,
    allow_reset_draft_picks: bool = False,
    league_id: int | None = None,
    owner_id: int | None = None,
    owner_team_name: str | None = None,
    json_output: str | None = None,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        owner_ids = _resolve_owner_ids(db, owner_id=owner_id, owner_team_name=owner_team_name)
        invalid_players = _query_invalid_players(db)

        report_rows: list[dict[str, Any]] = []
        actions_applied = 0
        rows_touched = 0

        for player in invalid_players:
            if player.id is None:
                continue

            scoped_refs = _reference_counts(
                db,
                player_id=player.id,
                league_id=league_id,
                owner_ids=owner_ids,
            )
            if scoped_refs["total_scoped_references"] == 0:
                continue

            replacement = _find_replacement_player(db, player)
            row: dict[str, Any] = {
                "player_id": player.id,
                "name": player.name,
                "position": player.position,
                "nfl_team": player.nfl_team,
                "gsis_id": player.gsis_id,
                "espn_id": player.espn_id,
                "scoped_references": scoped_refs,
                "replacement_player_id": replacement.id if replacement else None,
                "action": "remap" if replacement else ("reset_draft_picks" if allow_reset_draft_picks else "blocked"),
            }

            if apply_changes and row["action"] != "blocked":
                updates = _apply_scoped_cleanup(
                    db,
                    player_id=player.id,
                    replacement_id=replacement.id if replacement else None,
                    allow_reset_draft_picks=allow_reset_draft_picks,
                    league_id=league_id,
                    owner_ids=owner_ids,
                )
                row["changes"] = updates
                actions_applied += 1
                rows_touched += sum(int(v or 0) for v in updates.values())

            report_rows.append(row)

        if apply_changes:
            db.commit()

        summary = {
            "apply_changes": apply_changes,
            "allow_reset_draft_picks": allow_reset_draft_picks,
            "league_id": league_id,
            "owner_id": owner_id,
            "owner_team_name": owner_team_name,
            "invalid_players_with_scoped_refs": len(report_rows),
            "actions_applied": actions_applied,
            "rows_touched": rows_touched,
            "rows": report_rows,
        }

        if json_output:
            output_path = Path(json_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
