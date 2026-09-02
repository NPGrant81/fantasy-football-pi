from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_production_topology_matches_deployment_templates():
    systemd_service = _read("deploy/systemd/fantasy-football-backend.service.example")
    nginx_config = _read("deploy/nginx/fantasy-football-pi.conf.example")
    cloudflared_config = _read("deploy/cloudflared/config.cli.example.yml")
    incident_runbook = _read("docs/INCIDENT_RESPONSE_RUNBOOK.md")
    deployment_skill = _read(".github/skills/deployment/SKILL.md")
    deployment_guide = _read("docs/DEPLOYMENT.md")

    assert "ExecStartPre=/home/pi/fantasy-football-pi/backend/venv/bin/python -m backend.apply_migrations" in systemd_service
    assert "--host 127.0.0.1 --port 8000" in systemd_service
    assert "root /var/www/fantasy-football-pi/frontend/dist;" in nginx_config
    assert "proxy_pass http://127.0.0.1:8000;" in nginx_config
    assert cloudflared_config.count("service: http://127.0.0.1:80") == 2
    assert "systemctl restart fantasy-football-backend" in incident_runbook
    assert "http://localhost:8010" not in incident_runbook
    assert "# Update: SECRET_KEY=<new-secret>" in incident_runbook
    assert 'Environment="SECRET_KEY=<new-secret>"' not in incident_runbook
    assert "root /var/www/fantasy-football-pi/frontend/dist;" in deployment_skill
    assert "try_files $uri /index.html;" in deployment_skill
    assert "\t" not in deployment_guide


def test_architecture_authority_declares_development_and_redis_contracts():
    topology = _read("docs/architecture/overview.md")
    compose = _read("docker-compose.yml")
    rate_limiter = _read("backend/services/rate_limiter_service.py")

    assert "Development:" in topology
    assert "Production:" in topology
    assert "modular monolith" in topology
    assert "RATE_LIMITER_BACKEND=redis" in topology
    assert "redis:" in compose
    assert 'RATE_LIMITER_BACKEND = os.getenv("RATE_LIMITER_BACKEND", "memory")' in rate_limiter