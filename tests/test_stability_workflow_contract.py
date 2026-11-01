from pathlib import Path
import io
import json
import time
from urllib.error import URLError
import urllib.request

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def test_frontend_ci_requires_full_suite():
    steps = workflow("ci.yml")["jobs"]["frontend-test"]["steps"]
    unit = next(step for step in steps if step.get("id") == "frontend_unit_tests")
    assert unit["run"].strip() == "npm run test:coverage -- --run"


def test_canonical_migration_layout_gate_runs_for_every_change():
    jobs = workflow("ci.yml")["jobs"]
    migration_layout = jobs["migration-layout"]
    assert "needs" not in migration_layout
    assert "if" not in migration_layout
    assert any(
        step.get("run") == "python scripts/validate_migration_layout.py"
        for step in migration_layout["steps"]
    )

    ci_gate = jobs["ci-gate"]
    assert "migration-layout" in ci_gate["needs"]
    assert "migration-layout=${{ needs['migration-layout'].result }}" in (
        ci_gate["steps"][0]["env"]["RESULTS"]
    )
    assert "migration-layout=true" in ci_gate["steps"][0]["env"]["APPLICABILITY"]


def test_ui_automation_owns_readiness_and_reports_actual_outcomes():
    steps = workflow("ui-ux-automation.yml")["jobs"]["ui-ux-automation"]["steps"]
    node = next(step for step in steps if step.get("uses", "").startswith("actions/setup-node@"))
    assert node["with"]["node-version"] == 24
    startup = next(step for step in steps if step.get("id") == "ui_server")
    assert "node node_modules/vite/bin/vite.js" in startup["run"]
    assert "fetch(process.argv[1]" in startup["run"]
    assert "AbortSignal.timeout(5000)" in startup["run"]
    assert "curl" not in startup["run"]
    assert "kill -0" in startup["run"]
    assert "for attempt in {1..60}" in startup["run"]
    assert "after 60 bounded attempts" in startup["run"]
    for step_id in ("accessibility", "screenshots"):
        step = next(step for step in steps if step.get("id") == step_id)
        assert "npx cypress run" in step["run"]
        assert not step.get("continue-on-error")
    summary = next(step for step in steps if step["name"] == "Publish UI UX pipeline summary")
    assert "steps.accessibility.outcome" in summary["run"]
    assert "steps.screenshots.outcome" in summary["run"]
    assert "checks: executed" not in summary["run"]
    assert any(step["name"] == "Stop UI server" and step["if"] == "always()" for step in steps)


def test_recovery_check_requires_actual_disposable_restore():
    script = (ROOT / "scripts" / "validate_backup_recovery.sh").read_text()
    assert "scripts/verify_backup_restore.py" in script
    assert '--archive "${latest_backup}"' in script
    assert 'verification_db_url="sqlite:///${REPO_ROOT}/${db_path}"' in script
    assert 'DB_URL="${verification_db_url}"' in script


def test_microsd_backup_unit_loads_production_database_environment():
    unit = (ROOT / "deploy" / "systemd" / "microsd-db-backup.service.example").read_text()
    script = (ROOT / "ops" / "backup" / "microsd_db_backup.sh").read_text()
    assert "EnvironmentFile=/etc/fantasy-football-pi/backend.env" in unit
    assert 'DB_URL="${DB_URL:-${DATABASE_URL:-}}"' in script
    assert (
        'if [[ -z "${DB_URL:-}" && -z "${DATABASE_URL:-}" && '
        '-f "${REPO_ROOT}/backend/.env" ]]'
    ) in script
    assert (
        'if [[ -z "${DB_URL:-}" && -z "${DATABASE_URL:-}" && '
        '-f "${REPO_ROOT}/.env" ]]'
    ) in script


def test_production_migration_runbook_uses_protected_systemd_environment():
    runbook = (
        ROOT / ".github" / "skills" / "database" / "references" / "migration-runbook.md"
    ).read_text(encoding="utf-8")
    assert "systemd-run --wait --pipe --collect" in runbook
    assert "--property=EnvironmentFile=/etc/fantasy-football-pi/backend.env" in runbook
    assert "--property=User=pi" in runbook
    assert "python -m backend.apply_migrations" in runbook
    assert "alembic current" in runbook
    assert "alembic heads" in runbook


def test_nginx_vary_header_is_set_at_server_scope():
    config = (ROOT / "deploy" / "nginx" / "fantasy-football-pi.conf.example").read_text()
    server_start = config.index("server {", config.index("server {") + 1)
    assert server_start < config.index("add_header Vary Accept always;") < config.index("location /")


def test_both_deployments_verify_health_before_recording_success():
    for name in ("deploy-production.yml", "deploy-staging.yml"):
        steps = workflow(name)["jobs"][name.removesuffix(".yml")]["steps"]
        execution = next(step["run"] for step in steps if step["name"].startswith("Execute "))
        check = execution.index("Deployment health verification failed")
        metadata = execution.index('echo "$TARGET_REF_RESOLVED" > .deploy/current_')
        assert check < metadata
        assert check < execution.index('> .deploy/last_success_')
        assert 'payload.get("schema") == "ok"' in execution
        assert 'payload.get("database") == "ok"' in execution


@pytest.mark.parametrize("filename", ["deploy-production.yml", "deploy-staging.yml"])
@pytest.mark.parametrize("state", ["healthy", "degraded", "unreachable", "invalid-json"])
def test_deployment_health_gate_executes_fail_closed(filename, state, monkeypatch):
    steps = workflow(filename)["jobs"][filename.removesuffix(".yml")]["steps"]
    execution = next(step["run"] for step in steps if step["name"].startswith("Execute "))
    code = execution.split("<<'HEALTH_CHECK'\n", 1)[1].split("\nHEALTH_CHECK", 1)[0]
    calls = []

    def open_health(url, timeout):
        calls.append(url)
        if state == "unreachable":
            raise URLError("unavailable")
        if state == "invalid-json":
            return io.StringIO("invalid")
        return io.StringIO(json.dumps({
            "status": "ok",
            "database": "ok",
            "schema": "ok" if state == "healthy" else "error",
        }))

    monkeypatch.setattr(urllib.request, "urlopen", open_health)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    if state == "healthy":
        exec(compile(code, filename, "exec"), {})
        assert len(calls) == 1
    else:
        with pytest.raises(SystemExit, match="success metadata was not advanced"):
            exec(compile(code, filename, "exec"), {})
        assert len(calls) == 30
