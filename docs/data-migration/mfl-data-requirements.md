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

Confirmed from current shared MFL home page URLs and validated against the 2026 league history block:

- 2002 -> `29721`
- 2003 -> `39069`
- 2004 -> `46417`
- 2005 -> `20248`
- 2006 -> `22804`
- 2007 -> `14291`
- 2008 -> `48937`
- 2009 -> `24809`
- 2010 -> `10547`
- 2011 -> `15794`
- 2012 -> `33168`
- 2013 -> `16794`
- 2014 -> `23495`
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

- 2001 season league id not yet located (if league existed in 2001).

Technical extraction risk:

- 2002 and 2003 use different public hosts than the newer seasons:
  - 2002 home -> `https://www47.myfantasyleague.com/2002/home/29721`
  - 2003 home -> `https://www44.myfantasyleague.com/2003/home/39069`
- Public HTML report pages for history and stats are reachable on those hosts via `options?L=<league_id>&O=<code>`.
- API export coverage for 2002-2003 still needs explicit rerun verification after correcting the league ids above.
- Manual CSV fallback remains available if either API export or HTML scraping proves incomplete.

## Legacy Seasons Manual Fallback (2002-2003)

When API extraction or HTML page scraping is blocked or incomplete, use the manual CSV fallback path.

1. Scaffold templates:
  - `python -m backend.manage scaffold-mfl-manual-csv --start-year 2002 --end-year 2003`
2. Fill generated files under `exports/history_manual/`:
  - `franchises/{season}.csv`
  - `players/{season}.csv`
  - `draftResults/{season}.csv`
3. Import with existing importer in dry-run mode first:
  - `python -m backend.manage import-mfl-csv --input-root exports/history_manual --target-league-id <APP_LEAGUE_ID> --start-year 2002 --end-year 2003`
4. Apply once dry-run results are clean:
  - Add `--apply` to the command above.

Notes:

- Manual fallback currently focuses on draft-history minimum viable migration (`franchises`, `players`, `draftResults`).
- History/stat pages such as League Champions, League Awards, and record reports should first be attempted through the HTML `options?O=` pages documented in `mfl-extraction-matrix.md`.
- Keep required metadata fields populated (`season`, `league_id`, `source_system`, `source_endpoint`, `extracted_at_utc`).
- Use `source_endpoint=manual_csv` for rows transcribed from manual exports/snapshots.

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