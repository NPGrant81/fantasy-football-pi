# Live Scoring Reliability Runbook

Date: 2026-03-14
Scope: Live scoreboard ingestion reliability controls and operator workflow.

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
- Degraded mode signal is emitted when:
  - failover URL is required, or
  - required payload paths are missing

### Diagnostics
- API endpoint for direct run diagnostics:
  - `POST /admin/live-scoring/ingest`
- API endpoint for trend diagnostics:
  - `GET /admin/live-scoring/health?limit=50`
- API endpoint for explicit watchdog evaluation:
  - `POST /admin/live-scoring/watchdog`
- API endpoint for recent watchdog alerts:
  - `GET /admin/live-scoring/watchdog/alerts?limit=20`
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

### Hot-Fix Process
- Operators can run one-off ingest with temporary override URL:
  - `override_url` in `POST /admin/live-scoring/ingest`
- Operators can disable failover to isolate a specific endpoint issue:
  - `enable_failover=false`
- Safe dry-run mode allows payload validation with no DB writes:
  - `dry_run=true`

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
  "enable_failover": true
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
