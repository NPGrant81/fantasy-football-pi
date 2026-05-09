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
| `SECRET_KEY` | Django/FastAPI session encryption, JWT signing | **Quarterly (90 days)** or on compromise | 32+ bytes | URL-safe base64 |
| `JWT_SECRET` (if separate) | JWT token signing | **Quarterly (90 days)** or on compromise | 32+ bytes | URL-safe base64 |

### Tier 2: External API Credentials (Medium Sensitivity)

These grant access to third-party services. Rotate if service is breached or credentials are exposed.

| Credential | Service | Rotation Cadence | Format |
|------------|---------|------------------|--------|
| OAuth2 Client Secret | MFL OAuth | **Semi-annual (180 days)** or on breach notification | UUID or client-generated |
| Cloudflare API Token | Cloudflare Tunnel | **Annual (365 days)** or after zone changes | Bearer token |
| GitHub App Secret | GitHub integrations (bug reports) | **Annual (365 days)** or on key exposure | URL-safe base64 |
| Slack Webhook (if used) | Notifications | **On-demand** (no scheduled rotation) | HTTPS URL |

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
- [ ] Verify backup of current secrets (encrypted, stored in secure vault)
- [ ] Test new secrets in non-production environment first
- [ ] Have rollback plan ready (old secret, verified working)

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
   - Existing sessions from old SECRET_KEY fail gracefully

3. **Verify no hard-coded secrets:**
   ```bash
   grep -r "SECRET_KEY=" . --include="*.py" --include="*.env" | grep -v ".venv" | grep -v "__pycache__"
   ```

#### Step 3: Deploy New Secret

**Option A: Blue-Green Deployment (Recommended)**
- Deploy new instance with `SECRET_KEY=<new-secret>`
- Verify health checks pass
- Route 10% traffic to new instance, monitor errors
- If stable, route 100% traffic
- Keep old instance running for 1 hour as rollback

**Option B: Rolling Restart (Single Instance)**
1. Update `SECRET_KEY` in environment (Raspberry Pi systemd service or Docker `.env`)
2. Restart application service:
   ```bash
   sudo systemctl restart fantasy-football-pi
   # or
   docker-compose up -d
   ```
3. Monitor logs for auth/JWT errors
4. Verify login flow works

#### Step 4: Post-Rotation Validation

- [ ] New users can log in
- [ ] Existing sessions remain valid (grace period: 30 minutes)
- [ ] JWT tokens issued with new SECRET_KEY are valid
- [ ] CSRF tokens are correctly signed
- [ ] No auth/session errors in logs
- [ ] Old SECRET_KEY-signed tokens are rejected after grace period

#### Step 5: Archive Old Secret

- [ ] Document rotation date and time
- [ ] Store old SECRET_KEY in encrypted archive with timestamp
- [ ] Retain for 90 days (recovery window)
- [ ] Never commit to version control

---

### External API Credential Rotation

#### OAuth2 Client Secret (MFL)

**Cadence:** Semi-annual (180 days) or on service breach notification

1. Log into MFL API settings (if available)
2. Request new client secret (old one typically revoked immediately)
3. Update `MFL_OAUTH_CLIENT_SECRET` in environment
4. Test MFL import/auth flow:
   ```bash
   python backend/scripts/validate_mfl_auth.py
   ```
5. Monitor MFL API calls for auth failures

#### Cloudflare API Token (Tunnel)

**Cadence:** Annual (365 days) or after zone configuration changes

1. Log into Cloudflare dashboard
2. Regenerate API token for "Cloudflare Tunnel" permission scope
3. Download new token JSON (`/etc/cloudflared/cert.pem` equivalent)
4. Update `/etc/cloudflared/config.yml` or Docker `.env`
5. Restart cloudflared service:
   ```bash
   sudo systemctl restart cloudflared
   ```
6. Verify tunnel status:
   ```bash
   cloudflared tunnel list
   ```

#### GitHub App Secret

**Cadence:** Annual (365 days) or on key exposure

1. Go to GitHub App settings (Organization Settings → Developer Settings → Apps)
2. Rotate webhook secret or client secret
3. Update `GITHUB_APP_SECRET` in environment
4. Test bug report creation flow
5. Monitor webhook delivery logs in GitHub

---

## Runtime Guardrails

### Production Safety Checks

The application includes runtime validation to prevent deployment with default/insecure secrets:

```python
# backend/main.py
if os.getenv("APP_ENV") == "production":
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key or secret_key == "change-me-in-production" or len(secret_key) < 32:
        raise RuntimeError(
            "FATAL: SECRET_KEY is not set or insecure in production. "
            "Set a strong random value via environment variable before deployment."
        )
```

**When this check triggers:**
- Application fails to start
- Error is logged with timestamp
- Deployment is blocked
- No fallback to insecure default

### Pre-Deployment Validation

```bash
# Local validation before pushing to production
./scripts/validate_secrets.py
```

**Checks:**
- `SECRET_KEY` is not a default/weak value
- `SECRET_KEY` length >= 32 bytes
- No secrets committed to git
- Environment variables are set
- All required Tier 1 secrets are present

---

## Incident Response: Compromised Secret

### If SECRET_KEY is Exposed

**Severity:** CRITICAL

**Immediate Actions (< 5 minutes):**

1. **Revoke all existing sessions:**
   ```sql
   TRUNCATE TABLE revoked_tokens;
   UPDATE user_sessions SET revoked_at = NOW();
   ```

2. **Force user logout:**
   - All cookies/JWT tokens become invalid
   - Users must log in again with new credentials

3. **Generate and deploy new SECRET_KEY:**
   - Follow rotation procedure above
   - Deploy to production immediately

4. **Notify users:**
   - Email all league commissioners and owners
   - Post announcement on UI dashboard
   - Recommend password change as precaution

**Follow-up Actions (< 1 hour):**

5. **Audit logs for unauthorized access:**
   ```sql
   SELECT * FROM admin_audit_logs 
   WHERE created_at > NOW() - INTERVAL '24 hours' 
   AND action NOT IN ('login', 'view_league')
   ORDER BY created_at DESC;
   ```

6. **Check for suspicious API activity:**
   - Unusual player trades
   - Unauthorized admin actions
   - League setting changes

7. **Document incident:**
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
2026-05-09T14:33:00+00:00 INFO  auth: 1,242 sessions invalidated
```

---

## Testing Rotation in Non-Production

### Test Environment Setup

```bash
# 1. Set current SECRET_KEY
export SECRET_KEY="test-secret-1-1234567890123456789012"

# 2. Start application
cd backend && python main.py

# 3. Create test session
curl -X POST http://localhost:8010/auth/login \
  -d '{"username": "test", "password": "test123"}' \
  -c cookies.txt

# 4. Verify session is valid
curl http://localhost:8010/auth/me -b cookies.txt

# 5. Change SECRET_KEY (simulating rotation)
export SECRET_KEY="test-secret-2-0987654321098765432109"

# 6. Restart application
# SIGNAL: send SIGTERM, restart process

# 7. Verify old session is invalid (should get 401 Unauthorized)
curl http://localhost:8010/auth/me -b cookies.txt

# 8. Create new session with new SECRET_KEY
curl -X POST http://localhost:8010/auth/login \
  -d '{"username": "test", "password": "test123"}' \
  -c cookies2.txt

# 9. Verify new session works
curl http://localhost:8010/auth/me -b cookies2.txt

# PASS: Old sessions invalidated, new sessions work
```

---

## Related Documentation

- [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) — Overall security baseline
- [DEPLOYMENT_WORKFLOWS.md](./DEPLOYMENT_WORKFLOWS.md) — Production deployment procedures
- [Incident Response Runbook](./INCIDENT_RESPONSE_RUNBOOK.md) — Full incident response procedures
