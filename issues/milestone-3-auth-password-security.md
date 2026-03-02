### Issue 7 — Authentication & Password Security

**Milestone:** [Milestone 3 — Security Hardening](../docs/milestones/milestone-3-security-hardening.md)  
**Labels:** `security`, `backend`, `users`

---

**Summary**

Implement secure user authentication and password handling.

---

**Tasks**

- [ ] Add bcrypt/argon2 password hashing
- [ ] Add login rate limiting
- [ ] Add session/token management (JWT or secure session)
- [ ] Add secure cookie settings (HTTP‑only, SameSite)

---

**Acceptance Criteria**

- Passwords never stored in plaintext
- Login attempts rate‑limited
- Sessions secure (HTTP‑only, SameSite)
