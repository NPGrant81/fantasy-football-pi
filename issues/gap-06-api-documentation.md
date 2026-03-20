### Gap 06 — API Documentation & Schema Validation

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `api`, `documentation`, `pydantic`, `backend`

---

**Summary**

Expose machine-readable API documentation via an OpenAPI schema, enforce request/response validation with Pydantic models on all endpoints, and establish a versioning strategy so consumers can rely on a stable contract.

Currently, some endpoints lack Pydantic response models and the `/docs` endpoint may not reflect the full API surface.

---

**Tasks**

- [ ] Audit all FastAPI routers: ensure every endpoint declares explicit `response_model` and input body types using Pydantic models
- [ ] Enable and verify the `/docs` (Swagger UI) and `/redoc` endpoints are accessible in production (behind authentication if required)
- [ ] Add an `/openapi.json` download step to CI that saves the schema as a build artifact for diffing across PRs
- [ ] Implement request validation for all `POST`/`PUT`/`PATCH` endpoints — return `422 Unprocessable Entity` with field-level error details on invalid input
- [ ] Add API versioning prefix (`/api/v1/`) to all routes (or document the explicit decision to defer versioning in an ADR)
- [ ] Generate and commit `docs/openapi.json` (or `docs/openapi.yaml`) as the canonical schema reference
- [ ] Document API usage examples and authentication requirements in `docs/API.md`

---

**Acceptance Criteria**

- Every endpoint has a declared `response_model`; Pydantic validates all inputs
- `/docs` and `/redoc` are accessible and reflect the full current API
- `openapi.json` is exported as a CI artifact on every build
- Invalid request bodies return `422` with field-level error details
- `docs/API.md` documents authentication, common patterns, and at least one example request/response per router
- Schema versioning strategy is documented (or explicitly deferred with ADR)
