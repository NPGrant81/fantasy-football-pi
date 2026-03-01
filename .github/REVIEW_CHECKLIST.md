# Reviewer Quick Checklist

Use this as a fast triage guide when reviewing a PR.

## 1. Automated Checks (must be green before merging)

- [ ] CI workflow (`ci-contributor.yml`) passes – backend tests, frontend tests, lint
- [ ] No new linting errors introduced
- [ ] Code coverage has not regressed significantly

## 2. Manual Review Points

- [ ] PR description is complete (summary, motivation, how-to-test filled in)
- [ ] Logic is correct and edge cases are handled
- [ ] No secrets, credentials, or debug statements committed
- [ ] Database migrations (if any) are reversible and tested
- [ ] API changes are backwards-compatible or versioned
- [ ] Frontend changes are responsive (check major breakpoints)

## 3. Local Validation Commands

### Backend

```bash
# install deps and run tests
pip install -r backend/requirements.txt
pytest backend -q

# optional: run with coverage
pytest backend --cov=backend --cov-report=term-missing
```

### Frontend

```bash
cd frontend
npm ci --legacy-peer-deps
npm run lint
npm test
```

## 4. Merging Guidance

- Prefer **Squash and Merge** for feature branches to keep history clean.
- Ensure the commit message summarizes the PR purpose.
- Delete the source branch after merging.

## 5. Frugal AI Tips

- Use AI suggestions as a starting point, not the final answer – always read the diff yourself.
- Keep PRs small; large PRs are expensive to review and error-prone.
- Prefer targeted prompts: specify the file, function, or test you want help with.
