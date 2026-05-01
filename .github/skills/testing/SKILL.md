---
name: testing
description: 'Backend pytest patterns, frontend Vitest/Testing Library conventions, fixture usage, mocking strategy, test file layout, and coverage expectations for Fantasy Football PI. Use when: writing tests, debugging test failures, setting up fixtures, mocking APIs, understanding test structure, or checking coverage requirements.'
argument-hint: 'Optional: focus area (backend | frontend | fixtures | mocks | coverage | flaky)'
---

# Testing

## Why This Exists
273+ tests across 48 files form the safety net that enables confident refactoring and feature development. The test suite runs in CI and must always be green. This skill documents the exact patterns to follow so new tests integrate cleanly.

## Test File Layout

```
backend/tests/
  conftest.py                    ← Shared fixtures (DB session, mock users)
  test_analytics_router.py       ← Tests for routers/analytics.py
  test_player_service.py         ← Tests for services/player_service.py
  test_waiver_service.py
  ...

frontend/tests/
  AnalyticsDashboard.test.jsx    ← Tests for pages/Analytics/AnalyticsDashboard.jsx
  BracketAccordion.test.jsx      ← Tests for components
  LuckIndexChart.test.jsx
  ...
```

**Rule**: Test file must mirror source file path, not be in a separate structure.

## Backend Tests (pytest)

### Setup
```python
# conftest.py provides:
# - db: in-memory SQLite session via pytest fixture
# - client: FastAPI TestClient
# - test_user, test_commissioner: User fixtures

from backend.conftest import db, client, test_user
```

### Test structure
```python
def test_get_luck_index_returns_rows(db, client, test_user):
    # Arrange — set up data using the db fixture
    league = models.League(name="Test", commissioner_id=test_user.id)
    db.add(league)
    db.commit()

    # Act
    response = client.get(
        f"/analytics/league/{league.id}/luck-index",
        headers={"Authorization": f"Bearer {test_user.token}"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "meta" in data
```

### What to test
- Happy path: valid inputs return expected shape
- Edge cases: empty league, no matchups, single week data
- Auth: unauthenticated returns 401, wrong role returns 403
- Validation: invalid params return 422

### What NOT to test
- SQLAlchemy internals (trust the ORM)
- Alembic migration correctness (tested by running migrations)
- Third-party library behavior

### Mocking external APIs
```python
import responses  # or requests_mock

@responses.activate
def test_espn_fetch():
    responses.add(responses.GET, "https://site.api.espn.com/...", json={...})
    result = fetch_espn_data(season=2025, week=1)
    assert result is not None
```

## Frontend Tests (Vitest + Testing Library)

### Standard mock setup
```javascript
// Always mock apiClient — never hit real endpoints
import { vi } from 'vitest';

vi.mock('../../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));
```

### Component test template
```jsx
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import LuckIndexChart from '../../src/components/charts/LuckIndexChart';
import apiClient from '../../src/api/client';

vi.mock('../../src/api/client', ...);

describe('LuckIndexChart', () => {
  beforeEach(() => {
    apiClient.get.mockResolvedValue({
      data: {
        rows: [
          { owner_id: 1, owner_name: 'Alice', luck: 2.5, quadrant: 'Good/Lucky', ... }
        ],
        meta: { metric: 'luck_index', league_id: 1, season: 2025 },
      }
    });
  });

  it('renders player rows', async () => {
    render(<LuckIndexChart />);
    await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument());
  });

  it('shows error when API fails', async () => {
    apiClient.get.mockRejectedValue(new Error('Network error'));
    render(<LuckIndexChart />);
    await waitFor(() => expect(screen.getByText(/error/i)).toBeInTheDocument());
  });
});
```

### Asserting analytics badge rendering (BracketAccordion pattern)
```jsx
// Test for conditional badge
expect(screen.getByText(/8 Team Playoff/i)).toBeInTheDocument();
expect(screen.getByText(/Reseeding/i)).toBeInTheDocument();
// Negative assertion
expect(screen.queryByText(/Consolation/i)).not.toBeInTheDocument();
```

## Running Tests

```bash
# Backend — all tests
cd backend && python -m pytest

# Backend — specific file
python -m pytest tests/test_analytics_router.py -v

# Frontend — all tests (one-time run)
cd frontend && npm test -- --run

# Frontend — specific file
npm test -- --run tests/LuckIndexChart.test.jsx

# Frontend — watch mode (dev)
npm test

# Frontend — coverage
npm test -- --run --coverage
```

## Known Flaky Test
`tests/MyTeam.test.jsx > refreshes commissioner rules on focus` — timing-sensitive test that fails in the full suite ~10% of the time but passes in isolation. Do not refactor to fix unless the root cause is isolated.

## Always Do
- Write a test before considering a feature complete
- Mock all external API calls (never let tests hit real endpoints)
- Use `waitFor` for async assertions in React tests
- Use `beforeEach` to reset mocks between tests
- Name tests with "given/when/then" or "it [verb]s [expectation]" pattern
- Include error-path tests (API failure, empty data, 403 response)

## Never Do
- Never hit a real database in frontend tests
- Never test implementation details (internal state, private methods)
- Never skip the `vi.mock()` for `apiClient`
- Never use `screen.getByTestId` unless `getByText`/`getByRole` are unavailable
- Never commit a test with `.only` or `.skip` (CI will catch this)

## Common Problems & Remediation

| Problem | Fix |
|---------|-----|
| `TypeError: Cannot read properties of undefined (reading 'data')` | Mock returns `{ data: ... }` not just the data object |
| Test passes in isolation, fails in suite | Shared state leak — check mocks are reset in `beforeEach` |
| `act(...)` warning in React test | Wrap async state updates in `waitFor(() => ...)` |
| pytest `ImportError` | Check `PYTHONPATH=backend` is set |
| 422 response in API test | Check required Pydantic fields in request body |

## Related Skills
- [API Patterns](../api-patterns/SKILL.md) — what to test in routers
- [Database](../database/SKILL.md) — conftest.py fixture patterns
- [UI/UX](../ui-ux/SKILL.md) — component test patterns
- [Git Workflow](../git-workflow/SKILL.md) — CI test gates
