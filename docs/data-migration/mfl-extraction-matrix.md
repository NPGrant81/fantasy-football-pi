# MFL Extraction Matrix

Status: Working matrix for extraction planning and fallback tracking.

## Purpose

This document maps each required MFL report/page to its preferred extraction method, fallback path, auth expectation, and target artifact. Update it whenever a new report is tested or a better extraction path is discovered.

## Method Legend

- `api-export-json`: `https://api.myfantasyleague.com/{year}/export?TYPE=...&L=...&JSON=1`
- `html-options-page`: public or authenticated `options?L=...&O=...` report page scraping
- `html-report-page`: public or authenticated `reports?L=...&R=...` report page scraping
- `manual-csv`: operator-transcribed fallback for blocked or incomplete sources

## Core Data Reports

| Domain | Report/Page | Preferred Method | Fallback 1 | Fallback 2 | Auth | Artifact Target | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| League metadata | League | `api-export-json` `TYPE=league` | `html-options-page` `O=09` / `O=01` | `manual-csv` | Public for many leagues | `exports/history/league/{season}.csv` | Also provides season-to-history URL clues. |
| Owners/franchises | Franchises | `api-export-json` `TYPE=franchises` or `TYPE=league` franchise block | `html-options-page` `O=01` | `manual-csv` | Public for many leagues | `exports/history/franchises/{season}.csv` | 2026 quick run succeeded. |
| Players master | Players | `api-export-json` `TYPE=players` | `html-report-page` `R=FULLFA` plus roster pages | `manual-csv` | Public | `exports/history/players/{season}.csv` | Preserve zero-padded player IDs. |
| Draft results | Draft Results | `api-export-json` `TYPE=draftResults` | `html-options-page` `O=17` | `manual-csv` | Public | `exports/history/draftResults/{season}.csv` | Current API response shape may be sparse for some seasons. |
| Rosters | Rosters | `api-export-json` `TYPE=rosters` | `html-options-page` `O=07` | `manual-csv` | Public | `exports/history/rosters/{season}.csv` | May need auth if league privacy differs by year. |
| Standings | Standings | `api-export-json` `TYPE=standings` | `html-page` `/standings?L=...` | `manual-csv` | Public | `exports/history/standings/{season}.csv` | Home page also exposes partial standings. |
| Schedule/results | Schedule | `api-export-json` `TYPE=schedule` | `html-options-page` `O=22`, `O=31`, `O=15` | `manual-csv` | Public | `exports/history/schedule/{season}.csv` | Split by matchup results vs schedule if needed. |
| Transactions | Transactions | `api-export-json` `TYPE=transactions` | `html-options-page` `O=03` | `manual-csv` | Often public | `exports/history/transactions/{season}.csv` | Validate transaction completeness by year. |

## History And Records Pages

| Report/Page | O/R Code | Preferred Method | Fallback 1 | Fallback 2 | Auth | Years Confirmed Reachable | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| League History | `O=112` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Good candidate for league history rollup. |
| League Champions | `O=194` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Verified `200 OK`. |
| League Awards | `O=202` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Verified `200 OK`. |
| Franchise Records | `O=156` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| Player Records | `O=157` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| Matchup Records | `O=158` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| All-Time Series Records | `O=171` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| Season Records | `O=204` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| Career Records | `O=208` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |
| Record Streaks | `O=232` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Needs parser fixture. |

## Stats Pages From Current Screenshot Scope

| Report/Page | O/R Code | Preferred Method | Fallback 1 | Fallback 2 | Auth | Years Confirmed Reachable | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Top Performers/Player Stats | `O=08` | `html-options-page` | `api-export-json` for partial player stats if available | `manual-csv` | Public | 2002, 2003 | Verified `200 OK`. |
| Projected Stats | `O=236` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Useful only if historical projections matter. |
| Starter Pts - Position | `O=23` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Matches screenshot target. |
| Starter Pts - Player | `O=37` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Matches screenshot target. |
| Points Allowed - By Position | `O=81` | `html-options-page` | `manual-csv` | n/a | Public | 2002, 2003 | Matches screenshot target. |

## Host Notes By Year

| Year | League ID | Home URL | Observed Host | Notes |
| --- | --- | --- | --- | --- |
| 2002 | `29721` | `https://www47.myfantasyleague.com/2002/home/29721` | `www47` | Public home and options pages reachable. |
| 2003 | `39069` | `https://www44.myfantasyleague.com/2003/home/39069` | `www44` | Public home and options pages reachable. |
| 2026 | `11422` | `https://www46.myfantasyleague.com/2026/home/11422` | `www46` | League history block exposes prior-year URLs. |

## Immediate Priorities

1. Build HTML parser fixtures for `O=194`, `O=202`, `O=08`, `O=23`, and `O=81`.
2. Retest API export for 2002 and 2003 using corrected league IDs.
3. Record every run in `mfl-test-results-log.md` and update `mfl-year-status-matrix.md`.