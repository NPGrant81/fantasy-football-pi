### Gap 01 — CI/CD Pipeline for ARM64 Builds

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `ci-cd`, `docker`, `raspberry-pi`, `infrastructure`

---

**Summary**

Implement a fully automated CI/CD pipeline that builds multi-architecture Docker images (including ARM64 for Raspberry Pi), publishes them to GitHub Container Registry (GHCR), and deploys to the Pi on merge to the main branch.

Currently, Docker images are built only for the host architecture and there is no automated pipeline to publish or deploy to the Pi.

---

**Tasks**

- [ ] Enable Docker `buildx` with QEMU emulation for cross-platform builds (`linux/amd64`, `linux/arm64/v8`)
- [ ] Update GitHub Actions CI workflow to build and push multi-arch images to GHCR on merge to `main`
- [ ] Implement automated image tagging strategy (`latest`, `sha-<short>`, `v<semver>`)
- [ ] Add a `deploy-pi.yml` GitHub Actions workflow (or extend `deploy-production.yml`) that SSH-deploys the new image to the Pi
- [ ] Validate the ARM64 build runs cleanly on actual Raspberry Pi hardware (or emulated ARM64 runner)
- [ ] Document required GitHub Actions secrets (`GHCR_TOKEN`, `PI_SSH_KEY`, `PI_HOST`, etc.)
- [ ] Add a build-status badge to `README.md`

---

**Acceptance Criteria**

- Merging to `main` triggers a multi-arch build and pushes both `amd64` and `arm64` images to GHCR
- Images are tagged with commit SHA and `latest`; semver tags applied on release
- The Pi receives the updated image automatically after a successful build (zero manual steps)
- ARM64 image starts and passes health checks on a Raspberry Pi 4 (or equivalent)
- Build workflow completes in under 15 minutes
- Workflow secrets are documented in `docs/SECRETS.md` (or equivalent)
