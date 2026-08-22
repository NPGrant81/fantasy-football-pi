import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_import(command, cwd=REPO_ROOT):
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "testing",
            "DATABASE_URL": "sqlite:///:memory:",
        }
    )
    return subprocess.run(
        [sys.executable, "-c", command],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_database_supports_legacy_top_level_import():
    result = _run_import("import database", cwd=REPO_ROOT / "backend")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "import backend.scripts.import_nfl_data",
        (
            "import runpy; "
            "runpy.run_path('backend/scripts/import_nfl_data.py', run_name='import_check')"
        ),
        (
            "import runpy; "
            "runpy.run_path('backend/scripts/archive_weekly_stats.py', run_name='import_check')"
        ),
    ],
)
def test_data_scripts_support_declared_import_modes(command):
    result = _run_import(command)

    assert result.returncode == 0, result.stderr