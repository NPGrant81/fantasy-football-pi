import re
from pathlib import Path


# Match postgres URLs with embedded passwords, e.g.:
# postgresql://user:password@host/db
POSTGRES_URL_WITH_PASSWORD = re.compile(r"postgres(?:ql)?://[^\s'\"@:]+:[^\s'\"@<]+@", re.IGNORECASE)


def test_no_hardcoded_postgres_passwords_in_runtime_python_files():
    """Prevent credential leakage/drift in runtime code.

    Runtime code should rely on env-provided DATABASE_URL and not hardcode
    credential-bearing Postgres DSNs.
    """

    repo_root = Path(__file__).resolve().parents[2]
    scan_roots = [repo_root / "backend", repo_root / "etl", repo_root / "scripts"]

    offenders = []
    for root in scan_roots:
        if not root.exists():
            continue

        for py_file in root.rglob("*.py"):
            if any(part in {"tests", "__pycache__", ".venv", "node_modules"} for part in py_file.parts):
                continue

            for line_number, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if POSTGRES_URL_WITH_PASSWORD.search(line):
                    offenders.append(f"{py_file.relative_to(repo_root).as_posix()}:{line_number}")

    assert offenders == [], (
        "Hardcoded Postgres credential URL(s) found in runtime code: "
        + ", ".join(sorted(offenders))
    )
