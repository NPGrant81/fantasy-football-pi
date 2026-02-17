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
- The example test calls `main.read_root()` directly to avoid running the FastAPI startup event (which seeds the DB). For tests that need the running app, use `TestClient` but be cautious about side effects.
- Add tests under `backend/tests/` and name files `test_*.py`.
