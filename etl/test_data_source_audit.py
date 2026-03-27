from pathlib import Path

from etl.validation.data_source_audit import DATASET_FILES, audit_sources, report_to_markdown


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


def test_audit_sources_detects_missing_refs_and_invalid_years_with_tmp_data(tmp_path):
    data_dir = tmp_path / "backend" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    files = {
        DATASET_FILES["draft_results"]: "PlayerID,OwnerID,Year,PositionID\nP1,O1,2024,QB\nP2,O1,1999,ZZ\n",
        DATASET_FILES["player_id"]: "Player_ID,PlayerName,PositionID\nP1,Player One,QB\n",
        DATASET_FILES["position_id"]: "PositionID,Position,PositionStatus\nQB,Quarterback,active\n",
        DATASET_FILES["budget"]: "DraftBudget,Year,OwnerID\n100,2024,O1\n200,bad-year,O2\n",
        DATASET_FILES["owner_registry"]: "Team,TeamID\nA,O1\n",
    }

    for filename, content in files.items():
        (data_dir / filename).write_text(content, encoding="utf-8")

    report = audit_sources(data_dir)
    id_audit = report["identifier_audit"]

    assert id_audit["missing_player_references_in_player_id"] == ["P2"]
    assert id_audit["missing_position_references_in_position_id"] == ["ZZ"]
    assert id_audit["inactive_or_unknown_position_ids_in_draft_results"] == ["ZZ"]
    assert id_audit["owner_id_mismatch_between_draft_results_and_budget"] == []
    assert id_audit["draft_results_invalid_year_rows"] == 1
    assert id_audit["budget_invalid_year_rows"] == 1
