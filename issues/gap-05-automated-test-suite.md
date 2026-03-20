### Gap 05 — Automated Test Suite

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `testing`, `ci-cd`, `backend`, `quality`

---

**Summary**

Expand the existing test infrastructure to achieve meaningful coverage across unit, integration, and (optionally) frontend layers. Enforce coverage thresholds in CI so regressions are caught before merging.

Currently, backend tests exist but coverage is untracked, integration tests are limited, and there are no frontend tests for critical flows.

---

**Tasks**

- [ ] Audit existing pytest tests and document current coverage baseline (`pytest --cov` report)
- [ ] Add unit tests for all public API route handlers with at least one happy-path and one error-path case each
- [ ] Add integration tests covering: database read/write via API, data import pipeline, and keeper/scoring calculations
- [ ] Add pytest fixtures for a populated in-memory SQLite test database shared across integration tests
- [ ] Configure `pytest-cov` with a minimum coverage threshold (target: 70% lines) enforced in CI; fail the build if threshold is not met
- [ ] Update `ci.yml` to run the full test suite (with coverage report) on every PR
- [ ] (Optional) Add Cypress or Playwright smoke tests for the most critical frontend flows (login, dashboard load, roster view)
- [ ] Document testing conventions and how to run tests locally in `docs/TESTING.md`

---

**Acceptance Criteria**

- `pytest` runs cleanly with zero failures on the `main` branch
- Line coverage ≥ 70% enforced in CI; PRs that drop below threshold fail
- All public API endpoints have at least one unit test and one integration test
- Integration tests exercise the real database layer (SQLite in-memory) end-to-end
- CI runs the test suite on every PR and posts a coverage summary
- Testing conventions documented in `docs/TESTING.md`
