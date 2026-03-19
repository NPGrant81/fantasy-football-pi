# MFL Year Status Matrix

Status: Rolling status board for extraction coverage by season.

## Purpose

Use this table to track whether each season is blocked by host issues, parser gaps, bad mappings, auth requirements, or data-shape problems. Update it after every test run.

## Legend

- `pass`: verified working for the tested method
- `partial`: some artifacts generated but parser/data quality gap remains
- `blocked`: known failure or missing prerequisite
- `pending`: not yet tested in current workflow

| Year | League ID | Home Host | API Export | HTML Options Pages | Import/Reconcile | Overall | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2002 | `29721` | `www47` | `pass` | `pass` | `partial` | `partial` | Draft parser still yields `0` usable API draft rows, and direct legacy URL validation confirms `O=17` contains no player-level draft data (`Draft has not been setup yet.` with empty Player cells). Do not incorporate 2002 `draftResults` into Postgres from this source. Non-draft history pages remain valid; any future 2002 draft ingestion requires a different authoritative source. |
| 2003 | `39069` | `www44` | `pass` | `pass` | `partial` | `partial` | Draft parser still yields `0` usable API draft rows (metadata-only payload with no `draftPick` records). Stage continues to emit a header-only manual template for `2003`, and season completion remains blocked pending external/manual player-id backfill data. |
| 2004 | `46417` | `pending` | `pass` | `pending` | `pending` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2004_2006`; draftResults yielded 160 rows. |
| 2005 | `20248` | `pending` | `pass` | `pending` | `pending` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2004_2006`; draftResults yielded 160 rows. |
| 2006 | `22804` | `pending` | `pass` | `pending` | `pending` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2004_2006`; draftResults yielded 160 rows. |
| 2007 | `14291` | `pending` | `pass` | `pending` | `pending` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2007_2010`; draftResults yielded 160 rows. |
| 2008 | `48937` | `pending` | `pass` | `pending` | `pending` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2007_2010`; draftResults yielded 160 rows. |
| 2009 | `24809` | `pending` | `pass` | `pending` | `pending` | `partial` | `api_info` exposes `draftResults`/`auctionResults`, but `TYPE=auctionResults` returns `Auction has not been setup yet.` and `O=17` shows rows with blank players plus `League does not have a draft configured.` comment. |
| 2010 | `10547` | `pending` | `pass` | `pending` | `pending` | `partial` | `api_info` exposes `auctionResults`, but runtime returns `Auction has not been setup yet.`; `O=17` draft table is empty and `O=102` has no detail grid, so no recoverable player-linked picks yet. |
| 2011 | `15794` | `pending` | `pass` | `pending` | `pending` | `partial` | `api_info` exposes `auctionResults`, but runtime returns `Auction has not been setup yet.`; `O=17` draft table is empty and `O=102` has no detail grid, so no recoverable player-linked picks yet. |
| 2012 | `33168` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 169 draft rows with player IDs (`draftResults` + `auctionResults` fallback path). |
| 2013 | `16794` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 168 draft rows with player IDs (`draftResults` + `auctionResults` fallback path). |
| 2014 | `23495` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 168 draft rows with player IDs (`draftResults` + `auctionResults` fallback path). |
| 2015 | `43630` | `pending` | `pass` | `pending` | `pending` | `partial` | `api_info` exposes `auctionResults`, but runtime returns `Auction has not been setup yet.`; `O=17` draft table is empty and `O=102` has no detail grid, so no recoverable player-linked picks yet. |
| 2016 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | `api_info` exposes `auctionResults`, but runtime returns `Auction has not been setup yet.`; `O=17` draft table is empty and `O=102` has no detail grid, so no recoverable player-linked picks yet. |
| 2017 | `38909` | `www47` | `pass` | `partial` | `pending` | `partial` | `draftResults` now uses `auctionResults` fallback when player IDs are absent; retest under `backend/exports/history_api_2017_retest` yielded 168 rows with full player IDs. |
| 2018 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 168 draft rows with player IDs. |
| 2019 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 169 draft rows with player IDs. |
| 2020 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 144 draft rows with player IDs. |
| 2021 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 145 draft rows with player IDs. |
| 2022 | `38909` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 144 draft rows with player IDs. |
| 2023 | `11422` | `pending` | `pass` | `pending` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 144 draft rows with player IDs. |
| 2024 | `11422` | `www46` | `pass` | `partial` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 140 draft rows with player IDs; `O=102` HTML extraction independently matches this coverage (`140/140`). |
| 2025 | `11422` | `www46` | `pass` | `partial` | `pending` | `partial` | Fallback sweep under `backend/exports/history_api_2009_2026_fallback` recovered 144 draft rows with player IDs; `O=102` HTML extraction independently matches this coverage (`144/144`). |
| 2026 | `11422` | `www46` | `pass` | `pending` | `partial` | `partial` | API extraction now passes for `franchises`, `players`, and `draftResults` under `backend/exports/history_api_2023_2026`; draftResults currently yields 0 rows (manual/backfill path required). |

## Known Failure Modes To Track

| Failure Type | Example Symptom | How To Record It |
| --- | --- | --- |
| Wrong league id | 404, empty export, or wrong league contents | Note season, old id, new id, and evidence source in Notes column. |
| Host drift | redirect to different `wwwXX` host | Record observed home host and whether redirect remained public. |
| API schema gap | export returns sparse or malformed JSON | Note report type and attach raw JSON artifact path. |
| HTML parser gap | page reachable but parser misses tables | Record `O=` code and keep snapshot or sample HTML path. |
| Auth/privacy issue | login page or restricted content | Mark method as `blocked` and note cookie/APIKEY requirement. |

## Update Rules

1. Do not mark a year `pass` unless command/page evidence exists in `mfl-test-results-log.md`.
2. If only one method works, set `Overall` to `partial` rather than `pass`.
3. Prefer evidence-backed notes over assumptions.