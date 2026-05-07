# Live Scoring Reliability Runbook

Date: 2026-03-14
Scope: Live scoreboard ingestion reliability controls and operator workflow.

Last updated: 2026-05-06 (Issues #263-#265 hardening)

## What Is Implemented

### Detection
- Every ingest run captures fetch diagnostics:
  - attempted URLs
  - latency per attempt
  - status code and error signature per attempt
  - whether failover was used
- Watchdog checks are available through Admin tools and can also run on a scheduler when enabled.
- Contract drift detection is built into ingest result:
  - `missing_required_paths_count`
  - `missing_required_paths`
- Deep event contract checks are enabled by default on ingest:
  - summary contract (`espn_summary_primary`)
  - play-by-play contract (`espn_play_by_play_primary`)
  - response field: `event_contracts[]`
- Degraded mode signal is emitted when:
  - failover URL is required, or
  - required payload paths are missing
- Polling cycle output includes state-transition and change-detection metadata:
  - `state_transitions[]`
  - `scoreboard_fingerprint`
  - `change_detected`
  - `downstream_updates_triggered`
- Reconciliation output includes matchup projection snapshots:
  - `matchup_projection_snapshots[]`
  - `home_projected` / `away_projected`
  - `home_win_probability` / `away_win_probability`

### Diagnostics
- API endpoint for direct run diagnostics:
  - `POST /admin/live-scoring/ingest`
  - default behavior includes deep checks for up to 3 events (`event_contracts_limit=3`)
- API endpoint for trend diagnostics:
  - `GET /admin/live-scoring/health?limit=50`
- API endpoint for explicit watchdog evaluation:
  - `POST /admin/live-scoring/watchdog`
- API endpoint for recent watchdog alerts:
  - `GET /admin/live-scoring/watchdog/alerts?limit=20`
- API endpoint for current polling runtime status:
  - `GET /admin/live-scoring/polling/status`
- API endpoint for recent polling cycle records:
  - `GET /admin/live-scoring/polling/cycles?limit=50`
- API endpoint for polling cycle aggregate summary:
  - `GET /admin/live-scoring/polling/summary?limit=50`
  - returns `status_counts` and `mode_counts` for recent cycles
- Health summary includes:
  - success/failure/degraded counts
  - failure rate
  - top error signatures
  - last run payload

### Redundancy / Backup
- Multiple candidate URLs are attempted in order:
  1. primary source URL
  2. backup source URL (when failover is enabled)
- Automatic failover is enabled by default.
- Automatic watchdog scheduling defaults to Sunday-focused cron behavior when enabled:
  - day of week: `sun`
  - hour: `*`
  - minute: `*/5`
- Non-Sunday coverage is still supported through interval mode or cron env overrides.
- Live polling scheduler supports active vs idle cadence:
  - active window interval: 15-30s target (default 20s)
  - idle window interval: slower polling (default 90s)
  - change guard prevents downstream scoring updates when scoreboard fingerprint is unchanged

### Hot-Fix Process
- Operators can run one-off ingest with temporary override URL:
  - `override_url` in `POST /admin/live-scoring/ingest`
- Operators can disable failover to isolate a specific endpoint issue:
  - `enable_failover=false`
- Safe dry-run mode allows payload validation with no DB writes:
  - `dry_run=true`
- Deep check controls are tunable per run:
  - `inspect_event_contracts_enabled` (default `true`)
  - `event_contracts_limit` (default `3`)

### Long-Term Antifragile Storage
- Every ingest run is persisted to append-only JSONL run log:
  - `backend/data/ingest_health/live_scoring_ingest_runs.jsonl`
- Stored fields include:
  - timestamp
  - mode (`dry_run` or `apply`)
  - status (`success` or `failed`)
  - error signature
  - fetch attempts/used URL/failover flag
  - normalized row counts

## Production Defaults (Recommended)

Use these values as a stable baseline for Sunday live windows on the Raspberry Pi deployment.

- `LIVE_SCORING_RATE_LIMIT_SECONDS=0.25`
  - Why: keeps outbound ESPN traffic controlled while still allowing near-real-time refresh cadence.
- `LIVE_SCORING_CACHE_TTL_SECONDS=15`
  - Why: reduces duplicate external calls and transient source pressure; keeps freshness within acceptable live-scoring tolerance.
- `LIVE_SCORING_STORE_RAW_RESPONSES=1`
  - Why: preserves forensic payload evidence for incident triage and contract drift analysis.
- `LIVE_SCORING_RAW_RESPONSE_MAX_FILES=500`
  - Why: caps disk growth in sustained live windows.
- `LIVE_SCORING_RAW_RESPONSE_MAX_AGE_SECONDS=604800`
  - Why: keeps one week of snapshots, covering game-day to postmortem review cycle.
- `LIVE_SCORING_POLLING_ENABLED=1` (when live polling is desired)
  - Why: enables scheduled polling cycle for live game windows.
- `LIVE_SCORING_POLL_ACTIVE_INTERVAL_SECONDS=20`
  - Why: balances update timeliness with external API pressure during active games.
- `LIVE_SCORING_POLL_IDLE_INTERVAL_SECONDS=90`
  - Why: reduces noise and load when no games are live.
- `LIVE_SCORING_POLL_TICK_SECONDS=15`
  - Why: keeps scheduler responsive while interval-gate logic enforces active/idle cadence.
- `LIVE_SCORING_POLL_INSPECT_EVENT_CONTRACTS=0`
  - Why: keeps poll path lightweight by default; deep checks remain available for explicit ingest runs.

Retention behavior in code:
- Raw payload snapshots are pruned after each successful write.
- Pruning order is age-based first, then file-count based (oldest first).
- Pruning failures are logged as warnings and do not fail ingestion.

Suggested higher-load fallback profile (if CPU or disk pressure appears on Pi):
- `LIVE_SCORING_RATE_LIMIT_SECONDS=0.5`
- `LIVE_SCORING_CACHE_TTL_SECONDS=20`
- `LIVE_SCORING_RAW_RESPONSE_MAX_FILES=300`
- `LIVE_SCORING_RAW_RESPONSE_MAX_AGE_SECONDS=259200` (3 days)
- `LIVE_SCORING_POLL_ACTIVE_INTERVAL_SECONDS=30`
- `LIVE_SCORING_POLL_IDLE_INTERVAL_SECONDS=120`

## Polling State Semantics
- Statuses are normalized into phases for transition tracking:
  - `pre` (scheduled/not started)
  - `live` (in progress)
  - `halftime`
  - `final`
- Transition examples:
  - `pre -> live` at kickoff
  - `live -> halftime`
  - `halftime -> live`
  - `live -> final`

## Change-Only Downstream Triggering
- Polling passes the previous scoreboard fingerprint into ingest as a change guard.
- If fingerprint is unchanged:
  - ingest mode returns `apply_skipped`
  - DB write/upsert and downstream matchup recalculation are skipped
  - response sets `downstream_updates_triggered=false`
- If fingerprint changes:
  - ingest runs in `apply` mode
  - downstream matchup recalculation is allowed
  - response sets `downstream_updates_triggered=true`

## Operator Playbook

### 1) Detect an Incident
- Call:
  - `GET /admin/live-scoring/health?limit=100`
- Trigger incident when any condition is true:
  - failure rate > 0.20 over recent runs
  - degraded runs spike above baseline
  - repeated same error signature in top errors

### 2) Diagnose Quickly
- Run a dry diagnostic fetch:
  - `POST /admin/live-scoring/ingest` with `{ "year": <year>, "week": <week>, "dry_run": true }`
- Inspect:
  - `fetch_diagnostics.attempts`
  - `missing_required_paths`
  - `degraded`

### 3) Activate Backup/Fallback
- Keep `enable_failover=true` (default).
- If both standard URLs are failing, use a temporary mirror endpoint via `override_url`.

### 4) Execute Hot Fix
- Validate with dry-run first using the hot-fix override URL.
- If dry-run results are healthy, run apply mode using same override URL.
- Keep incident notes linked to issue #264.

### 5) Harden Long-Term
- Review run log weekly and track:
  - error signatures that recur
  - URL-specific failure patterns
  - contract path drift trends
- Promote recurring failures into:
  - source contract updates
  - parser fallbacks
  - test fixtures reproducing the failure shape

## Suggested Alert Thresholds
- P1: `failure_rate >= 0.50` (last 20 runs)
- P2: `degraded_runs >= 5` (last 20 runs)
- P2: same error signature appears >= 3 times in last 20 runs

## Example Dry-Run Payload
```json
{
  "year": 2026,
  "week": 1,
  "dry_run": true,
  "timeout_seconds": 20,
  "enable_failover": true,
  "inspect_event_contracts_enabled": true,
  "event_contracts_limit": 3
}
```

## Example Hot-Fix Payload
```json
{
  "year": 2026,
  "week": 1,
  "dry_run": false,
  "override_url": "https://<temporary-mirror>/scoreboard",
  "enable_failover": false
}
```
