"""Helper functions for generating and evaluating playoff brackets.

This module implements the core tournament logic, including seeding rules,
re-seeding behavior, consolation bracket generation, and tiebreaker evaluation.
It is intentionally kept separate from router code so that unit tests can import
individual pieces.
"""
from typing import Any, Dict, List, Optional


def tiebreaker_winner(team_a: Dict[str, Any], team_b: Dict[str, Any],
                      priority: List[str]) -> Dict[str, Any]:
    """Return the winning team according to tiebreaker priority list.

    Each team dict should contain fields referenced by the priority sequence,
    e.g. "points_for", "head_to_head", "division_wins", "wins", etc.  If
    all configured criteria are equal the higher seed (lower numeric value) is
    declared the winner by default.
    """
    for key in priority:
        token = (key or "").strip().lower()
        if token == "overall_record":
            # Backward compatible mapping to existing standings payloads.
            a_val = team_a.get("wins", team_a.get("overall_wins"))
            b_val = team_b.get("wins", team_b.get("overall_wins"))
        elif token == "points_for":
            a_val = team_a.get("points_for", team_a.get("pf"))
            b_val = team_b.get("points_for", team_b.get("pf"))
        elif token == "points_against":
            # Lower points against is better, so invert comparison values.
            a_raw = team_a.get("points_against", team_a.get("pa"))
            b_raw = team_b.get("points_against", team_b.get("pa"))
            a_val = -a_raw if a_raw is not None else None
            b_val = -b_raw if b_raw is not None else None
        elif token == "random_draw":
            # Placeholder deterministic fallback: hash team id.
            a_val = str(team_a.get("id", ""))
            b_val = str(team_b.get("id", ""))
        else:
            a_val = team_a.get(token)
            b_val = team_b.get(token)

        if a_val is None or b_val is None:
            continue
        if a_val > b_val:
            return team_a
        elif b_val > a_val:
            return team_b

    # fallback to seed advantage; handle missing seeds safely
    a_seed = team_a.get("seed")
    b_seed = team_b.get("seed")
    if a_seed is None and b_seed is None:
        # if no seed info available, arbitrarily choose team_a for consistency
        return team_a
    if a_seed is None:
        return team_b
    if b_seed is None:
        return team_a
    return team_a if a_seed < b_seed else team_b


def generate_round2_matches(round1_winners: List[Dict[str, Any]],
                            bye_teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute second round matchups given winners and bye teams.

    The default behaviour pairs highest seed vs lowest remaining seed in order.
    Assumes each item has at least ``id`` and ``seed`` fields.
    """
    # combine and drop any None placeholders which might arise from
    # incomplete DB records or bye-handling quirks.
    remaining = [t for t in (bye_teams + round1_winners) if t]
    # ensure seeds default to 0 when explicitly None (get default only when key missing)
    remaining.sort(key=lambda t: t.get("seed") if t.get("seed") is not None else 0)
    matches: List[Dict[str, Any]] = []
    total = len(remaining)
    for i in range(total // 2):
        matches.append({
            "match_id": f"r2_m{i + 1}",
            "home_team": remaining[i],
            "away_team": remaining[total - 1 - i],
        })
    return matches


def generate_consolation_bracket(all_teams: List[Dict[str, Any]],
                                 playoff_teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build an initial consolation bracket ("toilet bowl").

    The outside-in pairing strategy is used: highest seed in the pool versus
    lowest seed, moving inward.  The returned list consists of match dicts
    similar to the championship bracket.

    The pool contains every team *not* qualified for the main playoff; if the
    league has an odd number of non-qualified teams the lowest seed will be
    dropped (the commissioner can choose to adjust qualifiers instead).
    """
    playoff_ids = {t["id"] for t in playoff_teams}
    pool = [t for t in all_teams if t["id"] not in playoff_ids]
    pool.sort(key=lambda t: t.get("seed", 0))
    matches: List[Dict[str, Any]] = []

    # only pair an even number of teams
    pair_count = len(pool) // 2
    for i in range(pair_count):
        matches.append({
            "match_id": f"con_r1_m{i + 1}",
            "round": 1,
            "team_1": pool[i],
            "team_2": pool[-1 - i],
            "label": "Consolation Round 1",
            "winner_to": f"con_r2_m{(i // 2) + 1}" if pair_count > 1 else None,
        })
    return matches


import math


def build_initial_bracket(teams: List[Dict[str, Any]],
                          qualifiers: int,
                          reseed: bool = False) -> Dict[str, Any]:
    """Create the first-round structure for the championship bracket.

    ``teams`` should already be sorted by seed and (optionally) trimmed to the
    number of qualifiers.  The function will generate one entry for every
    first-round "match"; top seeds may receive byes if the qualifier count is
    not a power of two.  Each match dictionary includes a ``winner_to`` key
    pointing at the identifier of the next-round match, which simplifies the
    rendering logic on the frontend.

    The returned structure is intentionally minimal so that later rounds can be
    built by the same or companion helpers (see :func:`generate_round2_matches`).
    """
    if qualifiers < 2:
        raise ValueError("qualifiers must be at least 2")

    qteams = teams[:qualifiers]
    total = len(qteams)

    # compute next power of two so we know how many byes are needed
    next_pow2 = 1 << ((total - 1).bit_length())
    byes = next_pow2 - total

    bracket: List[Dict[str, Any]] = []

    # first create explicit bye slots for the top seeds
    for i in range(byes):
        bracket.append({
            "match_id": f"m{len(bracket) + 1}",
            "round": 1,
            "is_bye": True,
            "team_1": qteams[i],
            "team_2": None,
            # ``winner_to`` will be filled below
            "winner_to": None,
        })

    # pair the remaining teams outside-in (highest vs lowest)
    left = byes
    right = total - 1
    while left < right:
        bracket.append({
            "match_id": f"m{len(bracket) + 1}",
            "round": 1,
            "is_bye": False,
            "team_1": qteams[left],
            "team_2": qteams[right],
            "winner_to": None,
        })
        left += 1
        right -= 1

    # assign winner_to targets: every two first-round matches feed the same
    # second-round slot.  This is still valid even when there are byes, since
    # byes count as "matches" that immediately advance.
    for idx, match in enumerate(bracket):
        target = idx // 2 + 1
        match["winner_to"] = f"r2_m{target}"

    return {"championship": bracket}


# --- additional helpers for live bracket management -----------------------

def extract_round_winners(matches: List[Dict[str, Any]],
                          priority: List[str]) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
    """Given a list of completed matches, separate winners and bye teams.

    "matches" is expected to be a list of dicts containing at least:
    ``team_1``, ``team_2``, ``team_1_score``, ``team_2_score``, ``is_bye``.

    Returns a tuple ``(winners, byes)`` where each element is a list of team
    dicts.  Ties are resolved using :func:`tiebreaker_winner` and the supplied
    priority order.
    """
    winners: List[Dict[str, Any]] = []
    byes: List[Dict[str, Any]] = []

    for m in matches:
        if m.get("is_bye"):
            # bye slots automatically advance
            if m.get("team_1"):
                byes.append(m["team_1"])
        else:
            t1 = m.get("team_1")
            t2 = m.get("team_2")
            # guard against malformed entries
            if not t1 and not t2:
                # nothing to do for this match
                continue
            if not t1:
                winners.append(t2)
                continue
            if not t2:
                winners.append(t1)
                continue

            s1 = m.get("team_1_score", 0) or 0
            s2 = m.get("team_2_score", 0) or 0
            if s1 > s2:
                winners.append(t1)
            elif s2 > s1:
                winners.append(t2)
            else:
                # resolve tie
                winners.append(tiebreaker_winner(t1, t2, priority))
    return winners, byes


def reseed_bracket(current_matches: List[Dict[str, Any]],
                    priority: List[str]) -> List[Dict[str, Any]]:
    """Generate next-round matches from the results of the current round.

    This helper uses :func:`extract_round_winners` to determine which teams
    advance and :func:`generate_round2_matches` to pair them according to seed
    order.  It is agnostic to the round number; callers may choose to label
    the resulting matches however they like.
    """
    winners, byes = extract_round_winners(current_matches, priority)
    return generate_round2_matches(winners, byes)
