# MFL HTML Records Normalization Plan

Status: Draft v1 (implementation-ready mapping contract)

## Purpose

Define deterministic normalization rules for the extracted HTML report families so they can be consumed consistently by analytics/import pipelines.

Source extracts covered:
- `league_champions`
- `league_awards`
- `franchise_records`
- `player_records`
- `matchup_records`
- `all_time_series_records`
- `season_records`
- `career_records`
- `record_streaks`

Primary extraction roots:
- `backend/exports/history_html_records_2002_2003`
- `backend/exports/history_html_records_2004_2026`

## Shared Metadata Contract

All normalized outputs keep these fields:
- `season` (int): extraction season context
- `league_id` (string)
- `source_system` (string): expected `mfl_html`
- `source_endpoint` (string): report key
- `source_url` (string)
- `extracted_at_utc` (string ISO timestamp)
- `normalization_version` (string): start with `v1`

## Target Normalized Datasets

### 1) `html_league_champions_normalized`

Source shape issue:
- Columns are year-specific (`2002_place`, `2002_franchise`, ..., `2025_place`, `2025_franchise`) and vary by extraction year.

Normalization rules:
- Unpivot paired columns matching regex: `^(\d{4})_(place|franchise)$`.
- Emit one row per `(champion_season, place, franchise)`.
- Parse place text like `"1."` to `place_rank = 1`.

Target fields:
- shared metadata
- `champion_season` (int)
- `place_text` (string)
- `place_rank` (int, nullable)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)

### 2) `html_league_awards_normalized`

Source shape:
- Already close to row format with `report_season`, `award_title`, `franchise`.

Normalization rules:
- Cast `report_season` to int where possible.
- Keep `award_title` as controlled free-text (no lossy remap in v1).

Target fields:
- shared metadata
- `award_season` (int, nullable)
- `award_title` (string)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)

### 3) `html_franchise_records_normalized`

Source shape:
- Rank + franchise + context columns (`year`, `week`, `pts`).

Normalization rules:
- `value` -> `record_rank` numeric.
- `pts` -> float.
- Keep `week` nullable int.

Target fields:
- shared metadata
- `record_rank` (int, nullable)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)
- `record_year` (int, nullable)
- `record_week` (int, nullable)
- `points` (float, nullable)

### 4) `html_player_records_normalized`

Source shape:
- Includes `player`, `ovr`, `status`, `pts`, `year`, `week`.

Normalization rules:
- Parse `player` tail tokenization into optional `nfl_team` and `position` where pattern matches `Name TEAM POS`.
- Preserve full `player` string as source-of-truth.

Target fields:
- shared metadata
- `record_rank` (int, nullable) from `value`
- `overall_rank` (int, nullable) from `ovr`
- `player_display_raw` (string)
- `player_name` (string, nullable)
- `nfl_team` (string, nullable)
- `position` (string, nullable)
- `owner_context_raw` (string, nullable) from `status`
- `record_year` (int, nullable)
- `record_week` (int, nullable)
- `points` (float, nullable)

### 5) `html_matchup_records_normalized`

Source shape:
- Matchup pair with both team names/scores and derived metrics.

Normalization rules:
- Cast numeric fields (`pts`, `pts_1`, `combined_score`, `margin_of_victory`) to float.
- Keep both home/away names as text.

Target fields:
- shared metadata
- `record_rank` (int, nullable)
- `away_franchise_raw` (string)
- `home_franchise_raw` (string)
- `away_points` (float, nullable)
- `home_points` (float, nullable)
- `record_year` (int, nullable)
- `record_week` (int, nullable)
- `combined_score` (float, nullable)
- `margin_of_victory` (float, nullable)

### 6) `html_all_time_series_normalized`

Source shape issue:
- Wide year columns (`2002_w_l_t`, ..., `2026_w_l_t`) with summary columns (`total_w_l_t`, `pct`).

Normalization rules:
- Unpivot columns matching `^(\d{4})_w_l_t$` into rows.
- Parse `W-L-T` text into integer `wins/losses/ties`.
- Keep total summary as separate columns on each emitted row (or split to companion summary table in v2).

Target fields:
- shared metadata
- `opponent_franchise_raw` (string)
- `series_season` (int)
- `season_w_l_t_raw` (string)
- `season_wins` (int, nullable)
- `season_losses` (int, nullable)
- `season_ties` (int, nullable)
- `total_w_l_t_raw` (string, nullable)
- `total_pct` (float, nullable)

### 7) `html_season_records_normalized`

Source shape:
- Per-franchise season outcome rows with `w/l/t/pf/pa`.

Normalization rules:
- Cast w/l/t to ints and pf/pa to floats.

Target fields:
- shared metadata
- `record_rank` (int, nullable)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)
- `record_year` (int, nullable)
- `wins` (int, nullable)
- `losses` (int, nullable)
- `ties` (int, nullable)
- `points_for` (float, nullable)
- `points_against` (float, nullable)

### 8) `html_career_records_normalized`

Source shape:
- Franchise lifetime summary metrics.

Normalization rules:
- Cast numeric fields (`w/l/t/pct/pf/avg_pf/pa/avg_pa`) appropriately.
- Preserve `seasons` as raw CSV text in v1.

Target fields:
- shared metadata
- `record_rank` (int, nullable)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)
- `wins` (int, nullable)
- `losses` (int, nullable)
- `ties` (int, nullable)
- `win_pct` (float, nullable)
- `points_for` (float, nullable)
- `avg_points_for` (float, nullable)
- `points_against` (float, nullable)
- `avg_points_against` (float, nullable)
- `seasons_raw` (string, nullable)

### 9) `html_record_streaks_normalized`

Source shape:
- Streak rows with start week/length/type.

Normalization rules:
- Cast week and streak length to ints.
- Normalize `streak_type` casing (`Winning`, `Losing`, etc.) without changing meaning.

Target fields:
- shared metadata
- `record_rank` (int, nullable)
- `franchise_name_raw` (string)
- `franchise_name_clean` (string)
- `record_year` (int, nullable)
- `start_week` (int, nullable)
- `streak_length` (int, nullable)
- `streak_type` (string)

## Text Cleanup Policy

Some values include encoding artifacts (for example curly quotes rendered as replacement characters).

v1 policy:
- Keep `*_raw` text exactly as extracted.
- Create `*_clean` where cleanup is reversible/safe:
  - trim whitespace
  - collapse repeated spaces
  - normalize obvious mojibake quote artifacts when confidently mappable
- Never overwrite raw text.

## Validation Rules

Required checks per report:
1. Source row count preserved after normalization, except intentional unpivot (where row count increases deterministically).
2. Shared metadata populated on all rows.
3. Numeric casts tracked with null-rate metrics.
4. Unpivoted year keys constrained to `2002..2026`.

Additional checks:
- `league_champions`: each `(champion_season, place_rank)` should be unique per league_id.
- `all_time_series`: parsed wins/losses/ties should be non-negative ints when present.

## Implementation Sequence

1. Build one normalization script that reads report CSVs from a root and writes normalized outputs to a sibling root:
   - input example: `backend/exports/history_html_records_2004_2026`
   - output example: `backend/exports/history_html_records_2004_2026_normalized`
2. Implement transforms in this order:
   - `league_awards`, `franchise_records`, `season_records` (lowest complexity)
   - `player_records`, `matchup_records`, `career_records`, `record_streaks`
   - `league_champions`, `all_time_series_records` (unpivot complexity)
3. Add fixture tests for unpivot logic and numeric parsing edge cases.
4. Add run summary JSON with:
   - input files processed
   - output rows written per normalized dataset
   - parse warnings/errors

## Open Questions

1. Should `league_champions` be represented as one canonical table or split by place buckets?
2. Should `career_records.seasons_raw` be parsed into a child table in v2?
3. For `player_records.status`, do we need owner/team split now or defer?
4. Do we want a single cross-report normalized table (`record_type` discriminator) in addition to per-report outputs?
