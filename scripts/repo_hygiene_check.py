#!/usr/bin/env python3
"""Repository hygiene checks for organization and standards consistency.

Checks performed:
- docs/INDEX.md links resolve and include every docs/*.md file (except INDEX.md)
- No case-only path collisions in tracked git files
- React files under frontend/src/components and frontend/src/pages use PascalCase
  (except explicit entrypoints like index/main/setup files)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DOCS_INDEX = DOCS_DIR / "INDEX.md"
DOCS_REVIEW_REGISTRY = DOCS_DIR / "governance" / "doc_review_registry.json"
FRONTEND_SRC = ROOT / "frontend" / "src"
BACKEND_DIR = ROOT / "backend"

ALLOW_REACT_BASENAMES = {"index", "main", "setupTests"}

DEADLINE_PATTERN_TARGETS = [
    BACKEND_DIR / "routers" / "trades.py",
    BACKEND_DIR / "services" / "waiver_service.py",
]

ALLOWED_DOC_OWNERS = {
    "engineering",
    "product",
    "backend",
    "frontend",
    "platform",
    "security",
    "data",
    "qa",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _classify_doc_path(rel_path: str) -> tuple[str, str] | None:
    """Return (domain, artifact_type) for a docs path.

    This provides deterministic routing for governance ownership and drift checks.
    """
    rel = _normalize_rel_path(rel_path).lower()

    if not rel.startswith("docs/") or not rel.endswith(".md"):
        return None

    if rel == "docs/index.md":
        return ("governance", "index")
    if rel.startswith("docs/archive/"):
        return ("archive", "historical")
    if rel.startswith("docs/governance/"):
        return ("governance", "policy")
    if rel.startswith("docs/patterns/"):
        return ("governance", "pattern-workspace")
    if rel.startswith("docs/milestones/"):
        return ("product", "roadmap")
    if rel.startswith("docs/uat/"):
        return ("qa", "uat")
    if rel.startswith("docs/diagrams/"):
        return ("engineering", "diagram")
    if rel.startswith("docs/data-migration/"):
        return ("data", "migration")
    if rel.startswith("docs/pi-setup/"):
        return ("platform", "setup")
    if rel.startswith("docs/architecture/"):
        return ("engineering", "architecture")
    if rel.startswith("docs/gaps/"):
        return ("product", "gap-analysis")

    name = Path(rel).name
    if any(token in name for token in ["api_", "draft_day_advisor", "player_api_filtering", "model-serving", "backend_ci_pipeline"]):
        return ("backend", "api-or-service")
    if any(token in name for token in ["frontend", "ui_", "ux-", "responsive", "ui_reference"]):
        return ("frontend", "ui-or-ux")
    if any(token in name for token in ["cloudflare", "deployment", "raspberry", "restore", "pi_update", "ci_cd_observability"]):
        return ("platform", "operations")
    if any(token in name for token in ["security", "permissions"]):
        return ("security", "policy")
    if any(token in name for token in ["data", "scoring", "validation", "dictionary", "monte-carlo", "mfl_", "cross_module_edge_case", "db_migration_phase1"]):
        return ("data", "data-contract-or-quality")
    if any(token in name for token in ["pattern", "governance", "doc_issue", "documentation_update", "testing_session_summary", "dependency_maintenance", "dev-environment"]):
        return ("governance", "process")
    if any(token in name for token in ["project_management", "issue_status", "backlog_triage", "pr_notes", "cli_checkin"]):
        return ("product", "tracking")
    if any(token in name for token in ["trade_qa", "qa_regression"]):
        return ("qa", "qa-regression")
    if name == "architecture.md":
        return ("engineering", "architecture")

    return None


def _git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _pascal_case(name: str) -> bool:
    # Examples: MyComponent, APIBadge, TeamOwnerCard
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9]*", name))


def check_docs_index() -> list[str]:
    issues: list[str] = []
    if not DOCS_INDEX.exists():
        return [f"missing docs index: {DOCS_INDEX}"]

    index_text = _read_text(DOCS_INDEX)
    linked_paths = re.findall(r"\(([^)#]+\.md)\)", index_text)
    linked_set = {path.strip().lstrip("./") for path in linked_paths}

    # Check all markdown files recursively under docs/, not just top-level
    all_doc_files = {
        path.relative_to(DOCS_DIR).as_posix()
        for path in DOCS_DIR.rglob("*.md")
        if path.name.lower() != "index.md"
    }
    linked_normalized = {_normalize_rel_path(p).removeprefix("docs/") for p in linked_set}

    # Validate linked paths exist
    for rel_path in sorted(linked_set):
        if not (DOCS_DIR / rel_path).exists():
            issues.append(f"docs index has dangling link: docs/{rel_path}")

    # Validate all docs files are in index
    missing_from_index = sorted(all_doc_files - linked_normalized)
    for filename in missing_from_index:
        issues.append(f"docs file missing from index: docs/{filename}")

    return issues


def check_case_collisions() -> list[str]:
    issues: list[str] = []
    tracked = _git_tracked_files()
    by_lower: dict[str, list[str]] = {}
    for rel_path in tracked:
        by_lower.setdefault(rel_path.lower(), []).append(rel_path)

    for _, paths in sorted(by_lower.items()):
        unique = sorted(set(paths))
        if len(unique) > 1:
            issues.append(f"case-collision tracked paths: {', '.join(unique)}")

    return issues


def check_frontend_component_naming() -> list[str]:
    issues: list[str] = []
    targets = [FRONTEND_SRC / "components", FRONTEND_SRC / "pages"]

    for base in targets:
        if not base.exists():
            continue
        for file in base.rglob("*.jsx"):
            basename = file.stem
            if basename in ALLOW_REACT_BASENAMES:
                continue
            if not _pascal_case(basename):
                issues.append(
                    "frontend component/page filename must be PascalCase: "
                    f"{file.relative_to(ROOT).as_posix()}"
                )
        for file in base.rglob("*.tsx"):
            basename = file.stem
            if basename in ALLOW_REACT_BASENAMES:
                continue
            if not _pascal_case(basename):
                issues.append(
                    "frontend component/page filename must be PascalCase: "
                    f"{file.relative_to(ROOT).as_posix()}"
                )

    return issues


def check_frontend_ui_guardrails() -> list[str]:
    """Enforce baseline frontend standardization guardrails.

    Current guardrail scope (Stage 2):
    - Route pages should not introduce raw `<table>` markup unless they also
      consume shared table primitives from `@components/table/TablePrimitives`.
    """
    issues: list[str] = []
    pages_dir = FRONTEND_SRC / "pages"
    if not pages_dir.exists():
        return issues

    for file in list(pages_dir.rglob("*.jsx")) + list(pages_dir.rglob("*.tsx")):
        text = _read_text(file)
        has_raw_table = "<table" in text
        uses_primitives = "@components/table/TablePrimitives" in text
        if has_raw_table and not uses_primitives:
            issues.append(
                "route page contains raw <table> without TablePrimitives import: "
                f"{file.relative_to(ROOT).as_posix()}"
            )

    return issues


def check_pattern_contracts() -> list[str]:
    """Enforce baseline cross-cutting pattern contracts.

    Stage 1 scope:
    - Commissioner deadline enforcement contract in scoped backend targets.
    - Pattern docs workspace existence checks.
    """
    issues: list[str] = []

    helper_file = BACKEND_DIR / "services" / "commissioner_deadline_service.py"
    if not helper_file.exists():
        issues.append(
            "missing shared deadline helper: "
            "backend/services/commissioner_deadline_service.py"
        )

    for target in DEADLINE_PATTERN_TARGETS:
        if not target.exists():
            issues.append(f"missing deadline pattern target: {target.relative_to(ROOT).as_posix()}")
            continue

        text = _read_text(target)
        rel = target.relative_to(ROOT).as_posix()

        if "enforce_commissioner_deadline(" not in text:
            issues.append(
                "deadline pattern violation (helper not used): "
                f"{rel}"
            )

        if "datetime.fromisoformat(" in text:
            issues.append(
                "deadline pattern violation (inline parse logic found): "
                f"{rel}"
            )

    required_docs = [
        ROOT / "docs" / "PATTERN_LIBRARY.md",
        ROOT / "docs" / "patterns" / "README.md",
        ROOT / "docs" / "patterns" / "PATTERN_DECISION_LOG.md",
    ]
    for path in required_docs:
        if not path.exists():
            issues.append(f"missing pattern governance doc: {path.relative_to(ROOT).as_posix()}")

    return issues


def check_docs_governance_registry() -> list[str]:
    """Enforce documentation governance coverage and classification drift checks."""
    issues: list[str] = []

    if not DOCS_REVIEW_REGISTRY.exists():
        return [
            "missing docs governance registry: "
            "docs/governance/doc_review_registry.json"
        ]

    try:
        registry = json.loads(_read_text(DOCS_REVIEW_REGISTRY))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON in docs registry: {exc}"]

    if not isinstance(registry, list):
        return ["docs registry must be a JSON array"]

    seen_paths: dict[str, int] = {}
    registry_paths: set[str] = set()
    required_keys = {"path", "owner", "cadence_days", "last_reviewed"}

    for idx, entry in enumerate(registry, start=1):
        if not isinstance(entry, dict):
            issues.append(f"registry entry {idx} is not an object")
            continue

        missing = sorted(required_keys - set(entry.keys()))
        if missing:
            issues.append(f"registry entry {idx} missing keys: {', '.join(missing)}")
            continue

        rel_path = _normalize_rel_path(str(entry["path"]))
        rel_lower = rel_path.lower()
        owner = str(entry["owner"]).strip().lower()

        seen_paths[rel_lower] = seen_paths.get(rel_lower, 0) + 1
        registry_paths.add(rel_lower)

        if owner not in ALLOWED_DOC_OWNERS:
            issues.append(
                "invalid docs owner in registry "
                f"({owner}): {rel_path}"
            )

        full_path = ROOT / rel_path
        if not full_path.exists():
            issues.append(f"registry path does not exist: {rel_path}")

        if _classify_doc_path(rel_path) is None:
            issues.append(
                "unclassified docs path (update classification rules): "
                f"{rel_path}"
            )

    for rel_lower, count in sorted(seen_paths.items()):
        if count > 1:
            issues.append(f"duplicate docs registry path: {rel_lower}")

    docs_paths = {
        _normalize_rel_path(path.relative_to(ROOT).as_posix()).lower()
        for path in DOCS_DIR.rglob("*.md")
    }

    missing_from_registry = sorted(docs_paths - registry_paths)
    extra_in_registry = sorted(registry_paths - docs_paths)

    for rel in missing_from_registry:
        issues.append(f"docs file missing from governance registry: {rel}")
    for rel in extra_in_registry:
        issues.append(f"registry entry points to missing docs file: {rel}")

    for rel in sorted(docs_paths):
        if _classify_doc_path(rel) is None:
            issues.append(
                "unclassified docs file discovered (add rule or archive): "
                f"{rel}"
            )

    return issues


def main() -> int:
    issues: list[str] = []
    issues.extend(check_docs_index())
    issues.extend(check_docs_governance_registry())
    issues.extend(check_case_collisions())
    issues.extend(check_frontend_component_naming())
    issues.extend(check_frontend_ui_guardrails())
    issues.extend(check_pattern_contracts())

    if issues:
        print("repo hygiene check failed:")
        for item in issues:
            print(f"- {item}")
        return 1

    print("repo hygiene check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
