### Gap 02 — Secrets Management

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `security`, `secrets`, `ci-cd`, `infrastructure`

---

**Summary**

Establish a secure, documented secrets management strategy covering local development, GitHub Actions CI/CD, and the production Raspberry Pi environment. Prevent accidental credential exposure and define a clear process for rotating secrets.

Currently there is no `.env` template, no documented secrets conventions, and no enforcement of secret hygiene in CI.

---

**Tasks**

- [ ] Create a `.env.example` template at the repo root (and per-service if needed) listing all required environment variables with placeholder values and descriptions
- [ ] Add `.env` and any `*.env` variants to `.gitignore` (verify no existing `.env` files are tracked)
- [ ] Document all GitHub Actions secrets required by CI/CD workflows in `docs/SECRETS.md`
- [ ] Implement or verify `secrets-scan.yml` workflow catches committed secrets (truffleHog / gitleaks)
- [ ] Define Pi-side secret storage convention (e.g., `/etc/fantasy-football-pi/.env` with `600` permissions, owned by service user)
- [ ] Document TLS key/certificate handling if Nginx terminates TLS on the Pi
- [ ] Add a secret rotation runbook section to `docs/SECRETS.md`

---

**Acceptance Criteria**

- `.env.example` exists and documents every variable the application reads at runtime
- No real credentials appear anywhere in the repository history
- `secrets-scan.yml` CI check runs on every PR and fails on detected secrets
- `docs/SECRETS.md` explains where each secret lives in dev, CI, and production
- Pi-side `.env` file is owned by the service user with `600` permissions
- Secret rotation procedure is documented
