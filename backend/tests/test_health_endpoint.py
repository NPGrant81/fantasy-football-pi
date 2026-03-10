import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import main as backend_main


def test_health_endpoint_returns_service_status(client):
    response = client.get('/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'fantasy-football-backend'
    assert payload['status'] == 'ok'
    assert payload['database'] == 'ok'


def test_health_endpoint_returns_503_when_db_probe_fails(client, monkeypatch):
    class FailingEngine:
        def connect(self):
            raise RuntimeError('simulated db failure should not leak')

    monkeypatch.setattr(backend_main, 'engine', FailingEngine())

    response = client.get('/health')

    assert response.status_code == 503
    payload = response.json()
    assert payload['service'] == 'fantasy-football-backend'
    assert payload['status'] == 'degraded'
    assert payload['database'] == 'error'
    assert 'error' not in payload
