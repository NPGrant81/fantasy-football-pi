# Security Hardening Baseline

This document captures the current security baseline implemented for issue #77 and the next phases for the Fantasy Football Pi platform.

## Implemented baseline (Phase 1 + Phase 2)

### Backend API hardening
- Security response headers are applied to all backend responses:
  - `Content-Security-Policy`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy`
  - `Cross-Origin-Opener-Policy: same-origin`
  - `Strict-Transport-Security` (HTTPS requests)
- Trusted host filtering is enabled via `ALLOWED_HOSTS`.
- Frontend CORS origins are configurable via `FRONTEND_ALLOWED_ORIGINS`.

### Authentication hardening
- JWT access token lifetime now defaults to 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Production startup now fails fast if `SECRET_KEY` is not explicitly set.
- Login endpoint now includes lightweight brute-force protection:
  - Configurable time window: `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
  - Configurable max failures: `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`
  - Per-IP/per-username attempt tracking with `429` on lockout
  - Failed and rate-limited attempts are logged
- Cookie-based sessions are issued at login:
  - HTTP-only access token cookie (`ffpi_access_token` by default)
  - CSRF cookie (`ffpi_csrf_token`) for double-submit verification
- CSRF protection is enforced for `POST`/`PUT`/`PATCH`/`DELETE` requests when cookie auth is used.
- `POST /auth/logout` clears auth and CSRF cookies.
- Frontend is now cookie-session first and no longer stores bearer access tokens in browser storage.
- Bearer header auth is now opt-in (`ALLOW_BEARER_AUTH=1`) for controlled interoperability.

### CI security checks
- `dependency-check.yml` now runs on dependency-related PR changes in addition to schedule/manual.
- Backend checks include:
  - Existing dependency checker
  - `bandit` static security scan
- Frontend checks include:
  - `npm audit --audit-level=high`
- `secrets-scan.yml` runs gitleaks on push/PR to `main` with repository-specific allowlist tuning in `.gitleaks.toml`.

## Environment variables

Recommended runtime settings:

- `APP_ENV=production`
- `SECRET_KEY=<strong random secret>`
- `ACCESS_TOKEN_EXPIRE_MINUTES=30`
- `ACCESS_TOKEN_COOKIE_NAME=ffpi_access_token`
- `CSRF_COOKIE_NAME=ffpi_csrf_token`
- `CSRF_HEADER_NAME=X-CSRF-Token`
- `USE_COOKIE_AUTH=1`
- `AUTH_COOKIE_SAMESITE=lax`
- `AUTH_COOKIE_SECURE=1` (set to `0` for local HTTP development)
- `ALLOWED_HOSTS=your.domain.com,localhost,127.0.0.1`
- `FRONTEND_ALLOWED_ORIGINS=https://your.domain.com`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS=300`
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS=10`

## Remaining roadmap (Phase 2+)

### User/account security
- Add password reset and email verification token flows.
- Add account lockout telemetry dashboard.

### Backend authorization and abuse controls
- Add endpoint-level scope enforcement for commissioner/admin actions.
- Add distributed rate limiter (Redis-backed) for multi-instance scalability.

### Infrastructure and operations
- Enforce HTTPS-only at Nginx with HSTS preload decision review.
- Add incident response runbook and backup restoration drills.

### Nginx hardening template
- A deploy-ready starter config for Raspberry Pi is available at:
  - `deploy/nginx/fantasy-football-pi.conf.example`
- It includes:
  - HTTP to HTTPS redirect
  - TLS 1.2/1.3 only
  - HSTS and defensive headers
  - Request/connection rate limiting
  - Safe proxy timeouts and forwarded headers

## Incident response quick-start

1. Identify and isolate affected service (API, DB, frontend, CI).
2. Rotate exposed secrets immediately (`SECRET_KEY`, database credentials, API keys).
3. Gather logs and preserve artifacts for timeline reconstruction.
4. Patch root cause and verify with targeted tests plus CI security checks.
5. Document post-incident actions and prevent recurrence via automation.