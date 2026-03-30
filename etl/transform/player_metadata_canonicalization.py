from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .normalize import normalize_player_name


REQUIRED_COLUMNS = ["player_id", "player_name", "position"]


@dataclass
class CanonicalizationResult:
    canonical_players: pd.DataFrame
    run_report: dict[str, Any]


def _validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _normalize_position(value: object) -> str:
    token = str(value or "").strip().upper()
    if token in {"DST", "D/ST"}:
        return "DEF"
    return token


def _stable_digest(df: pd.DataFrame) -> str:
    serialized = df.sort_values(["player_id"]).to_json(orient="records", date_format="iso")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonicalize_player_metadata(
    players_df: pd.DataFrame,
    alias_map: dict[str, str] | None = None,
) -> CanonicalizationResult:
    _validate_columns(players_df, REQUIRED_COLUMNS)

    alias_map = alias_map or {}
    normalized_alias = {normalize_player_name(key): value.strip() for key, value in alias_map.items() if str(key).strip()}

    working = players_df.copy()
    working["player_id"] = pd.to_numeric(working["player_id"], errors="coerce")
    working = working.dropna(subset=["player_id"]).copy()
    if working.empty:
        empty = pd.DataFrame(columns=["player_id", "canonical_name", "normalized_name", "position", "nfl_team"])
        return CanonicalizationResult(
            canonical_players=empty,
            run_report={
                "input_rows": int(players_df.shape[0]),
                "output_rows": 0,
                "merge_count": 0,
                "split_count": 0,
                "unresolved_alias_count": 0,
                "position_resolution_pct": 0.0,
                "digest": _stable_digest(empty),
            },
        )

    working["player_id"] = working["player_id"].astype(int)
    working["raw_name"] = working["player_name"].astype(str).str.strip()
    working["normalized_name"] = working["raw_name"].map(normalize_player_name)
    working["canonical_name"] = working["normalized_name"].map(normalized_alias)
    working["canonical_name"] = working["canonical_name"].fillna(working["raw_name"])
    working["canonical_name"] = working["canonical_name"].astype(str).str.strip()
    working["position"] = working["position"].map(_normalize_position)

    if "nfl_team" not in working.columns:
        working["nfl_team"] = ""
    working["nfl_team"] = working["nfl_team"].fillna("").astype(str).str.upper().str.strip()

    # Deterministic dedupe by player_id: keep row with best non-empty position/team payload.
    working["completeness"] = (
        (working["position"] != "").astype(int)
        + (working["nfl_team"] != "").astype(int)
        + (working["canonical_name"] != "").astype(int)
    )
    working = working.sort_values(
        ["player_id", "completeness", "canonical_name", "normalized_name", "raw_name"],
        ascending=[True, False, True, True, True],
    )
    canonical_players = working.drop_duplicates(subset=["player_id"], keep="first").copy()

    merge_count = int(canonical_players.duplicated(subset=["canonical_name"], keep=False).sum())
    split_count = int(canonical_players.groupby("normalized_name")["player_id"].nunique().gt(1).sum())
    unresolved_alias_count = int(
        canonical_players[
            canonical_players["normalized_name"].isin(normalized_alias.keys())
            & (canonical_players["canonical_name"] == canonical_players["raw_name"])
        ].shape[0]
    )

    canonical_players = canonical_players[["player_id", "canonical_name", "normalized_name", "position", "nfl_team"]]
    canonical_players = canonical_players.sort_values(["canonical_name", "player_id"]).reset_index(drop=True)

    known_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}
    resolved_positions = int(canonical_players["position"].isin(known_positions).sum())
    position_resolution_pct = round((resolved_positions / max(1, len(canonical_players))) * 100.0, 2)

    report = {
        "input_rows": int(players_df.shape[0]),
        "output_rows": int(canonical_players.shape[0]),
        "merge_count": merge_count,
        "split_count": split_count,
        "unresolved_alias_count": unresolved_alias_count,
        "position_resolution_pct": position_resolution_pct,
        "digest": _stable_digest(canonical_players),
    }

    return CanonicalizationResult(canonical_players=canonical_players, run_report=report)


def write_canonicalization_outputs(
    result: CanonicalizationResult,
    output_csv_path: str | Path,
    report_json_path: str | Path,
) -> None:
    output_csv_path = Path(output_csv_path)
    report_json_path = Path(report_json_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    result.canonical_players.to_csv(output_csv_path, index=False)
    report_json_path.write_text(json.dumps(result.run_report, indent=2), encoding="utf-8")
