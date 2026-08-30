## How to run backend tests

1. Install backend dependencies (includes pytest in requirements):

```powershell
python3.13.exe -m pip install -r backend/requirements.txt
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
- Routine local runs replace any inherited `DATABASE_URL` with disposable
  SQLite. CI preserves its migrated PostgreSQL service by setting
  `FFPI_PYTEST_USE_CONFIGURED_DATABASE=1`; do not set that opt-in for a
  developer or production database. Configured-database mode requires the
  GitHub Actions runtime signal, and pytest does not copy or log the configured
  URL.

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
