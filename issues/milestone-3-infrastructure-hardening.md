### Issue 9 — Infrastructure Hardening

**Milestone:** [Milestone 3 — Security Hardening](../docs/milestones/milestone-3-security-hardening.md)  
**Labels:** `security`, `infrastructure`, `raspberry-pi`

---

**Summary**

Secure the Raspberry Pi production environment.

---

**Tasks**

- [ ] Enable SSH key‑based authentication
- [ ] Disable password‑based SSH login
- [ ] Configure firewall (UFW) — only required ports exposed
- [ ] Enable HTTPS and HSTS in Nginx
- [ ] Add fail2ban for brute‑force protection

---

**Acceptance Criteria**

- SSH hardened (key‑only, no password login)
- Only required ports exposed
- HTTPS enforced with HSTS headers
