# Draft Analyzer API Audit

Generated: 2026-03-29 21:47:48Z

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
| `/draft/simulation` | PostgreSQL: draft_picks, players, draft_values, draft_budgets, league users |

## Dataset Health

| Dataset Check | Status | Details |
|---|---|---|
| `dataset:players` | PASS | count=30690 |
| `dataset:draft_values_total` | PASS | count=609 |
| `dataset:draft_values_2025` | PASS | count=473 |
| `dataset:draft_values_2026` | PASS | count=136 |
| `dataset:player_weekly_stats_total` | WARN | count=0 |
| `dataset:scoring_rules` | PASS | count=87 |
| `dataset:draft_picks` | PASS | count=1197 |
| `dataset:draft_budgets` | PASS | count=36 |
| `optional_export:historical_rankings.csv` | PASS | size=245 |

## API Check Matrix

| API Check | Status | Details |
|---|---|---|
| `api:/draft/rankings?season=2025` | PASS | rows=10 |
| `api:/draft/rankings?season=2026` | PASS | rows=10 |
| `api:/draft/model/predict` | PASS | recommendations=5 |
| `api:/draft/simulation` | PASS | key_target_probabilities=10 |
| `api:/advisor/draft-day/query` | PASS | headline=Draft Day answer |
| `api:/players/{id}/season-details` | PASS | player_id=1001 games=0 |

## Findings

- `WARN` on sparse historical datasets means endpoint may function but output quality may be reduced.
- `/draft/simulation` now runs from PostgreSQL-backed league data; legacy exports are optional diagnostics only.
