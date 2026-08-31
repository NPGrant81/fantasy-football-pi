# Architecture Navigation

- Status: navigation only
- Owner: engineering
- Last reviewed: 2026-08-31
- Review cadence: 90 days
- Supersession: replaces the former Issue #113 architecture summary; it is not an architecture authority

## Canonical Authorities

Use the authority that owns the question. When another document conflicts with
one of these authorities, the authority takes precedence within its scope.

| Question | Canonical authority | Scope |
| --- | --- | --- |
| What is deployed, and is the system a monolith or microservices? | [`docs/architecture/overview.md`](architecture/overview.md) | As-built topology, deployment units, service boundaries, and decomposition triggers |
| Where does code belong, and which layers may depend on which? | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Code placement, dependency direction, backend layers, frontend placement, and cross-layer boundaries |

The terms are complementary: Fantasy Football PI is a **modular monolith**, and
its backend contains **service-oriented modules**. Those modules are internal
code boundaries, not independently deployable microservices.

## Supporting References

- [`docs/API_PAGE_MATRIX.md`](API_PAGE_MATRIX.md) maps frontend pages to API contracts.
- [`docs/PATTERN_LIBRARY.md`](PATTERN_LIBRARY.md) records reusable implementation patterns.
- [`docs/patterns/PATTERN_DECISION_LOG.md`](patterns/PATTERN_DECISION_LOG.md) records accepted and superseded pattern decisions.
- [`docs/DOC_ISSUE_CORRELATION_MAP.md`](DOC_ISSUE_CORRELATION_MAP.md) maps documentation to issue history.

Supporting references defer to the two canonical authorities above for topology
and layer-placement decisions.
