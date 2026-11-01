# Secrets Rotation Policy

**Issue:** #415  
**Created:** May 9, 2026  
**Status:** Active

---

## Purpose

This document defines the rotation cadence, procedures, and safeguards for managing cryptographic secrets and external API credentials in the Fantasy Football Pi production environment.

---

## Secrets Inventory

### Tier 1: Cryptographic Secrets (Most Sensitive)

These secrets directly control authentication and encryption. Rotation is critical.

| Secret | Purpose | Rotation Cadence | Length | Format |
|--------|---------|------------------|--------|--------|
| `SECRET_KEY` | FastAPI auth secret for JWT signing/verification | **Quarterly (90 days)** or on compromise | 32+ characters | URL-safe base64 |

### Tier 2: External API Credentials (Medium Sensitivity)

These grant access to third-party services. Rotate immediately if exposed and
otherwise follow the provider's rotation requirements.

| Credential | Service | Rotation Cadence | Format |
|------------|---------|------------------|--------|
| `YAHOO_CLIENT_SECRET` and OAuth tokens | Yahoo Fantasy Sports | On exposure or provider requirement | OAuth2 credentials |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Google AI advisor | On exposure or provider requirement | API key |
| Cloudflare API Token | Cloudflare Tunnel | **Annual (365 days)** or after zone changes | Bearer token |
| `GITHUB_APP_PRIVATE_KEY` or `GITHUB_TOKEN` / `GH_TOKEN` | GitHub issue integration | On exposure or provider requirement | App private key or token |
| `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` | CI and ETL notifications | On exposure or provider requirement | HTTPS webhook URL |

The current application does not configure `MFL_OAUTH_CLIENT_SECRET`,
`JWT_SECRET`, or `GITHUB_APP_SECRET`; do not use those names as rotation inputs.
The Cloudflare API token row applies only if operators separately use an
account-level token; the tunnel service itself uses a credentials JSON file.

### Tier 3: Database Credentials (High Sensitivity)

Managed by PostgreSQL administrators. Rotate when:
- User access policy changes
- Service account is compromised
- Quarterly audit cycle triggers rotation

| Credential | Rotation Cadence | Owner |
|------------|------------------|-------|
| `DATABASE_URL` | **Semi-annual (180 days)** | DBA / Infrastructure |
| PostgreSQL superuser password | **Annual (365 days)** | DBA / System owner |

---

## Rotation Procedures

### Pre-Rotation Checklist

- [ ] Schedule rotation during low-traffic window (avoid peak draft/waiver times)
- [ ] Notify deployment team and on-call engineer
- [ ] For routine rotation only, verify the current secret is backed up in an
      encrypted, restricted vault; never back up or restore a compromised value
- [ ] Test new secrets in non-production environment first
- [ ] Have a recovery plan ready that does not restore a compromised secret

### SECRET_KEY Rotation (Tier 1)

#### Step 1: Generate New Secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Output example:**
```
aBcDeFgHiJkLmNoPqRsT-UvWxYz0123456789_ABCD-EfGhIjKlMnOpQrS
```

#### Step 2: Validate in Non-Production

1. **Local or staging environment:**
   ```bash
   export SECRET_KEY="<new-secret>"
   cd backend && python -m pytest tests/ -v -k "auth or session"
   ```

2. **Verify auth flow:**
   - Login creates valid session
   - JWT tokens are correctly signed/verified
   - CSRF protection still functional
   - Access JWTs signed with the old key will be rejected after the application
     starts with the new key; persisted refresh tokens are not invalidated by
     this change alone.

3. **Verify no hard-coded secrets:**
   ```bash
   grep -r "SECRET_KEY=" . --include="*.py" --include="*.env" | grep -v ".venv" | grep -v "__pycache__"
   ```

#### Step 3: Deploy New Secret

**Blue-Green deployment is not currently supported.** The current application
supports one active JWT signing key and does not support verification with both
the old and new keys. Do not split traffic between instances using different
`SECRET_KEY` values: each instance will reject access tokens signed by the
other. Blue-green rotation requires a separately designed and tested multi-key
verification procedure before it is safe to use.

**Single-instance rotation (supported):**
1. Update `SECRET_KEY` in environment (Raspberry Pi systemd service or Docker `.env`)
2. Restart application service:
   ```bash
   sudo systemctl restart fantasy-football-backend
   # or
   docker-compose up -d
   ```
3. Monitor logs for auth/JWT errors
4. Verify login flow works

#### Step 4: Post-Rotation Validation

- [ ] New users can log in
- [ ] Access JWTs signed with the old `SECRET_KEY` are rejected
- [ ] JWT tokens issued with new SECRET_KEY are valid
- [ ] CSRF tokens are correctly signed
- [ ] No auth/session errors in logs
- [ ] Confirm refresh-token handling separately: refresh tokens are opaque database records, not signed with `SECRET_KEY`, and may issue new access tokens until expired or revoked

Changing `SECRET_KEY` invalidates old access JWTs, but does not by itself
invalidate persisted refresh tokens. For a suspected compromise, do not claim
all sessions are invalidated until refresh-token revocation has been completed
through a reviewed, approved operator procedure. Backend code has a per-user
revocation helper, but the application has no global administrative
refresh-token revocation workflow; coordinate the incident-wide procedure with
the security and database owners before claiming all sessions are invalidated.

#### Step 5: Archive Old Secret

- [ ] Document rotation date and time
- [ ] If rotation is routine, store the old SECRET_KEY in a restricted encrypted archive with timestamp
- [ ] Retain only for the approved recovery window; do not retain a compromised secret for recovery
- [ ] Never commit to version control

---

### External API Credential Rotation

#### Yahoo Fantasy Sports OAuth Credentials

1. Revoke or replace the exposed OAuth credential in the Yahoo developer console.
2. Update `YAHOO_CLIENT_SECRET`, `YAHOO_ACCESS_TOKEN`, and
   `YAHOO_REFRESH_TOKEN` in the configured secret source. The extractor also
   supports a legacy root-level `oauth2.json`; do not leave compromised values
   there.
3. Run the normal Yahoo OAuth/data-extraction validation flow.
4. Monitor extraction logs for authorization failures.

#### Google AI API Key

1. Revoke or replace the exposed key in the Google AI provider console.
2. Update `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the configured secret source.
3. Verify the advisor feature can authenticate with the replacement key.

#### Cloudflare Tunnel Credentials

The tunnel service uses the tunnel credentials JSON referenced by
`credentials-file` in `/etc/cloudflared/config.yml`; this is not
`/etc/cloudflared/cert.pem` or an application API token.

1. Replace or revoke the compromised tunnel credential using Cloudflare's
   supported tunnel-credential procedure.
2. Update the configured credentials JSON and preserve the service's required
   file ownership and permissions.
3. Restart and verify the service:
   ```bash
   sudo systemctl restart cloudflared
   sudo systemctl status cloudflared --no-pager
   sudo journalctl -u cloudflared -n 100 --no-pager
   ```

#### GitHub Issue Integration Credentials

The integration accepts a GitHub App private key (`GITHUB_APP_PRIVATE_KEY` or
`GITHUB_APP_PRIVATE_KEY_PATH`) or a personal access token (`GITHUB_TOKEN` or
`GH_TOKEN`). Replace the credential through its issuing GitHub settings, update
the configured secret source, then verify bug-report issue creation.

#### Slack and Teams Notification Webhooks

Replace a compromised webhook in its provider, update the corresponding
`SLACK_WEBHOOK_URL` or `TEAMS_WEBHOOK_URL` GitHub Actions secret, and verify a
workflow notification. ETL Slack configuration uses `SLACK_WEBHOOK_URL`.

---

## Runtime Guardrails

### Production Safety Checks

The application includes runtime validation to prevent deployment with default/insecure secrets:

Production settings, including `SECRET_KEY` presence, minimum length, and
weak-pattern rejection, are validated by `RuntimeSettings` in
`backend/core/config.py`.

**When this check triggers:**
- Application fails to start
- Error is logged with timestamp
- Deployment is blocked
- No fallback to insecure default

### Pre-Deployment Validation

```bash
# Local validation before pushing to production
python backend/scripts/validate_secrets.py
```

**Checks:**
- In production, `SECRET_KEY` is present, at least 32 characters long, and
  does not contain a rejected weak pattern
- `.env` and `backend/.env` are not tracked by Git
- A root-level `.env`, if present, has restricted permissions
- Production `AUTH_COOKIE_SECURE` is enabled (warning-level check)

The script does not check every provider credential or validate the permissions
of `backend/.env` or `/etc/fantasy-football-pi/backend.env`; configure those
checks separately.
Warnings do not fail the default run; `--strict` makes warnings return exit code
2.

---

## Incident Response: Compromised Secret

### If SECRET_KEY is Exposed

**Severity:** CRITICAL

**Immediate Actions (< 5 minutes):**

1. **Generate and deploy new SECRET_KEY immediately:**
   - Follow rotation procedure above
   - Deploy to production immediately

2. **Invalidate old access JWTs:**
   - Restart the application after updating `SECRET_KEY`
   - Access JWTs signed with the old key are rejected by the new process
   - This does not revoke persisted refresh tokens; follow a reviewed
     operator-approved revocation procedure before claiming all sessions ended

3. **Notify users:**
   - Email all league commissioners and owners
   - Post announcement on UI dashboard
   - Recommend password change as precaution

**Follow-up Actions (< 1 hour):**

4. **Audit logs for unauthorized access:**
   - Review application and reverse-proxy logs for unusual login or privileged API activity

5. **Check for suspicious API activity:**
   - Unusual player trades
   - Unauthorized admin actions
   - League setting changes

6. **Document incident:**
   - Time of detection
   - Scope of exposure (e.g., test server, staging, production)
   - Actions taken
   - User notifications sent

### If External API Credential is Compromised

**Severity:** HIGH (if public-facing) or MEDIUM (if internal)

1. **Immediately revoke/regenerate credential** in external service
2. **Update local environment variable** with new credential
3. **Restart application** to apply changes
4. **Monitor external service logs** for unauthorized access attempts
5. **If data was accessed**, follow breach notification procedures

---

## Monitoring and Alerting

### Recommended Alerts

| Trigger | Action |
|---------|--------|
| Auth failure rate > 5% for 5 minutes | Page on-call engineer |
| Multiple failed login attempts from single IP | Trigger rate limiter + alert |
| SECRET_KEY validation fails at startup | Critical alert + no deployment |
| Vault access fails during secret rotation | Alert ops team |

### Audit Trail

All secret rotation events are logged:

```
2026-05-09T14:32:00+00:00 INFO  secrets_rotation: SECRET_KEY rotated by ops-team
2026-05-09T14:32:15+00:00 INFO  secrets_rotation: New SECRET_KEY validation passed
2026-05-09T14:32:30+00:00 INFO  secrets_rotation: Application restarted successfully
2026-05-09T14:33:00+00:00 INFO  auth: old access JWT rejected
```

---

## Testing Rotation in Non-Production

### Test Environment Setup

Use a local non-production database with a pre-created test account. Do not use
production credentials. Run the server in Terminal 1 and the requests below in
Terminal 2 so the server can be stopped and restarted with the rotated key.
Run the server commands from the repository root.

```bash
# Terminal 1: start with the current test key
export SECRET_KEY="test-secret-1-1234567890123456789012"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

```bash
# Terminal 2: create a session using the local test account
curl -X POST http://127.0.0.1:8010/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test&password=test123" \
  -c cookies.txt

# Verify the access token is valid
curl http://127.0.0.1:8010/auth/me -b cookies.txt
```

Stop the server in Terminal 1, set the new key, and restart it:

```bash
# Terminal 1: after stopping the server
export SECRET_KEY="test-secret-2-0987654321098765432109"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

In Terminal 2, verify the old access token is rejected, then log in again:

```bash
# Expect 401. This does not test whether a persisted refresh token can mint a new access token.
curl -i http://127.0.0.1:8010/auth/me -b cookies.txt

curl -X POST http://127.0.0.1:8010/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test&password=test123" \
  -c cookies2.txt

curl http://127.0.0.1:8010/auth/me -b cookies2.txt
```

---

## Related Documentation

- [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) — Overall security baseline
- [DEPLOYMENT_WORKFLOWS.md](./DEPLOYMENT_WORKFLOWS.md) — Production deployment procedures
- [Incident Response Runbook](./INCIDENT_RESPONSE_RUNBOOK.md) — Full incident response procedures
