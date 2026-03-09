### Issue 6 — CI Pipeline Setup

**Milestone:** [Milestone 2 — Cross‑Platform Compatibility & Deployment](../docs/milestones/milestone-2-cross-platform-deployment.md)  
**Labels:** `ci/cd`, `security`, `automation`

---

**Summary**

Create GitHub Actions workflows for linting, type checking, and dependency scanning.

---

**Tasks**

- [ ] Add Python linting (ruff/flake8)
- [ ] Add type checking (mypy/pyright)
- [ ] Add Node linting
- [ ] Add dependency vulnerability scanning
- [ ] Add test runner
- [ ] Add workflow YAML validation as a required CI guardrail
- [ ] Document workflow-edit hygiene to prevent malformed step blocks

---

**Acceptance Criteria**

- CI runs on every PR
- CI validates cross‑platform compatibility
- CI blocks unsafe dependencies
- CI fails fast on invalid workflow YAML structure
- Workflow changes include reviewer-visible evidence of syntax/hygiene verification
