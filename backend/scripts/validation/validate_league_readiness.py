"""Validate league readiness for 2026 season: current_season set, 2026 data structure, no conflicts."""

from sqlalchemy.orm import Session
from sqlalchemy import func
from ...database import SessionLocal
from ... import models


def run_validate_league_readiness(league_id: int) -> dict:
    """
    Validate that a league is ready for live 2026 season operations.

    Checks:
    1. current_season is set to 2026
    2. Historical data (2002-2025) is complete and intact
    3. 2026 records exist and are structured for hybrid operations (app-created + MFL-synced)
    4. No data conflicts or orphaned records
    5. All required relationships are in place

    Returns dict with readiness assessment.
    """
    db = SessionLocal()
    summary = {
        "league_id": league_id,
        "checks": {},
        "errors": [],
        "warnings": [],
        "ready": True,
    }

    try:
        # Check 1: current_season set to 2026
        league = db.query(models.League).filter(models.League.id == league_id).first()
        if not league:
            summary["errors"].append(f"League {league_id} not found")
            summary["ready"] = False
            return summary

        current_season = league.current_season
        summary["checks"]["current_season_set"] = current_season == 2026
        if current_season != 2026:
            summary["errors"].append(f"current_season is {current_season}, expected 2026")
            summary["ready"] = False

        # Check 2: Historical data completeness (2002-2025)
        historical_matchup_counts = db.query(
            func.count(models.Matchup.id)
        ).filter(
            models.Matchup.league_id == league_id,
            models.Matchup.season < 2026
        ).scalar()

        summary["checks"]["historical_matchups_loaded"] = (historical_matchup_counts or 0) > 0
        if not summary["checks"]["historical_matchups_loaded"]:
            summary["warnings"].append("No historical matchups (2002-2025) found")

        # Verify all historical seasons are present
        historical_seasons = db.query(
            func.count(func.distinct(models.Matchup.season))
        ).filter(
            models.Matchup.league_id == league_id,
            models.Matchup.season < 2026
        ).scalar()

        expected_historical_seasons = 24  # 2002-2025
        summary["checks"]["all_historical_seasons_present"] = historical_seasons == expected_historical_seasons
        if historical_seasons != expected_historical_seasons:
            summary["warnings"].append(f"Historical seasons: {historical_seasons}/{expected_historical_seasons}")

        # Check 3: 2026 season structure
        season_2026_matchups = db.query(
            func.count(models.Matchup.id)
        ).filter(
            models.Matchup.league_id == league_id,
            models.Matchup.season == 2026
        ).scalar()

        summary["checks"]["2026_matchups_exist"] = (season_2026_matchups or 0) > 0
        summary["2026_matchups_count"] = season_2026_matchups or 0

        season_2026_transactions = db.query(
            func.count(models.TransactionHistory.id)
        ).filter(
            models.TransactionHistory.league_id == league_id,
            models.TransactionHistory.season == 2026
        ).scalar()

        summary["checks"]["2026_transactions_exist"] = (season_2026_transactions or 0) > 0
        summary["2026_transactions_count"] = season_2026_transactions or 0

        # Check 4: Data integrity (no orphaned records)
        orphaned_matchups = db.query(
            func.count(models.Matchup.id)
        ).filter(
            models.Matchup.league_id == league_id,
            (models.Matchup.home_team_id.is_(None) | models.Matchup.away_team_id.is_(None))
        ).scalar()

        summary["checks"]["no_orphaned_matchups"] = (orphaned_matchups or 0) == 0
        if orphaned_matchups and orphaned_matchups > 0:
            summary["errors"].append(f"Found {orphaned_matchups} matchups with orphaned team references")
            summary["ready"] = False

        # Check 5: Team references exist
        teams_with_matchups = db.query(
            func.count(func.distinct(models.Matchup.home_team_id))
        ).filter(
            models.Matchup.league_id == league_id
        ).scalar()

        summary["checks"]["teams_registered"] = (teams_with_matchups or 0) > 0
        summary["teams_count"] = teams_with_matchups or 0

        # Summary
        summary["league_name"] = league.name
        summary["total_users"] = len(league.users) if league.users else 0

    finally:
        db.close()

    # Determine overall readiness
    if summary["errors"]:
        summary["ready"] = False

    return summary


def format_league_readiness_output(summary: dict) -> str:
    """Format league readiness validation for console output."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"League Readiness Assessment - League {summary['league_id']} ({summary.get('league_name', 'N/A')})")
    lines.append("=" * 70)

    status_icon = "[READY]" if summary["ready"] else "[NOT READY]"
    lines.append(f"\nStatus: {status_icon}")

    lines.append(f"\n[READINESS CHECKS]")
    for check_name, passed in summary["checks"].items():
        icon = "[PASS]" if passed else "[FAIL]"
        check_display = check_name.replace("_", " ").title()
        lines.append(f"  {icon} {check_display}")

    lines.append(f"\n[DATA SUMMARY]")
    lines.append(f"  Users registered: {summary.get('total_users', 0)}")
    lines.append(f"  Teams in system: {summary.get('teams_count', 0)}")
    lines.append(f"  Historical matchups (2002-2025): {summary['checks'].get('historical_matchups_loaded', False) and '[YES]' or '[NO]'}")
    if summary.get("2026_matchups_count", 0) > 0:
        lines.append(f"  2026 matchups: {summary['2026_matchups_count']}")
    if summary.get("2026_transactions_count", 0) > 0:
        lines.append(f"  2026 transactions: {summary['2026_transactions_count']}")

    if summary["errors"]:
        lines.append("\n[ERRORS]")
        for error in summary["errors"]:
            lines.append(f"  [ERROR] {error}")

    if summary["warnings"]:
        lines.append("\n[WARNINGS]")
        for warning in summary["warnings"]:
            lines.append(f"  [WARNING] {warning}")

    if summary["ready"]:
        lines.append("\n[SUCCESS] League is ready for 2026 season operations!")
    else:
        lines.append("\n[WARNING] League requires attention before live 2026 operations.")

    lines.append("=" * 70)
    return "\n".join(lines)
