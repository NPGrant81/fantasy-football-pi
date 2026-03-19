"""Validate MFL import integrity: matchup/transaction counts, FK constraints, duplicates, and playoff flags."""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from ...database import SessionLocal
from ... import models


def run_validate_mfl_import(league_id: int, json_output: str | None = None) -> dict:
    """
    Run comprehensive validation on MFL-imported matchups and transactions.

    Checks:
    1. Matchup counts per season (basic integrity)
    2. FK integrity (no null team_ids or season)
    3. Duplicate detection (on league_id, season, week, home_team_id, away_team_id)
    4. Playoff flag consistency (playoff weeks should have fewer games per week)
    5. Transaction counts per season

    Returns dict with summary metrics.
    """
    db = SessionLocal()
    summary = {
        "league_id": league_id,
        "matchup_validation": {},
        "transaction_validation": {},
        "overall_integrity": {},
        "errors": [],
        "warnings": [],
    }

    try:
        # ====== MATCHUP VALIDATION ======
        matchup_counts = db.query(
            models.Matchup.season,
            func.count(models.Matchup.id).label("total_matchups"),
            func.sum(case((models.Matchup.is_playoff == True, 1), else_=0)).label("playoff_matchups"),
            func.sum(case((models.Matchup.is_playoff == False, 1), else_=0)).label("regular_season_matchups"),
        ).filter(
            models.Matchup.league_id == league_id
        ).group_by(
            models.Matchup.season
        ).order_by(
            models.Matchup.season
        ).all()

        total_matchups = 0
        for season, total, playoff, regular in matchup_counts:
            total_matchups += total
            summary["matchup_validation"][season] = {
                "total": total,
                "playoff": playoff or 0,
                "regular_season": regular or 0,
            }

        summary["overall_integrity"]["total_matchups"] = total_matchups
        summary["overall_integrity"]["seasons_loaded"] = len(summary["matchup_validation"])

        # ====== FK INTEGRITY CHECK ======
        fk_nulls = db.query(
            func.count(models.Matchup.id).label("null_count")
        ).filter(
            and_(
                models.Matchup.league_id == league_id,
                (models.Matchup.home_team_id.is_(None) | models.Matchup.away_team_id.is_(None) | models.Matchup.season.is_(None))
            )
        ).scalar()

        summary["overall_integrity"]["fk_nulls"] = fk_nulls or 0
        if fk_nulls and fk_nulls > 0:
            summary["errors"].append(f"Found {fk_nulls} matchups with NULL FK values (home_team_id, away_team_id, or season)")

        # ====== DUPLICATE CHECK ======
        duplicates = db.query(
            models.Matchup.league_id,
            models.Matchup.season,
            models.Matchup.week,
            models.Matchup.home_team_id,
            models.Matchup.away_team_id,
            func.count(models.Matchup.id).label("dup_count")
        ).filter(
            models.Matchup.league_id == league_id
        ).group_by(
            models.Matchup.league_id,
            models.Matchup.season,
            models.Matchup.week,
            models.Matchup.home_team_id,
            models.Matchup.away_team_id
        ).having(
            func.count(models.Matchup.id) > 1
        ).all()

        summary["overall_integrity"]["duplicates_found"] = len(duplicates)
        if duplicates:
            summary["errors"].append(f"Found {len(duplicates)} duplicate matchup keys")
            for dup in duplicates:
                summary["errors"].append(f"  - Season {dup.season}, Week {dup.week}: {dup.home_team_id} vs {dup.away_team_id} ({dup.dup_count} rows)")

        # ====== PLAYOFF FLAG VALIDITY ======
        # Playoff weeks should have fewer games than regular season
        playoff_validation = db.query(
            models.Matchup.season,
            models.Matchup.week,
            func.count(models.Matchup.id).label("games_in_week"),
            func.sum(case((models.Matchup.is_playoff == True, 1), else_=0)).label("playoff_flagged"),
            func.sum(case((models.Matchup.is_playoff == False, 1), else_=0)).label("regular_flagged"),
        ).filter(
            models.Matchup.league_id == league_id
        ).group_by(
            models.Matchup.season,
            models.Matchup.week
        ).all()

        inconsistent_playoff_flags = 0
        for season, week, games_in_week, playoff_flagged, regular_flagged in playoff_validation:
            # If a week has playoff matchups, all should be flagged as playoff
            if (playoff_flagged or 0) > 0 and (regular_flagged or 0) > 0:
                inconsistent_playoff_flags += 1
                summary["warnings"].append(f"Season {season}, Week {week}: mixed playoff flags ({playoff_flagged or 0} playoff, {regular_flagged or 0} regular)")

        summary["overall_integrity"]["inconsistent_playoff_flags"] = inconsistent_playoff_flags

        # ====== TRANSACTION VALIDATION (if any loaded) ======
        transaction_count = db.query(
            func.count(models.TransactionHistory.id)
        ).filter(
            models.TransactionHistory.league_id == league_id
        ).scalar()

        summary["overall_integrity"]["total_transactions"] = transaction_count or 0

        transaction_counts = db.query(
            models.TransactionHistory.season,
            func.count(models.TransactionHistory.id).label("transaction_count")
        ).filter(
            models.TransactionHistory.league_id == league_id
        ).group_by(
            models.TransactionHistory.season
        ).order_by(
            models.TransactionHistory.season
        ).all()

        for season, count in transaction_counts:
            summary["transaction_validation"][season] = count

    finally:
        db.close()

    return summary


def format_validation_output(summary: dict) -> str:
    """Format validation summary for console output."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"MFL Import Validation Report - League {summary['league_id']}")
    lines.append("=" * 70)

    # Overall integrity
    lines.append("\n[OVERALL INTEGRITY]")
    lines.append(f"  Total matchups: {summary['overall_integrity'].get('total_matchups', 0)}")
    lines.append(f"  Seasons loaded: {summary['overall_integrity'].get('seasons_loaded', 0)}")
    lines.append(f"  Total transactions: {summary['overall_integrity'].get('total_transactions', 0)}")
    lines.append(f"  FK nulls: {summary['overall_integrity'].get('fk_nulls', 0)}")
    lines.append(f"  Duplicate keys: {summary['overall_integrity'].get('duplicates_found', 0)}")
    lines.append(f"  Inconsistent playoff flags: {summary['overall_integrity'].get('inconsistent_playoff_flags', 0)}")

    # Matchup summary by season
    if summary["matchup_validation"]:
        lines.append("\n[MATCHUPS BY SEASON]")
        for season in sorted(summary["matchup_validation"].keys()):
            counts = summary["matchup_validation"][season]
            lines.append(
                f"  {season}: {counts['total']} total "
                f"({counts['regular_season']} regular, {counts['playoff']} playoff)"
            )

    # Transaction summary by season
    if summary["transaction_validation"]:
        lines.append("\n[TRANSACTIONS BY SEASON]")
        for season in sorted(summary["transaction_validation"].keys()):
            lines.append(f"  {season}: {summary['transaction_validation'][season]} transactions")

    # Errors
    if summary["errors"]:
        lines.append("\n[ERRORS]")
        for error in summary["errors"]:
            lines.append(f"  [ERROR] {error}")

    # Warnings
    if summary["warnings"]:
        lines.append("\n[WARNINGS]")
        for warning in summary["warnings"]:
            lines.append(f"  [WARNING] {warning}")

    if not summary["errors"] and not summary["warnings"]:
        lines.append("\n[SUCCESS] All validation checks passed!")

    lines.append("=" * 70)
    return "\n".join(lines)
