from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import models


_MIN_POSITION_TARGETS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
}


@dataclass
class TeamOutlook:
    owner_id: int
    owner_name: str
    team_name: str
    roster_size: int
    projected_points: float
    projected_points_vs_league_avg: float
    risk_score: float
    positional_balance_score: float
    strength_score: float
    positional_gaps: list[str]


def _empty_counts() -> dict[str, int]:
    return {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "DEF": 0}


def build_post_draft_outlook(
    db: Session,
    *,
    league_id: int,
    season: int,
    owner_id: int | None = None,
) -> tuple[list[TeamOutlook], TeamOutlook | None]:
    league = db.query(models.League.id).filter(models.League.id == league_id).first()
    if not league:
        raise ValueError("League not found")

    owners = (
        db.query(models.User)
        .filter(models.User.league_id == league_id, ~models.User.username.like("hist_%"))
        .all()
    )
    if not owners:
        raise ValueError("No owners found in this league")

    owner_by_id = {int(owner.id): owner for owner in owners}

    if owner_id is not None and owner_id not in owner_by_id:
        raise ValueError("Owner not found in this league")

    player_rows = (
        db.query(models.DraftPick.owner_id, models.Player.position, models.Player.projected_points)
        .join(models.Player, models.Player.id == models.DraftPick.player_id)
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.owner_id.in_(list(owner_by_id.keys())),
            models.DraftPick.player_id.isnot(None),
        )
        .all()
    )

    projected_by_owner = {owner_key: 0.0 for owner_key in owner_by_id}
    roster_size_by_owner = {owner_key: 0 for owner_key in owner_by_id}
    missing_projection_by_owner = {owner_key: 0 for owner_key in owner_by_id}
    position_counts_by_owner = {owner_key: _empty_counts() for owner_key in owner_by_id}

    for row in player_rows:
        owner_key = int(row.owner_id)
        position = (row.position or "").strip().upper()
        projection = float(row.projected_points or 0.0)

        roster_size_by_owner[owner_key] += 1
        projected_by_owner[owner_key] += projection
        if projection <= 0:
            missing_projection_by_owner[owner_key] += 1

        if position in position_counts_by_owner[owner_key]:
            position_counts_by_owner[owner_key][position] += 1

    league_average = sum(projected_by_owner.values()) / max(1, len(projected_by_owner))

    rows: list[TeamOutlook] = []
    for owner_key, owner in owner_by_id.items():
        roster_size = roster_size_by_owner[owner_key]
        projected_points = round(projected_by_owner[owner_key], 2)

        missing_projection = missing_projection_by_owner[owner_key]
        risk_score = round((missing_projection / max(1, roster_size)), 3)

        counts = position_counts_by_owner[owner_key]
        met_slots = 0
        positional_gaps: list[str] = []
        for position, minimum in _MIN_POSITION_TARGETS.items():
            if counts[position] >= minimum:
                met_slots += 1
            else:
                positional_gaps.append(position)

        positional_balance_score = round(met_slots / len(_MIN_POSITION_TARGETS), 3)
        strength_score = round(projected_points * (1.0 - (risk_score * 0.35)) + (positional_balance_score * 25), 2)

        rows.append(
            TeamOutlook(
                owner_id=owner_key,
                owner_name=owner.username,
                team_name=owner.team_name or owner.username,
                roster_size=roster_size,
                projected_points=projected_points,
                projected_points_vs_league_avg=round(projected_points - league_average, 2),
                risk_score=risk_score,
                positional_balance_score=positional_balance_score,
                strength_score=strength_score,
                positional_gaps=positional_gaps,
            )
        )

    rows.sort(key=lambda item: item.strength_score, reverse=True)

    focus: TeamOutlook | None = None
    for idx, row in enumerate(rows, start=1):
        if row.owner_id == owner_id:
            focus = TeamOutlook(
                owner_id=row.owner_id,
                owner_name=row.owner_name,
                team_name=row.team_name,
                roster_size=row.roster_size,
                projected_points=row.projected_points,
                projected_points_vs_league_avg=row.projected_points_vs_league_avg,
                risk_score=row.risk_score,
                positional_balance_score=row.positional_balance_score,
                strength_score=row.strength_score,
                positional_gaps=row.positional_gaps,
            )
            break

    return rows, focus
