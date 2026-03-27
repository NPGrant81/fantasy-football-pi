# Issue #102 Data Source Audit

- Data directory: ./backend/data
- Dataset count: 6
- Missing files: None

## Dataset Inventory

| Dataset | Exists | Rows | Headers |
|---|---:|---:|---|
| draft_results | true | 1197 | PlayerID, OwnerID, Year, PositionID, TeamID, WinningBid |
| yearly_results | true | 473 | season, rank, player_id, player_name, position, predicted_auction_value, value_over_replacement, model_score, consensus_tier, avg_bid, median_bid, recent_3yr_avg, trend_slope, appearances |
| player_id | true | 1850 | Player_ID, PlayerName, PositionID |
| position_id | true | 9 | PositionID, Position, PositionStatus |
| budget | true | 24 | DraftBudget, Year, OwnerID |
| owner_registry | true | 35 | Team, TeamID |

## Identifier Audit

- Missing player refs in `player_id`: 0
- Missing position refs in `position_id`: 0
- Inactive/unknown position refs used in draft results: 0
- Owner ID mismatches (draft vs budget): 0
- Draft results invalid year rows: 0
- Budget invalid year rows: 0
