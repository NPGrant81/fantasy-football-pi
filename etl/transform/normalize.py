"""
Normalization utilities for player names, ADP, and position rank.
"""
import re

def normalize_player_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    name = raw_name.lower()
    name = re.sub(r"[.',]", "", name)
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", name)
    return name.strip()

def standardize_adp(raw_adp: str, league_size: int = 12) -> float:
    if not raw_adp:
        return 0.0
    raw_adp = str(raw_adp).strip()
    match = re.match(r"^(\d{1,2})\.(\d{1,2})$", raw_adp)
    if match:
        draft_round = int(match.group(1))
        pick = int(match.group(2))
        overall_pick = ((draft_round - 1) * league_size) + pick
        return float(overall_pick)
    try:
        return float(raw_adp)
    except ValueError:
        return 0.0

def extract_position_rank(raw_rank: str) -> int:
    if not raw_rank:
        return 0
    digits = re.findall(r"\d+", str(raw_rank))
    if digits:
        return int("".join(digits))
    return 0
