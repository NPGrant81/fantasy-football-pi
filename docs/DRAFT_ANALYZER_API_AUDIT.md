# Draft Analyzer API Audit

Generated: 2026-03-08 21:49:04Z

## Context

- Scope: Draft Day Analyzer data paths
- Validation mode: direct router invocation with live SQLAlchemy session

## Endpoint Source Map

| Endpoint | Primary Data Source |
|---|---|
| `/draft/rankings` | PostgreSQL: draft_values, players, scoring_rules, draft_picks, keepers, player_weekly_stats |
| `/draft/model/predict` | PostgreSQL: same as /draft/rankings (+ request draft_state payload) |
| `/advisor/draft-day/query` | PostgreSQL: rankings-backed data from /draft/rankings service path |
| `/players/{id}/season-details` | PostgreSQL: players, player_weekly_stats |
| `/draft/simulation` | CSV files: backend/data/draft_results.csv, players.csv, historical_rankings.csv, draft_budget.csv |

## Dataset Health

| Dataset Check | Status | Details |
|---|---|---|
| `dataset:players` | PASS | count=933 |
| `dataset:draft_values_total` | PASS | count=2 |
| `dataset:draft_values_2025` | WARN | count=0 |
| `dataset:draft_values_2026` | PASS | count=2 |
| `dataset:player_weekly_stats_total` | WARN | count=0 |
| `dataset:scoring_rules` | PASS | count=6 |
| `dataset:draft_picks` | PASS | count=186 |
| `dataset_csv:draft_results.csv` | PASS | size=35559 |
| `dataset_csv:players.csv` | PASS | size=41761 |
| `dataset_csv:historical_rankings.csv` | PASS | size=47856 |
| `dataset_csv:draft_budget.csv` | PASS | size=535 |

## API Check Matrix

| API Check | Status | Details |
|---|---|---|
| `api:/draft/rankings?season=2025` | PASS | rows=10 |
| `api:/draft/rankings?season=2026` | PASS | rows=2 |
| `api:/draft/model/predict` | PASS | recommendations=2 |
| `api:/draft/simulation` | PASS | key_target_probabilities=10 |
| `api:/advisor/draft-day/query` | PASS | headline=Draft Day answer |
| `api:/players/{id}/season-details` | PASS | player_id=1101 games=0 |

## Findings

- `WARN` on sparse historical datasets means endpoint may function but output quality may be reduced.
- `/draft/simulation` health depends on CSV freshness/shape, not only PostgreSQL values.
