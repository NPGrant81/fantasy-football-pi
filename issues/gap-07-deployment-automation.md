### Gap 07 — Deployment Automation

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `deployment`, `automation`, `raspberry-pi`, `infrastructure`

---

**Summary**

Provide a `Makefile` (or equivalent Bash scripts) that encapsulates all common deployment, maintenance, and debugging operations for the Pi. Eliminate manual multi-step SSH commands and enable zero-downtime deploys.

Currently, deploying and managing the service requires remembering ad-hoc commands. There is no standardized deploy script or zero-downtime strategy.

---

**Tasks**

- [ ] Create a `Makefile` at the repo root with targets covering: `deploy`, `rollback`, `logs`, `restart`, `status`, `backup`, `restore`
- [ ] Implement zero-downtime deploy strategy: pull new image → start new container → health-check → stop old container (blue/green or rolling via Docker Compose)
- [ ] Add a `rollback` target that reverts to the previously running image tag
- [ ] Add a `logs` target that tails application and Nginx logs (last 100 lines, then follows)
- [ ] Add a `status` target that shows container health, uptime, disk usage, and last backup time
- [ ] Integrate `make deploy` into the `deploy-production.yml` GitHub Actions workflow (replace raw SSH commands)
- [ ] Document all `make` targets with usage examples in `docs/DEPLOYMENT.md`

---

**Acceptance Criteria**

- `make deploy` pulls the latest image and restarts the service with zero downtime (verified by a health-check during the deploy)
- `make rollback` reverts to the previous image and passes health checks
- `make logs` streams live logs without additional arguments
- `make status` returns container health and key metrics in under 5 seconds
- `deploy-production.yml` uses `make deploy` rather than inline shell commands
- All targets documented in `docs/DEPLOYMENT.md` with example output
