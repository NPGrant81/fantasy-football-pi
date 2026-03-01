## Summary

<!-- Briefly describe what this PR does and why. -->

## Motivation

<!-- What problem does this solve? Link any related issues: Fixes #<issue-number> -->

## How to Test Locally

### Backend (FastAPI / pytest)

```bash
# from repo root
cd backend
pip install -r requirements.txt
pytest -q
```

### Frontend (Vite / React)

```bash
# from repo root
cd frontend
npm install
npm test -- --run
npm run lint
```

## Checklist

- [ ] Code follows the project style / linting rules
- [ ] Backend tests pass (`pytest backend -q`)
- [ ] Frontend tests pass (`npm test -- --run`)
- [ ] Frontend lint passes (`npm run lint`)
- [ ] New tests added for new functionality (or justified why not)
- [ ] Documentation updated if needed
- [ ] No secrets or credentials committed

## Notes for Reviewers

<!-- Anything reviewers should pay special attention to, known trade-offs, screenshots, etc. -->
