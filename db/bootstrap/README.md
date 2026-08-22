# Empty Database Bootstrap

This is a dedicated Alembic lineage for creating the static schema represented
by main migration revision `0028_reconcile_runtime_schema`.

`python -m backend.apply_migrations` uses it only when PostgreSQL has no
application tables. After bootstrap, the runner stamps the main lineage at
`0028_reconcile_runtime_schema` and applies later main migrations normally.

Do not modify an existing bootstrap revision. When a new baseline is required,
generate a new immutable bootstrap revision and update the pinned main revision
in `backend/apply_migrations.py`.