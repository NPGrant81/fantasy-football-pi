# Pre-Deployment Checklist — Fantasy Football PI

**Version:** 1.0
**Effective date:** 2026-05-04
**Issue:** #113
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence
**Owner:** platform-ops

---

## 1. Purpose

This checklist must be completed before every production deployment.
It is the final quality gate between the `main` branch and the live Pi instance.

For staging deployments, complete Sections 2–5 only.
For production deployments, complete all sections.

---

## 2. Code Quality Gates

All items must pass before the commit is eligible for deployment.

### 2.1 CI status

- [ ] `ci.yml` workflow is green on the commit being deployed
- [ ] No failing tests in any CI job (backend or frontend)
- [ ] No ESLint errors on changed frontend files
- [ ] No `mypy` or type-check errors on changed backend files (if applicable)

### 2.2 Security gates

- [ ] `secrets-scan.yml` has no alerts on the target commit
- [ ] `dependency-check.yml` passes (no known critical CVEs in dependencies)
- [ ] No new `FIXME`/`TODO` security notes left in changed files
- [ ] CORS origins are locked to expected values in `.env` (not wildcard `*`)
- [ ] `SECRET_KEY` is set in the production `.env` — startup will fail-fast if missing
- [ ] JWT access token expiry is ≤ 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)

### 2.3 Data quality gates

Run before deploying any ETL or migration changes:

```bash
python -m pytest backend/tests/test_data_quality_guardrails.py -v
python -m pytest backend/tests/test_data_quality_seasonal_guardrails.py -v
python -m pytest backend/tests/test_data_quality_volume_guardrails.py -v
python -m pytest backend/tests/test_db_credentials_guardrail.py -v
python -m pytest backend/tests/test_sqlite_runtime_guardrail.py -v
```

- [ ] All data quality guardrail tests pass

### 2.4 Migration safety

If this deploy includes Alembic migrations:

- [ ] Migration has been reviewed for destructive operations (`DROP COLUMN`, `DROP TABLE`, truncates)
- [ ] Migration is reversible — `downgrade()` is implemented and tested locally
- [ ] `apply_migrations.py` has been dry-run against a copy of the production database
- [ ] Backup of the production database taken and stored (see §6)

---

## 3. Integration Smoke Tests

Run the integration smoke suite against the staging environment before promoting to production:

```bash
python -m pytest backend/tests/test_api_integration_pipeline.py -v
python -m pytest backend/tests/test_scoring_router_integration.py -v
python -m pytest backend/tests/test_health_endpoint.py -v
```

- [ ] Health endpoint returns `200 OK`
- [ ] Authentication endpoints respond correctly (login, token refresh, logout)
- [ ] Draft Day Mode smoke test passes:
  ```bash
  python -m pytest backend/tests/test_advisor_draft_day.py -v
  ```
- [ ] Model serving endpoint responds correctly:
  ```bash
  python -m pytest backend/tests/test_model_serving_endpoint.py -v
  ```
- [ ] In-season analytics endpoints respond:
  ```bash
  python -m pytest backend/tests/test_analytics.py -k "in_season" -v
  ```

---

## 4. Frontend Build Verification

- [ ] `npm run build` completes without errors on the target commit
- [ ] Bundle size has not increased by more than 20 % vs the prior deploy (check build output)
- [ ] No console errors on key pages in a local preview of the production build:
  - Home / Dashboard
  - Your Locker Room
  - Waiver Wire
  - Draft Analyzer

---

## 5. Environment Configuration

- [ ] All required environment variables are present in the production `.env`:
  - `DATABASE_URL` (credentialed DSN — not localhost-only)
  - `SECRET_KEY`
  - `FRONTEND_ALLOWED_ORIGINS`
  - `ALLOWED_HOSTS`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
- [ ] `GEMINI_API_KEY` is set if AI advisor features are in scope for this deploy
- [ ] No local dev overrides (e.g., `DEBUG=true`, `LOG_LEVEL=DEBUG`) are present in production `.env`
- [ ] Nginx config has been reviewed if any new routes were added (`deploy/nginx/`)
- [ ] Systemd service files are up to date if new background workers were added (`deploy/systemd/`)

---

## 6. Database Backup

Take a manual backup immediately before any schema migration or major data change:

```bash
# On the Pi:
pg_dump -Fc ffpi_prod > /backups/ffpi_prod_$(date +%Y%m%d_%H%M%S).dump
```

- [ ] Backup taken and size verified (non-zero)
- [ ] Backup stored in the designated backup location
- [ ] Restore procedure tested at least once per season (see `docs/RASPBERRY_PI_DEPLOYMENT.md`)

---

## 7. Deployment Steps

### 7.1 Staging deploy

Trigger via GitHub Actions:
```
Actions → deploy-staging.yml → Run workflow → select branch
```

- [ ] Staging deploy succeeded
- [ ] Smoke tests pass on staging

### 7.2 Production deploy

Trigger via GitHub Actions:
```
Actions → deploy-production.yml → Run workflow → select branch
```

- [ ] Production deploy succeeded
- [ ] Health endpoint returns `200 OK` on production URL
- [ ] Cloudflare Tunnel is routing correctly (check tunnel status)
- [ ] No error spikes in backend logs in the first 5 minutes post-deploy

---

## 8. Post-Deploy Validation

- [ ] At least one real-user action verified on production (login, page load, or API call)
- [ ] Live scoring ingestion is running if in-season (check watchdog status)
- [ ] No new ERROR-level log entries in the first 10 minutes after deploy
- [ ] Deployment date and commit SHA recorded in the ops log or release notes

---

## 9. Rollback Procedure

If the deploy introduces a regression:

1. Trigger the previous deploy workflow with the last known-good commit SHA.
2. If a migration was applied, restore the database backup from §6 before rolling back app code.
3. File a post-mortem issue within 24 hours documenting root cause and missed gate.

---

## 10. Related Documents

- [Deployment Workflows](DEPLOYMENT_WORKFLOWS.md)
- [Raspberry Pi Deployment](RASPBERRY_PI_DEPLOYMENT.md)
- [Security Hardening](SECURITY_HARDENING.md)
- [Data Quality Runbook](DATA_QUALITY_RUNBOOK.md)
- [Season Reset Workflow](season-reset.md)
- [Model Versioning and Promotion Rules](model-versioning.md)
