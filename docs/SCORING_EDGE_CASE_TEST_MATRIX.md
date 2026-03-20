# Scoring Edge-Case Test Matrix (Issue #43)

Date: 2026-03-08
Owner: feature/scoring-integration-analytics
Related Issues: #43, #100, #155

## Purpose
This matrix captures edge-case scoring scenarios, expected behavior, and automated test coverage status so hardening work remains explicit and repeatable.

## Matrix
| ID | Scenario | Module | Expected Behavior | Automated Coverage | Status |
|---|---|---|---|---|---|
| SC-01 | League-specific starter filtering | `scoring_service.recalculate_matchup_scores` | Picks from other leagues are excluded | `backend/tests/test_scoring_engine_service.py::test_recalculate_matchup_scores_isolates_draft_picks_by_league` | Pass |
| SC-02 | Legacy NULL `league_id` picks | `scoring_service.recalculate_matchup_scores` | Legacy picks are included for scoring | `backend/tests/test_scoring_engine_service.py::test_recalculate_matchup_scores_includes_legacy_null_league_id_picks` | Pass |
| SC-03 | Taxi starters excluded | `scoring_service.recalculate_matchup_scores` | Taxi picks do not score | `backend/tests/test_scoring_engine_service.py::test_recalculate_matchup_scores_excludes_taxi_picks` | Pass |
| SC-04 | Position-gated rule application | `calculate_points_for_stats` | Non-matching positions do not receive rule points | `backend/tests/test_scoring_engine_service.py::test_calculate_points_for_stats_handles_decimal_and_ppr_rules` | Pass |
| SC-05 | Alias resolution + DST normalization | `calculate_points_for_stats` | Alias stat keys resolve, DEF and D/ST normalize consistently | `backend/tests/test_scoring_engine_service.py::test_calculate_points_for_stats_supports_stat_key_aliases_and_dst_normalization` | Added (this pass) |
| SC-06 | No rules fallback behavior | `calculate_player_week_points` | Falls back to weekly `fantasy_points` when no active rules are configured | `backend/tests/test_scoring_engine_service.py::test_calculate_player_week_points_falls_back_to_weekly_fantasy_points_without_rules` | Added (this pass) |
| SC-07 | Matchup projected aggregation parity | `matchups` router + scoring service | Matchup payload projected totals match scored starters sum | `backend/tests/test_matchups_scoring_router.py::test_get_matchup_detail_aggregates_projected_from_scored_starters` | Pass |
| SC-08 | Win probability zero-total fallback | `matchups` router | If both projected totals are zero, return 50/50 probabilities | `backend/tests/test_matchups_scoring_router.py::test_calculate_win_probabilities_handles_zero_projection_totals` | Pass |
| SC-09 | Mid-season scoring changes propagation | Commissioner settings -> scoring/matchups | Scoring changes recalc future weeks and preserve auditability | `backend/tests/test_scoring_router_integration.py::test_commissioner_rule_update_propagates_to_recalc_and_matchup_detail` | Added (this pass) |
| SC-10 | Concurrent rules edits | Commissioner settings endpoints | Rule updates remain atomic with rollback on failure | `backend/tests/test_scoring_router_integration.py::test_batch_upsert_rolls_back_all_changes_when_any_rule_update_fails` | Added (this pass) |
| SC-11 | CSV import replacement + audit trail | `scoring` router `/import/apply` + `/history` | Season replacement deactivates stale rules and logs imported/deleted change events | `backend/tests/test_scoring_router_integration.py::test_import_apply_replacement_deactivates_stale_rules_and_logs_history` | Added (this pass) |
| SC-12 | Imported rules scoring parity | `scoring` router `/import/apply` + `/calculate/matchups/{id}/recalculate` | Matchup recalculation totals match imported rule math from weekly stats | `backend/tests/test_scoring_router_integration.py::test_imported_rules_drive_matchup_recalculation_scores` | Added (this pass) |
| SC-13 | Template lifecycle parity + audit | `scoring` router `/templates/import` + `/templates/{id}/export` + `/templates/{id}/apply` + `/history` | Template import/export/apply remains consistent, deactivates prior active non-template rules, and applied rules drive matchup recalculation totals | `backend/tests/test_scoring_router_integration.py::test_template_lifecycle_import_export_apply_and_recalc` | Added (this pass) |
| SC-14 | Replacement propagation with stale-rule guard | `scoring` router `/import/apply` (replace) + `/rulesets/current` + matchup/detail endpoints | Replace flow deactivates stale active rules so projected/recalculated matchup totals reflect only replacement rules | `backend/tests/test_scoring_router_integration.py::test_import_replacement_propagates_without_stale_rule_leakage` | Added (this pass) |
| SC-15 | Template export/import round-trip parity | `scoring` router `/templates/{id}/export` + `/templates/import` + `/templates/{id}/apply` | Exported template CSV can be re-imported without changing rule semantics, and the re-imported template drives identical matchup totals | `backend/tests/test_scoring_router_integration.py::test_template_export_round_trip_preserves_scoring_parity` | Added (this pass) |

## Notes
- This matrix is intentionally scoped to high-risk boundaries first: league isolation, legacy data compatibility, and fallback behavior.
- New failures discovered during this sweep should be tracked under #155 with linked bug issues.
