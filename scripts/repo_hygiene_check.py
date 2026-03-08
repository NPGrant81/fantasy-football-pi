#!/usr/bin/env python3
"""Repository hygiene checks for organization and standards consistency.

Checks performed:
- docs/INDEX.md links resolve and include every docs/*.md file (except INDEX.md)
- No case-only path collisions in tracked git files
- React files under frontend/src/components and frontend/src/pages use PascalCase
  (except explicit entrypoints like index/main/setup files)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DOCS_INDEX = DOCS_DIR / "INDEX.md"
FRONTEND_SRC = ROOT / "frontend" / "src"

ALLOW_REACT_BASENAMES = {"index", "main", "setupTests"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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

    doc_files = {
        path.name
        for path in DOCS_DIR.glob("*.md")
        if path.name.lower() != "index.md"
    }
    linked_top_level = {
        Path(rel).name
        for rel in linked_set
        if Path(rel).parent.as_posix() in {"", "."}
    }

    for rel_path in sorted(linked_set):
        if not (DOCS_DIR / rel_path).exists():
            issues.append(f"docs index has dangling link: docs/{rel_path}")

    for filename in sorted(doc_files - linked_top_level):
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


def main() -> int:
    issues: list[str] = []
    issues.extend(check_docs_index())
    issues.extend(check_case_collisions())
    issues.extend(check_frontend_component_naming())

    if issues:
        print("repo hygiene check failed:")
        for item in issues:
            print(f"- {item}")
        return 1

    print("repo hygiene check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
