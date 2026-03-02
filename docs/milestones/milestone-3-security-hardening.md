# Milestone 3 — Security Hardening Across the Stack

This milestone implements the security baseline for users, frontend, backend, data, and infrastructure.

---

## Scope

- Password hashing and secure authentication (bcrypt/argon2)
- Role‑based access control
- Session and token security
- CSRF protection
- Content Security Policy and XSS protections
- Rate limiting for UI and API
- Secure error handling
- SSH hardening, firewall rules, HTTPS, HSTS
- Secrets management

---

## Completion Criteria

- [ ] Authentication flows secure
- [ ] Frontend protected by CSP and CSRF tokens
- [ ] Backend enforces validation and authorization
- [ ] Raspberry Pi hardened (SSH, firewall, Nginx HTTPS)
- [ ] CI includes secrets scanning and dependency scanning

---

## Child Issues

| Issue | Title | Labels |
|-------|-------|--------|
| [Issue 7](../../issues/milestone-3-auth-password-security.md) | Authentication & Password Security | `security`, `backend`, `users` |
| [Issue 8](../../issues/milestone-3-frontend-security.md) | Frontend Security Controls | `security`, `frontend` |
| [Issue 9](../../issues/milestone-3-infrastructure-hardening.md) | Infrastructure Hardening | `security`, `infrastructure`, `raspberry-pi` |

---

## Dependencies

- Milestone 1 — Core Application Foundation
- Milestone 2 — Cross‑Platform Compatibility & Deployment Pipeline

---

## Notes

See [docs/SECURITY_HARDENING.md](../SECURITY_HARDENING.md) for existing security decisions and guidance.
