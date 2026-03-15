import json
from pathlib import Path
import zipfile

from backend.scripts import archive_mfl_html_exports


class _FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, record):
        if getattr(record, "id", None) is None:
            record.id = 1

    def close(self):
        self.closed = True


def _write_html(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_archive_mfl_html_exports_dry_run_preserves_files(tmp_path, monkeypatch):
    input_root = tmp_path / "history_html_records_sample"
    file_a = input_root / "raw" / "franchise_records" / "2026.html"
    file_b = input_root / "raw" / "league_awards" / "2025.html"
    _write_html(file_a, "<html>A</html>")
    _write_html(file_b, "<html>B</html>")

    fake_db = _FakeDb()
    monkeypatch.setattr(archive_mfl_html_exports, "SessionLocal", lambda: fake_db)

    summary = archive_mfl_html_exports.run_archive_mfl_html_exports(
        input_root=str(input_root),
        dry_run=True,
        prune_html=True,
    )

    assert summary["run_id"] == 1
    assert summary["html_files_seen"] == 2
    assert summary["html_files_archived"] == 0
    assert summary["html_files_pruned"] == 0
    assert file_a.exists() is True
    assert file_b.exists() is True
    assert Path(summary["archive_path"]).exists() is False

    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]
    run_rows = [record for record in fake_db.added if hasattr(record, "pipeline_stage")]

    assert fake_db.committed is True
    assert fake_db.closed is True
    assert run_rows[0].pipeline_stage == "archive_html_exports"
    assert file_rows[0].retention_class == "pending_archive_html"


def test_archive_mfl_html_exports_apply_prunes_files(tmp_path, monkeypatch):
    input_root = tmp_path / "history_html_records_sample"
    file_a = input_root / "raw" / "franchise_records" / "2026.html"
    file_b = input_root / "raw" / "league_awards" / "2025.html"
    _write_html(file_a, "<html>A</html>")
    _write_html(file_b, "<html>B</html>")

    fake_db = _FakeDb()
    monkeypatch.setattr(archive_mfl_html_exports, "SessionLocal", lambda: fake_db)

    summary = archive_mfl_html_exports.run_archive_mfl_html_exports(
        input_root=str(input_root),
        dry_run=False,
        prune_html=True,
    )

    archive_path = Path(summary["archive_path"])
    manifest_path = Path(summary["manifest_path"])

    assert summary["html_files_seen"] == 2
    assert summary["html_files_archived"] == 2
    assert summary["html_files_pruned"] == 2
    assert archive_path.exists() is True
    assert manifest_path.exists() is True
    assert file_a.exists() is False
    assert file_b.exists() is False

    with zipfile.ZipFile(archive_path) as archive_file:
        assert sorted(archive_file.namelist()) == [
            "raw/franchise_records/2026.html",
            "raw/league_awards/2025.html",
        ]

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["html_files_pruned"] == 2
    assert len(manifest_payload["files"]) == 2

    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]
    assert file_rows[0].retention_class == "archived_raw_html"
    assert file_rows[0].archived_path.endswith("::raw/franchise_records/2026.html")