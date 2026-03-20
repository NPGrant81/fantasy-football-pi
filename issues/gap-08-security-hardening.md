### Gap 08 — Security Hardening

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `security`, `hardening`, `raspberry-pi`, `nginx`, `docker`

---

**Summary**

Apply a defense-in-depth security configuration to the Raspberry Pi host, Nginx reverse proxy, and Docker environment. Reduce the attack surface and ensure the platform meets baseline security expectations for a production deployment exposed to the internet.

---

**Tasks**

**Host / OS**
- [ ] Configure UFW firewall: allow only ports 22 (SSH), 80 (HTTP), 443 (HTTPS); deny all other inbound
- [ ] Install and configure Fail2ban with jails for SSH and Nginx HTTP auth failures
- [ ] Harden SSH: disable password authentication, disable root login, set `MaxAuthTries 3`, use a non-default port (optional)
- [ ] Enable automatic unattended security updates (`unattended-upgrades`)

**Nginx**
- [ ] Add security headers to Nginx config: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`
- [ ] Configure Nginx rate limiting for the API (`limit_req_zone`) to mitigate brute force and DoS
- [ ] Ensure TLS is configured with at least TLS 1.2; disable weak cipher suites

**Docker**
- [ ] Run application containers as a non-root user (verify `USER` directive in all Dockerfiles)
- [ ] Set `read_only: true` on container filesystems where possible; use explicit `tmpfs` for ephemeral write paths
- [ ] Pin all base image digests or use specific version tags (no `latest` in production Dockerfiles)
- [ ] Enable Docker Content Trust or image signature verification

**Verification**
- [ ] Run `docker scout` or `trivy` scan on production images and remediate critical/high CVEs
- [ ] Document the full hardening checklist in `docs/SECURITY_HARDENING.md` with completion status

---

**Acceptance Criteria**

- UFW is active; only required ports are open (verified with `ufw status`)
- Fail2ban is running with active jails for SSH and Nginx
- SSH password authentication is disabled
- All Nginx security headers score A or better on securityheaders.com
- Application containers run as non-root
- No critical CVEs in production Docker images (trivy/scout scan passes)
- `docs/SECURITY_HARDENING.md` documents every control with pass/fail status
