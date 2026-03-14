# Player Metadata Rules

## Purpose
Define stable identity rules for players and separate identity from time-varying state.

## Canonical Identity
- Canonical key: `players.id`.
- Provider IDs (`gsis_id`, `espn_id`) are stable identity attributes.
- `player_name` is display metadata, not a primary join key.

## Dependent Attributes
Attributes that can change over time must be season- or week-scoped.

- Season-scoped table: `player_seasons`
  - `player_id`
  - `season`
  - `nfl_team`
  - `position`
  - `bye_week`
  - `is_active`
  - `source`
- Week-scoped table: `player_weekly_stats`
  - `player_id`, `season`, `week`, `source`, stats payload
- Season projections/value tables
  - `platform_projections` and `draft_values` keyed by `player_id + season`

## Alias Handling
- Store alternate display names in `player_aliases`.
- Keep one canonical alias (`is_primary=true`) per player from trusted source.
- Resolve inbound name-only records to canonical `player_id` through alias mapping before inserts.

## Ingestion Rules
- Ingestion must resolve `player_id` first, then write dependent rows.
- Do not create a new `players` row for team changes or seasonal roster movement.
- Daily/season sync jobs must upsert `player_seasons` for the target season.

## Rookies
- Add rookies as new canonical `players` rows only when no provider-id or alias match exists.
- Create primary alias and current-season `player_seasons` row at insert time.

## Trades / Team Changes
- Update `player_seasons` row for the season, never duplicate player identity.
- Preserve prior seasons unchanged.

## Retired / Inactive Players
- Keep canonical `players` row.
- Set `player_seasons.is_active=false` for seasons where player is inactive.
- Historical facts remain queryable via `player_id` foreign keys.

## Validation Checks
- Uniqueness: `player_seasons (player_id, season)`.
- Uniqueness: `player_aliases (player_id, alias_name, source)`.
- No duplicate canonical rows for same provider IDs.
- No dependent table rows referencing missing `players.id`.

## Current Implementation Notes (Phase 1)
- Added `player_seasons` and `player_aliases` models and migration.
- Added `backend/services/player_identity_service.py` for shared upsert logic.
- Updated active sync scripts to populate season-dependent rows.
