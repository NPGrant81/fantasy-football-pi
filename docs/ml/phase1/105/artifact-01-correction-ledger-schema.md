# Artifact 01: Correction Ledger Schema (#105)

## Columns
- `row_index` (int): source row index in the input draft dataset
- `field` (str): field associated with the correction/flag
- `old_value` (str/int): observed input value
- `new_value` (str/int): transformed/final value (or unchanged if only flagged)
- `action` (str): `flagged` or `unresolved`
- `reason` (str): machine-readable cause (for example `duplicate_pick_slot`)

## Reason Taxonomy (initial)
- `missing_critical_reference`
- `duplicate_pick_slot`
- `unknown_player_reference`
- `unknown_owner_reference`

## Governance
- Ledger rows are append-only for a single run.
- Every unresolved or flagged validation event must produce one ledger row.
