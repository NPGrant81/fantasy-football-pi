from click.testing import CliRunner

import backend.manage as manage


def test_load_mfl_html_normalized_command_is_retired():
    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "load-mfl-html-normalized",
            "--input-roots",
            "exports/history_html_normalized",
        ],
    )

    assert result.exit_code != 0
    assert "No such command 'load-mfl-html-normalized'" in result.output
