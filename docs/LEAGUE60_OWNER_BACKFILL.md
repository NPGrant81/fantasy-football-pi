# League 60 Historical Owner Backfill Workflow

**Related issues:** #341, #313, #314, #316

## Background

League 60 (Post Pacific League) has historical seasons dating back to 2002. For many earlier seasons the MFL API franchise export stores `owner_name == franchise_name`, meaning no true person-identity is recorded in the source data.

The enrichment infrastructure (API endpoints, commissioner UI, diagnostics) was delivered in issues #313–#316. This document describes how to use those tools to enumerate and fix the remaining placeholder mappings.

## Why placeholders exist

When `extract-mfl-history` pulls franchise records from the MFL API, it stores whatever the API returns as `owner_name`. For older League 60 seasons the MFL API only had the team/franchise name available — no person name. The pipeline detects this condition (`owner_name == team_name`) and suppresses those values from UI display, leaving the rows as "unresolved."

## Prerequisites

- Python venv activated: `source .venv/bin/activate`
- Backend environment loaded (`.env` or equivalent with `DATABASE_URL` pointing at the target DB)
- Commissioner access (for UI workflow) or direct DB access (for CLI workflow)

---

## Step 1 — Enumerate gaps

### Via CLI

```bash
python -m backend.manage history-owner-gap-report --league-id 60
```

This prints a season-by-season summary of placeholder rows. Add `--json-output gaps.json` to get the full list.

### Via API / UI

Navigate to the commissioner panel → **History Owner Mapping** (route `/commissioner/history-owner-mapping?leagueId=60`). The gap summary cards show placeholder count, unresolved match teams, and unresolved series teams.

---

## Step 2 — Export a seed CSV

```bash
python -m backend.manage export-history-owner-seed \
    --league-id 60 \
    --output /tmp/league60_owners.csv \
    --placeholders-only
```

The output CSV has columns: `id, season, team_name, owner_name, owner_id, notes`.

- `id` — existing DB row id; leave as-is so the importer can update rather than duplicate.
- `owner_name` — fill in the real person name (e.g. `"Jane Smith"`).
- `owner_id` — optionally link to a `users.id` in the same league for cross-reference queries.
- Leave `owner_name` blank for any rows you can't confirm — they will be skipped on import.

Alternatively, download the same CSV from the commissioner UI's **Export seed CSV** button.

---

## Step 3 — Fill in owner names

Edit the exported CSV. Data sources for League 60 owners:

| Season range | Suggested source |
|---|---|
| 2002–2010 | Original league organizer records / email archives |
| 2011–2022 | MFL franchise page (if updated) or league member self-report |
| 2023–present | Current `users` table — match by `team_name` |

For the current active members you can cross-reference:

```sql
SELECT id, username, team_name FROM users WHERE league_id = 60 ORDER BY team_name;
```

---

## Step 4 — Dry-run the import

```bash
python -m backend.manage import-history-owner-seed \
    --league-id 60 \
    --csv /tmp/league60_owners_filled.csv
```

Review the printed `[UPDATE]` / `[INSERT]` lines. Warnings about invalid `owner_id` values or malformed rows are printed but do not abort the run.

---

## Step 5 — Apply the import

```bash
python -m backend.manage import-history-owner-seed \
    --league-id 60 \
    --csv /tmp/league60_owners_filled.csv \
    --apply
```

Alternatively, use the commissioner UI's **Upload seed CSV** button which calls the same upsert endpoint.

---

## Step 6 — Verify in League History

After importing, visit:

- **League History → Match Records** — owner names should appear for enriched seasons.
- **League History → All-Time Series** — perspective/opponent owner columns should be resolved.
- **History Owner Mapping** commissioner page — placeholder count should drop.

Re-run the gap report to confirm:

```bash
python -m backend.manage history-owner-gap-report --league-id 60
```

---

## Repeating for additional seasons

The workflow is fully repeatable:

1. Export remaining placeholders (`--placeholders-only`).
2. Fill in what you can.
3. Dry-run → apply.
4. Verify.

Rows with empty `owner_name` in the CSV are skipped without error, so partial fills are safe.

---

## Data sources used (to be updated as seasons are enriched)

| Season | Status | Source | Notes |
|---|---|---|---|
| *(none yet)* | Pending | — | Run workflow to begin enrichment |

Update this table as seasons are enriched so future maintainers know which seasons have been verified.

---

## Remaining known gaps

- The MFL API does not expose historical person-name ownership for franchises that changed hands before MFL began tracking it.
- For very early seasons (2002–2006) the only reliable source is league organizer memory or external records.
- Seasons with no matchup records in `mfl_html_record_facts` cannot produce unresolved match/series entries even if owner identity is unknown.
