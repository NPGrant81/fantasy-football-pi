import json
from pathlib import Path

import pytest

from scripts import validate_workflow_integration as validator


def _contract(
    *,
    enablement_variable="SERVICE_ENABLED",
    required_variables=None,
):
    return {
        "service": {
            "enablement_variable": enablement_variable,
            "required_variables": required_variables or ["SERVICE_TOKEN"],
            "workflows": [".github/workflows/service.yml"],
            "owner": "platform-ops",
        }
    }


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_disabled_integration_is_not_configured(value):
    result = validator.evaluate_integration(
        "service",
        {"SERVICE_ENABLED": value},
        _contract(),
    )

    assert result.state == "NOT_CONFIGURED"
    assert result.missing_variables == ()


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_enabled_complete_integration_passes(value):
    result = validator.evaluate_integration(
        "service",
        {"SERVICE_ENABLED": value, "SERVICE_TOKEN": "secret-value"},
        _contract(),
    )

    assert result.state == "PASS"


def test_enabled_incomplete_integration_fails_without_exposing_values():
    environment = {
        "SERVICE_ENABLED": "true",
        "SERVICE_TOKEN": "",
        "OTHER_SECRET": "must-not-leak",
    }

    result = validator.evaluate_integration("service", environment, _contract())

    assert result.state == "FAIL"
    assert result.missing_variables == ("SERVICE_TOKEN",)
    assert "must-not-leak" not in result.message


@pytest.mark.parametrize("value", ["", "enabled", "maybe"])
def test_missing_or_malformed_enablement_fails_closed(value):
    result = validator.evaluate_integration(
        "service",
        {"SERVICE_ENABLED": value, "SERVICE_TOKEN": "configured"},
        _contract(),
    )

    assert result.state == "FAIL"
    assert result.missing_variables == ("SERVICE_ENABLED",)


def test_unknown_integration_is_rejected():
    with pytest.raises(validator.ContractError, match="Unknown integration"):
        validator.evaluate_integration("missing", {}, _contract())


def test_contract_rejects_unknown_fields(tmp_path):
    payload = {
        "version": 1,
        "integrations": _contract(),
        "unexpected": True,
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(validator.ContractError, match="root"):
        validator.load_contract(contract_path)


def test_contract_rejects_unknown_integration_fields(tmp_path):
    integrations = _contract()
    integrations["service"]["unexpected"] = True
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({"version": 1, "integrations": integrations}),
        encoding="utf-8",
    )

    with pytest.raises(validator.ContractError, match="required contract fields"):
        validator.load_contract(contract_path)


def test_contract_rejects_duplicate_variable_names(tmp_path):
    integrations = _contract(required_variables=["SERVICE_TOKEN", "SERVICE_TOKEN"])
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({"version": 1, "integrations": integrations}),
        encoding="utf-8",
    )

    with pytest.raises(validator.ContractError, match="required_variables"):
        validator.load_contract(contract_path)


def test_cli_does_not_print_configured_secret_values(monkeypatch, capsys):
    monkeypatch.setenv("PRODUCTION_DEPLOY_ENABLED", "true")
    integrations = validator.load_contract()
    secret_value = "sensitive-value-must-not-appear"
    for variable in integrations["production_deploy"]["required_variables"]:
        monkeypatch.setenv(variable, secret_value)

    assert validator.main(["production_deploy"]) == 0

    captured = capsys.readouterr()
    assert secret_value not in captured.out
    assert secret_value not in captured.err


def test_cli_writes_fail_outputs_when_contract_is_invalid(
    monkeypatch, tmp_path, capsys
):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({"version": 2, "integrations": _contract()}),
        encoding="utf-8",
    )
    output_path = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    assert (
        validator.main(["service", "--contract", str(contract_path)])
        == 2
    )

    captured = capsys.readouterr()
    assert "FAIL:" in captured.err
    assert output_path.read_text(encoding="utf-8") == (
        "state=FAIL\nmissing_csv=\ncan_run=false\n"
    )


def test_repository_contract_is_valid():
    integrations = validator.load_contract()

    assert set(integrations) == {
        "production_deploy",
        "staging_deploy",
        "roster_sync",
        "fantasynerds",
        "yahoo",
    }


def test_repository_workflows_match_contract():
    integrations = validator.load_contract()

    for name, config in integrations.items():
        expected_variables = {
            config["enablement_variable"],
            *config["required_variables"],
        }
        for relative_path in config["workflows"]:
            workflow_path = validator.ROOT / Path(relative_path)
            workflow = workflow_path.read_text(encoding="utf-8")

            assert f"validate_workflow_integration {name}" in workflow
            for variable in expected_variables:
                assert variable in workflow, f"{variable} missing from {relative_path}"


def test_deployment_precheck_requires_production_pass():
    workflow_path = (
        validator.ROOT / ".github" / "workflows" / "deployment-secrets-precheck.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "needs.precheck-production.outputs.state != 'PASS'" in workflow
    assert "needs.precheck-staging.outputs.state != 'NOT_CONFIGURED'" in workflow
    assert (
        'elif [ "${{ needs.precheck-production.outputs.state }}" = "NOT_CONFIGURED" ]'
        in workflow
    )
    assert (
        "needs.precheck-production.outputs.state != 'NOT_CONFIGURED'"
        in workflow
    )


def test_required_checks_are_unconditional_gates_only():
    required_checks_path = validator.ROOT / ".github" / "REQUIRED_CHECKS.md"
    required_checks = required_checks_path.read_text(encoding="utf-8")
    merge_blocking_section = required_checks.split(
        "## Merge-blocking checks", maxsplit=1
    )[1].split("## Operational checks", maxsplit=1)[0]
    check_names = {
        line.removeprefix("- `").removesuffix("`")
        for line in merge_blocking_section.splitlines()
        if line.startswith("- `")
    }

    assert check_names == {"ci-gate", "gitleaks"}


def test_production_deploy_summary_reports_validation_state():
    workflow_path = (
        validator.ROOT / ".github" / "workflows" / "deploy-production.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")

    assert 'echo "- State: ${{ steps.validate.outputs.state }}"' in workflow
    assert "      - name: Publish production deployment intent\n        if: always()" in workflow


def test_staging_deploy_summary_runs_after_validation_failure():
    workflow_path = validator.ROOT / ".github" / "workflows" / "deploy-staging.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "      - name: Publish staging deployment intent\n        if: always()" in workflow


def test_roster_sync_accepts_only_confirmed_completion_marker():
    workflow_path = validator.ROOT / ".github" / "workflows" / "sync-rosters.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    assert 'grep -Fq "NFL Reality Sync Complete."' in workflow
    assert "if completed is False:" in workflow
    assert 'echo "executed=true" >> "$GITHUB_OUTPUT"' in workflow


def test_workflow_contract_suite_runs_in_ci_and_contract_changes_select_backend_lane():
    ci_workflow = (
        validator.ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    classifier = (
        validator.ROOT / ".github" / "workflows" / "detect-changes.yml"
    ).read_text(encoding="utf-8")

    assert "python -m pytest tests/test_workflow_integration_contract.py -q" in ci_workflow
    assert ".github/integration-contracts.json" in classifier
