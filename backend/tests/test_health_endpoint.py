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
    assert payload['schema'] in {'ok', 'error', 'unknown'}
    assert isinstance(payload['version'], str) and payload['version']
    assert 'checks' in payload
    assert payload['checks']['database'] == 'ok'
    assert payload['checks']['schema'] in {'ok', 'error', 'unknown'}
    assert isinstance(payload['uptime_seconds'], (int, float))


def test_health_head_returns_status_without_body(client):
    response = client.head('/health')

    assert response.status_code == 200
    assert response.content == b''


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
    assert payload['schema'] in {'error', 'unknown'}
    assert 'checks' in payload
    assert payload['checks']['database'] == 'error'
    assert payload['checks']['schema'] in {'error', 'unknown'}


def test_health_head_returns_bodyless_503_when_db_probe_fails(client, monkeypatch):
    class FailingEngine:
        def connect(self):
            raise RuntimeError('simulated db failure should not leak')

    monkeypatch.setattr(backend_main, 'engine', FailingEngine())

    response = client.head('/health')

    assert response.status_code == 503
    assert response.content == b''
