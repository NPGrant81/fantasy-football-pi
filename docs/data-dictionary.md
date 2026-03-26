# Data Dictionary (Issue #102)

This document defines the normalized schema baseline for core fantasy football
entities used by analytics, ML, and draft simulation pipelines.

## Source Mapping

| Canonical Entity | Current Source File | Legacy Tab Name |
|---|---|---|
| DraftResult | `backend/data/draft_results.csv` | `DraftResult` |
| YearlyResults | `draft_values` table (PostgreSQL) | `YearlyResults` |
| PlayerID | `backend/data/players.csv` | `PlayerID` |
| PositionID | `backend/data/positions.csv` | `PositionID` |
| Budget | `backend/data/draft_budget.csv` | `2024DraftBudget` |
| Owner Registry | `backend/data/teams.csv` | Owner/team mapping |

## Global Normalization Rules

- Field names should be represented in `snake_case` in transformed datasets.
- IDs must be stable and joinable across all related entities.
- `year` fields must be integer values in a valid fantasy season range.
- Position references should resolve to active positions only.
- No orphaned foreign-key style references should remain after normalization.

## Canonical Schemas

### DraftResult

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| player_id | integer | yes | Must exist in `PlayerID.player_id` | Drafted player identifier |
| owner_id | integer | yes | Must align with budget owner IDs | Team/owner who drafted player |
| year | integer | yes | 2000-2100 | Draft season |
| position_id | integer | yes | Must exist in active `PositionID.position_id` | Position mapping |
| team_id | integer | no | Optional legacy linkage | Team table identifier |
| winning_bid | numeric | yes | Non-negative | Auction value at draft |

### YearlyResults

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| season | integer | yes | 2000-2100 | Season year |
| rank | integer | no | Non-negative | Ranking order |
| player_id | integer | yes | Must exist in `PlayerID.player_id` | Player key |
| player_name | string | yes | Non-empty | Display name |
| position | string | yes | QB/RB/WR/TE/DEF/K, etc. | Position label |
| predicted_auction_value | numeric | no | Non-negative | Model estimate |
| value_over_replacement | numeric | no | Any numeric | Relative value metric |
| model_score | numeric | no | Any numeric | Composite model score |
| consensus_tier | string | no | Free text/category | Tier grouping |
| avg_bid | numeric | no | Non-negative | Avg observed bid |
| median_bid | numeric | no | Non-negative | Median observed bid |
| recent_3yr_avg | numeric | no | Non-negative | Rolling average |
| trend_slope | numeric | no | Any numeric | Trend slope indicator |
| appearances | integer | no | Non-negative | Number of observations |

### PlayerID

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| player_id | integer | yes | Unique, stable | Canonical player identifier |
| player_name | string | yes | Non-empty | Canonical player name |
| position_id | integer | yes | Must exist in `PositionID.position_id` | Canonical position reference |

### PositionID

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| position_id | integer | yes | Unique | Position identifier |
| position | string | yes | Non-empty | Position abbreviation/name |
| position_status | string | yes | `Active` or inactive category | Position lifecycle status |

### Budget

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| draft_budget | numeric | yes | Non-negative | Owner draft budget |
| year | integer | yes | 2000-2100 | Budget season |
| owner_id | integer | yes | Stable across years | Owner identifier |

### Owner Registry

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| team | string | yes | Non-empty | Display name |
| team_id | integer | yes | Unique | Team registry ID |

## Relationship Model

- `DraftResult.player_id` -> `PlayerID.player_id`
- `DraftResult.position_id` -> `PositionID.position_id`
- `PlayerID.position_id` -> `PositionID.position_id`
- `DraftResult.owner_id` <-> `Budget.owner_id` (consistency contract)
- `DraftResult.year` and `Budget.year` should align for comparable datasets

## Known Gaps (Current Repo Snapshot)

- Owner registry currently uses `team_id`; explicit `owner_id` mapping requires
  a normalization bridge for strict foreign-key style joins.

## Operational Linkage

- Automated audit script: `etl/validation/data_source_audit.py`
- Generated audit report: `docs/DATA_SOURCE_AUDIT_ISSUE_102.md`
- Generated JSON report: `reports/issue102_data_audit.json`
