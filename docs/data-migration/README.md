# Data Migration Contracts

This folder defines source-to-target data contracts for migrating legacy league history into the app.

Primary tracker: GitHub Issue #256 (Define Data Requirements & Schemas)

## Documents

- `mfl-data-requirements.md`: Required report inventory, field-level contracts, source mapping, and open questions.

## Scope

- Source platform: MyFantasyLeague (MFL) HTTP export API.
- Domain split:
  - Current-season operational data.
  - Historical analytics/archive data.

## Next issues in chain

- #257: Build extraction API/scripts (Legacy -> CSV)
- #258: Build import pipeline (CSV -> app)
- #259: Reconciliation and integrity checks
- #260: Workflow docs and rerun guidance
