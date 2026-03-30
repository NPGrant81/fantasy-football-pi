# Artifact 01: Correction Ledger Schema (#105)

## Columns
- `source_row_number` (int): source row index in the input draft dataset
- `action` (str): correction action emitted by validator (for example `dedupe_candidate`)
- `reason` (str): machine-readable cause (for example `duplicate season/owner/player tuple`)
- `season_year` (int): season year associated with the row
- `owner_id` (int): owner identifier associated with the row
- `player_id` (int): player identifier associated with the row

## Reason Taxonomy (initial)
- `duplicate season/owner/player tuple`

## Governance
- Ledger rows are append-only for a single run.
- Every unresolved or flagged duplicate-key validation event (for example `dedupe_candidate`) must produce one ledger row. Other validation errors are surfaced in the validation report.
