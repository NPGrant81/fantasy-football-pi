# Migration test fixtures

`pre_0001_legacy_schema.sql` is the frozen PostgreSQL schema that existed
immediately before the first incremental Alembic revision. It was generated
from `backend/models.py` at commit
`186dcf4652c6b29ad699e7a29f14d707a2db20d5`, the parent of the commit that
introduced `0001_create_draft_value_tables`.

The fixture intentionally does not use current ORM metadata. It represents the
legacy application schema required by the original migration history, including
the pre-existing `players` table referenced by the first revision. The
PostgreSQL equivalence test applies revision `0001` to this baseline, inserts
representative data, then upgrades through the normal migration runner.

Update this fixture only when new repository evidence establishes a different
supported pre-`0001` schema. Record the source commit and review the generated
DDL; do not generate it from `Base.metadata` at test time.

## Explicit legacy adoption

`python -m backend.adopt_legacy_schema` performs a preflight by default. It
temporarily creates and drops a fixture schema in a transaction, but makes no
persistent schema or data changes. It accepts only the exact table and object
shape represented by this fixture, and reports row counts and mapping
preconditions. To execute, set
`DATABASE_URL` to the intended PostgreSQL target and pass both `--apply` and
`--confirm-database <database-name>`. This command is separate from application
startup; startup never adopts an unversioned schema automatically.

The bridge first copies each source table, including its columns, indexes,
defaults, primary/unique/check constraints, foreign keys, and rows, into the
durable `ffpi_legacy_archive` schema. It then maps legacy `scoring_rules.points` to
`point_value`, uses the non-empty description (or category) for `event_name`,
and sets the documented legacy defaults: range `0..9999.99`, `flat_bonus`,
all positions, empty provider-position IDs, custom source, and active status.
Values that cannot be represented without loss or do not satisfy required
fields block before schema changes. The original `points` and `users.division`
values remain in the archive; division labels are converted into per-league
`divisions` rows and linked by `users.division_id`.

The published incremental revision graph has no table-creation revisions for
some current tables, even though later revisions add foreign keys that depend
on them. The bridge materializes the explicit set of empty bridge-managed
tables from current ORM metadata in the preparation transaction; the dry run
lists them. Existing legacy rows are not copied into these tables. After
canonical migrations reach their heads, the bridge reconciles the resulting
public schema against current ORM metadata, which is also the bootstrap
schema contract. Reconciliation refuses to drop tables and archives any
non-empty table whose migration-only columns must be removed under
`ffpi_legacy_archive` before applying the changes. It fails if the schema does
not converge to the metadata.

The preflight and initial schema preparation are transactional. A durable
`prepared` marker in the archive permits an explicit retry if canonical
migrations stop after preparation; the original tables remain archived.
Unknown schemas, archive collisions, pre-existing Alembic history, and
ambiguous scoring rows fail closed. Keep a separately verified database backup
before any non-test use; production adoption requires its own approved release
and restore plan.
