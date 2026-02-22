# Dependency Maintenance

This document describes the process for keeping the project's Python (and
JavaScript) dependencies up to date and secure over the long term.

## Tools

* **backend/scripts/check_dependencies.py** – a small helper that lists
  outdated packages, runs `pip audit` for security advisories, and writes a
  Markdown report (`dependency-report.md`). The script exits with a non-zero
  status when it finds any issues so automation jobs can detect them.
* **GitHub Actions workflow** (`.github/workflows/dependency-check.yml`) – runs
  the helper on the first day of each month and when manually dispatched. The
  job will fail if updates or vulnerabilities are found and uploads the report
  as an artifact.
* **Dependabot** (or similar bots) can be configured via GitHub to open PRs
  automatically when new releases are available. These PRs should be reviewed
  and merged after verifying the upgrade doesn’t break the app.

## Scheduled Checks

The action above handles the monthly check. To run locally or in another
environment, simply:

```bash
cd backend
python scripts/check_dependencies.py
```

When run manually you may specify `--lock-file` to include the
requirements-lock.txt file in the analysis.

## Responding to Findings

1. Update `backend/requirements.txt` with the desired version(s).
2. Install and test locally (e.g. `pip install -r requirements.txt`).
3. Refresh the lock file:
   ```bash
   python -m pip freeze > backend/requirements-lock.txt
   ```
4. Run the full test suite to ensure nothing broke.
5. Commit the changes and open a PR.

If the issue was security-related, the GitHub Actions workflow failure (or
Dependabot PR) serves as the trigger; otherwise a monthly check will catch
outdated packages before they age too far behind.

## Notes

* Pin versions when necessary and annotate the reason in the requirements
  file (e.g. “google-genai 1.64.0 locked for Gemini free‑tier”).
* JavaScript dependencies are managed separately; consider adding a similar
  check (e.g. `npm outdated`) if desired.
* Keeping dependencies current reduces the attack surface and makes upgrades
  easier when they are unavoidable.
