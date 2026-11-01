# Migration test fixtures

`pre_0001_legacy_schema.sql` is the frozen PostgreSQL schema that existed
immediately before the first incremental Alembic revision. It was generated
from `backend/models.py` at commit
`186dcf4652c6b29ad699e7a29f14d707a2db20d5`, the parent of the commit that
introduced `0001_create_draft_value_tables`.

The fixture intentionally does not use current ORM metadata. It represents the
historical application schema, including the pre-existing `players` table
referenced by the first revision. It is not independently upgradeable through
the entire published incremental history: revision `0003` assumes scoring
columns absent from this fixture, and later revisions assume a `divisions`
table. The reviewed, explicit legacy adoption bridge is tracked in
[#554](https://github.com/NPGrant81/fantasy-football-pi/issues/554) and
[PR #555](https://github.com/NPGrant81/fantasy-football-pi/pull/555).

Until that bridge is integrated, the equivalence test remains a failing
acceptance gate on PostgreSQL, not a supported direct-upgrade procedure.
Do not edit the fixture, rewrite published migrations, or stamp the database
to conceal those missing transitions. PR #553 must not merge while this
dependency is outstanding.

The test uses separate disposable databases for bootstrap and incremental
execution so unqualified catalog checks in published migrations cannot see
objects in the other path or the CI database. Schema snapshots include
reflected index expressions and structural sequence properties (type, start,
increment, bounds, cache, cycle, and owning table/column), but not mutable
sequence state such as `last_value` or `is_called`. Targeted regression tests
verify expression and sequence drift is detected and consuming IDs does not
create a false mismatch.

Update this fixture only when new repository evidence establishes a different
supported pre-`0001` schema. Record the source commit and review the generated
DDL; do not generate it from `Base.metadata` at test time.
