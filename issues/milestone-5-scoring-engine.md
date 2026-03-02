### Issue 16 — Gameplay Logic: Scoring Engine

**Milestone:** [Milestone 5 — Gameplay Logic & League Operations](../docs/milestones/milestone-5-gameplay-logic.md)  
**Labels:** `gameplay`, `backend`, `analytics`

---

**Summary**

Implement scoring calculations for weekly matchups with support for multiple scoring rule types.

---

**Tasks**

- [ ] Define scoring rule types (event‑based, yardage‑based, score‑based, decimal, PPR, half‑PPR)
- [ ] Implement scoring engine with reproducible calculations
- [ ] Support mid‑season scoring adjustments with retroactive recalculation
- [ ] Add tests for all scoring scenarios
- [ ] Add audit logs for scoring changes

---

**Acceptance Criteria**

- Scoring reproducible and validated
- All rule variations tested
- Mid‑season adjustments recalculate past weeks correctly
