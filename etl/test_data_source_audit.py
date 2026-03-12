from pathlib import Path

from etl.validation.data_source_audit import audit_sources, report_to_markdown


def test_audit_sources_reports_expected_datasets():
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "backend" / "data"

    report = audit_sources(data_dir)

    assert "summary" in report
    assert "datasets" in report
    assert "identifier_audit" in report
    assert "draft_results" in report["datasets"]
    assert report["datasets"]["draft_results"]["exists"] is True


def test_report_to_markdown_includes_core_sections():
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "backend" / "data"
    report = audit_sources(data_dir)

    markdown = report_to_markdown(report)

    assert "# Issue #102 Data Source Audit" in markdown
    assert "## Dataset Inventory" in markdown
    assert "## Identifier Audit" in markdown
