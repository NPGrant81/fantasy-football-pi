from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from etl.transform.normalize import normalize_player_name


def _normalize_name(value: str) -> str:
    return normalize_player_name(str(value or ""))


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_position_token(value: Any) -> str:
    token = str(value or "").strip().upper()
    normalized = {
        "D/ST": "DEF",
        "DST": "DEF",
        "DEFENSE": "DEF",
        "TD": "DEF",
        "PK": "K",
        "KICKER": "K",
    }
    return normalized.get(token, token)


def canonicalize_player_metadata(
    players_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    alias_map: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required_player_cols = {"Player_ID", "PlayerName"}
    missing_player_cols = sorted(required_player_cols - set(players_df.columns))
    if missing_player_cols:
        raise ValueError(f"Missing required columns in players_df: {', '.join(missing_player_cols)}")

    required_position_cols = {"PositionID", "Position"}
    missing_position_cols = sorted(required_position_cols - set(positions_df.columns))
    if missing_position_cols:
        raise ValueError(f"Missing required columns in positions_df: {', '.join(missing_position_cols)}")

    alias_map = alias_map or {}
    preferred_positions = ["QB", "RB", "WR", "TE", "K", "DEF"]
    priority_rank = {pos: rank for rank, pos in enumerate(preferred_positions)}
    default_rank = len(preferred_positions)

    pos_lookup: dict[int, str] = {}
    pos_rank_lookup: dict[int, int] = {}
    for _, row in positions_df.iterrows():
        position_id = _safe_int(row.get("PositionID"))
        if position_id is None:
            continue
        token = _normalize_position_token(row.get("Position"))
        rank = priority_rank.get(token, default_rank)

        if position_id not in pos_lookup:
            pos_lookup[position_id] = token
            pos_rank_lookup[position_id] = rank
            continue

        if rank < pos_rank_lookup.get(position_id, default_rank):
            pos_lookup[position_id] = token
            pos_rank_lookup[position_id] = rank

    rows: list[dict[str, Any]] = []
    for _, row in players_df.iterrows():
        player_id = _safe_int(row.get("Player_ID"))
        raw_name = str(row.get("PlayerName") or "").strip()
        raw_pos_id = _safe_int(row.get("PositionID"))
        raw_pos_token = _normalize_position_token(row.get("Position"))
        if player_id is None or not raw_name:
            continue

        alias_name = alias_map.get(raw_name, raw_name)
        canonical_name = _normalize_name(alias_name)
        canonical_name_key = canonical_name.lower()
        canonical_position = pos_lookup.get(raw_pos_id)
        if not canonical_position and raw_pos_token:
            canonical_position = raw_pos_token
        if not canonical_position:
            canonical_position = "UNKNOWN"

        rows.append(
            {
                "player_id": player_id,
                "source_name": raw_name,
                "canonical_name": canonical_name,
                "canonical_name_key": canonical_name_key,
                "source_position_id": raw_pos_id,
                "canonical_position": canonical_position,
            }
        )

    canonical_df = pd.DataFrame(rows)
    if canonical_df.empty:
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_rows": 0,
            "unique_player_ids": 0,
            "deduplicated_rows": 0,
            "position_distribution": {},
            "duplicate_name_keys": [],
            "content_digest": "",
        }
        return canonical_df, report

    canonical_df = canonical_df.sort_values(
        by=["player_id", "canonical_name", "source_name", "canonical_position"],
        kind="mergesort",
    )
    total_rows = int(len(canonical_df))

    canonical_df = canonical_df.drop_duplicates(subset=["player_id"], keep="first")
    canonical_df = canonical_df.sort_values(by=["player_id"], kind="mergesort").reset_index(drop=True)

    digest_input = canonical_df[["player_id", "canonical_name", "canonical_position"]].to_dict("records")
    digest_payload = json.dumps(digest_input, sort_keys=True, separators=(",", ":"))
    content_digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()

    duplicate_name_keys = (
        canonical_df.groupby("canonical_name_key")["player_id"]
        .nunique()
        .reset_index(name="player_count")
        .query("player_count > 1")
        .sort_values(by=["player_count", "canonical_name_key"], ascending=[False, True])
        .to_dict("records")
    )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": total_rows,
        "unique_player_ids": int(canonical_df["player_id"].nunique()),
        "deduplicated_rows": int(total_rows - len(canonical_df)),
        "position_distribution": {
            str(k): int(v)
            for k, v in canonical_df["canonical_position"].value_counts(dropna=False).to_dict().items()
        },
        "duplicate_name_keys": duplicate_name_keys,
        "content_digest": content_digest,
    }
    return canonical_df, report


def write_canonicalization_outputs(
    players_csv: Path,
    positions_csv: Path,
    alias_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """DEPRECATED: Reads source DataFrames from CSV files.

    Use ``write_canonicalization_outputs_from_dataframes()`` instead, which
    accepts DataFrames directly and is the active code path in
    ``etl/build_phase1_artifacts.py``.
    """
    import sys as _sys
    import warnings
    warnings.warn(
        "write_canonicalization_outputs() reads from CSV files and is a legacy interface. "
        "Call write_canonicalization_outputs_from_dataframes() directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    players_df = pd.read_csv(players_csv)
    positions_df = pd.read_csv(positions_csv)

    return write_canonicalization_outputs_from_dataframes(
        players_df=players_df,
        positions_df=positions_df,
        alias_map_path=alias_map_path,
        output_dir=output_dir,
    )


def write_canonicalization_outputs_from_dataframes(
    *,
    players_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    alias_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:

    alias_map: dict[str, str] = {}
    if alias_map_path.exists():
        alias_payload = yaml.safe_load(alias_map_path.read_text(encoding="utf-8")) or {}
        alias_map = {str(k): str(v) for k, v in (alias_payload.get("aliases") or {}).items()}

    canonical_df, report = canonicalize_player_metadata(players_df, positions_df, alias_map=alias_map)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "canonical_players_v1.csv"
    report_path = output_dir / "canonicalization_report_v1.json"

    canonical_df.to_csv(csv_path, index=False)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "csv": str(csv_path),
        "report": str(report_path),
        "rows": int(len(canonical_df)),
        "digest": report.get("content_digest", ""),
    }
