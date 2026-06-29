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
  - Distributed backend support: Redis-backed rate limiter with in-memory fallback (`RATE_LIMITER_BACKEND`)
- Cookie-based sessions are issued at login:
  - HTTP-only access token cookie (`ffpi_access_token` by default)
  - CSRF cookie (`ffpi_csrf_token`) for double-submit verification
- CSRF protection is enforced for `POST`/`PUT`/`PATCH`/`DELETE` requests when cookie auth is used.
- JWT token revocation is enforced via JTI blocklist:
  - Each JWT includes a unique ID (`jti`) for revocation tracking
  - Revoked JTI tokens are stored in `RevokedToken` table with expiration
  - `GET_current_user()` checks blocklist before accepting tokens
- Refresh token rotation is implemented:
  - Refresh tokens are persisted in `RefreshToken` table with secure hashing
  - Token rotation on each refresh creates family chain for replay detection
  - `rotated_from_token_hash` tracks rotation lineage for revocation on suspected breach
  - Soft deletion via `revoked_at` timestamp enables audit trail
- `POST /auth/logout` clears auth cookies and revokes all user refresh tokens
- `POST /auth/logout` clears auth cookies.
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

### Admin and privileged operation audit logging
- All administrative actions are recorded in `AdminAuditLog` immutable table:
  - Captures actor identity (user_id, username, role flags)
  - Records action type, scope, and target (type/id)
  - Includes optional metadata (JSON) for audit context
  - Immutable timestamps enable audit trail reconstruction
- Audit logging covers all 6 admin router modules:
  - `admin.py` (user/league management)
  - `platform_tools.py` (system utilities)
  - `admin_nfl.py` (NFL metadata)
  - `admin_drafts.py` (draft operations)
  - `admin_live_scoring.py` (scoring rule management)
  - `admin_config.py` (configuration)
- Superuser-only read endpoint available for audit review and compliance investigation

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
- `RATE_LIMITER_BACKEND=memory` (or `redis` for distributed deployments)
- `REDIS_URL=redis://localhost:6379/0` (if using Redis backend)
- `REDIS_POOL_SIZE=10` (connection pool size for Redis backend)

## Remaining roadmap (Phase 3+)

### User/account security
- Add password reset and email verification token flows.
- Add account lockout telemetry dashboard.

### Backend authorization and abuse controls
- Add endpoint-level scope enforcement for commissioner/admin actions.
- Enhance rate limiter with request-type specific thresholds (e.g., login vs. API calls).

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