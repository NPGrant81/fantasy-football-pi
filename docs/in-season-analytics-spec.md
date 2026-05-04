# In-Season Analytics Specification (Issue #114)

## Purpose

Define the weekly in-season intelligence contract for waiver, trade, and start/sit decisions,
with owner-specific personalization and integration-ready response shapes.

## Scope

This specification covers the first unified endpoint for weekly insight surfaces:

- `GET /analytics/league/{league_id}/in-season-insights`

The endpoint composes existing analytics modules and returns a single payload for:

- roster need detection
- waiver targeting with breakout and FAAB guidance
- trade leverage by position
- start/sit recommendations with alternatives
- proactive alerts

## Request Contract

Query parameters:

- `owner_id` (required): owner/team identifier for personalization
- `season` (optional): defaults to current year
- `waiver_limit` (optional, default `8`, range `3-20`)
- `start_sit_limit` (optional, default `10`, range `3-25`)

## Response Contract

Top-level fields:

- `owner_id`: personalized owner id
- `season`: resolved season year
- `roster_needs`: positional target/current/deficit summary
- `waiver_targets`: ranked weekly waiver candidates
- `trade_leverage`: position-level owner vs league deltas
- `start_sit_recommendations`: starter guidance + best alternative
- `alerts`: injury/start-sit/scarcity alerts
- `meta`: analytics metadata and capability flags

### `roster_needs[]`

- `position`
- `target_count`
- `current_count`
- `deficit`
- `surplus`

### `waiver_targets[]`

- `player_id`
- `player_name`
- `position`
- `nfl_team`
- `opportunity_score`
- `trend`
- `breakout_probability`
- `breakout_flag`
- `recommended_faab_bid_pct`
- `personalized_score`

### `trade_leverage[]`

- `position`
- `owner_projected_total`
- `league_avg_projected_total`
- `delta_vs_league`
- `recommended_action` (`sell_high`, `buy_help`, `hold`)
- `confidence`

### `start_sit_recommendations[]`

- `player_id`
- `player_name`
- `position`
- `nfl_team`
- `start_score`
- `projected_weekly_points`
- `recent_avg_points`
- `season_avg_points`
- `volatility_index`
- `matchup_difficulty_score`
- `recommendation` (`start`, `consider_bench`)
- `alternative` (nullable)
- `explanation`

### `alerts[]`

- `type` (`injury`, `start_sit`, `scarcity`)
- `severity`
- `player_id` (nullable)
- `player_name` (nullable)
- `message`

## Data Sources

- `draft_picks` + `players` for current owner and league rosters
- `player_weekly_stats` for trend/volatility/opportunity signals
- `league_settings.starting_slots` for positional need targets
- existing waiver opportunity analytics composition

## Personalization Rules

- Owner eligibility is validated against league membership.
- Positional deficits from league slot settings bias waiver ranking.
- FAAB recommendation percentage scales with opportunity + breakout + roster deficit.
- Start/sit recommendations prioritize replacement-adjusted alternatives.

## Integration Targets

This contract is intended for integration in:

- roster and lineup pages (start/sit + alerts)
- waiver wire surfaces (ranked targets and bid guidance)
- trade analysis context panels (leverage by position)
- chatbot in-season mode prompt context injection

## Weekly Refresh Workflow

1. Refresh/ingest weekly stats and projections.
2. Recompute waiver opportunity analytics.
3. Serve in-season insights via analytics endpoint.
4. Render updated UI surfaces and chatbot context.

## Validation and Testing

- Backend unit coverage added in `backend/tests/test_analytics.py`.
- Boundary validation remains enforced via FastAPI query constraints.
- Follow local pre-PR checks before merge.
