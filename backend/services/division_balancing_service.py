from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import random
from statistics import mean
from typing import Any


BAD_WORDS = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
}


@dataclass
class TeamStrengthInput:
    team_id: int
    avg_points_for_last_season: float
    win_pct_last_season: float
    projected_roster_score: float | None = None


@dataclass
class TeamStrengthOutput:
    team_id: int
    strength_raw: float
    strength_final: float


def sanitize_name(value: str) -> str:
    return (value or "").strip()


def validate_division_name(name: str, existing_names: set[str]) -> list[str]:
    errors: list[str] = []
    clean = sanitize_name(name)

    if not clean:
        errors.append("name is required")
        return errors

    if len(clean) > 60:
        errors.append("name must be 60 characters or fewer")

    lowered = clean.casefold()
    if lowered in existing_names:
        errors.append("name must be unique within the season")

    for token in BAD_WORDS:
        if token in lowered:
            errors.append("name contains blocked language")
            break

    return errors


def validate_division_math(team_count: int, division_count: int, min_teams_per_division: int = 3) -> list[str]:
    errors: list[str] = []

    if team_count < 6:
        errors.append("divisions require at least 6 teams in the league")
        return errors

    if division_count <= 0:
        errors.append("division_count must be greater than 0")
        return errors

    if team_count % division_count != 0:
        errors.append("division_count must divide team_count evenly")
        return errors

    teams_per_division = team_count // division_count
    if teams_per_division < min_teams_per_division:
        errors.append("each division must contain at least 3 teams")

    return errors


def compute_team_strength(row: TeamStrengthInput) -> TeamStrengthOutput:
    # Equivalent to (win_pct * 0.4 * 100), expressed as *40 for simpler math.
    strength_raw = (row.avg_points_for_last_season * 0.6) + (row.win_pct_last_season * 40.0)

    if row.projected_roster_score is None:
        strength_final = strength_raw
    else:
        strength_final = (strength_raw * 0.8) + (row.projected_roster_score * 0.2)

    return TeamStrengthOutput(
        team_id=row.team_id,
        strength_raw=round(strength_raw, 4),
        strength_final=round(strength_final, 4),
    )


def compute_division_strengths(assignments: dict[int, list[TeamStrengthOutput]]) -> dict[int, float]:
    strengths: dict[int, float] = {}
    for division_idx, teams in assignments.items():
        if not teams:
            strengths[division_idx] = 0.0
            continue
        strengths[division_idx] = round(mean(t.strength_final for t in teams), 4)
    return strengths


def compute_imbalance_pct(division_strengths: dict[int, float]) -> float:
    if not division_strengths:
        return 0.0

    high = max(division_strengths.values())
    low = min(division_strengths.values())
    if high <= 0:
        return 0.0

    return round(((high - low) / high) * 100.0, 4)


def compute_override_penalty(previous_imbalance_pct: float, new_imbalance_pct: float) -> int:
    if new_imbalance_pct > previous_imbalance_pct:
        return 5
    if new_imbalance_pct == previous_imbalance_pct:
        return 2
    return 0


def compute_confidence_score(imbalance_pct: float, override_penalty: int = 0) -> float:
    value = 100.0 - (imbalance_pct * 2.0) - float(override_penalty)
    return round(max(0.0, min(100.0, value)), 2)


def is_imbalance_warning(imbalance_pct: float) -> bool:
    return imbalance_pct > 10.0


def deterministic_random_assignment(team_ids: list[int], division_count: int, seed: str) -> dict[int, list[int]]:
    shuffled = sorted(team_ids)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    teams_per_division = len(team_ids) // division_count
    assignments: dict[int, list[int]] = {idx: [] for idx in range(division_count)}

    cursor = 0
    for division_idx in range(division_count):
        next_cursor = cursor + teams_per_division
        assignments[division_idx] = shuffled[cursor:next_cursor]
        cursor = next_cursor

    return assignments


def deterministic_balanced_assignment(
    strengths: list[TeamStrengthOutput],
    division_count: int,
    seed: str,
) -> dict[int, list[TeamStrengthOutput]]:
    # Stable tie-breaker: if strengths tie, randomize deterministically by seeded hash.
    def team_sort_key(team: TeamStrengthOutput) -> tuple[float, str]:
        digest = sha256(f"{seed}:{team.team_id}".encode("utf-8")).hexdigest()
        return (-team.strength_final, digest)

    ordered = sorted(strengths, key=team_sort_key)
    assignments: dict[int, list[TeamStrengthOutput]] = {idx: [] for idx in range(division_count)}

    direction = 1
    idx = 0
    for team in ordered:
        assignments[idx].append(team)
        if direction == 1:
            if idx == division_count - 1:
                direction = -1
            else:
                idx += 1
        else:
            if idx == 0:
                direction = 1
            else:
                idx -= 1

    return assignments


def format_balancing_response(
    *,
    assignment_method: str,
    assignments: dict[int, list[TeamStrengthOutput]],
    previous_assignments: dict[int, list[int]] | None,
    seed: str,
) -> dict[str, Any]:
    division_strengths = compute_division_strengths(assignments)
    imbalance_pct = compute_imbalance_pct(division_strengths)
    confidence_score = compute_confidence_score(imbalance_pct)

    output_assignments: list[dict[str, Any]] = []
    for division_idx, teams in assignments.items():
        output_assignments.append(
            {
                "division_index": division_idx,
                "team_ids": [t.team_id for t in teams],
                "strength_avg": division_strengths.get(division_idx, 0.0),
            }
        )

    return {
        "assignment_method": assignment_method,
        "seed": seed,
        "confidence_score": confidence_score,
        "imbalance_pct": imbalance_pct,
        "imbalance_warning": is_imbalance_warning(imbalance_pct),
        "assignments": output_assignments,
        "previous_assignments": previous_assignments or {},
        "team_strengths": [
            {
                "team_id": t.team_id,
                "strength_raw": t.strength_raw,
                "strength_final": t.strength_final,
            }
            for teams in assignments.values()
            for t in teams
        ],
    }
