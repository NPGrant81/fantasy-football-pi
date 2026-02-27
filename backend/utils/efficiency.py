"""Utility functions for manager efficiency analytics."""

from typing import List, Dict


def calculate_optimal_score(roster_history: List[Dict], settings: Dict, return_lineup: bool = False) -> float:
    """Return the optimal ("best ball") total points for a given roster week.

    Arguments:
        roster_history: list of player dicts, each containing at least:
            - ``actual_score`` (float)
            - ``position`` (QB, RB, WR, TE, K, DEF, etc.)
            - ``is_ir`` (bool) optional, treated as ineligible if truthy
            - ``is_taxi`` (bool) optional, treated as ineligible if truthy
    settings: league settings dict with ``starting_slots`` mapping similar to
        the ``LeagueSettings.starting_slots`` JSON column. e.g.
        {"QB":1, "RB":2, "WR":2, "TE":1, "K":1, "DEF":1, "FLEX":1}

    The algorithm fills every non-flex slot first, then selects the highest
    remaining eligible player for the FLEX position. Players marked as IR or
    taxi are ignored entirely.
    """

    # 1. filter out ineligible players
    eligible = []
    for p in roster_history:
        if p.get("is_ir") or p.get("is_taxi"):
            continue
        # sometimes actual_score may be missing; treat as zero
        score = p.get("actual_score", 0) or 0
        eligible.append({**p, "actual_score": score})

    opt_lineup = []

    # 2. sort by actual score descending
    sorted_players = sorted(eligible, key=lambda x: x["actual_score"], reverse=True)

    optimal_total = 0.0
    filled = {pos: 0 for pos in settings.get("starting_slots", {})}
    used = set()

    # 3. fill mandatory slots (all non-FLEX slots)
    for player in sorted_players:
        pos = player.get("position")
        if pos is None:
            continue
        if pos not in filled:
            # unknown positions are only eligible for FLEX later
            continue
        if pos == "FLEX":
            continue
        if filled.get(pos, 0) < settings["starting_slots"].get(pos, 0):
            optimal_total += player["actual_score"]
            filled[pos] += 1
            used.add(player.get("player_id") or id(player))
            opt_lineup.append(player)

    # 4. fill flex slot(s) with highest remaining eligible by flex rules
    flex_slots = settings["starting_slots"].get("FLEX", 0)
    if flex_slots:
        for player in sorted_players:
            if player.get("player_id") in used:
                continue
            if player.get("position") in ["RB", "WR", "TE"]:
                optimal_total += player["actual_score"]
                filled[player.get("position")] = filled.get(player.get("position"),0) + 1
                flex_slots -= 1
                used.add(player.get("player_id") or id(player))
                opt_lineup.append(player)
                if flex_slots <= 0:
                    break

    if return_lineup:
        return optimal_total, opt_lineup
    return optimal_total
