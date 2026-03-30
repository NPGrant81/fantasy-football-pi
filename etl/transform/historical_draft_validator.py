from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


CORRECTION_LEDGER_COLUMNS = [
    "source_row_number",
    "action",
    "reason",
    "season_year",
    "owner_id",
    "player_id",
]


def _to_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_amount(value: Any) -> float | None:
    if value is None:
        return None
    text = re.sub(r"[^0-9.-]", "", str(value).strip())
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_historical_draft_results(
    draft_results_df: pd.DataFrame,
    players_df: pd.DataFrame,
    users_df: pd.DataFrame,
    positions_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    required_draft_cols = {"PlayerID", "OwnerID", "Year", "PositionID", "TeamID", "WinningBid"}
    missing_draft_cols = sorted(required_draft_cols - set(draft_results_df.columns))
    if missing_draft_cols:
        raise ValueError(f"Missing required columns in draft_results_df: {', '.join(missing_draft_cols)}")

    required_player_cols = {"Player_ID"}
    missing_player_cols = sorted(required_player_cols - set(players_df.columns))
    if missing_player_cols:
        raise ValueError(f"Missing required columns in players_df: {', '.join(missing_player_cols)}")

    required_user_cols = {"OwnerID"}
    missing_user_cols = sorted(required_user_cols - set(users_df.columns))
    if missing_user_cols:
        raise ValueError(f"Missing required columns in users_df: {', '.join(missing_user_cols)}")

    required_position_cols = {"PositionID"}
    missing_position_cols = sorted(required_position_cols - set(positions_df.columns))
    if missing_position_cols:
        raise ValueError(f"Missing required columns in positions_df: {', '.join(missing_position_cols)}")

    player_ids = {
        int(v)
        for v in pd.to_numeric(players_df.get("Player_ID"), errors="coerce").dropna().astype(int).tolist()
    }
    owner_ids = {
        int(v)
        for v in pd.to_numeric(users_df.get("OwnerID"), errors="coerce").dropna().astype(int).tolist()
    }
    position_ids = {
        int(v)
        for v in pd.to_numeric(positions_df.get("PositionID"), errors="coerce").dropna().astype(int).tolist()
    }

    working = draft_results_df.copy().reset_index().rename(columns={"index": "source_row_number"})
    working["player_id"] = working["PlayerID"].apply(_to_int)
    working["owner_id"] = working["OwnerID"].apply(_to_int)
    working["season_year"] = working["Year"].apply(_to_int)
    working["position_id"] = working["PositionID"].apply(_to_int)
    working["winning_bid"] = working["WinningBid"].apply(_to_amount)

    validation_errors: list[dict[str, Any]] = []
    for _, row in working.iterrows():
        row_no = int(row["source_row_number"])
        if row["player_id"] is None or row["player_id"] not in player_ids:
            validation_errors.append({
                "source_row_number": row_no,
                "issue_type": "invalid_player_id",
                "detail": f"player_id={row['player_id']} missing from players dimension",
            })
        if row["owner_id"] is None or row["owner_id"] not in owner_ids:
            validation_errors.append({
                "source_row_number": row_no,
                "issue_type": "invalid_owner_id",
                "detail": f"owner_id={row['owner_id']} missing from users dimension",
            })
        if row["position_id"] is None or row["position_id"] not in position_ids:
            validation_errors.append({
                "source_row_number": row_no,
                "issue_type": "invalid_position_id",
                "detail": f"position_id={row['position_id']} missing from positions dimension",
            })
        if row["season_year"] is None:
            validation_errors.append({
                "source_row_number": row_no,
                "issue_type": "invalid_season_year",
                "detail": "year is null or non-numeric",
            })
        if row["winning_bid"] is None or row["winning_bid"] < 0:
            validation_errors.append({
                "source_row_number": row_no,
                "issue_type": "invalid_winning_bid",
                "detail": f"winning_bid={row['winning_bid']} is null/negative",
            })

    duplicate_keys = ["season_year", "owner_id", "player_id"]
    duplicates = (
        working.dropna(subset=duplicate_keys)
        .groupby(duplicate_keys, as_index=False)
        .size()
        .query("size > 1")
    )
    duplicate_key_set = {
        (int(r.season_year), int(r.owner_id), int(r.player_id)) for r in duplicates.itertuples()
    }

    correction_ledger: list[dict[str, Any]] = []
    for _, row in working.iterrows():
        key = row["season_year"], row["owner_id"], row["player_id"]
        if None not in key and (int(key[0]), int(key[1]), int(key[2])) in duplicate_key_set:
            correction_ledger.append({
                "source_row_number": int(row["source_row_number"]),
                "action": "dedupe_candidate",
                "reason": "duplicate season/owner/player tuple",
                "season_year": _to_int(row["season_year"]),
                "owner_id": _to_int(row["owner_id"]),
                "player_id": _to_int(row["player_id"]),
            })

    invalid_row_numbers = {int(err["source_row_number"]) for err in validation_errors}
    valid_row_mask = ~working["source_row_number"].astype(int).isin(invalid_row_numbers)
    valid_df = working.loc[valid_row_mask].copy()

    if not duplicates.empty:
        valid_df = valid_df.sort_values(
            by=["season_year", "owner_id", "player_id", "winning_bid", "source_row_number"],
            ascending=[True, True, True, False, True],
            kind="mergesort",
        )
        valid_df = valid_df.drop_duplicates(subset=duplicate_keys, keep="first")

    validated_df = valid_df[
        [
            "player_id",
            "owner_id",
            "season_year",
            "position_id",
            "TeamID",
            "winning_bid",
        ]
    ].rename(columns={"TeamID": "team_id"})
    validated_df = validated_df.sort_values(
        by=["season_year", "owner_id", "player_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    correction_df = pd.DataFrame(correction_ledger, columns=CORRECTION_LEDGER_COLUMNS)
    error_df = pd.DataFrame(validation_errors)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_rows": int(len(working)),
        "validated_rows": int(len(validated_df)),
        "error_count": int(len(error_df)),
        "duplicate_key_count": int(len(duplicates)),
        "correction_ledger_rows": int(len(correction_df)),
        "error_breakdown": {
            str(k): int(v)
            for k, v in error_df["issue_type"].value_counts().to_dict().items()
        } if not error_df.empty else {},
    }

    return validated_df, correction_df, report


def write_draft_validation_outputs(
    draft_results_csv: Path,
    players_csv: Path,
    users_csv: Path,
    positions_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    draft_results_df = pd.read_csv(draft_results_csv)
    players_df = pd.read_csv(players_csv)
    users_df = pd.read_csv(users_csv)
    positions_df = pd.read_csv(positions_csv)

    validated_df, correction_df, report = validate_historical_draft_results(
        draft_results_df,
        players_df,
        users_df,
        positions_df,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    validated_path = output_dir / "validated_draft_results_v1.csv"
    correction_path = output_dir / "draft_correction_ledger_v1.csv"
    report_path = output_dir / "draft_validation_report_v1.json"

    validated_df.to_csv(validated_path, index=False)
    correction_df.to_csv(correction_path, index=False)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "csv": str(validated_path),
        "correction_ledger": str(correction_path),
        "report": str(report_path),
        "rows": int(len(validated_df)),
        "corrections": int(len(correction_df)),
    }
