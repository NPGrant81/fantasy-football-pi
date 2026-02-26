How to run backend tests
------------------------

1) Install backend dependencies (includes pytest in requirements):

```powershell
cd backend
pip install -r requirements.txt
```

2) Run tests:

```powershell
cd backend
pytest -q
```

Notes:
- The example test calls `main.read_root()` directly to avoid running the FastAPI startup event (which seeds the DB).  For most tests you should instead rely on the provided fixtures:
  * `client` – a lightweight `TestClient` that **does not** execute the app's
    lifespan or seeding logic.  This is what `pytest` will inject by default
    when you declare a `client` parameter.
  * `integration_client` – a slower `TestClient` that **does** run the full
    lifespan (table creation + seeder).  Use this only for the few tests that
    must verify startup behaviour.

  These fixtures are defined in `backend/conftest.py` and dramatically
  improve test speed and isolation.
- Add tests under `backend/tests/` and name files `test_*.py`.
