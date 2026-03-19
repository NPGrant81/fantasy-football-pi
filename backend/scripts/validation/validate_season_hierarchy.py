"""Validate season hierarchy completeness: all seasons mapped, MFL IDs valid, no gaps."""

from sqlalchemy.orm import Session
from sqlalchemy import func
from ...database import SessionLocal
from ... import models


def run_validate_season_hierarchy(league_id: int) -> dict:
    """
    Validate that the league has complete season mapping.

    Checks:
    1. All expected seasons (SEASON_RANGE) are mapped in league_mfl_seasons
    2. MFL league IDs are populated and unique per season
    3. Season mapping aligns with actual loaded matchups

    Returns dict with validation results.
    """
    SEASON_RANGE = range(2002, 2027)  # 2002-2026 inclusive
    db = SessionLocal()
    summary = {
        "league_id": league_id,
        "expected_seasons": list(SEASON_RANGE),
        "mapped_seasons": [],
        "missing_seasons": [],
        "errors": [],
        "warnings": [],
    }

    try:
        # Get all mapped seasons
        mapped = db.query(models.LeagueMflSeason).filter(
            models.LeagueMflSeason.league_id == league_id
        ).all()

        summary["mapped_seasons"] = sorted([m.season for m in mapped])
        summary["total_mapped"] = len(mapped)

        # Check for missing seasons
        mapped_set = set(summary["mapped_seasons"])
        expected_set = set(SEASON_RANGE)
        summary["missing_seasons"] = sorted(expected_set - mapped_set)

        if summary["missing_seasons"]:
            summary["errors"].append(f"Missing seasons: {summary['missing_seasons']}")

        # Check for invalid MFL IDs
        invalid_mfl_ids = [m for m in mapped if not m.mfl_league_id]
        if invalid_mfl_ids:
            summary["errors"].append(f"Seasons with NULL MFL league ID: {[m.season for m in invalid_mfl_ids]}")

        # Check duplicate MFL IDs (should be unique per season, but same league can use same ID across seasons? Probably not)
        mfl_id_counts = db.query(
            models.LeagueMflSeason.mfl_league_id,
            func.count(models.LeagueMflSeason.id).label("count")
        ).filter(
            models.LeagueMflSeason.league_id == league_id
        ).group_by(
            models.LeagueMflSeason.mfl_league_id
        ).having(
            func.count(models.LeagueMflSeason.id) > 1
        ).all()

        if mfl_id_counts:
            for mfl_id, count in mfl_id_counts:
                summary["warnings"].append(f"MFL league ID {mfl_id} used {count} times (seasons may reuse IDs?)")

        # Validate against actual loaded matchups
        matchup_seasons_result = db.query(func.distinct(models.Matchup.season)).filter(
            models.Matchup.league_id == league_id
        ).all()

        matchup_seasons = set(s[0] for s in matchup_seasons_result if s[0] is not None)
        unmapped_loaded_seasons = matchup_seasons - mapped_set

        if unmapped_loaded_seasons:
            summary["warnings"].append(f"Loaded matchups in seasons not mapped: {sorted(unmapped_loaded_seasons)}")

        # Summary
        summary["total_mapped"] = len(summary["mapped_seasons"])
        summary["total_expected"] = len(SEASON_RANGE)
        summary["status"] = "VALID" if not summary["errors"] else "INVALID"

    finally:
        db.close()

    return summary


def format_season_hierarchy_output(summary: dict) -> str:
    """Format season hierarchy validation for console output."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"Season Hierarchy Validation - League {summary['league_id']}")
    lines.append("=" * 70)

    lines.append(f"\nStatus: {summary['status']}")
    lines.append(f"Mapped seasons: {summary['total_mapped']}/{summary['total_expected']}")

    if summary["mapped_seasons"]:
        lines.append(f"Seasons: {summary['mapped_seasons'][0]} - {summary['mapped_seasons'][-1]}")

    if summary["missing_seasons"]:
        lines.append(f"\n[ERROR] Missing seasons: {summary['missing_seasons']}")

    else:
        lines.append("\n[SUCCESS] All expected seasons are mapped!")

    if summary["errors"]:
        lines.append("\n[ERRORS]")
        for error in summary["errors"]:
            lines.append(f"  [ERROR] {error}")

    if summary["warnings"]:
        lines.append("\n[WARNINGS]")
        for warning in summary["warnings"]:
            lines.append(f"  [WARNING] {warning}")

    lines.append("=" * 70)
    return "\n".join(lines)
