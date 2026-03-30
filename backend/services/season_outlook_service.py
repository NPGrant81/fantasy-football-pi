from __future__ import annotations

from dataclasses import dataclass
import math

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
    confidence_score: float
    confidence_label: str
    positional_gaps: list[str]


@dataclass
class OutlookDiagnostics:
    degraded_mode: bool
    degradation_reasons: list[str]
    total_draft_rows: int
    included_rows: int
    skipped_rows: int
    duplicate_rows_skipped: int
    invalid_projection_rows: int
    unknown_position_rows: int
    projection_coverage: float


def _empty_counts() -> dict[str, int]:
    return {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "DEF": 0}


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_projection(value) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return numeric if math.isfinite(numeric) else 0.0


def _normalized_position(value: str | None) -> str:
    token = (value or "").strip().upper()
    if token in {"DST", "D/ST"}:
        return "DEF"
    return token


def _is_excluded_status(value: str | None) -> bool:
    token = (value or "").strip().upper()
    if not token:
        return False
    return token in {"DROPPED", "DROP", "CUT", "WAIVER_DROP", "RELEASED"}


def _confidence_label(score: float) -> str:
    if score >= 75.0:
        return "high"
    if score >= 55.0:
        return "moderate"
    return "low"


def build_post_draft_outlook(
    db: Session,
    *,
    league_id: int,
    season: int,
    owner_id: int | None = None,
) -> tuple[list[TeamOutlook], TeamOutlook | None, OutlookDiagnostics]:
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

    draft_rows = (
        db.query(
            models.DraftPick.id,
            models.DraftPick.owner_id,
            models.DraftPick.player_id,
            models.DraftPick.current_status,
            models.Player.position,
            models.Player.projected_points,
        )
        .outerjoin(models.Player, models.Player.id == models.DraftPick.player_id)
        .filter(
            models.DraftPick.league_id == league_id,
            models.DraftPick.year == season,
            models.DraftPick.owner_id.in_(list(owner_by_id.keys())),
        )
        .all()
    )

    projected_by_owner = {owner_key: 0.0 for owner_key in owner_by_id}
    roster_size_by_owner = {owner_key: 0 for owner_key in owner_by_id}
    missing_projection_by_owner = {owner_key: 0 for owner_key in owner_by_id}
    position_counts_by_owner = {owner_key: _empty_counts() for owner_key in owner_by_id}
    seen_owner_player: set[tuple[int, int]] = set()

    included_rows = 0
    skipped_rows = 0
    duplicate_rows_skipped = 0
    invalid_projection_rows = 0
    unknown_position_rows = 0

    for row in draft_rows:
        owner_key = _safe_int(row.owner_id)
        if owner_key is None or owner_key not in owner_by_id:
            skipped_rows += 1
            continue

        if _is_excluded_status(row.current_status):
            skipped_rows += 1
            continue

        player_id = _safe_int(row.player_id)
        if player_id is not None:
            dedupe_key = (owner_key, player_id)
            if dedupe_key in seen_owner_player:
                duplicate_rows_skipped += 1
                skipped_rows += 1
                continue
            seen_owner_player.add(dedupe_key)

        projection = _safe_projection(row.projected_points)
        if projection <= 0:
            missing_projection_by_owner[owner_key] += 1
            if row.projected_points not in (None, 0, 0.0):
                invalid_projection_rows += 1

        position = _normalized_position(row.position)
        if position and position not in position_counts_by_owner[owner_key]:
            unknown_position_rows += 1

        roster_size_by_owner[owner_key] += 1
        projected_by_owner[owner_key] += projection
        included_rows += 1
        if position in position_counts_by_owner[owner_key]:
            position_counts_by_owner[owner_key][position] += 1

    total_roster_slots = sum(roster_size_by_owner.values())
    total_missing = sum(missing_projection_by_owner.values())
    projection_coverage = 1.0 - (total_missing / max(1, total_roster_slots))

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

        confidence_raw = (
            ((1.0 - risk_score) * 0.55)
            + (positional_balance_score * 0.25)
            + (projection_coverage * 0.20)
        ) * 100.0
        confidence_score = round(max(5.0, min(95.0, confidence_raw)), 1)
        confidence_label = _confidence_label(confidence_score)

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
                confidence_score=confidence_score,
                confidence_label=confidence_label,
                positional_gaps=positional_gaps,
            )
        )

    rows.sort(key=lambda item: (-item.strength_score, -item.projected_points, item.owner_id))

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
                confidence_score=row.confidence_score,
                confidence_label=row.confidence_label,
                positional_gaps=row.positional_gaps,
            )
            break

    degradation_reasons: list[str] = []
    if included_rows == 0:
        degradation_reasons.append("no_roster_rows")
    if projection_coverage < 0.60:
        degradation_reasons.append("low_projection_coverage")
    if unknown_position_rows > 0:
        degradation_reasons.append("unknown_positions_present")
    if duplicate_rows_skipped > 0:
        degradation_reasons.append("duplicate_rows_suppressed")

    diagnostics = OutlookDiagnostics(
        degraded_mode=len(degradation_reasons) > 0,
        degradation_reasons=degradation_reasons,
        total_draft_rows=len(draft_rows),
        included_rows=included_rows,
        skipped_rows=skipped_rows,
        duplicate_rows_skipped=duplicate_rows_skipped,
        invalid_projection_rows=invalid_projection_rows,
        unknown_position_rows=unknown_position_rows,
        projection_coverage=round(max(0.0, min(1.0, projection_coverage)), 3),
    )

    return rows, focus, diagnostics
