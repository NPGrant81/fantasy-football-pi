# Issue #341: League History owner identity enrichment gap

GitHub issue: https://github.com/NPGrant81/fantasy-football-pi/issues/341

## Summary

League History still has unresolved historical owner attribution gaps for League 60. The recent router fix stopped showing misleading team-name placeholders as owner names, but the underlying source data still does not provide reliable person-name ownership for many seasons.

## Why this needs a new issue

- Prior historical-owner-mapping package issues `#313` through `#316` delivered the platform, commissioner utility, and diagnostics surfaces.
- The remaining problem is a net-new data-quality and backfill scope, not a regression in the UI shell itself.
- Keeping this as a dedicated issue makes it traceable without reopening already-closed package delivery tickets.

## Current observed behavior

- League 60 Match Records and related history views can still lack true owner identities for many seasons.
- Placeholder mappings where `owner_name == team_name` are now suppressed and render as unresolved instead of misleading person labels.
- The visible result is improved correctness, but not complete enrichment.

## Investigation notes

- `league_history_team_owner_map` contains many League 60 rows, but a large portion are placeholders where the stored `owner_name` simply repeats the franchise/team label.
- `mfl_html_record_facts` matchup payloads provide franchise labels, not normalized person identities.
- Historical franchise export files under `backend/exports/history_api_*/franchises/*.csv` also commonly contain `owner_name == franchise_name` for League 60 seasons.
- Because the imported source data lacks stable person-name ownership in those seasons, the current pipeline cannot fully enrich League History without supplemental mapping or better upstream data.

## Root cause

The remaining gap is primarily data quality and identity resolution, not rendering logic. Existing historical owner mapping infrastructure can store and display enriched mappings, but League 60 still lacks trustworthy source-level owner identity inputs for many rows.

## Scope candidates

- Detect and report placeholder owner mappings as first-class diagnostics.
- Produce a League 60 coverage report showing unresolved seasons, teams, and source tokens.
- Backfill known owner identities using commissioner-managed mappings or curated import files.
- Add a repair workflow to distinguish:
  - placeholder name-only mappings
  - valid linked-owner mappings
  - unresolved source rows requiring manual intervention
- Verify improved owner attribution in Match Records, team timelines, and related League History views.

## Acceptance criteria

- [ ] League 60 unresolved historical owner rows are enumerated with season and team-level diagnostics.
- [ ] Placeholder mappings are distinguishable from valid owner identities in commissioner tooling and diagnostics.
- [ ] A repeatable enrichment/backfill workflow exists for unresolved League 60 rows.
- [ ] At least one verified League 60 sample season is enriched end-to-end and displays real owner identities in League History.
- [ ] Follow-up documentation records the data sources used and any remaining unresolved seasons.

## Tracing notes

- Recent code hardening already landed in `backend/routers/league.py` so placeholder team labels no longer masquerade as owner names.
- Related platform work:
  - `#313` Historical owner mapping backend API + persistence hardening
  - `#314` Commissioner historical mapping utility with CSV and coverage workflows
  - `#316` Owner timeline and mapping diagnostics for historical owner attribution
- Potentially related user-facing symptom:
  - `#279` League 60 / Post Pacific League: User Not Recognized Summary

## Suggested implementation starting points

1. Add a targeted League 60 diagnostics query/report that lists unresolved rows by season.
2. Export unresolved source tokens into a commissioner-editable mapping seed file.
3. Import curated owner mappings for one or two high-value seasons first.
4. Re-run League History smoke checks against those seasons before broadening the backfill.