from click.testing import CliRunner

import backend.manage as manage


def test_normalize_mfl_html_records_command_is_retired(tmp_path):
    input_root = tmp_path / "html"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "normalize-mfl-html-records",
            "--input-root",
            str(input_root),
        ],
    )

    assert result.exit_code != 0
    assert "No such command 'normalize-mfl-html-records'" in result.output
