# Semantic Contract: Current Data Source Map

Status: Initial as-built map for [#547](https://github.com/NPGrant81/fantasy-football-pi/issues/547).
Owner: data
Contract: [Semantic Data Contract](SEMANTIC_DATA_CONTRACT.md)
Parent epic: [#540](https://github.com/NPGrant81/fantasy-football-pi/issues/540)

## Purpose and evidence boundary

This map records what current models and representative consumers actually
store or derive. It is not a declaration that all records are complete or
semantically equivalent. “Established” means the model or code explicitly
represents the mapping; it does not certify the quality of production data.
“Partial” and “Gap” identify decisions or evidence that are not established by
the current model/code examined for this phase.

The map is based on the current code in `backend/models.py`,
`backend/models_draft_value.py`, `backend/services/player_identity_service.py`,
`backend/services/live_scoring_ingest_service.py`,
`backend/services/scoring_service.py`, `backend/routers/scoring.py`,
`backend/scripts/import_mfl_csv.py`, and the consumers listed below. Projection
ETL mappings are maintained in `etl/load/load_to_postgres.py`. MFL operational
provenance is also described in
[`MFL_HISTORICAL_DATA_OPERATIONS.md`](MFL_HISTORICAL_DATA_OPERATIONS.md).

## Mapping matrix

| Semantic concept | Current persisted source and key | Current transformation / consumers | Status, gap, and owner |
|---|---|---|---|
| Canonical player | `players.id` (`Player.id`) | Runtime player records and foreign keys use this app-local integer. `Player.name`, `position`, and `nfl_team` are descriptive and can change. | **Established app key.** Not interchangeable with provider IDs. |
| Provider player identity | `players.gsis_id`, `players.espn_id`; `player_aliases(player_id, alias_name, source)`; `player_id_mappings(player_id, espn_id, yahoo_id, draftsharks_id, ...)` | ESPN live scoring resolves incoming IDs against `Player.espn_id`. Projection ETL updates `player_id_mappings`; it does not necessarily update `Player.espn_id`, so the ESPN IDs in the two stores can disagree and an ETL-resolved player can still be unmatched by live scoring. Alias helpers keep a source, but aliases are names, not provider IDs. | **Partial.** No native MFL/Sleeper IDs on `Player`, and the separate ESPN mapping stores are not guaranteed to agree. Name/position/team matching does not establish a universal provider-key contract. Provider columns and mapping ownership belong to [#526](https://github.com/NPGrant81/fantasy-football-pi/issues/526); canonicalization and confidence evidence belong to [#361](https://github.com/NPGrant81/fantasy-football-pi/issues/361). |
| App league to provider league | `league_mfl_seasons(league_id, season) -> mfl_league_id` | Explicitly maps an app league to the MFL league identifier for a particular season; MFL IDs may change from season to season. | **Established for MFL.** No common provider-neutral league identity is established. Keep provider IDs namespaced. |
| League account | `users.id`; `users.league_id` | A user row can point to one league. Member-list compatibility rules exclude `hist_%` usernames and superusers. | **Partial.** The current association does not itself describe a season-specific account-membership interval. Explicit historical-stub classification belongs to [#527](https://github.com/NPGrant81/fantasy-football-pi/issues/527). |
| Season-specific historical franchise owner | `league_history_team_owner_map(league_id, season, team_name_key) -> owner_id` | Manual, league-and-season-scoped mapping from an imported team label to an app owner. | **Partial/manual.** May have no resolved `owner_id`; it is not a complete player ownership history. Historical identity resolution remains coordinated with [#523](https://github.com/NPGrant81/fantasy-football-pi/issues/523). |
| NFL player-season attributes | `player_seasons(player_id, season)` | `PlayerSeason` stores season-specific NFL team, position, bye week, active flag, and source. `player_identity_service` upserts these values. | **Established for NFL season attributes.** This is not fantasy league membership or roster tenure. |
| Current roster association | `draft_picks(league_id, owner_id, player_id, year)` plus mutable `current_status` | `get_team_starters` selects picks whose current status is `STARTER`; it allows null-league picks alongside the requested league and does not filter by `DraftPick.year` or reconstruct the requested week's lineup. | **Partial.** A past matchup can therefore use today's starter status and picks from another year or with no league. Draft/acquisition rows plus mutable status do not establish time-varying roster membership. |
| Historical ownership events | `transaction_history(league_id, season, player_id, old_owner_id, new_owner_id, transaction_type, timestamp)` | MFL CSV import writes transaction `season` and ownership/type fields but omits `timestamp`, allowing the database default to record import time. An available transaction week is placed only in free-form `notes`. Waiver claim rows separately store a league, claimant, player, bid, and status but no season/week context. | **Partial.** MFL transaction timestamps do not establish historical event order; the noted week is not a structured field. Events are not guaranteed complete, season and owner references can be absent, and a transaction log is not a full roster snapshot. Ownership reconstruction requires coverage and reliable ordering evidence. Data-model hardening is coordinated with [#523](https://github.com/NPGrant81/fantasy-football-pi/issues/523). |
| League season | `leagues.current_season`; season-bearing rows such as `matchups.season`, `player_weekly_stats.season`, `player_seasons.season`, and `league_mfl_seasons.season` | `/matchups/week/{week_num}` has no season parameter; it selects `LeagueSettings.draft_year` or the server calendar year, not `League.current_season`. `/players/{player_id}/season-details` accepts a season but defaults to the current UTC year. The matchup response omits league and season. | **Partial.** The two candidate consumers can select different contexts unless callers supply and propagate the same season. A league's current season is not a substitute for a missing historical row season; missing season must remain unknown rather than being filled from today's setting. |
| Week and event context | `player_weekly_stats(player_id, season, week, source)`, `matchups(id, league_id, season, week, home_team_id, away_team_id)`, `nfl_games(season, week, event_id)` | All four `PlayerWeeklyStat` key columns are nullable, so its unique constraint does not prevent duplicate keys containing `NULL`. `(league_id, season, week)` is matchup scope, not row identity; `matchups.id` identifies the row, while the unique index also includes both participant IDs and only applies when season is set. | **Partial.** Matchup season and league can be null on legacy rows, and neither the weekly-stat constraint nor matchup scope is a reliable observation identity in all records. A week number alone is not unique. |
| Provider-reported player stats / points | `player_weekly_stats(player_id, season, week, source)` with `stats` JSON and nullable `fantasy_points` | Live ESPN ingestion resolves ESPN IDs, writes normalized stats and points, and upserts by player/season/week/source. Scoring CSV import inserts rows with `stats.imported_points_override`, but updates only `fantasy_points` on existing rows. The table has no league key; replace mode deletes all rows for the source/season/week, so imported values are read across leagues. | **Partial.** Neither the marker (absent on updated rows) nor the uploading league establishes point provenance. `fantasy_points` does not identify which scoring rules produced it; sources can coexist for the same player/week. `created_at` is a nullable string, not a reliable source-observation time. |
| League-calculated points | `scoring_rules(league_id, season_year, is_active, ...)`; `scoring_rule_change_logs` and scoring templates provide related audit/configuration records | `scoring_service.calculate_player_week_points` selects active rules for the league and optional season, reads a weekly stat row, and calculates from its stats; if there are no rules, it falls back to stored `fantasy_points`. The query for the weekly stat is not source-filtered and takes the newest row by ID. | **Partial.** Rules are mutable active rows; no immutable ruleset/version key is attached to each calculated result. The fallback can make a result source-reported rather than league-calculated while the caller receives a numeric score. Applicable rule selection and historical scoring context belong to [#399](https://github.com/NPGrant81/fantasy-football-pi/issues/399) and the scoring rules contract; do not label a result as reproducibly league-scored unless the applied rules and source basis are established. |
| Matchup/manager metrics | `matchups` stores participant IDs, season/week, scores, and status. `manager_efficiency` stores league/manager/season/week aggregates. | `/matchups/week/{week_num}` leaves both roster lists at their empty defaults, returns stored matchup scores, and calculates projected team totals from the selected current starters; it does not return individual player projected/actual values. `/matchups/{matchup_id}` includes player rows: `projected` comes from the scoring service, while `actual` prefers the weekly-stat payload's stored `fantasy_points` and falls back to the calculated value. | **Partial.** List and detail consumers expose different metric grains and scoring bases. Matchup score rows do not carry a scoring-definition version; `manager_efficiency` does not carry source/run or scoring-version fields. Aggregate values cannot be assumed comparable across scoring definitions without provenance. |
| Ingestion provenance | `live_scoring_ingest_events(source, season, week, scoreboard_fingerprint, created_at, ...)`; MFL `mfl_ingestion_runs`, `mfl_ingestion_files`, and `mfl_html_record_facts` | Live scoreboard events retain source, scope, fingerprint, and ingestion time. MFL run/file rows retain pipeline/source, scope, run status, git SHA, file path/checksum, and row counts; normalized HTML facts retain endpoint/URL, extracted time, normalization version, and row fingerprint. | **Partial but useful per pipeline.** These fields are not uniformly attached to served stat or metric rows; no claim that all sources have equivalent run-level evidence. Extraction/ETL contracts remain in [#398](https://github.com/NPGrant81/fantasy-football-pi/issues/398) and [#523](https://github.com/NPGrant81/fantasy-football-pi/issues/523). |
| Freshness / absence | No common freshness state on `PlayerWeeklyStat`, `Matchup`, or analytics result rows | Some ingestion records have created/extracted times. Analytics metadata commonly reports `computed_at` and the currently active scoring profile; this is calculation time/current configuration, not the source's observed time or the rules used historically. | **Gap.** There is no shared source-specific freshness policy or `fresh`/`stale`/`unknown` state for these consumers. Empty rows, unavailable inputs, and unknown coverage must not be collapsed into `no_data`. Define adapter degradation and freshness behavior in [#398](https://github.com/NPGrant81/fantasy-football-pi/issues/398) and [#400](https://github.com/NPGrant81/fantasy-football-pi/issues/400). |

## Consumer findings and candidates for #549

The following two consumers are selected as candidates because together they
exercise source-reported player points and league-calculated matchup points
across the player and matchup API surfaces:

1. `GET /players/{player_id}/season-details`
   (`backend/routers/players.py::get_player_season_details`) reads weekly
   `PlayerWeeklyStat` rows for a player and season, then returns weekly and
   season aggregates.
2. `GET /matchups/week/{week_num}`
   (`backend/routers/matchups.py::get_weekly_matchups`) scopes matchups by
   league, season, and week, then builds starter projections/actuals through
   `scoring_service.calculate_player_week_points`.

These are candidates, not an assertion that current outputs already satisfy
the contract. The source map found concrete parity decisions for #549:

- The season-details endpoint does not filter or group `PlayerWeeklyStat` by
  `source`; because the stored uniqueness key includes source, rows from
  multiple sources can be counted as separate weeks and summed together.
- Its empty-result response reports zero aggregates, while a measured zero is
  distinct from missing or unavailable data under the contract.
- The scoring service's weekly-stat lookup also does not select a source
  explicitly; it picks the latest row by ID. When no active scoring rules
  exist, it falls back to that row's stored points.
- Matchup responses expose numeric `projected` and `actual` values but do not
  expose the source basis, selected weekly-stat source, or immutable scoring
  definition that would make historical results reproducible.
- Analytics `_analytics_meta()` reports computation time and the active
  scoring profile. That profile is mutable current configuration, not proof of
  which rules produced a stored historical metric.

For #549, first define an explicit source-selection policy and distinguish
source-reported from league-calculated points. Tests should verify those
semantics across these candidate surfaces and preserve unknown/absent states.
If source choice or historical scoring cannot be proven from current data,
keep the output provisional/unknown; do not introduce a default source,
recalculate stored history, or change data/API semantics silently. Any
behavior-changing compatibility plan must be reviewed before implementation.

## Boundaries and next actions

- #547 is documentation and source mapping only: no schema, API, or persisted
  data changes are included.
- #549 owns the shared-definition adoption and consumer contract tests, using
  the two candidates above unless implementation review finds a blocking
  dependency.
- Provider identity columns/classification, settings propagation, adapter
  contracts, graceful degradation, and historical ingestion hardening remain
  with #526/#527, #399, #398/#400, and #523 respectively.
- A future DDL or data reinterpretation remains gated by a separate
  compatibility and migration plan; this map is not production-database
  evidence.
