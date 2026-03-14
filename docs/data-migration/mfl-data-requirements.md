# MFL Data Requirements And Schema Contract

Status: Draft for Issue #256

## Objective

Define a stable extraction contract from MFL into CSV so migration/import code can be implemented without schema drift.

## Source Context

- API pattern: `https://api.myfantasyleague.com/{year}/export?TYPE={type}&L={league_id}&JSON=1`
- League URL examples provided:
  - 2026 league: `https://www46.myfantasyleague.com/2026/home/11422#0`
  - 2025 league: `https://www46.myfantasyleague.com/2025/home/11422#0`

## Confirmed Season To League Mapping (Owner-Provided)

Confirmed from shared MFL URLs:

- 2015 -> `43630`
- 2016 -> `38909`
- 2017 -> `38909`
- 2018 -> `38909`
- 2019 -> `38909`
- 2020 -> `38909`
- 2021 -> `38909`
- 2022 -> `38909`
- 2023 -> `11422`
- 2024 -> `11422`
- 2025 -> `11422`
- 2026 -> `11422`

Gap still open:

- 2002-2014 league ids not yet located.

## Report Inventory

These report families are required for complete migration coverage.

1. League metadata
  - MFL `TYPE=league`
  - Purpose: league-level settings, franchise roster, season config, cap/budget details.
2. Franchises/owners
  - MFL `TYPE=league` (franchise block) and/or `TYPE=franchises` if available.
  - Purpose: owner identity continuity across seasons.
3. Players master
  - MFL `TYPE=players`
  - Purpose: canonical player identity and lookup keys.
4. Draft results
  - MFL `TYPE=draftResults`
  - Purpose: auction history, keeper economics, draft analytics.
5. Rosters
  - MFL `TYPE=rosters`
  - Purpose: season state and ownership snapshots.
6. Standings
  - MFL `TYPE=standings`
  - Purpose: win/loss/tie and scoring totals.
7. Matchups/schedule/results
  - MFL `TYPE=schedule` and league-specific weekly results export types.
  - Purpose: weekly and head-to-head history.
8. Transactions/waivers/trades
  - MFL `TYPE=transactions`
  - Purpose: acquisition history and waiver trend analytics.

## Current Vs Historical Model

Use one extraction contract, two logical lanes in import.

1. Current lane
  - Seasons: active season only (default current year).
  - Usage: UI operational pages (rosters, waivers, lineups, commissioner tools).
2. Historical lane
  - Seasons: all prior seasons from league inception.
  - Usage: analytics, draft advisor features, historical standings/champion modules.

Rule: all CSV schemas include `season` so loaders can route records to current and historical stores deterministically.

## CSV Folder Layout

Proposed extraction output:

- `exports/history/league/{season}.csv`
- `exports/history/franchises/{season}.csv`
- `exports/history/players/{season}.csv`
- `exports/history/draft_results/{season}.csv`
- `exports/history/rosters/{season}.csv`
- `exports/history/standings/{season}.csv`
- `exports/history/schedule/{season}.csv`
- `exports/history/transactions/{season}.csv`

## CSV Schema Contracts

All files share these required metadata columns:

- `season` (int, required)
- `league_id` (string/int, required)
- `source_system` (string, required, default `mfl`)
- `source_endpoint` (string, required)
- `extracted_at_utc` (ISO timestamp, required)

### 1) league

Required columns:

- `season`
- `league_id`
- `league_name`
- `franchise_count`
- `salary_cap` (nullable decimal)
- `roster_size` (nullable int)

### 2) franchises

Required columns:

- `season`
- `league_id`
- `franchise_id`
- `franchise_name`
- `owner_name`
- `owner_email` (nullable)
- `division` (nullable)

### 3) players

Required columns:

- `season`
- `player_mfl_id`
- `player_name`
- `position`
- `nfl_team`
- `status` (nullable)

Preferred identifiers (nullable but strongly recommended):

- `gsis_id`
- `espn_id`

### 4) draft_results

Required columns:

- `season`
- `league_id`
- `franchise_id`
- `player_mfl_id`
- `pick_number` (nullable int for auction formats)
- `round` (nullable int)
- `winning_bid` (nullable decimal)
- `is_keeper_pick` (bool, default false)

### 5) rosters

Required columns:

- `season`
- `league_id`
- `franchise_id`
- `player_mfl_id`
- `roster_status` (starter/bench/ir/taxi if available)

### 6) standings

Required columns:

- `season`
- `league_id`
- `franchise_id`
- `wins`
- `losses`
- `ties`
- `points_for`
- `points_against`
- `rank` (nullable int)

### 7) schedule

Required columns:

- `season`
- `league_id`
- `week`
- `home_franchise_id`
- `away_franchise_id`
- `home_score` (nullable decimal)
- `away_score` (nullable decimal)

### 8) transactions

Required columns:

- `season`
- `league_id`
- `transaction_id`
- `week` (nullable int)
- `franchise_id`
- `transaction_type` (waiver/add/drop/trade/etc)
- `player_mfl_id` (nullable for multi-player trade header rows)
- `amount` (nullable decimal)
- `processed_at` (nullable timestamp)

## Validation Rules (for #257/#258)

1. Required columns must exist and be non-null where required.
2. Numeric fields must coerce cleanly (`season`, `wins`, `winning_bid`, etc).
3. Referential keys must be consistent within season:
  - `franchise_id` in standings/rosters/drafts/transactions exists in `franchises`.
  - `player_mfl_id` in drafts/rosters/transactions exists in `players`.
4. Duplicate handling:
  - Primary uniqueness keys per file:
    - `draft_results`: (`season`, `league_id`, `franchise_id`, `player_mfl_id`, `round`, `pick_number`)
    - `rosters`: (`season`, `league_id`, `franchise_id`, `player_mfl_id`)
    - `standings`: (`season`, `league_id`, `franchise_id`)
    - `schedule`: (`season`, `league_id`, `week`, `home_franchise_id`, `away_franchise_id`)
    - `transactions`: (`season`, `league_id`, `transaction_id`, `player_mfl_id`)

## Mapping To Existing App Concepts

High-level mapping targets:

- `franchise_id` -> app owner/user identity mapping table (season-aware alias support).
- `player_mfl_id` -> canonical player identity map (with aliases/provider IDs).
- `draft_results.winning_bid` -> `draft_picks.amount` historical rows.
- `standings` -> analytics and future standings endpoints.
- `transactions` -> acquisition/waiver trend analytics.

## Open Questions Needed From League Owner

These are the minimum answers needed before implementing #257:

1. Provide league ids for 2002-2014 seasons (or confirm inaccessible).
2. Confirm first season year to extract (assumed 2001).
3. Confirm whether all seasons are public or require authenticated session.
4. Confirm if franchise ids remain stable across years or if owner identity must be name-based fallback.
5. Confirm auction vs snake draft format by season (for `winning_bid` expectations).
6. Confirm whether preseason/offseason transactions should be included.
7. Confirm timezone preference for reporting timestamps (default UTC in CSV).

## Immediate Implementation Plan

1. Issue #257: implement extractor with per-season report pulls and CSV write.
2. Issue #258: implement importer with dry-run and strict validation.
3. Issue #259: reconciliation checks and mismatch report.
4. Issue #260: operator runbook with rerun and backfill steps.
