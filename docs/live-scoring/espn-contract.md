# ESPN Live Scoring Contract

Date: 2026-05-06  
Issue: #263  
Scope: Endpoint discovery plus normalized data contracts for live scoring ingestion.

## Purpose

ESPN payloads are undocumented and may drift without notice. This contract defines:

1. Which upstream endpoints are required.
2. Which request parameters we rely on.
3. How raw payloads map to stable internal models.
4. Where known inconsistencies exist and how ingestion must normalize them.

This document is the authoritative contract for Layer A ingestion of live NFL game data.

## Upstream Endpoint Inventory

### A. Scoreboard (required, currently used)

Primary:
- `GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`

Backup/failover candidates currently used:
- `GET https://cdn.espn.com/core/nfl/schedule?xhr=1`
- `GET https://cdn.espn.com/core/nfl/scoreboard?xhr=1`

Required parameters:
- `year` or `dates`: integer season year (for example `2026`)
- `week`: integer regular-season week (optional for year-only pull)
- `seasontype`: use `2` for regular season when needed
- `limit`: high limit for full slate retrieval when supported
- `xhr=1`: required by some core ESPN endpoints

Usage in code:
- URL builder and failover logic are implemented in `backend/services/live_scoring_ingest_service.py`.
- Required contract path checks are implemented in `backend/services/live_scoring_contract.py`.

### B. Game Summary (required for full #262 pipeline, discovery phase in #263)

Candidate ESPN endpoint shape:
- `GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}`

sportsapis.dev wrapper usage:
- Use provider-specific game summary route that resolves to ESPN summary by event id.

Required parameters:
- `event` or equivalent game identifier

### C. Play-by-Play (required for full #262 pipeline, discovery phase in #263)

Candidate ESPN endpoint shape:
- `GET https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={event_id}`

sportsapis.dev wrapper usage:
- Use provider-specific play-by-play route resolved by event id.

Required parameters:
- `gameId` or equivalent event identifier
- `xhr=1` for ESPN core endpoint shape

### D. Player Metadata (supporting endpoint)

Candidate ESPN source families:
- Athlete records embedded in summary/play-by-play payloads.
- ESPN athlete lookup endpoints when enrichment is required.

Required output fields for contract mapping:
- Stable provider id (`player_espn_id`)
- Display name
- Position abbreviation
- Team abbreviation when available

### E. Team Metadata (supporting endpoint)

Source shape:
- Team metadata from event competitors in scoreboard/summary payloads.

Required output fields:
- `team_id`
- `team_abbr`
- Home/away role for game context

## Required Scoreboard JSON Paths

The following paths are currently required for scoreboard acceptance (contract inspection):

- `events`
- `events[].id`
- `events[].season.year`
- `events[].competitions[].date`
- `events[].competitions[].status.type.name`
- `events[].competitions[].competitors[].homeAway`
- `events[].competitions[].competitors[].team.id`
- `events[].competitions[].competitors[].team.abbreviation`
- `events[].competitions[].competitors[].score`

If any path is missing, ingestion proceeds in degraded mode and emits drift diagnostics.

## Known ESPN Inconsistencies and Normalization Rules

1. Scoreboard source shape differs between `site.api` and `cdn/core` endpoints.
2. Numeric fields may be strings (`"24"`) and must be parsed to numeric types.
3. `homeAway` markers may be missing or inconsistent; fallback to competitor order is required.
4. Week may be absent in event payloads; ingest overrides may provide week context.
5. Leader stats are not guaranteed for every competitor, category, or athlete.
6. Athlete names may appear as `displayName` or `fullName`; ingestion must support both.
7. Stat category labels vary (`passingYards`, `fantasyPoints`, spacing/casing differences).
8. Kickoff timestamps may be malformed or absent; parser must tolerate nulls.

## Internal Data Contracts

These internal contracts are ingestion outputs. They are independent from raw ESPN payload shape.

### 1) Game Contract

```json
{
  "event_id": "401772001",
  "season": 2026,
  "week": 1,
  "kickoff_utc": "2026-09-10T20:20:00+00:00",
  "status": "IN",
  "home_team_id": 2,
  "away_team_id": 9,
  "home_team_abbr": "BUF",
  "away_team_abbr": "LAR",
  "home_score": 24,
  "away_score": 17
}
```

Canonical model:
- `NormalizedGame` in `backend/schemas/live_scoring.py`

Idempotency key:
- `event_id`

### 2) Team Contract

```json
{
  "team_id": 2,
  "team_abbr": "BUF",
  "home_away": "home"
}
```

Notes:
- Team data is currently embedded in game context and not persisted as a standalone ingestion table in this layer.

### 3) Player Contract

```json
{
  "player_espn_id": "1001",
  "player_name": "Home QB",
  "position": "QB",
  "team_abbr": "BUF"
}
```

Canonical model fields live in:
- `NormalizedPlayerStat` in `backend/schemas/live_scoring.py`

### 4) Play Event Contract (definition for summary/pbp expansion)

```json
{
  "event_id": "401772001",
  "play_id": "401772001_3421",
  "sequence": 3421,
  "clock": "04:11",
  "period": 4,
  "down": 3,
  "distance": 8,
  "yard_line": "BUF 42",
  "play_type": "pass",
  "description": "QB complete to WR for 12 yards",
  "offense_team_abbr": "BUF",
  "defense_team_abbr": "LAR",
  "participants": [
    {
      "player_espn_id": "1001",
      "role": "passer"
    },
    {
      "player_espn_id": "1055",
      "role": "receiver"
    }
  ]
}
```

Idempotency key:
- `(event_id, play_id)`

### 5) Scoring Event Contract (definition for fantasy scoring engine)

```json
{
  "event_id": "401772001",
  "play_id": "401772001_3421",
  "scoring_event_id": "401772001_3421_pass_td",
  "player_espn_id": "1001",
  "team_abbr": "BUF",
  "category": "pass_td",
  "raw_value": 1,
  "derived_points": 4.0,
  "occurred_at_utc": "2026-09-10T23:41:00+00:00",
  "metadata": {
    "yards": 12
  }
}
```

Idempotency key:
- `scoring_event_id` (or deterministic hash of event/play/category/player)

## Current Normalized Payload Envelope

The current ingestion envelope is:

```json
{
  "source": "espn_site_api_v2",
  "schema_version": "2026-03-14",
  "generated_at_utc": "...",
  "games": [],
  "player_stats": []
}
```

Canonical model:
- `NormalizedLiveScoringPayload` in `backend/schemas/live_scoring.py`

## Validation and Drift Policy

1. Contract inspection runs before mapping.
2. Missing required paths are recorded in `missing_paths`.
3. Any non-empty `missing_paths` marks the run degraded.
4. Degraded runs are still logged and may proceed depending on endpoint availability and payload viability.
5. All runs must record fetch diagnostics and contract diagnostics for operator triage.

## Mapping Rules Implemented Today

1. Normalize status to uppercase (`IN`, `FINAL`, `PRE`).
2. Parse scores to integers; default to `0` when absent.
3. Normalize stat keys by lowercasing, replacing spaces with underscores, and stripping non-alphanumeric characters.
4. Merge duplicate player stat rows by `(event_id, player_espn_id, season, week)`.
5. Prefer first non-null values when merging (`fantasy_points`, `position`, `team_abbr`).

## Open Gaps for Follow-On Issues

1. Add formal summary endpoint contract tests and fixtures.
2. Add formal play-by-play endpoint contract tests and fixtures.
3. Persist play events and scoring events to dedicated tables.
4. Add schema-versioned JSON fixtures for known ESPN drift scenarios.
5. Add source-specific parser adapters for sportsapis.dev response wrappers.

## References

- Issue #262: Live Scoring Integration umbrella
- Issue #263: ESPN API discovery and contract definition
- `backend/services/live_scoring_contract.py`
- `backend/services/live_scoring_ingest_service.py`
- `backend/schemas/live_scoring.py`
- `backend/tests/test_live_scoring_contract.py`
- `docs/LIVE_SCORING_RELIABILITY_RUNBOOK.md`
