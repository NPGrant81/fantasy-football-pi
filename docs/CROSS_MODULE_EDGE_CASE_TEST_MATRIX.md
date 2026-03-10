# Cross-Module Edge-Case Test Matrix (Issue #155)

Date: 2026-03-10
Owner: feat/issue-155-edge-case-matrix
Related Issues: #155

## Purpose
This matrix tracks cross-module brittle-boundary scenarios and links each to automated coverage so reliability regressions are visible and actionable.

## Matrix
| ID | Scenario | Module | Expected Behavior | Automated Coverage | Status |
|---|---|---|---|---|---|
| CM-01 | Matchup detail with empty away roster and partial scoring data | `matchups` router GameCenter payload | Endpoint returns valid payload; empty roster side remains `[]` with `0.0` projected points and stable win probabilities | `backend/tests/test_matchups_scoring_router.py::test_get_matchup_detail_handles_empty_away_roster` | Added (this pass) |
| CM-02 | Historical playoff bracket retrieval with no live match rows | `playoffs` router read path | Historical season requests fall back to stored snapshot payload and include snapshot-source metadata | `backend/tests/test_playoff_router.py::test_get_bracket_falls_back_to_historical_snapshot_when_matches_missing` | Added (this pass) |
| CM-03 | Waiver budget API when keeper lock ledger entries exist | `league` router waiver budgets + ledger model interaction | FAAB balances ignore non-FAAB currency entries (for example `DRAFT_DOLLARS` keeper locks) | `backend/tests/test_waiver_budgets.py::test_get_waiver_budgets_ignores_keeper_lock_currency` | Added (this pass) |
| CM-04 | Legacy NULL `league_id` matchups in owner standings context | `league` router owner standings aggregation | NULL-league historical matchup rows are ignored for league-scoped owner standings | `backend/tests/test_league_owners_api.py::test_get_league_owners_ignores_legacy_null_league_matchups` | Added (this pass) |
| CM-05 | Analytics query boundaries: malformed season and out-of-range weeks | `analytics` router API boundary validation | Invalid query values are rejected with 422 validation responses | `backend/tests/test_analytics_api_boundaries.py::test_analytics_boundaries_reject_out_of_range_and_malformed_query_params` | Added (this pass) |
| CM-06 | Weekly matchup comparison with malformed legacy owner/team ids | `analytics` router | Malformed/null legacy matchup rows are skipped instead of raising runtime errors | `backend/tests/test_analytics.py::test_weekly_matchup_comparison_ignores_malformed_rows` | Pass (prior contribution) |
| CM-07 | Rivalry graph with null trade owner ids | `analytics` router | Null trade-owner rows are filtered out; graph payload remains valid | `backend/tests/test_analytics.py::test_rivalry_graph_ignores_null_trade_rows` | Pass (prior contribution) |

## Notes
- This pass focused on one concrete automated edge test for each #155 scope area.
- Remaining expansion work should add deeper permutations per area and open follow-up bugs for any discovered unsupported behavior.
