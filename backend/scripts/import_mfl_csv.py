"""Import MFL CSV exports into app tables with dry-run support.

Issue #258 baseline:
- Validate CSV structure.
- Map players and draft results into existing models.
- Provide dry-run summary and safe apply mode.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend import models
from backend.database import SessionLocal
from backend.services.player_service import canonical_player_identity


REQUIRED_COLUMNS: dict[str, list[str]] = {
    "franchises": ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
    "players": ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
    "draftResults": ["season", "league_id", "franchise_id", "player_mfl_id"],
    "schedule": ["season", "league_id", "week", "home_franchise_id", "away_franchise_id"],
    "transactions": ["season", "league_id", "franchise_id", "transaction_type", "player_mfl_id"],
}

DB_DATASET_KEYS: dict[str, set[str]] = {
    "franchises": {"html_franchises_normalized"},
    "players": {"html_players_normalized"},
    "draftResults": {"html_draft_results_normalized"},
    "schedule": {"html_schedule_normalized"},
    "transactions": {"html_transactions_normalized"},
}


@dataclass
class ImportSummary:
    input_root: str
    target_league_id: int
    dry_run: bool
    seasons: list[int]
    files_checked: int = 0
    files_missing: int = 0
    rows_validated: int = 0
    rows_invalid: int = 0
    players_inserted: int = 0
    players_matched: int = 0
    draft_picks_inserted: int = 0
    draft_picks_skipped: int = 0
    matchups_inserted: int = 0
    matchups_skipped: int = 0
    bye_matchups_skipped: int = 0
    transactions_inserted: int = 0
    transactions_skipped: int = 0
    skipped_missing_owner_map: int = 0
    skipped_missing_player_map: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "target_league_id": self.target_league_id,
            "dry_run": self.dry_run,
            "seasons": self.seasons,
            "files_checked": self.files_checked,
            "files_missing": self.files_missing,
            "rows_validated": self.rows_validated,
            "rows_invalid": self.rows_invalid,
            "players_inserted": self.players_inserted,
            "players_matched": self.players_matched,
            "draft_picks_inserted": self.draft_picks_inserted,
            "draft_picks_skipped": self.draft_picks_skipped,
            "matchups_inserted": self.matchups_inserted,
            "matchups_skipped": self.matchups_skipped,
            "bye_matchups_skipped": self.bye_matchups_skipped,
            "transactions_inserted": self.transactions_inserted,
            "transactions_skipped": self.transactions_skipped,
            "skipped_missing_owner_map": self.skipped_missing_owner_map,
            "skipped_missing_player_map": self.skipped_missing_player_map,
            "warnings": self.warnings,
        }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _load_report_rows(
    *,
    input_root: Path,
    report_type: str,
    seasons: list[int],
    summary: ImportSummary,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    required = REQUIRED_COLUMNS.get(report_type, [])

    for season in seasons:
        path = input_root / report_type / f"{season}.csv"
        if not path.exists():
            summary.files_missing += 1
            summary.warnings.append(f"missing file: {path}")
            continue

        summary.files_checked += 1
        file_rows = _read_csv(path)
        for row in file_rows:
            summary.rows_validated += 1
            missing = [col for col in required if (row.get(col) or "").strip() == ""]
            if missing:
                summary.rows_invalid += 1
                summary.warnings.append(
                    f"invalid {report_type} row season={season}: missing columns {missing}"
                )
                continue
            rows.append(row)

    return rows


def _load_report_rows_from_db(
    *,
    db: Session,
    report_type: str,
    seasons: list[int],
    summary: ImportSummary,
    source_league_id: str | None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    required = REQUIRED_COLUMNS.get(report_type, [])
    dataset_keys = DB_DATASET_KEYS.get(report_type, set())
    season_set = set(seasons)
    matched_seasons: set[int] = set()

    facts_query = db.query(models.MflHtmlRecordFact).filter(models.MflHtmlRecordFact.season.in_(seasons))
    if dataset_keys:
        facts_query = facts_query.filter(models.MflHtmlRecordFact.dataset_key.in_(dataset_keys))
    if source_league_id:
        facts_query = facts_query.filter(models.MflHtmlRecordFact.league_id == source_league_id)

    for fact in facts_query.all():
        record = fact.record_json or {}
        if not isinstance(record, dict):
            continue

        row_season = _safe_int(str(record.get("season") if record.get("season") is not None else fact.season))
        if row_season is None or row_season not in season_set:
            continue

        row_league_id = str(record.get("league_id") or fact.league_id or "").strip()
        if source_league_id and row_league_id and row_league_id != source_league_id:
            continue

        if not all(col in record for col in required):
            continue

        matched_seasons.add(row_season)
        row = {str(k): "" if v is None else str(v) for k, v in record.items()}
        row.setdefault("season", str(row_season))
        if row_league_id:
            row.setdefault("league_id", row_league_id)

        summary.rows_validated += 1
        missing = [col for col in required if (row.get(col) or "").strip() == ""]
        if missing:
            summary.rows_invalid += 1
            summary.warnings.append(
                f"invalid {report_type} row season={row_season}: missing columns {missing}"
            )
            continue

        rows.append(row)

    for season in seasons:
        if season in matched_seasons:
            summary.files_checked += 1
        else:
            summary.files_missing += 1
            summary.warnings.append(f"missing db rows: report={report_type} season={season}")

    return rows


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    try:
        return int(float(cleaned))
    except Exception:  # noqa: BLE001
        return None


def _safe_amount(value: str | None) -> int:
    if value is None:
        return 0
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return 0
    try:
        return int(round(float(cleaned)))
    except Exception:  # noqa: BLE001
        return 0


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except Exception:  # noqa: BLE001
        return None


def _build_owner_map(
    db: Session,
    *,
    target_league_id: int,
    franchise_rows: list[dict[str, str]],
) -> dict[tuple[int, str], int]:
    users = (
        db.query(models.User)
        .filter(models.User.league_id == target_league_id)
        .all()
    )

    by_team_name = {
        (u.team_name or "").strip().lower(): int(u.id)
        for u in users
        if (u.team_name or "").strip()
    }
    by_username = {
        (u.username or "").strip().lower(): int(u.id)
        for u in users
        if (u.username or "").strip()
    }
    by_stub_franchise_id = {
        username.rsplit("_", 1)[-1]: user_id
        for username, user_id in by_username.items()
        if username.startswith("hist_") and "_" in username
    }

    owner_map: dict[tuple[int, str], int] = {}
    for row in franchise_rows:
        season = _safe_int(row.get("season"))
        franchise_id = (row.get("franchise_id") or "").strip()
        if season is None or not franchise_id:
            continue

        franchise_name = (row.get("franchise_name") or "").strip().lower()
        owner_name = (row.get("owner_name") or "").strip().lower()

        mapped_user_id = (
            by_team_name.get(franchise_name)
            or by_username.get(franchise_name)
            or by_team_name.get(owner_name)
            or by_username.get(owner_name)
            or by_stub_franchise_id.get(franchise_id)
        )

        if mapped_user_id:
            owner_map[(season, franchise_id)] = mapped_user_id

    return owner_map


def _build_existing_player_index(db: Session) -> dict[tuple[str, str, str], models.Player]:
    index: dict[tuple[str, str, str], models.Player] = {}
    for player in db.query(models.Player).all():
        key = canonical_player_identity(player.name, player.position, player.nfl_team)
        if key[0] and key[1] and key[2]:
            index[key] = player
    return index


def _build_franchise_division_map(
    franchise_rows: list[dict[str, str]],
) -> dict[tuple[int, str], str | None]:
    division_map: dict[tuple[int, str], str | None] = {}
    for row in franchise_rows:
        season = _safe_int(row.get("season"))
        franchise_id = (row.get("franchise_id") or "").strip()
        if season is None or not franchise_id:
            continue
        division = (row.get("division") or "").strip() or None
        division_map[(season, franchise_id)] = division
    return division_map


def _build_playoff_week_map(
    schedule_rows: list[dict[str, str]],
    franchise_rows: list[dict[str, str]],
) -> dict[tuple[int, int], bool]:
    franchise_counts: dict[int, int] = {}
    for row in franchise_rows:
        season = _safe_int(row.get("season"))
        franchise_id = (row.get("franchise_id") or "").strip()
        if season is None or not franchise_id:
            continue
        franchise_counts.setdefault(season, 0)
        franchise_counts[season] += 1

    rows_per_week: dict[tuple[int, int], int] = {}
    for row in schedule_rows:
        season = _safe_int(row.get("season"))
        week = _safe_int(row.get("week"))
        if season is None or week is None:
            continue
        key = (season, week)
        rows_per_week[key] = rows_per_week.get(key, 0) + 1

    playoff_week_map: dict[tuple[int, int], bool] = {}
    for (season, week), row_count in rows_per_week.items():
        franchise_count = franchise_counts.get(season, 0)
        regular_season_matchups = franchise_count / 2 if franchise_count else 0
        playoff_week_map[(season, week)] = bool(
            regular_season_matchups and row_count < regular_season_matchups
        )
    return playoff_week_map


def run_import_mfl_csv(
    *,
    input_root: str | None,
    target_league_id: int,
    start_year: int,
    end_year: int,
    dry_run: bool = True,
    source_mode: str = "csv",
    source_league_id: str | None = None,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    summary = ImportSummary(
        input_root=input_root or "db:mfl_html_record_facts",
        target_league_id=target_league_id,
        dry_run=dry_run,
        seasons=seasons,
    )

    if source_mode not in {"csv", "db"}:
        raise ValueError("source_mode must be either 'csv' or 'db'")
    if source_mode == "csv" and not input_root:
        raise ValueError("input_root is required when source_mode='csv'")

    root = Path(input_root) if input_root else None
    db = SessionLocal()
    try:
        if source_mode == "db":
            franchise_rows = _load_report_rows_from_db(
                db=db,
                report_type="franchises",
                seasons=seasons,
                summary=summary,
                source_league_id=source_league_id,
            )
            player_rows = _load_report_rows_from_db(
                db=db,
                report_type="players",
                seasons=seasons,
                summary=summary,
                source_league_id=source_league_id,
            )
            draft_rows = _load_report_rows_from_db(
                db=db,
                report_type="draftResults",
                seasons=seasons,
                summary=summary,
                source_league_id=source_league_id,
            )
            schedule_rows = _load_report_rows_from_db(
                db=db,
                report_type="schedule",
                seasons=seasons,
                summary=summary,
                source_league_id=source_league_id,
            )
            transaction_rows = _load_report_rows_from_db(
                db=db,
                report_type="transactions",
                seasons=seasons,
                summary=summary,
                source_league_id=source_league_id,
            )
        else:
            franchise_rows = _load_report_rows(
                input_root=root,
                report_type="franchises",
                seasons=seasons,
                summary=summary,
            )
            player_rows = _load_report_rows(
                input_root=root,
                report_type="players",
                seasons=seasons,
                summary=summary,
            )
            draft_rows = _load_report_rows(
                input_root=root,
                report_type="draftResults",
                seasons=seasons,
                summary=summary,
            )
            schedule_rows = _load_report_rows(
                input_root=root,
                report_type="schedule",
                seasons=seasons,
                summary=summary,
            )
            transaction_rows = _load_report_rows(
                input_root=root,
                report_type="transactions",
                seasons=seasons,
                summary=summary,
            )

        owner_map = _build_owner_map(
            db,
            target_league_id=target_league_id,
            franchise_rows=franchise_rows,
        )
        division_map = _build_franchise_division_map(franchise_rows)
        playoff_week_map = _build_playoff_week_map(schedule_rows, franchise_rows)

        player_index = _build_existing_player_index(db)
        mfl_player_to_local: dict[tuple[int, str], int] = {}

        for row in player_rows:
            season = _safe_int(row.get("season"))
            mfl_player_id = (row.get("player_mfl_id") or "").strip()
            if season is None or not mfl_player_id:
                continue

            name = (row.get("player_name") or "").strip()
            position = (row.get("position") or "").strip().upper()
            nfl_team = (row.get("nfl_team") or "").strip().upper()
            if not name or not position or not nfl_team:
                summary.rows_invalid += 1
                continue

            key = canonical_player_identity(name, position, nfl_team)
            existing = player_index.get(key)
            if existing is None:
                existing = models.Player(
                    name=name,
                    position=position,
                    nfl_team=nfl_team,
                    adp=0.0,
                    projected_points=0.0,
                )
                db.add(existing)
                db.flush()
                player_index[key] = existing
                summary.players_inserted += 1
            else:
                summary.players_matched += 1

            mfl_player_to_local[(season, mfl_player_id)] = int(existing.id)

        existing_pick_keys = {
            (
                int(row.year or 0),
                int(row.owner_id or 0),
                int(row.player_id or 0),
                int(row.round_num or 0),
                int(row.pick_num or 0),
                str(row.session_id or ""),
                int(row.league_id or 0),
            )
            for row in db.query(models.DraftPick).filter(models.DraftPick.league_id == target_league_id).all()
        }

        for row in draft_rows:
            season = _safe_int(row.get("season"))
            franchise_id = (row.get("franchise_id") or "").strip()
            player_mfl_id = (row.get("player_mfl_id") or "").strip()
            if season is None or not franchise_id or not player_mfl_id:
                summary.draft_picks_skipped += 1
                continue

            owner_id = owner_map.get((season, franchise_id))
            if owner_id is None:
                summary.skipped_missing_owner_map += 1
                summary.draft_picks_skipped += 1
                continue

            player_id = mfl_player_to_local.get((season, player_mfl_id))
            if player_id is None:
                summary.skipped_missing_player_map += 1
                summary.draft_picks_skipped += 1
                continue

            round_num = _safe_int(row.get("round")) or 0
            pick_num = _safe_int(row.get("pick_number")) or 0
            session_id = f"MFL_{season}"
            key = (season, owner_id, player_id, round_num, pick_num, session_id, target_league_id)
            if key in existing_pick_keys:
                summary.draft_picks_skipped += 1
                continue

            amount = _safe_amount(row.get("winning_bid"))
            db.add(
                models.DraftPick(
                    year=season,
                    round_num=round_num if round_num > 0 else None,
                    pick_num=pick_num if pick_num > 0 else None,
                    amount=amount,
                    session_id=session_id,
                    owner_id=owner_id,
                    player_id=player_id,
                    league_id=target_league_id,
                    current_status="BENCH",
                )
            )
            existing_pick_keys.add(key)
            summary.draft_picks_inserted += 1

        existing_matchup_keys = {
            (
                int(row.league_id or 0),
                int(row.season or 0),
                int(row.week or 0),
                int(row.home_team_id or 0),
                int(row.away_team_id or 0),
            )
            for row in db.query(models.Matchup)
            .filter(models.Matchup.league_id == target_league_id)
            .all()
            if row.season is not None and row.week is not None and row.home_team_id is not None and row.away_team_id is not None
        }

        for row in schedule_rows:
            season = _safe_int(row.get("season"))
            week = _safe_int(row.get("week"))
            home_franchise_id = (row.get("home_franchise_id") or "").strip()
            away_franchise_id = (row.get("away_franchise_id") or "").strip()
            if season is None or week is None or not home_franchise_id or not away_franchise_id:
                summary.matchups_skipped += 1
                continue

            if home_franchise_id.upper() == "BYE" or away_franchise_id.upper() == "BYE":
                summary.matchups_skipped += 1
                summary.bye_matchups_skipped += 1
                continue

            home_team_id = owner_map.get((season, home_franchise_id))
            away_team_id = owner_map.get((season, away_franchise_id))
            if home_team_id is None or away_team_id is None:
                summary.skipped_missing_owner_map += 1
                summary.matchups_skipped += 1
                summary.warnings.append(
                    f"missing owner map for matchup season={season} week={week} home={home_franchise_id} away={away_franchise_id}"
                )
                continue

            key = (target_league_id, season, week, home_team_id, away_team_id)
            if key in existing_matchup_keys:
                summary.matchups_skipped += 1
                continue

            home_score = _safe_float(row.get("home_score"))
            away_score = _safe_float(row.get("away_score"))
            is_completed = home_score is not None and away_score is not None
            home_division = division_map.get((season, home_franchise_id))
            away_division = division_map.get((season, away_franchise_id))

            db.add(
                models.Matchup(
                    league_id=target_league_id,
                    season=season,
                    week=week,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=home_score or 0.0,
                    away_score=away_score or 0.0,
                    is_completed=is_completed,
                    game_status="FINAL" if is_completed else "NOT_STARTED",
                    is_playoff=playoff_week_map.get((season, week), False),
                    is_division_matchup=bool(home_division and away_division and home_division == away_division),
                    is_rivalry_week=False,
                )
            )
            existing_matchup_keys.add(key)
            summary.matchups_inserted += 1

        # ====== LOAD TRANSACTIONS ======
        existing_transaction_keys = {
            (
                int(row.league_id or 0),
                int(row.season or 0),
                int(row.player_id or 0),
                str(row.old_owner_id or ""),
                str(row.new_owner_id or ""),
                str(row.transaction_type or ""),
            )
            for row in db.query(models.TransactionHistory).filter(models.TransactionHistory.league_id == target_league_id).all()
            if row.season is not None
        }

        for row in transaction_rows:
            season = _safe_int(row.get("season"))
            franchise_id = (row.get("franchise_id") or "").strip()
            player_mfl_id = (row.get("player_mfl_id") or "").strip()
            transaction_type = (row.get("transaction_type") or "").strip().lower()
            if season is None or not franchise_id or not player_mfl_id or not transaction_type:
                summary.transactions_skipped += 1
                continue

            owner_id = owner_map.get((season, franchise_id))
            if owner_id is None:
                summary.skipped_missing_owner_map += 1
                summary.transactions_skipped += 1
                continue

            player_id = mfl_player_to_local.get((season, player_mfl_id))
            if player_id is None:
                summary.skipped_missing_player_map += 1
                summary.transactions_skipped += 1
                continue

            # Determine old_owner_id and new_owner_id based on transaction type
            # - waiver_add: new_owner_id = owner_id, old_owner_id = None
            # - waiver_drop / drop: old_owner_id = owner_id, new_owner_id = None
            # - trade: depends on transaction context (for now, both point to owner_id)
            # - draft: owner_id is the new owner, old_owner_id = None
            old_owner_id = None
            new_owner_id = None

            if transaction_type in ("waiver_add", "draft"):
                new_owner_id = owner_id
            elif transaction_type in ("waiver_drop", "drop"):
                old_owner_id = owner_id
            elif transaction_type == "trade":
                # For trades, we only know one franchise_id; old_owner_id and new_owner_id would require more context
                # For now, assume owner_id is the new owner (acquired the player)
                new_owner_id = owner_id
            else:
                # unknown transaction type
                summary.transactions_skipped += 1
                summary.warnings.append(f"Unknown transaction_type: {transaction_type}")
                continue

            amount_str = (row.get("amount") or "").strip()
            amount = _safe_amount(amount_str) if amount_str else 0

            notes = f"Type: {transaction_type}"
            if amount:
                notes += f", Amount: ${amount}"
            week = _safe_int(row.get("week"))
            if week:
                notes += f", Week: {week}"

            key = (target_league_id, season, player_id, str(old_owner_id or ""), str(new_owner_id or ""), transaction_type)
            if key in existing_transaction_keys:
                summary.transactions_skipped += 1
                continue

            db.add(
                models.TransactionHistory(
                    league_id=target_league_id,
                    season=season,
                    player_id=player_id,
                    old_owner_id=old_owner_id,
                    new_owner_id=new_owner_id,
                    transaction_type=transaction_type,
                    notes=notes,
                )
            )
            existing_transaction_keys.add(key)
            summary.transactions_inserted += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return summary.to_dict()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()