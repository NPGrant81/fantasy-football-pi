from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
for owner in [1, 2]:
    res = client.get(f"/team/{owner}?week=1")
    print(owner, res.status_code, res.text)
