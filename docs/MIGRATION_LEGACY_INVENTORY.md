# Retired Alembic Lineage Inventory

## Canonical Migration Authority

Active incremental revisions are stored exclusively in `db/migrations/`. Alembic
loads `db/env.py` through `backend/alembic.ini`, and deployment invokes
`python -m backend.apply_migrations` from the repository root. Empty-database
bootstrap is an immutable, separate lineage in `db/bootstrap/`.

The historical `backend/alembic/` tree was disconnected from the canonical graph
and was retired in Issue #502. Its contents remain recoverable from Git history;
they must not be reintroduced as a second revision authority.

## Inventory and Disposition

The retired tree contained one environment file and eight revision files. The
revision IDs below were read from the retired source in Git history. Their
parents form one linear lineage rooted at `20260302_01`; that root is not part
of the canonical Alembic graph.

| Retired file / revision | Legacy parent | Upgrade effect and canonical representation | Downgrade effect |
| --- | --- | --- | --- |
| `backend/alembic/env.py` | N/A | Superseded environment; `backend/alembic.ini` loads `db/env.py` instead. | N/A |
| `20260302_01_add_economic_ledger.py` (`20260302_01`) | None | Creates `economic_ledger` and its indexes; represented by the bootstrap table and indexes. | Drops those indexes and the table; ledger data is lost. |
| `20260307_01_scoring_rules_schema_foundation.py` (`20260307_01`) | `20260302_01` | Adds eight `scoring_rules` columns and three foreign keys, lookup index, and five scoring tables with indexes. The bootstrap contains the final tables/columns/indexes/foreign keys; `0028_reconcile_runtime_schema` ensures the three named `scoring_rules` foreign keys and lookup indexes. Its three `UPDATE` statements backfill existing null `source`, `is_active`, and `position_ids` values; the fresh-database bootstrap instead defines the final non-null columns with defaults. | Drops the five scoring tables, introduced columns, index, and foreign keys. These drops lose stored data; the three backfills are not reversed. |
| `20260311_01_add_site_visits.py` (`20260311_01`) | `20260307_01` | Creates `site_visits` and indexes; represented by the bootstrap table and indexes. | Drops indexes and the table; visit data is lost. |
| `20260328_01_add_league_history_team_owner_map.py` (`20260328_01`) | `20260311_01` | Creates `league_history_team_owner_map`, its constraint, and indexes; represented by the bootstrap table, constraint, and indexes. | Drops indexes and the table; owner-map data is lost. |
| `20260330_01_add_trades_and_trade_assets.py` (`20260330_01`) | `20260328_01` | Creates `trades` and `trade_assets` with indexes; represented by the bootstrap tables and indexes. | Drops indexes and both tables; trade and asset data is lost. |
| `20260330_02_add_trade_events.py` (`20260330_02`) | `20260330_01` | Creates `trade_events` and indexes; represented by the bootstrap table and indexes. | Drops indexes and the table; event data is lost. |
| `20260401_01_add_trade_window_settings.py` (`20260401_01`) | `20260330_02` | Adds four trade-window columns to `league_settings`; represented by the bootstrap schema and canonical migration `0021_add_league_settings_trade_governance_columns`. | Drops all four columns; their values are lost. |
| `20260427_01_add_trade_governance_fields.py` (`20260427_01`) | `20260401_01` | Adds six governance columns to `league_settings`; represented by the bootstrap schema and canonical migration `0021_add_league_settings_trade_governance_columns` (with the same final contract in `0028_reconcile_runtime_schema`). | Drops all six columns; their values are lost. |

The schema comparison checked every retired table, column, and index created by
these revisions against the bootstrap and canonical incremental migration
inventory. It also checked the three named scoring-rule foreign keys against
the bootstrap and `0028` reconciliation. This establishes final-schema
representation, not an upgrade path from the retired IDs: canonical runtime
must reject those unknown revision IDs before DDL or stamping.

## Verification Boundary

The retired upgrade and downgrade functions were reviewed from Git history.
Their downgrades reverse the introduced DDL and are destructive for data held
in the affected tables or columns; they are not safe recovery steps. The
scoring-rule null backfills are also irreversible. No retired revision was
replayed against a database as part of this source review.

The local runner tests and canonical graph checks pass, but disposable
PostgreSQL execution and deployed `alembic_version` history have not been
verified. Do not treat this inventory as production-history evidence or close
Issue #502 until those checks are completed using an isolated database and an
approved, read-only deployed-history inventory.

## Legacy Database Recovery

The migration runner rejects unknown Alembic revision IDs before DDL or stamping.
If a database reports one of the retired revisions, stop deployment, back up the
database, record its table inventory and Alembic history, and recover using the
Git revision that owns that lineage. Do not purge or restamp the database until a
reviewed schema-equivalence procedure verifies its canonical state.

## Guardrail

CI scans repository-wide for Python files with module-level Alembic revision
assignments. Only `db/migrations/` and the governed
`db/bootstrap/versions/0001_create_schema_at_0028.py` exception are permitted;
the check runs for every change and is part of the required `ci-gate`. New active
revisions belong in `db/migrations/`; changes to the immutable bootstrap lineage
require the governed bootstrap-equivalence procedure.