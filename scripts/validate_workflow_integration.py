#!/usr/bin/env python3
"""Validate the configuration state of a workflow integration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT_PATH = ROOT / ".github" / "integration-contracts.json"
EXPECTED_ROOT_FIELDS = {"version", "integrations"}
EXPECTED_INTEGRATION_FIELDS = {
    "enablement_variable",
    "required_variables",
    "workflows",
    "owner",
}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class ContractError(ValueError):
    """Raised when an integration contract is invalid."""


@dataclass(frozen=True)
class IntegrationResult:
    state: str
    missing_variables: tuple[str, ...] = ()
    message: str = ""


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, dict[str, object]]:
    """Load and structurally validate the integration contract."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Unable to load integration contract: {exc}") from exc

    if not isinstance(payload, dict) or set(payload) != EXPECTED_ROOT_FIELDS:
        raise ContractError("Contract root must contain only version and integrations")
    if payload["version"] != 1:
        raise ContractError("Unsupported integration contract version")
    if not isinstance(payload["integrations"], dict) or not payload["integrations"]:
        raise ContractError("Contract integrations must be a non-empty object")

    for name, config in payload["integrations"].items():
        if not isinstance(name, str) or not name:
            raise ContractError("Integration names must be non-empty strings")
        _validate_integration_config(name, config)

    return payload["integrations"]


def _validate_integration_config(name: str, config: object) -> None:
    if not isinstance(config, dict) or set(config) != EXPECTED_INTEGRATION_FIELDS:
        raise ContractError(
            f"Integration {name!r} must contain only the required contract fields"
        )

    scalar_fields = ("enablement_variable", "owner")
    for field in scalar_fields:
        if not isinstance(config[field], str) or not config[field].strip():
            raise ContractError(f"Integration {name!r} has invalid {field}")

    for field in ("required_variables", "workflows"):
        values = config[field]
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
            or len(values) != len(set(values))
        ):
            raise ContractError(f"Integration {name!r} has invalid {field}")


def evaluate_integration(
    name: str,
    environment: Mapping[str, str],
    integrations: Mapping[str, Mapping[str, object]],
) -> IntegrationResult:
    """Return the explicit workflow state without exposing variable values."""
    if name not in integrations:
        raise ContractError(f"Unknown integration: {name}")

    config = integrations[name]
    enablement_variable = str(config["enablement_variable"])
    raw_enabled = environment.get(enablement_variable, "").strip().lower()

    if raw_enabled in FALSE_VALUES:
        return IntegrationResult(
            state="NOT_CONFIGURED",
            message=f"{name} is explicitly disabled by {enablement_variable}",
        )
    if raw_enabled not in TRUE_VALUES:
        return IntegrationResult(
            state="FAIL",
            missing_variables=(enablement_variable,),
            message=f"{enablement_variable} must be explicitly true or false",
        )

    required_variables = tuple(str(value) for value in config["required_variables"])
    missing = tuple(
        variable for variable in required_variables if not environment.get(variable, "").strip()
    )
    if missing:
        return IntegrationResult(
            state="FAIL",
            missing_variables=missing,
            message=f"{name} is enabled but required configuration is missing",
        )

    return IntegrationResult(state="PASS", message=f"{name} configuration is complete")


def _write_github_outputs(path: Path, result: IntegrationResult) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"state={result.state}\n")
        output.write(f"missing_csv={','.join(result.missing_variables)}\n")
        output.write(f"can_run={'true' if result.state == 'PASS' else 'false'}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integration", help="Integration name from the contract")
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
        help="Path to the integration contract JSON file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        integrations = load_contract(args.contract)
        result = evaluate_integration(args.integration, os.environ, integrations)
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            _write_github_outputs(
                Path(github_output),
                IntegrationResult(state="FAIL"),
            )
        return 2

    print(f"{result.state}: {result.message}")
    if result.missing_variables:
        print(f"Missing variables: {','.join(result.missing_variables)}")

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        _write_github_outputs(Path(github_output), result)

    return 0 if result.state != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
