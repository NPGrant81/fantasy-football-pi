# Data Validation Strategy

This document defines the layered validation approach for Issue #76.

## Library-to-layer mapping

- **Pydantic**: boundary validation for API/request payloads and typed models.
- **Cerberus**: dynamic rule validation where schema logic may evolve quickly.
- **Marshmallow**: serialization/deserialization for structured data transfer.
- **Pandera**: DataFrame contracts for ETL and analytics datasets.
- **Great Expectations**: long-term expectation checks for data quality monitoring.

## Current implementation

### Backend

- `backend/services/validation_service.py`
  - `validate_waiver_claim_boundary` (Pydantic)
  - `validate_waiver_claim_dynamic_rules` (Cerberus when available, deterministic fallback otherwise)
  - `validate_draft_pick_boundary` (Pydantic)
  - `validate_draft_pick_dynamic_rules` (Cerberus when available, deterministic fallback otherwise)
  - `validate_trade_proposal_boundary` (Pydantic)
  - `validate_trade_proposal_dynamic_rules` (Cerberus when available, deterministic fallback otherwise)
  - `serialize_ledger_entries` (Marshmallow when available, deterministic fallback otherwise)

- `backend/services/waiver_service.py`
  - Waiver claims now execute boundary + dynamic validation before transactional logic.

- `backend/routers/draft.py`
  - Draft pick submission now executes boundary + dynamic validation before business logic.

- `backend/routers/trades.py`
  - Trade proposal now executes boundary + dynamic validation before business logic.

### ETL

- `etl/validation/dataframe_validation.py`
  - `validate_normalized_players_dataframe` (Pandera when available, deterministic fallback otherwise)

- `etl/validation/great_expectations_runner.py`
  - `run_normalized_players_expectations` (Great Expectations-aware runner with deterministic fallback checks)

- `etl/load/load_to_postgres.py`
  - Loader now validates incoming normalized DataFrames and expectation checks before any DB write.

## Dependency strategy

The framework is designed to run safely even if optional validation libraries are not installed.

For full multi-library support, install:

```bash
pip install -r backend/requirements-validation.txt
```

## Extension guidelines

- Add new boundary models in `validation_service.py` for API payloads.
- Add dynamic Cerberus schemas for commissioner-configurable rules.
- Add Pandera contracts for every normalized DataFrame passed to loaders.
- Add Great Expectations suites for production-critical datasets and schedule them in CI.
