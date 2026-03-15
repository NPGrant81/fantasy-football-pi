import json
from pathlib import Path
import zipfile

from backend.scripts import restore_mfl_archive


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


def _make_archive_bundle(tmp_path: Path) -> tuple[Path, Path]:
    archive_path = tmp_path / "sample_html.zip"
    manifest_path = tmp_path / "sample_html_archive.json"
    files = {
        "raw/franchise_records/2026.html": "<html>record</html>",
        "raw/franchise_records/2025.html": "<html>older</html>",
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
        for relative_path, content in files.items():
            source_path = tmp_path / relative_path.replace("/", "_")
            source_path.write_text(content, encoding="utf-8")
            archive_file.write(source_path, arcname=relative_path)

    manifest_payload = {
        "files": [
            {
                "relative_path": relative_path,
                "dataset_key": "html_archive/raw/franchise_records",
                "season": int(Path(relative_path).stem),
                "size_bytes": len(content.encode("utf-8")),
                "sha256": restore_mfl_archive._file_sha256(tmp_path / relative_path.replace("/", "_")),
                "archived_path": f"archive/sample_html.zip::{relative_path}",
            }
            for relative_path, content in files.items()
        ]
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    return archive_path, manifest_path


def test_restore_mfl_archive_dry_run_lists_files(tmp_path, monkeypatch):
    archive_path, manifest_path = _make_archive_bundle(tmp_path)
    destination = tmp_path / "restore_target"

    fake_db = _FakeDb()
    monkeypatch.setattr(restore_mfl_archive, "SessionLocal", lambda: fake_db)

    summary = restore_mfl_archive.run_restore_mfl_archive(
        archive_path=str(archive_path),
        destination_root=str(destination),
        manifest_path=str(manifest_path),
        dry_run=True,
    )

    assert summary["run_id"] == 1
    assert summary["files_listed"] == 2
    assert summary["files_restored"] == 0
    assert destination.exists() is False
    assert fake_db.committed is True
    assert fake_db.closed is True


def test_restore_mfl_archive_apply_restores_and_verifies_manifest(tmp_path, monkeypatch):
    archive_path, manifest_path = _make_archive_bundle(tmp_path)
    destination = tmp_path / "restore_target"

    fake_db = _FakeDb()
    monkeypatch.setattr(restore_mfl_archive, "SessionLocal", lambda: fake_db)

    summary = restore_mfl_archive.run_restore_mfl_archive(
        archive_path=str(archive_path),
        destination_root=str(destination),
        manifest_path=str(manifest_path),
        dry_run=False,
    )

    assert summary["files_listed"] == 2
    assert summary["files_restored"] == 2
    assert (destination / "raw" / "franchise_records" / "2026.html").exists() is True
    assert (destination / "raw" / "franchise_records" / "2025.html").exists() is True

    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]
    run_rows = [record for record in fake_db.added if hasattr(record, "pipeline_stage")]

    assert run_rows[0].pipeline_stage == "restore_archived_exports"
    assert file_rows[0].retention_class == "restored_archive_file"
    assert file_rows[0].archived_path.endswith("::raw/franchise_records/2025.html")


def test_restore_mfl_archive_apply_overwrites_existing_destination(tmp_path, monkeypatch):
    archive_path, manifest_path = _make_archive_bundle(tmp_path)
    destination = tmp_path / "restore_target"
    destination.mkdir(parents=True, exist_ok=True)
    stale_file = destination / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")

    fake_db = _FakeDb()
    monkeypatch.setattr(restore_mfl_archive, "SessionLocal", lambda: fake_db)

    summary = restore_mfl_archive.run_restore_mfl_archive(
        archive_path=str(archive_path),
        destination_root=str(destination),
        manifest_path=str(manifest_path),
        dry_run=False,
        overwrite_existing=True,
    )

    assert summary["files_listed"] == 2
    assert summary["files_restored"] == 2
    assert stale_file.exists() is False
    assert (destination / "raw" / "franchise_records" / "2026.html").exists() is True