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

# Bid at or below this threshold is treated as a keeper/retained pick.
KEEPER_BID_THRESHOLD: float = 1.0

# Expected pick count range per draft year (inclusive). Flags years outside
# this range in the year completeness report.
EXPECTED_PICKS_MIN: int = 130
EXPECTED_PICKS_MAX: int = 200


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


def _build_position_lookup(
    canonical_players_df: pd.DataFrame | None,
    positions_df: pd.DataFrame,
) -> dict[int, int]:
    """Return {player_id: position_id} derived from canonical_players_df.

    Used to resolve rows whose ``PositionID`` is null (e.g. ESPN-sourced 2025
    data that does not carry a position field).  Falls back to an empty dict
    when no canonical_players_df is supplied or when the necessary columns are
    absent.
    """
    if canonical_players_df is None:
        return {}

    # canonical_players_v1.csv carries 'source_position_id' as float strings
    # like "8004.0" and 'canonical_position' like "WR".  We prefer the numeric
    # ID; build an abbrev → ID reverse map from positions_df as a fallback.
    abbrev_to_id: dict[str, int] = {}
    if "Position" in positions_df.columns:
        for _, prow in positions_df.iterrows():
            pid = _to_int(prow.get("PositionID"))
            abbrev = str(prow.get("Position", "")).strip().upper()
            if pid is not None and abbrev:
                abbrev_to_id[abbrev] = pid

    lookup: dict[int, int] = {}
    needed_cols = {"player_id", "source_position_id"}
    if not needed_cols.issubset(canonical_players_df.columns):
        return {}

    for _, row in canonical_players_df.iterrows():
        pid = _to_int(row.get("player_id"))
        if pid is None:
            continue
        # source_position_id is stored as a float string ("8004.0") in the
        # canonical CSV, so go through float before int.
        raw_pos = row.get("source_position_id")
        try:
            pos_id = int(float(str(raw_pos).strip())) if raw_pos is not None and str(raw_pos).strip() not in ("", "nan") else None
        except (TypeError, ValueError):
            pos_id = None
        if pos_id is None:
            # Try canonical_position → abbreviation lookup
            abbrev = str(row.get("canonical_position", "")).strip().upper()
            pos_id = abbrev_to_id.get(abbrev)
        if pos_id is not None:
            lookup[pid] = pos_id

    return lookup


def validate_historical_draft_results(
    draft_results_df: pd.DataFrame,
    players_df: pd.DataFrame,
    users_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    *,
    canonical_players_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Validate and clean historical draft results.

    Parameters
    ----------
    draft_results_df:
        Raw draft results from the source CSV.
    players_df:
        Players dimension table; must have ``Player_ID`` column.
    users_df:
        League owners table; must have ``OwnerID`` column.
    positions_df:
        Positions dimension table; must have ``PositionID`` column.
    canonical_players_df:
        Optional canonical player metadata produced by the player-identity ETL.
        When supplied, null ``PositionID`` values are resolved via the player's
        known position and logged to the correction ledger rather than being
        treated as hard errors.

    Returns
    -------
    validated_df:
        Cleaned, validated rows with ``is_keeper`` flag.
    correction_df:
        Correction ledger recording every resolved or excluded row.
    report:
        Summary statistics dict.
    """
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

    # Build player→position lookup for resolving null PositionID values.
    player_to_position = _build_position_lookup(canonical_players_df, positions_df)

    working = draft_results_df.copy().reset_index().rename(columns={"index": "source_row_number"})
    working["player_id"] = working["PlayerID"].apply(_to_int)
    working["owner_id"] = working["OwnerID"].apply(_to_int)
    working["season_year"] = working["Year"].apply(_to_int)
    working["position_id"] = working["PositionID"].apply(_to_int)
    working["winning_bid"] = working["WinningBid"].apply(_to_amount)

    correction_ledger: list[dict[str, Any]] = []

    # --- Position resolution pass ---
    # For rows with null position_id, attempt to resolve via canonical player
    # metadata.  Resolved rows are NOT flagged as errors; they get a correction
    # ledger entry with action="position_resolved".
    resolved_position_rows: set[int] = set()
    for idx, row in working.iterrows():
        if pd.isna(row["position_id"]) and not pd.isna(row.get("player_id")):
            resolved = player_to_position.get(int(row["player_id"]))
            if resolved is not None:
                working.at[idx, "position_id"] = resolved
                resolved_position_rows.add(int(row["source_row_number"]))
                correction_ledger.append({
                    "source_row_number": int(row["source_row_number"]),
                    "action": "position_resolved",
                    "reason": (
                        f"position_id was null; resolved to {resolved} "
                        f"from canonical player metadata"
                    ),
                    "season_year": _to_int(row["season_year"]),
                    "owner_id": _to_int(row["owner_id"]),
                    "player_id": _to_int(row["player_id"]),
                })

    # --- Hard validation ---
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

    # Log excluded rows to the correction ledger.
    invalid_row_numbers = {int(err["source_row_number"]) for err in validation_errors}
    excluded_row_numbers: dict[int, list[str]] = {}
    for err in validation_errors:
        row_no = int(err["source_row_number"])
        excluded_row_numbers.setdefault(row_no, []).append(err["issue_type"])

    for _, row in working.iterrows():
        row_no = int(row["source_row_number"])
        if row_no in excluded_row_numbers:
            correction_ledger.append({
                "source_row_number": row_no,
                "action": "excluded",
                "reason": "; ".join(excluded_row_numbers[row_no]),
                "season_year": _to_int(row["season_year"]),
                "owner_id": _to_int(row["owner_id"]),
                "player_id": _to_int(row["player_id"]),
            })

    # --- Duplicate detection ---
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

    # --- Build valid set ---
    valid_row_mask = ~working["source_row_number"].astype(int).isin(invalid_row_numbers)
    valid_df = working.loc[valid_row_mask].copy()

    if not duplicates.empty:
        valid_df = valid_df.sort_values(
            by=["season_year", "owner_id", "player_id", "winning_bid", "source_row_number"],
            ascending=[True, True, True, False, True],
            kind="mergesort",
        )
        valid_df = valid_df.drop_duplicates(subset=duplicate_keys, keep="first")

    # --- Keeper labeling ---
    valid_df["is_keeper"] = valid_df["winning_bid"].apply(
        lambda v: v is not None and float(v) <= KEEPER_BID_THRESHOLD
    )

    validated_df = valid_df[
        [
            "player_id",
            "owner_id",
            "season_year",
            "position_id",
            "TeamID",
            "winning_bid",
            "is_keeper",
        ]
    ].rename(columns={"TeamID": "team_id"})
    validated_df = validated_df.sort_values(
        by=["season_year", "owner_id", "player_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    # --- Year completeness check ---
    year_completeness = _check_year_completeness(validated_df)

    correction_df = pd.DataFrame(correction_ledger, columns=CORRECTION_LEDGER_COLUMNS)
    error_df = pd.DataFrame(validation_errors)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_rows": int(len(working)),
        "validated_rows": int(len(validated_df)),
        "error_count": int(len(error_df)),
        "duplicate_key_count": int(len(duplicates)),
        "correction_ledger_rows": int(len(correction_df)),
        "position_resolved_count": len(resolved_position_rows),
        "keeper_count": int(validated_df["is_keeper"].sum()),
        "error_breakdown": {
            str(k): int(v)
            for k, v in error_df["issue_type"].value_counts().to_dict().items()
        } if not error_df.empty else {},
        "year_completeness": year_completeness,
    }

    return validated_df, correction_df, report


def _check_year_completeness(
    validated_df: pd.DataFrame,
    *,
    expected_min: int = EXPECTED_PICKS_MIN,
    expected_max: int = EXPECTED_PICKS_MAX,
) -> dict[str, Any]:
    """Return per-year pick counts and flag years outside the expected range."""
    if validated_df.empty:
        return {"years": {}, "flagged_years": []}

    per_year = validated_df.groupby("season_year").size().to_dict()
    years_out: list[dict[str, Any]] = []
    for yr, count in sorted(per_year.items()):
        if count < expected_min or count > expected_max:
            years_out.append({"year": int(yr), "pick_count": int(count), "expected_range": [expected_min, expected_max]})

    return {
        "years": {int(k): int(v) for k, v in sorted(per_year.items())},
        "flagged_years": years_out,
    }


def write_draft_validation_outputs(
    draft_results_csv: Path,
    players_csv: Path,
    users_csv: Path,
    positions_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """DEPRECATED: Reads source DataFrames from CSV files.

    Use ``write_draft_validation_outputs_from_dataframes()`` instead, which
    accepts DataFrames directly and is the active code path in
    ``etl/build_phase1_artifacts.py``.
    """
    import warnings
    warnings.warn(
        "write_draft_validation_outputs() reads from CSV files and is a legacy interface. "
        "Call write_draft_validation_outputs_from_dataframes() directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    draft_results_df = pd.read_csv(draft_results_csv)
    players_df = pd.read_csv(players_csv)
    users_df = pd.read_csv(users_csv)
    positions_df = pd.read_csv(positions_csv)

    return write_draft_validation_outputs_from_dataframes(
        draft_results_df=draft_results_df,
        players_df=players_df,
        users_df=users_df,
        positions_df=positions_df,
        output_dir=output_dir,
    )


def write_draft_validation_outputs_from_dataframes(
    *,
    draft_results_df: pd.DataFrame,
    players_df: pd.DataFrame,
    users_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    output_dir: Path,
    canonical_players_df: pd.DataFrame | None = None,
) -> dict[str, Any]:

    validated_df, correction_df, report = validate_historical_draft_results(
        draft_results_df,
        players_df,
        users_df,
        positions_df,
        canonical_players_df=canonical_players_df,
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
