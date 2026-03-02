### Issue 13 — Implement Pandera DataFrame Validation

**Milestone:** [Milestone 4 — Data‑Validation Architecture](../docs/milestones/milestone-4-data-validation.md)  
**Labels:** `validation`, `analytics`

---

**Summary**

Add Pandera schema checks for analytics and scoring logic that uses pandas DataFrames.

---

**Tasks**

- [ ] Create Pandera DataFrame schemas for scoring inputs
- [ ] Add schema validation to ETL and analytics pipelines
- [ ] Add CI tests that fail on schema violations

---

**Acceptance Criteria**

- Pandera validates all DataFrame operations in scoring and analytics
- CI fails on schema violations
