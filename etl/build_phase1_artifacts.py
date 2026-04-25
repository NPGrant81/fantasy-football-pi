from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, inspect

from etl.transform.historical_draft_validator import write_draft_validation_outputs_from_dataframes
from etl.transform.owner_budget_timeline import write_budget_timeline_outputs_from_dataframes
from etl.transform.player_metadata_canonicalization import write_canonicalization_outputs_from_dataframes

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data"
OUTPUT_DIR = ROOT / "etl" / "outputs"


def _manifest_rel(path_value: str | Path) -> str:
    path_obj = Path(path_value)
    if path_obj.is_absolute():
        try:
            return path_obj.relative_to(ROOT).as_posix()
        except ValueError:
            return path_obj.as_posix()
    return path_obj.as_posix()


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def _load_from_postgres_or_exports() -> dict[str, Any]:
    dataset_dir = OUTPUT_DIR / "_source_snapshots"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    snapshot_paths = {
        "players": dataset_dir / "players.csv",
        "positions": dataset_dir / "positions.csv",
        "users": dataset_dir / "users.csv",
        "draft_budget": dataset_dir / "draft_budget.csv",
        "draft_results": dataset_dir / "draft_results.csv",
    }

    frames: dict[str, pd.DataFrame] = {}

    database_url = os.getenv("DATABASE_URL")
    source_mode = "csv_exports"

    if database_url:
        try:
            engine = create_engine(database_url)
            inspector = inspect(engine)

            players_columns = {col["name"] for col in inspector.get_columns("players")}
            if {"Player_ID", "PlayerName"}.issubset(players_columns):
                if "PositionID" in players_columns:
                    position_id_expr = '"PositionID"'
                else:
                    position_id_expr = 'NULL as "PositionID"'
                if "Position" in players_columns:
                    position_expr = '"Position"'
                elif "position" in players_columns:
                    position_expr = 'position as "Position"'
                else:
                    position_expr = 'NULL as "Position"'
                players_query = f'SELECT "Player_ID", "PlayerName", {position_id_expr}, {position_expr} FROM players ORDER BY "Player_ID"'
            elif {"id", "name"}.issubset(players_columns):
                if "position_id" in players_columns:
                    position_id_expr = 'position_id as "PositionID"'
                else:
                    position_id_expr = 'NULL as "PositionID"'
                if "position" in players_columns:
                    position_expr = 'position as "Position"'
                elif "Position" in players_columns:
                    position_expr = '"Position"'
                else:
                    position_expr = 'NULL as "Position"'
                players_query = f'SELECT id as "Player_ID", name as "PlayerName", {position_id_expr}, {position_expr} FROM players ORDER BY id'
            else:
                players_query = "SELECT * FROM players"
            frames["players"] = pd.read_sql(players_query, engine)

            positions_columns = {col["name"] for col in inspector.get_columns("positions")}
            if {"PositionID", "Position"}.issubset(positions_columns):
                positions_query = 'SELECT "PositionID", "Position" FROM positions'
            elif {"id", "name"}.issubset(positions_columns):
                positions_query = 'SELECT id as "PositionID", name as "Position" FROM positions'
            else:
                positions_query = "SELECT * FROM positions"
            frames["positions"] = pd.read_sql(positions_query, engine)

            frames["users"] = pd.read_sql("SELECT id as \"OwnerID\", username as \"OwnerName\" FROM users", engine)

            budget_columns = {col["name"] for col in inspector.get_columns("draft_budgets")}
            if {"owner_id", "year"}.issubset(budget_columns) and ("budget" in budget_columns or "total_budget" in budget_columns):
                budget_amount_col = "budget" if "budget" in budget_columns else "total_budget"
                frames["draft_budget"] = pd.read_sql(
                    f'SELECT {budget_amount_col} as "DraftBudget", year as "Year", owner_id as "OwnerID" FROM draft_budgets',
                    engine,
                )
            else:
                latest_year_df = pd.read_sql('SELECT MAX(year) as "Year" FROM draft_picks', engine)
                latest_year = None
                if not latest_year_df.empty and not latest_year_df["Year"].isna().all():
                    latest_year = int(latest_year_df["Year"].iloc[0])
                if latest_year is None:
                    latest_year = datetime.now(UTC).year
                frames["draft_budget"] = pd.read_sql(
                    f'SELECT future_draft_budget as "DraftBudget", {latest_year} as "Year", id as "OwnerID" FROM users',
                    engine,
                )

            draft_pick_columns = {col["name"] for col in inspector.get_columns("draft_picks")}
            if not {"player_id", "owner_id", "year"}.issubset(draft_pick_columns):
                raise RuntimeError("draft_picks is missing one or more required columns: player_id, owner_id, year")
            bid_col = "amount" if "amount" in draft_pick_columns else ("winning_bid" if "winning_bid" in draft_pick_columns else None)
            if bid_col is None:
                raise RuntimeError("draft_picks is missing required bid column (amount or winning_bid)")

            position_expr = 'position_id as "PositionID"' if "position_id" in draft_pick_columns else 'NULL as "PositionID"'
            team_expr = 'team_id as "TeamID"' if "team_id" in draft_pick_columns else 'NULL as "TeamID"'
            stable_pick_order_col = "id" if "id" in draft_pick_columns else "player_id"
            order_by_clause = f"year, owner_id, {stable_pick_order_col}"
            frames["draft_results"] = pd.read_sql(
                f'SELECT player_id as "PlayerID", owner_id as "OwnerID", year as "Year", {position_expr}, {team_expr}, {bid_col} as "WinningBid" FROM draft_picks ORDER BY {order_by_clause}',
                engine,
            )
            source_mode = "postgres"
        except Exception as exc:
            print(
                f"Warning: Postgres extraction failed (error type: {type(exc).__name__}), falling back to CSV exports.",
                file=sys.stderr,
            )
            source_mode = "csv_exports"

    if source_mode != "postgres":
        fallback_map = {
            "players": DATA_DIR / "players.csv",
            "positions": DATA_DIR / "positions.csv",
            "users": DATA_DIR / "users.csv",
            "draft_budget": DATA_DIR / "draft_budget.csv",
            "draft_results": DATA_DIR / "draft_results.csv",
        }
        for key, src in fallback_map.items():
            if not src.exists():
                raise FileNotFoundError(f"Missing required source export: {src}")
            frames[key] = _read_csv_with_fallback(src)

    for key, frame in frames.items():
        frame.to_csv(snapshot_paths[key], index=False)

    return {
        "source_mode": source_mode,
        "frames": frames,
        "source_paths": {k: str(v) for k, v in snapshot_paths.items()},
    }


def main() -> int:
    source_info = _load_from_postgres_or_exports()
    frames: dict[str, pd.DataFrame] = source_info["frames"]

    canonical_output = write_canonicalization_outputs_from_dataframes(
        players_df=frames["players"],
        positions_df=frames["positions"],
        alias_map_path=ROOT / "etl" / "transform" / "player_metadata_alias_map.yml",
        output_dir=OUTPUT_DIR / "player_metadata",
    )

    budget_output = write_budget_timeline_outputs_from_dataframes(
        draft_budget_df=frames["draft_budget"],
        draft_results_df=frames["draft_results"],
        users_df=frames["users"],
        output_dir=OUTPUT_DIR / "owner_budget",
    )

    draft_validation_output = write_draft_validation_outputs_from_dataframes(
        draft_results_df=frames["draft_results"],
        players_df=frames["players"],
        users_df=frames["users"],
        positions_df=frames["positions"],
        output_dir=OUTPUT_DIR / "draft_validation",
    )

    source_manifest = {
        k: _manifest_rel(v)
        for k, v in source_info["source_paths"].items()
    }
    canonical_manifest = {
        **canonical_output,
        "csv": _manifest_rel(canonical_output["csv"]),
        "report": _manifest_rel(canonical_output["report"]),
    }
    budget_manifest = {
        **budget_output,
        "csv": _manifest_rel(budget_output["csv"]),
        "report": _manifest_rel(budget_output["report"]),
    }
    draft_validation_manifest = {
        **draft_validation_output,
        "csv": _manifest_rel(draft_validation_output["csv"]),
        "correction_ledger": _manifest_rel(draft_validation_output["correction_ledger"]),
        "report": _manifest_rel(draft_validation_output["report"]),
    }

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_mode": source_info["source_mode"],
        "sources": source_manifest,
        "artifacts": {
            "361_player_metadata": canonical_manifest,
            "362_owner_budget_timeline": budget_manifest,
            "363_historical_draft_validation": draft_validation_manifest,
        },
    }

    manifest_path = OUTPUT_DIR / "phase1_artifact_manifest_v1.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
