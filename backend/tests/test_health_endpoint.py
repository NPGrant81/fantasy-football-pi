import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_health_endpoint_returns_service_status(client):
    response = client.get('/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'fantasy-football-backend'
    assert payload['status'] in {'ok', 'degraded'}
    assert payload['database'] in {'ok', 'error'}
