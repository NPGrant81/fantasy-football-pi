# MFL Hardening Verification Gates (Items 1-24)

Status: Pre-apply verification checklist for league 60 hardening runs.

## Scope

Use this checklist before any apply-mode ingestion for seasons 2002-2026.

## Global Rules

1. Run dry-run first for every stage.
2. Require source evidence for manual draft backfill sheet rows.
3. Keep `--enforce-2002-source-policy` enabled.
4. Apply only after all relevant gates are green.

## Verified Sample Run (league 60)

Date: 2026-03-17

- `apply-mfl-draft-backfill-sheet` dry-run (`2003`): pass (no policy violations, sheet missing warning only)
- `import-mfl-csv` dry-run (`2003`): pass (`rows_invalid=0`, `files_missing=0`)
- `reconcile-mfl-import` (`2003`): expected dry-run mismatch (`owners/players not persisted in dry-run`)
- `load-mfl-html-normalized` dry-run (`2002-2003 normalized root`): pass (`files_loaded=18`, rows skipped existing only)

## Item Verification Gates

1. League metadata
- Gate: API extract run summary has season CSV and raw JSON.
- Verify: `exports/history_api_*/league/{season}.csv` and `_run_summary.json`.

2. Franchises/owners
- Gate: `import-mfl-csv` dry-run has `files_missing=0` and no invalid rows.
- Verify: import summary + reconcile source counts.

3. Players master
- Gate: player CSV exists and dry-run reports expected validated rows.
- Verify: import summary `rows_validated` and player counts.

4. Rosters
- Gate: roster extract root contains season CSV and no failed pull.
- Verify: `_run_summary.json` in relevant extract root.

5. Standings
- Gate: standings extract root contains season CSV and no failed pull.
- Verify: `_run_summary.json` and standings CSV path.

6. Schedule/results
- Gate: schedule extract root contains season CSV and no failed pull.
- Verify: `_run_summary.json` and schedule CSV path.

7. Transactions
- Gate: transactions extract root contains season CSV and no failed pull.
- Verify: `_run_summary.json` and transactions CSV path.

8. League champions
- Gate: html extract exists and normalization writes rows.
- Verify: `league_champions/{season}.csv` and normalized champions dataset.

9. League awards
- Gate: html extract exists and normalization writes rows.
- Verify: `league_awards/{season}.csv` and normalized awards dataset.

10. Franchise records
- Gate: records extract and normalization both succeed.
- Verify: `franchise_records/{season}.csv` and normalized dataset rows.

11. Player records
- Gate: records extract and normalization both succeed.
- Verify: `player_records/{season}.csv` and normalized dataset rows.

12. Matchup records
- Gate: records extract and normalization both succeed.
- Verify: `matchup_records/{season}.csv` and normalized dataset rows.

13. All-time series records
- Gate: records extract and normalization both succeed.
- Verify: `all_time_series_records/{season}.csv` and normalized dataset rows.

14. Season records
- Gate: records extract and normalization both succeed.
- Verify: `season_records/{season}.csv` and normalized dataset rows.

15. Career records
- Gate: records extract and normalization both succeed.
- Verify: `career_records/{season}.csv` and normalized dataset rows.

16. Record streaks
- Gate: records extract and normalization both succeed.
- Verify: `record_streaks/{season}.csv` and normalized dataset rows.

17. Top performers/player stats
- Gate: html extract exists for season and parser has non-failure status.
- Verify: `top_performers_player_stats/{season}.csv` and run summary.

18. Starter points by position
- Gate: html extract exists for season and parser has non-failure status.
- Verify: `starter_points_by_position/{season}.csv` and run summary.

19. Starter points by player
- Gate: html extract exists when report key is included.
- Verify: output CSV exists and row count > 0 if source page has table.

20. Points allowed by position
- Gate: html extract exists for season and parser has non-failure status.
- Verify: `points_allowed_by_position/{season}.csv` and run summary.

21. Draft detailed HTML artifacts (where available)
- Gate: `draft_results_detailed` extraction produces rows and IDs.
- Verify: output CSV rows and player-id coverage checks.

22. Normalized HTML records datasets
- Gate: normalize command summary shows `files_processed > 0`, `files_skipped=0` for selected roots.
- Verify: `_normalize_summary.json` and output datasets.

23. Staged importer roots
- Gate: stage command creates required importer files + stage summary.
- Verify: `franchises/{season}.csv`, `players/{season}.csv`, `draftResults/{season}.csv`, `_stage_summary.json`.

24. Manual draft backfill workflow
- Gate A: `prepare-mfl-draft-backfill-sheet` writes sheets.
- Gate B: `resolve-mfl-draft-backfill-names` dry-run reports match/unmatched counts.
- Gate C: `apply-mfl-draft-backfill-sheet` dry-run shows zero policy violations for intended rows.
- Gate D: `import-mfl-csv` dry-run returns no invalid rows.
- Gate E: `reconcile-mfl-import` expected to mismatch in dry-run; rerun after apply for true hardening verification.

## Policy Notes

- 2002 draft from legacy `O=17` and matching API draft feeds is non-sourceable and blocked by default policy.
- Keep `--enforce-2002-source-policy` on unless explicit exception approval is documented.
- Target app league for real hardening pathway is `60`.
