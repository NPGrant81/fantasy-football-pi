"""Helpers for repository-wide pytest bootstrap."""

from pathlib import Path


def backend_tests_requested(arguments: list[str], repository_root: Path) -> bool:
    """Return whether pytest arguments select the repository or backend tree."""
    backend_directory = repository_root / "backend"
    selected_paths = [
        Path(argument.split("::", 1)[0]).resolve()
        for argument in arguments
        if not argument.startswith("-")
        and Path(argument.split("::", 1)[0]).exists()
    ]
    if not selected_paths:
        return True
    return any(
        path == repository_root
        or path == backend_directory
        or path.is_relative_to(backend_directory)
        for path in selected_paths
    )
