# Incident Response Runbook: Security Events

**Issue:** #415  
**Document Version:** 1.0  
**Last Updated:** May 9, 2026

---

## Overview

This runbook provides step-by-step procedures for responding to security incidents including secret exposure, unauthorized access, and data breaches. Follow the appropriate section based on the incident type.

---

## 1. Compromised SECRET_KEY (CRITICAL)

**Incident:** A developer accidentally commits `SECRET_KEY` to git, or a server log exposes the secret.

### Triage (< 5 minutes)

**Goal:** Determine scope and impact

- [ ] **Where was the secret exposed?**
  - [ ] Committed to git repository (public or private)?
  - [ ] Visible in server logs (application, container, CI)?
  - [ ] Shared in chat/email/ticket?
  - [ ] Leaked in a debugging output?

- [ ] **How long was it exposed?**
  - [ ] < 1 hour
  - [ ] 1-24 hours
  - [ ] > 24 hours
  - Estimate time of compromise

- [ ] **Scope assessment:**
  - [ ] Test/staging environment only → Severity: MEDIUM
  - [ ] Production environment → Severity: CRITICAL
  - [ ] Production + publicly accessible → Severity: CRITICAL + notify users

### Immediate Remediation (< 15 minutes)

**Goal:** Stop active threats and revoke all existing sessions

1. **If committed to git:**
   ```bash
   # Remove from history (if private repo)
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch .env' \
     --prune-empty --tag-name-filter cat -- --all
   
   # Force push (WARNING: destructive)
   git push origin --force-all
   
   # Notify all developers to re-clone
   ```

2. **Revoke all existing sessions:**
   ```sql
   -- Connect to production database
   psql -d fantasy_football_pi
   
   -- Invalidate all access tokens
   TRUNCATE TABLE revoked_tokens;
   
   -- Invalidate all refresh tokens
   UPDATE refresh_tokens SET revoked_at = NOW() WHERE revoked_at IS NULL;
   
   -- Clear any cached auth in Redis (if applicable)
   FLUSHDB;
   ```

3. **Generate new SECRET_KEY:**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   # Output: [save this securely in vault]
   ```

4. **Deploy new SECRET_KEY to production:**
   
   **Via environment (Raspberry Pi systemd):**
   ```bash
   sudo nano /etc/systemd/system/fantasy-football-pi.service
   # Update: Environment="SECRET_KEY=<new-secret>"
   
   sudo systemctl daemon-reload
   sudo systemctl restart fantasy-football-pi
   ```
   
   **Via Docker:**
   ```bash
   # Update .env file or docker-compose.yml
   docker-compose down
   docker-compose up -d
   ```

5. **Verify new key is active:**
   ```bash
   curl http://localhost:8010/health
   # Should return 200 OK
   
   curl http://localhost:8010/auth/login \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"username": "test_user", "password": "test_password"}'
   # Should work with new sessions
   ```

### Short-term Actions (< 1 hour)

6. **Audit access logs for unauthorized activity:**
   ```sql
   -- Check for unusual login patterns
   SELECT user_id, COUNT(*) as login_attempts, 
          MIN(created_at) as first_login, MAX(created_at) as last_login
   FROM auth_logs
   WHERE created_at > NOW() - INTERVAL '24 hours'
   GROUP BY user_id
   HAVING COUNT(*) > 10
   ORDER BY login_attempts DESC;
   ```

7. **Check for privileged action abuse:**
   ```sql
   -- Look for suspicious admin/commissioner actions
   SELECT * FROM admin_audit_logs
   WHERE created_at > NOW() - INTERVAL '24 hours'
   AND action IN ('update_league_settings', 'force_trade_approval', 'reset_draft')
   ORDER BY created_at DESC;
   ```

8. **Force password reset for all users (optional, if high confidence):**
   ```sql
   -- Requires password_reset_required table
   UPDATE users SET password_reset_required = TRUE;
   ```

### Communication (< 2 hours)

9. **Notify users:**
   - **Email subject:** "Action Required: Security Incident — Please Reset Your Password"
   - **Include:**
     - What happened (non-technical summary)
     - What we did (sessions invalidated, new credentials deployed)
     - What users should do (change password if they feel uneasy)
     - Link to incident blog post

10. **Notify commissioners separately:**
    - Confirm their league data is intact
    - Check for suspicious trades or roster changes
    - Advise on monitoring their leagues

11. **Post incident blog (internal/public depending on scope):**
    - Timeline of discovery
    - Root cause (e.g., developer left credentials in test)
    - Remediation steps
    - Prevention measures

### Follow-up (24+ hours)

12. **Post-incident investigation:**
    - How did the secret end up exposed?
    - Should review processes change?
    - Was there unauthorized access? Confirm with logs.

13. **Update runbook based on incident:**
    - Did any steps fail?
    - What would have helped?
    - Add lessons learned

---

## 2. Unauthorized Admin Actions (HIGH)

**Incident:** Commissioner reports suspicious league settings changes, trades, or waivers they didn't approve.

### Triage (< 15 minutes)

**Goal:** Confirm unauthorized access and identify attacker

- [ ] **What action was unauthorized?**
  - [ ] League settings changed (roster size, scoring rules, etc.)
  - [ ] Trade was force-approved without commissioner approval
  - [ ] Waiver claims were processed incorrectly
  - [ ] Player draft picks were altered

- [ ] **When did it happen?**
  - Get exact timestamp from league log

- [ ] **Who reported it?**
  - Get their name, contact, and level of access

### Immediate Response (< 30 minutes)

1. **Verify the claim:**
   ```sql
   -- Check recent admin audit logs
   SELECT * FROM admin_audit_logs
   WHERE league_id = <affected_league_id>
   AND created_at > NOW() - INTERVAL '48 hours'
   ORDER BY created_at DESC;
   ```

2. **Identify the actor:**
   ```sql
   -- Get actor details
   SELECT actor_user_id, actor_username, actor_is_commissioner, 
          action, scope, metadata_json, created_at
   FROM admin_audit_logs
   WHERE league_id = <affected_league_id>
   AND id = <suspicious_audit_id>;
   ```

3. **Check if actor's session was compromised:**
   ```sql
   -- Get all sessions for that user in the timeframe
   SELECT * FROM user_sessions
   WHERE user_id = <actor_id>
   AND created_at > NOW() - INTERVAL '72 hours'
   ORDER BY created_at DESC;
   ```

4. **Assess damage:**
   - Was league data corrupted?
   - Were financial transactions (FAAB bids) affected?
   - Did picks/trades violate league rules?

### Remediation (< 1 hour)

5. **Revoke user session if compromised:**
   ```sql
   UPDATE user_sessions SET revoked_at = NOW()
   WHERE user_id = <actor_id> AND created_at > NOW() - INTERVAL '2 hours';
   ```

6. **Undo the unauthorized action:**
   - Contact the commissioner
   - Determine what the correct action should have been
   - **If reversible:** Revert in database with audit note
   - **If irreversible:** Work with league commissioner to agree on remediation

7. **Notify affected user:**
   - Explain what happened
   - Confirm we revoked their sessions
   - Request password reset
   - Ask them to check for any other unusual activity

### Investigation (24+ hours)

8. **Determine how account was compromised:**
   - [ ] Weak password?
   - [ ] Reused password from another service (have them check haveibeenpwned.com)?
   - [ ] Phishing?
   - [ ] Session hijacking?
   - [ ] Malware on their device?

9. **Update audit log:**
   ```sql
   INSERT INTO admin_audit_logs (actor_user_id, actor_username, 
     actor_is_superuser, action, scope, metadata_json, created_at)
   VALUES (NULL, 'system', TRUE, 'incident_response', 'security', 
     '{"type": "unauthorized_action_remediated", 
       "league_id": <id>, "original_actor": "<user>", "action_reverted": true}', NOW());
   ```

---

## 3. Suspicious Brute Force / Rate Limit Bypass (MEDIUM)

**Incident:** Rate limiter detects many failed login attempts, or suspicious volume of API calls from single IP.

### Triage (< 5 minutes)

**Goal:** Confirm attack pattern

- [ ] **Check rate limiter logs:**
  ```bash
  # If using Redis-backed rate limiter
  redis-cli KEYS "rate_limit:*" | head -20
  redis-cli GET "rate_limit:<ip>:<username>"
  ```

- [ ] **Source IP:**
  - Single IP or distributed?
  - Residential or datacenter?
  - Use `whois` to identify ISP/owner

### Immediate Response (< 10 minutes)

1. **Block the IP at firewall level (if truly malicious):**
   ```bash
   sudo ufw insert 1 deny from <attacker_ip>
   ```

2. **Verify rate limiter is working:**
   ```bash
   # Check failed login attempts
   tail -100 /var/log/fantasy-football-pi/auth.log | grep "rate.*limited"
   ```

3. **Monitor for escalation:**
   - Is attack continuing?
   - Are other IPs joining?
   - Are they trying different usernames?

### Follow-up (1+ hours)

4. **Notify affected users (if any succeeded):**
   - If failed attempts only: No action needed
   - If some succeeded: Same as "Unauthorized Access" incident

5. **Review rate limit configuration:**
   - Should it be stricter?
   - Should it apply to other endpoints (API calls)?

---

## 4. PII Exposure in Error Messages (MEDIUM)

**Incident:** An error message leaks user data (email, phone, etc.) or database details.

### Triage (< 10 minutes)

**Goal:** Find and patch the vulnerable endpoint

- [ ] **Where was PII exposed?**
  - Error message in API response?
  - In server logs?
  - In frontend error display?

- [ ] **What PII was exposed?**
  - User email
  - User ID
  - Database query details
  - Internal API paths

### Immediate Remediation (< 30 minutes)

1. **Patch the vulnerable code:**
   - Catch exception and return generic error message
   - Log details internally, don't expose to client
   - Deploy fix

   Example:
   ```python
   # BEFORE (BAD):
   except Exception as e:
       return {"error": str(e), "query": db_query}
   
   # AFTER (GOOD):
   except Exception as e:
       logger.error(f"Query failed for user {user_id}: {e}")
       return {"error": "Database error", "request_id": request_id}
   ```

2. **Audit similar endpoints:**
   ```bash
   # Search for error handling that might leak data
   grep -r "str(.*Exception" backend/ --include="*.py"
   grep -r "query.*error" backend/ --include="*.py"
   ```

3. **Deploy fix:**
   ```bash
   git add -A && git commit -m "fix(security): remove PII from error messages"
   git push origin feat/fix-pii-exposure
   ```

### Follow-up

4. **Update error handling guidelines:**
   - Always log details to server logs
   - Return generic error to client
   - Include request ID for debugging

5. **Add security test to CI:**
   - Parse all error responses
   - Verify no PII patterns (email, phone, etc.)
   - Fail CI if PII is detected

---

## 5. Dependency Vulnerability Detected (VARIABLE)

**Incident:** Dependabot or security scanner finds a CVE in a dependency.

### Triage (< 1 hour)

**Goal:** Assess severity and patch urgency

- [ ] **Severity level:**
  - [ ] Critical (CVSS 9+, exploitable, affects our code path)
  - [ ] High (CVSS 7-8, possible exploitation)
  - [ ] Medium (CVSS 4-6, unlikely to affect us)
  - [ ] Low (CVSS 0-3, very unlikely)

- [ ] **Does our code use the vulnerable function/class?**
  ```bash
  # Search for usage of vulnerable package
  grep -r "import <package>" backend/ frontend/
  ```

- [ ] **Are we exposed in production?**
  - Does the vulnerability require authentication? (less severe)
  - Does it affect our dependency tree or direct import? (more severe)

### Remediation (timeline varies)

**CRITICAL (patch immediately, within hours):**
1. Update dependency version: `pip install <package>==<patched-version>`
2. Run full test suite: `pytest backend/tests/`
3. Verify functionality in staging
4. Deploy to production
5. Monitor for regressions

**HIGH (patch within 24-48 hours):**
1. Schedule patching in next deployment window
2. Test thoroughly in non-prod first
3. Deploy with monitoring

**MEDIUM/LOW (patch in next release):**
1. Include in next scheduled update cycle
2. Still prioritize over unrelated changes
3. Document reason for delay (if any)

### Process

```bash
# Update and test
pip install --upgrade <package>
pytest backend/tests/ -v

# Commit and push
git add requirements.txt requirements-lock.txt
git commit -m "chore(deps): patch <package> for CVE-XXXX-XXXXX"
git push origin feat/patch-cve

# Create PR with security label
# GitHub Actions should run security checks
```

---

## Escalation & Communication

### When to Escalate

- **CRITICAL incidents** (compromised secret, large-scale breach)
  - Notify organization leadership immediately
  - Follow crisis communication protocol
  - Consider external notification (regulatory, customers)

- **HIGH incidents** (unauthorized admin access, data corruption)
  - Notify incident commander and on-call team
  - Page engineering lead
  - Have remediation plan before user notification

- **MEDIUM/LOW incidents**
  - Document in incident tracker
  - Address in next sprint/cycle
  - Monitor for patterns

### Communication Template

**For User-Facing Incidents:**

```
Subject: [INCIDENT] Brief description of issue

We identified a security issue that may have affected your account.

WHAT HAPPENED:
[Explain in non-technical terms]

WHAT WE DID:
[Describe remediation steps]

WHAT YOU SHOULD DO:
[Action items for users, e.g., password reset]

QUESTIONS:
[Contact info]

More details: [link to blog post or FAQ]
```

---

## Post-Incident Review

### Checklist (24-48 hours after incident)

- [ ] Root cause identified
- [ ] Permanent fix deployed (not just band-aid)
- [ ] Tests added to prevent recurrence
- [ ] Documentation updated
- [ ] Team trained on prevention
- [ ] Monitoring/alerting improved

### Update Runbook

If this runbook was unclear or missing steps:
- Update the relevant section
- Commit changes: `git add docs/INCIDENT_RESPONSE_RUNBOOK.md`
- Share with team for feedback

---

## External Resources

- [OWASP Incident Response](https://owasp.org/www-community/controls/Incident_Response)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [haveibeenpwned.com](https://haveibeenpwned.com) — Check for account breaches
