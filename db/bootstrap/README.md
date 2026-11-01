# Empty Database Bootstrap

This is a dedicated Alembic lineage for creating the static schema represented
by main migration revision `0028_reconcile_runtime_schema`.

`python -m backend.apply_migrations` uses it only when PostgreSQL has no
application tables. After bootstrap, the runner stamps the main lineage at
`0028_reconcile_runtime_schema` and applies later main migrations normally.

Bootstrap revisions are immutable, reviewed snapshots owned by the database
migration maintainers. Do not edit an existing revision to make it match current
ORM metadata or to repair a later migration.

When the main migration head advances, create a new bootstrap revision from the
reviewed head, preserve prior revisions, and update
`BOOTSTRAP_MAIN_REVISION` in `backend/apply_migrations.py` in the same change.
Prove the new snapshot is equivalent to upgrading the frozen pre-`0001` legacy
fixture through the incremental migrations, including preserved representative
data and detection of a deliberate schema mismatch. The historical fixture and
its provenance are documented in [`../test_fixtures/README.md`](../test_fixtures/README.md).