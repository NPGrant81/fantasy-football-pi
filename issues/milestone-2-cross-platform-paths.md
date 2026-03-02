### Issue 4 — Cross‑Platform Path Handling

**Milestone:** [Milestone 2 — Cross‑Platform Compatibility & Deployment](../docs/milestones/milestone-2-cross-platform-deployment.md)  
**Labels:** `cross-platform`, `backend`, `tech-debt`

---

**Summary**

Ensure all file paths and OS interactions use cross‑platform safe methods.

---

**Tasks**

- [ ] Replace any hard‑coded paths with `pathlib`
- [ ] Standardize environment variable usage
- [ ] Audit code for Windows‑specific logic

---

**Acceptance Criteria**

- Code runs identically on Windows and Raspberry Pi
- No OS‑specific paths remain
