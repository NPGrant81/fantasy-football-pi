### Issue 10 — Implement Pydantic Validation

**Milestone:** [Milestone 4 — Data‑Validation Architecture](../docs/milestones/milestone-4-data-validation.md)  
**Labels:** `validation`, `backend`

---

**Summary**

Add Pydantic models for API request/response validation across all endpoints.

---

**Tasks**

- [ ] Create Pydantic request models for each endpoint
- [ ] Create Pydantic response models for each endpoint
- [ ] Add consistent validation error handling (422 responses)
- [ ] Document Pydantic usage patterns

---

**Acceptance Criteria**

- All API endpoints use Pydantic models
- Validation errors return consistent, structured responses
