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


def run_import_mfl_csv(
    *,
    input_root: str,
    target_league_id: int,
    start_year: int,
    end_year: int,
    dry_run: bool = True,
) -> dict[str, Any]:
    seasons = list(range(start_year, end_year + 1))
    summary = ImportSummary(
        input_root=input_root,
        target_league_id=target_league_id,
        dry_run=dry_run,
        seasons=seasons,
    )

    root = Path(input_root)
    db = SessionLocal()
    try:
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

        owner_map = _build_owner_map(
            db,
            target_league_id=target_league_id,
            franchise_rows=franchise_rows,
        )

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