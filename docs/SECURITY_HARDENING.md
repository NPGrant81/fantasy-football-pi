# Security Hardening Baseline

This document records implemented security controls and remaining work. It
describes repository code and example configuration; it is not evidence that
production settings or operational controls have been verified.

## Implemented controls

### Backend API hardening

- The backend adds defensive response headers, including Content Security
  Policy, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, and `Cross-Origin-Opener-Policy`.
- Backend HSTS is added only when the ASGI request scheme is HTTPS. Verify the
  deployed proxy and Cloudflare configuration rather than assuming this from
  the code alone.
- Trusted hosts are restricted through `ALLOWED_HOSTS`; browser origins are
  configured through `FRONTEND_ALLOWED_ORIGINS`.
- `/health` GET and HEAD report service, database, and schema readiness.

### Authentication and account security

- Access JWT lifetime defaults to 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Production startup requires a strong, explicitly configured `SECRET_KEY`.
- Failed-login protection is configurable with
  `LOGIN_RATE_LIMIT_WINDOW_SECONDS` and `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`;
  attempts are tracked per IP and username, and limited requests receive 429.
- Rate limiting defaults to process-local memory. A Redis backend is available
  with `RATE_LIMITER_BACKEND=redis`; Redis failure falls back to process-local
  memory, which does not provide shared limits across instances.
- Cookie authentication uses an HTTP-only access-token cookie and a
  double-submit CSRF cookie. Unsafe methods require CSRF validation when cookie
  authentication is enabled.
- Logout clears cookies and revokes the presented access and refresh tokens.
- Refresh tokens are persisted as hashes, rotated on refresh, and replay
  detection revokes that user's active refresh tokens.
- Password-reset token creation and confirmation endpoints exist, but the
  request endpoint does not deliver email. Self-service reset is therefore not
  operational end-to-end. Email verification is not implemented.
- The frontend is cookie-session first and does not store bearer access tokens
  in browser storage. Bearer-token authentication is opt-in with
  `ALLOW_BEARER_AUTH=1`.
- Privileged-action audit-log storage and a superuser read endpoint exist.
  Treat coverage as partial until every required privileged operation is
  verified; the application-level log is not an immutable audit store.

### CI security checks

- `.github/workflows/dependency-check.yml` runs monthly, manually, and on
  dependency-related pull-request changes. On pull requests, dependency and
  npm audit findings are non-blocking; Bandit and strict backend lock
  validation still run.
- The dependency workflow runs backend dependency checks, Bandit, and
  high-severity npm audit checks.
- `.github/workflows/secrets-scan.yml` runs Gitleaks on pull requests targeting
  `main`, pushes to `main`, and manual dispatch, using `.gitleaks.toml`.

## Production settings to verify

- `APP_ENV=production`
- `SECRET_KEY=<strong random secret>`
- `ACCESS_TOKEN_EXPIRE_MINUTES=30`
- `ACCESS_TOKEN_COOKIE_NAME=ffpi_access_token`
- `CSRF_COOKIE_NAME=ffpi_csrf_token`
- `CSRF_HEADER_NAME=X-CSRF-Token`
- `USE_COOKIE_AUTH=1`
- `AUTH_COOKIE_SAMESITE=lax`
- `AUTH_COOKIE_SECURE=1`
- `ALLOW_ALL_ORIGINS=0`
- `AUTO_SEED_ON_STARTUP=0`
- `ALLOWED_HOSTS=<production hostnames>`
- `FRONTEND_ALLOWED_ORIGINS=<production HTTPS origins>`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS=300`
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS=10`
- `RATE_LIMITER_BACKEND=memory` (use `redis` only when Redis is configured
  and monitored)

Use the deployment environment file and production configuration checks as the
source of truth for required settings. Never commit secret values.

## Remaining work

### User/account security

- Connect password-reset token delivery to a supported email service and
  verify the complete request-to-confirm flow before advertising password
  reset.
- Design and implement email verification if required by the product.
- Add account-lockout telemetry and operator visibility.

### Authorization and abuse controls

- Audit route authorization and cross-league isolation for all mutations and
  sensitive reads; the existence of role dependencies does not prove complete
  endpoint coverage.
- Add request-type-specific API limits beyond failed-login protection where
  threat analysis calls for them.
- For multi-instance deployments, configure and monitor Redis; the memory
  fallback is per-process and is not a distributed control.

### Token lifecycle and audit

- Verify access-token revocation and refresh-token rotation/replay handling
  with automated tests and operational procedures.
- Complete and test privileged-action audit coverage. Use an external or
  append-only store if immutable audit evidence is required.

### Infrastructure and operations

- Review the HSTS preload decision before enabling preload. Current Nginx
  configuration includes HSTS, but it does not establish that the production
  Cloudflare-to-origin topology is correct.
- Run and retain evidence for production incident-response and backup-restore
  drills. Procedures are documented in
  [INCIDENT_RESPONSE_RUNBOOK.md](./INCIDENT_RESPONSE_RUNBOOK.md) and
  [restore.md](./restore.md).

## Nginx and Cloudflare origin configuration

The Nginx example at `deploy/nginx/fantasy-football-pi.conf.example` includes
an HTTP-to-HTTPS redirect and a TLS listener. The named Cloudflare Tunnel
example currently targets HTTP on Nginx port 80. These examples are not a
verified compatible pair as written: a tunnel request can receive a redirect
back to the public HTTPS hostname instead of reaching the app. Resolve the
origin mode and verify local and public health checks before production
cutover; see [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md).

## Incident response

The incident response procedure is documented in
[INCIDENT_RESPONSE_RUNBOOK.md](./INCIDENT_RESPONSE_RUNBOOK.md), and backup
restore procedures are documented in [restore.md](./restore.md). Production
drills still need dated evidence; documentation alone does not establish that
the procedures work against the intended production environment.

1. Identify and isolate the affected service (API, database, frontend, or CI).
2. Rotate exposed secrets immediately; do not restore a compromised value.
3. Preserve logs and artifacts for timeline reconstruction.
4. Patch the root cause and verify with targeted tests and CI security checks.
5. Record follow-up actions and prevent recurrence with automation.
