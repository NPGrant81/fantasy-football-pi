from pathlib import Path


def test_no_sqlite_url_literals_in_runtime_backend_code():
    """Prevent accidental SQLite runtime drift in production backend modules.

    SQLite is intentionally used in tests for speed and portability, while
    deployed/runtime environments are expected to use Postgres via DATABASE_URL.
    """

    backend_root = Path(__file__).resolve().parents[1]

    # These files are intentionally test-oriented helpers/docs for local debugging.
    allowlist = {
        backend_root / "conftest.py",
        backend_root / "scripts" / "debug_import.py",
    }

    offenders = []

    for py_file in backend_root.rglob("*.py"):
        if "tests" in py_file.parts:
            continue
        if py_file in allowlist:
            continue

        text = py_file.read_text(encoding="utf-8")
        if "sqlite://" in text:
            offenders.append(py_file.relative_to(backend_root.parent).as_posix())

    assert offenders == [], (
        "Found sqlite:// literals in runtime backend code. "
        "Use DATABASE_URL (Postgres) for runtime paths. Offenders: "
        + ", ".join(sorted(offenders))
    )
