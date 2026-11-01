#!/usr/bin/env python3
"""Reject Alembic revision files outside the governed migration locations."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


CANONICAL_MIGRATIONS = Path("db/migrations")
BOOTSTRAP_REVISION = Path("db/bootstrap/versions/0001_create_schema_at_0028.py")
IGNORED_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def _assigns_revision(statement: ast.stmt) -> bool:
    if isinstance(statement, ast.Assign):
        return any(
            isinstance(target, ast.Name) and target.id == "revision"
            for target in statement.targets
        )
    if isinstance(statement, ast.AnnAssign):
        return isinstance(statement.target, ast.Name) and statement.target.id == "revision"
    return False


def _has_module_revision(tree: ast.Module) -> bool:
    return any(_assigns_revision(statement) for statement in tree.body)


def find_revision_files(repository_root: Path) -> list[Path]:
    revision_files = []
    for path in repository_root.rglob("*.py"):
        relative_path = path.relative_to(repository_root)
        if IGNORED_DIRECTORIES.intersection(relative_path.parts):
            continue

        source = path.read_text(encoding="utf-8")
        if _has_module_revision(ast.parse(source, filename=str(relative_path))):
            revision_files.append(relative_path)
    return sorted(revision_files)


def find_noncanonical_revision_files(repository_root: Path) -> list[Path]:
    invalid_paths = []
    for path in find_revision_files(repository_root):
        is_canonical = path.parts[:2] == CANONICAL_MIGRATIONS.parts
        if not is_canonical and path != BOOTSTRAP_REVISION:
            invalid_paths.append(path)
    return invalid_paths


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    invalid_paths = find_noncanonical_revision_files(repository_root)
    if invalid_paths:
        print("ERROR: Alembic revision files must be in db/migrations/.")
        print(f"The governed bootstrap revision is the only exception: {BOOTSTRAP_REVISION}")
        for path in invalid_paths:
            print(f"  {path.as_posix()}")
        return 1

    print("Canonical migration layout check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
