## How to run backend tests

1. Install backend dependencies (includes pytest in requirements):

```powershell
cd backend
pip install -r requirements.txt
```

2. From the repository root, run the complete backend suite without setting
   `TESTING` or `DATABASE_URL`:

```powershell
# Windows PowerShell
python3.13.exe -m pytest backend -q
```

```bash
# POSIX shell
python3.13 -m pytest backend -q
```

Notes:

- Pytest selects a unique temporary SQLite database before importing the
  backend package, initializes the ORM schema once per session, and removes the
  database after the run. Repeated local runs cannot reuse a stale schema.
- An explicitly configured `DATABASE_URL` is preserved for CI and tests that
  intentionally exercise PostgreSQL. Never point routine local tests at a
  developer or production database.

- The example test calls `main.read_root()` directly to avoid running the FastAPI startup event (which seeds the DB). For most tests you should instead rely on the provided fixtures:
  - `client` – a lightweight `TestClient` that **does not** execute the app's
    lifespan or seeding logic. This is what `pytest` will inject by default
    when you declare a `client` parameter.
  - `integration_client` – a slower `TestClient` that **does** run the full
    lifespan (schema readiness + seeder). Use this only for the few tests that
    must verify startup behaviour.

  These fixtures are defined in `backend/conftest.py` and dramatically
  improve test speed and isolation.

- Add tests under `backend/tests/` and name files `test_*.py`.
