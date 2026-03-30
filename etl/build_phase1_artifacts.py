from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from etl.transform.historical_draft_validator import write_draft_validation_outputs
from etl.transform.owner_budget_timeline import write_budget_timeline_outputs
from etl.transform.player_metadata_canonicalization import write_canonicalization_outputs

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data"
OUTPUT_DIR = ROOT / "etl" / "outputs"


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def _load_from_postgres_or_exports() -> dict[str, Path]:
    dataset_dir = OUTPUT_DIR / "_source_snapshots"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    required = {
        "players": dataset_dir / "players.csv",
        "positions": dataset_dir / "positions.csv",
        "users": dataset_dir / "users.csv",
        "draft_budget": dataset_dir / "draft_budget.csv",
        "draft_results": dataset_dir / "draft_results.csv",
    }

    database_url = os.getenv("DATABASE_URL")
    source_mode = "csv_exports"

    if database_url:
        try:
            engine = create_engine(database_url)
            pd.read_sql("SELECT * FROM players", engine).to_csv(required["players"], index=False)
            pd.read_sql("SELECT * FROM positions", engine).to_csv(required["positions"], index=False)
            pd.read_sql("SELECT id as \"OwnerID\", username as \"OwnerName\" FROM users", engine).to_csv(required["users"], index=False)
            pd.read_sql("SELECT future_draft_budget as \"DraftBudget\", 2026 as \"Year\", id as \"OwnerID\" FROM users", engine).to_csv(required["draft_budget"], index=False)
            pd.read_sql(
                "SELECT player_id as \"PlayerID\", owner_id as \"OwnerID\", year as \"Year\", position_id as \"PositionID\", team_id as \"TeamID\", amount as \"WinningBid\" FROM draft_picks",
                engine,
            ).to_csv(required["draft_results"], index=False)
            source_mode = "postgres"
        except Exception:
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
            _read_csv_with_fallback(src).to_csv(required[key], index=False)

    return {
        "source_mode": source_mode,
        **{k: str(v) for k, v in required.items()},
    }


def main() -> int:
    source_info = _load_from_postgres_or_exports()

    canonical_output = write_canonicalization_outputs(
        players_csv=Path(source_info["players"]),
        positions_csv=Path(source_info["positions"]),
        alias_map_path=ROOT / "etl" / "transform" / "player_metadata_alias_map.yml",
        output_dir=OUTPUT_DIR / "player_metadata",
    )

    budget_output = write_budget_timeline_outputs(
        draft_budget_csv=Path(source_info["draft_budget"]),
        draft_results_csv=Path(source_info["draft_results"]),
        users_csv=Path(source_info["users"]),
        output_dir=OUTPUT_DIR / "owner_budget",
    )

    draft_validation_output = write_draft_validation_outputs(
        draft_results_csv=Path(source_info["draft_results"]),
        players_csv=Path(source_info["players"]),
        users_csv=Path(source_info["users"]),
        positions_csv=Path(source_info["positions"]),
        output_dir=OUTPUT_DIR / "draft_validation",
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_mode": source_info["source_mode"],
        "sources": {
            k: v
            for k, v in source_info.items()
            if k != "source_mode"
        },
        "artifacts": {
            "361_player_metadata": canonical_output,
            "362_owner_budget_timeline": budget_output,
            "363_historical_draft_validation": draft_validation_output,
        },
    }

    manifest_path = OUTPUT_DIR / "phase1_artifact_manifest_v1.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
