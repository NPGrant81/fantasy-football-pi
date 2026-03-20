### Gap 10 — Performance & Load Testing

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `performance`, `testing`, `quality`, `infrastructure`

---

**Summary**

Establish baseline performance metrics for the API on Raspberry Pi hardware and implement repeatable load tests using Locust or k6. Define regression thresholds so that performance degradation is caught before reaching production.

Currently there are no performance benchmarks, no load tests, and no CI gates for latency or throughput.

---

**Tasks**

- [ ] Measure and document baseline performance on the target Pi hardware: P50/P95/P99 latency and requests-per-second for the top 5 API endpoints under realistic concurrency
- [ ] Choose and configure a load testing tool: Locust (Python, easier integration with existing stack) or k6 (JS, lower overhead)
- [ ] Write load test scenarios for the most critical flows: standings fetch, roster view, keeper eligibility check, scoring recalculation
- [ ] Define performance regression thresholds: e.g., P95 latency ≤ 500 ms at 20 concurrent users; error rate < 1%
- [ ] Add a `make load-test` target that runs load tests against a local or staging environment
- [ ] Integrate load tests into CI on a scheduled workflow (weekly or pre-release) — not on every PR (too slow/expensive)
- [ ] Store baseline results in `docs/performance/baseline.md` and update after each major release
- [ ] Add a CI step that fails if measured P95 latency exceeds the defined threshold (on the scheduled run)

---

**Acceptance Criteria**

- Baseline performance metrics documented in `docs/performance/baseline.md` for ≥ 5 endpoints
- Load test scenarios exist for all critical flows and run without errors against staging
- Performance thresholds (P95 latency, error rate) are defined and documented
- `make load-test` runs load tests from a developer workstation
- Scheduled CI load test runs weekly and posts results as a workflow summary
- CI fails the scheduled run if P95 latency exceeds the defined threshold
- Results from at least one full load test run are committed to `docs/performance/`
