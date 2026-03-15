import json
from pathlib import Path
import zipfile

from backend.scripts import archive_mfl_csv_exports


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


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_archive_mfl_csv_exports_dry_run_preserves_files(tmp_path, monkeypatch):
    input_root = tmp_path / "history_csv_sample"
    file_a = input_root / "players" / "2026.csv"
    file_b = input_root / "franchises" / "2025.csv"
    _write_csv(file_a, "id,name\n1,a\n")
    _write_csv(file_b, "id,name\n2,b\n")

    fake_db = _FakeDb()
    monkeypatch.setattr(archive_mfl_csv_exports, "SessionLocal", lambda: fake_db)

    summary = archive_mfl_csv_exports.run_archive_mfl_csv_exports(
        input_root=str(input_root),
        dry_run=True,
        prune_csv=True,
    )

    assert summary["run_id"] == 1
    assert summary["csv_files_seen"] == 2
    assert summary["csv_files_archived"] == 0
    assert summary["csv_files_pruned"] == 0
    assert file_a.exists() is True
    assert file_b.exists() is True
    assert Path(summary["archive_path"]).exists() is False

    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]
    run_rows = [record for record in fake_db.added if hasattr(record, "pipeline_stage")]

    assert fake_db.committed is True
    assert fake_db.closed is True
    assert run_rows[0].pipeline_stage == "archive_csv_exports"
    assert file_rows[0].retention_class == "pending_archive_csv"


def test_archive_mfl_csv_exports_apply_prunes_files(tmp_path, monkeypatch):
    input_root = tmp_path / "history_csv_sample"
    file_a = input_root / "players" / "2026.csv"
    file_b = input_root / "franchises" / "2025.csv"
    _write_csv(file_a, "id,name\n1,a\n")
    _write_csv(file_b, "id,name\n2,b\n")

    fake_db = _FakeDb()
    monkeypatch.setattr(archive_mfl_csv_exports, "SessionLocal", lambda: fake_db)

    summary = archive_mfl_csv_exports.run_archive_mfl_csv_exports(
        input_root=str(input_root),
        dry_run=False,
        prune_csv=True,
    )

    archive_path = Path(summary["archive_path"])
    manifest_path = Path(summary["manifest_path"])

    assert summary["csv_files_seen"] == 2
    assert summary["csv_files_archived"] == 2
    assert summary["csv_files_pruned"] == 2
    assert archive_path.exists() is True
    assert manifest_path.exists() is True
    assert file_a.exists() is False
    assert file_b.exists() is False

    with zipfile.ZipFile(archive_path) as archive_file:
        assert sorted(archive_file.namelist()) == [
            "franchises/2025.csv",
            "players/2026.csv",
        ]

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["csv_files_pruned"] == 2
    assert len(manifest_payload["files"]) == 2

    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]
    assert file_rows[0].retention_class == "archived_raw_csv"
    assert file_rows[0].archived_path.endswith("::franchises/2025.csv")