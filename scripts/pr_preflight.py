#!/usr/bin/env python3
"""PR preflight checks for branch hygiene and CI alignment.

Usage:
    python scripts/pr_preflight.py
    python scripts/pr_preflight.py --run-local-checks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAPPING_FILE = ROOT / ".github" / "required-check-contexts.json"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
GENERATED_PATH_PREFIXES = (
    "frontend/coverage/",
    "frontend/lcov-report/",
)


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    message: str


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _status_lines() -> list[str]:
    result = _run_git(["status", "--porcelain"], check=True)
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _extract_path_from_status(line: str) -> str:
    # Porcelain format: XY<space>PATH (or old -> new for renames)
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip()


def check_clean_worktree(status_lines: list[str]) -> CheckResult:
    if not status_lines:
        return CheckResult("clean-worktree", "pass", "Working tree is clean.")
    return CheckResult(
        "clean-worktree",
        "fail",
        "Working tree is dirty. Stash or commit before preflight.",
    )


def check_fetch_origin_main() -> CheckResult:
    try:
        _run_git(["fetch", "origin", "main"], check=True)
    except subprocess.CalledProcessError as exc:
        return CheckResult(
            "fetch-origin-main",
            "fail",
            f"Failed to fetch origin/main: {exc.stderr.strip() or exc.stdout.strip()}",
        )
    return CheckResult("fetch-origin-main", "pass", "Fetched origin/main.")


def check_branch_drift() -> CheckResult:
    try:
        head = _run_git(["rev-parse", "HEAD"], check=True).stdout.strip()
        origin_main = _run_git(["rev-parse", "origin/main"], check=True).stdout.strip()
        merge_base = _run_git(["merge-base", "HEAD", "origin/main"], check=True).stdout.strip()
    except subprocess.CalledProcessError as exc:
        return CheckResult(
            "branch-drift",
            "fail",
            f"Unable to compute branch drift: {exc.stderr.strip() or exc.stdout.strip()}",
        )

    if head == origin_main:
        return CheckResult("branch-drift", "pass", "Branch is exactly at origin/main.")

    if merge_base != origin_main:
        return CheckResult(
            "branch-drift",
            "warn",
            "Branch does not include latest origin/main commit. Rebase or merge from main.",
        )

    return CheckResult("branch-drift", "pass", "Branch is based on latest origin/main.")


def check_merge_risk() -> CheckResult:
    try:
        merge_base = _run_git(["merge-base", "HEAD", "origin/main"], check=True).stdout.strip()
        simulated = _run_git(["merge-tree", merge_base, "HEAD", "origin/main"], check=True).stdout
    except subprocess.CalledProcessError as exc:
        return CheckResult(
            "merge-risk",
            "warn",
            f"Could not run merge simulation: {exc.stderr.strip() or exc.stdout.strip()}",
        )

    if "<<<<<<<" in simulated:
        return CheckResult(
            "merge-risk",
            "warn",
            "Simulated merge with origin/main indicates conflicts.",
        )
    return CheckResult("merge-risk", "pass", "No simulated merge conflicts detected.")


def check_generated_coverage_churn(status_lines: list[str]) -> CheckResult:
    changed_paths = [_extract_path_from_status(line) for line in status_lines]
    offenders = [
        p for p in changed_paths if any(p.startswith(prefix) for prefix in GENERATED_PATH_PREFIXES)
    ]
    if not offenders:
        return CheckResult("coverage-artifacts", "pass", "No generated coverage artifact churn detected.")
    return CheckResult(
        "coverage-artifacts",
        "warn",
        "Generated coverage artifacts are present in changes. Keep them out of PR commits.",
    )


def check_required_context_mapping() -> CheckResult:
    if not MAPPING_FILE.exists():
        return CheckResult(
            "required-context-mapping",
            "fail",
            f"Missing mapping file: {MAPPING_FILE.relative_to(ROOT).as_posix()}",
        )
    if not CI_WORKFLOW.exists():
        return CheckResult(
            "required-context-mapping",
            "fail",
            f"Missing CI workflow: {CI_WORKFLOW.relative_to(ROOT).as_posix()}",
        )

    try:
        mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult(
            "required-context-mapping",
            "fail",
            f"Invalid JSON in mapping file: {exc}",
        )

    required = mapping.get("required_contexts", [])
    if not required:
        return CheckResult("required-context-mapping", "fail", "required_contexts is empty.")

    ci_text = CI_WORKFLOW.read_text(encoding="utf-8")
    missing_jobs: list[str] = []
    for item in required:
        job_id = item.get("job_id", "").strip()
        context = item.get("context", "").strip()
        if not job_id or not context:
            return CheckResult(
                "required-context-mapping",
                "fail",
                "Each required_contexts entry must include non-empty context and job_id.",
            )
        marker = f"  {job_id}:"
        if marker not in ci_text:
            missing_jobs.append(job_id)

    if missing_jobs:
        return CheckResult(
            "required-context-mapping",
            "fail",
            f"Mapped job ids not found in ci.yml: {', '.join(sorted(set(missing_jobs)))}",
        )

    return CheckResult(
        "required-context-mapping",
        "pass",
        "Required-check mapping and ci.yml job ids are aligned.",
    )


def check_rerere() -> CheckResult:
    result = _run_git(["config", "--bool", "--get", "rerere.enabled"], check=False)
    value = result.stdout.strip().lower()
    if value == "true":
        return CheckResult("git-rerere", "pass", "git rerere is enabled.")
    return CheckResult(
        "git-rerere",
        "warn",
        "git rerere is disabled. Enable with: git config --global rerere.enabled true",
    )


def run_optional_local_checks() -> list[CheckResult]:
    if not MAPPING_FILE.exists():
        return [
            CheckResult(
                "local-checks",
                "warn",
                "Skipped local checks because mapping file is missing.",
            )
        ]

    mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    commands: list[str] = mapping.get("local_check_commands", [])
    if not commands:
        return [CheckResult("local-checks", "warn", "No local_check_commands configured.")]

    results: list[CheckResult] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            results.append(CheckResult("local-check", "pass", f"Passed: {command}"))
        else:
            results.append(
                CheckResult(
                    "local-check",
                    "warn",
                    f"Failed ({completed.returncode}): {command}",
                )
            )
    return results


def print_results(results: list[CheckResult]) -> int:
    rank = {"pass": 0, "warn": 1, "fail": 2}
    worst = 0

    print("PR preflight summary")
    print("=" * 60)
    for result in results:
        worst = max(worst, rank[result.status])
        print(f"[{result.status.upper()}] {result.name}: {result.message}")

    print("=" * 60)
    if worst == 2:
        print("Preflight failed. Resolve failures before pushing or opening a PR.")
        return 1
    if worst == 1:
        print("Preflight completed with warnings. Review items before pushing or opening a PR.")
        return 0
    print("Preflight passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PR preflight checks")
    parser.add_argument(
        "--run-local-checks",
        action="store_true",
        help="Run optional local check commands from .github/required-check-contexts.json",
    )
    args = parser.parse_args()

    status_lines = _status_lines()
    results: list[CheckResult] = [
        check_clean_worktree(status_lines),
        check_fetch_origin_main(),
        check_branch_drift(),
        check_merge_risk(),
        check_generated_coverage_churn(status_lines),
        check_required_context_mapping(),
        check_rerere(),
    ]

    if args.run_local_checks:
        results.extend(run_optional_local_checks())

    return print_results(results)


if __name__ == "__main__":
    sys.exit(main())
