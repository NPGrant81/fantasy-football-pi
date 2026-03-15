from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import zipfile

from backend import models
from backend.database import SessionLocal


@dataclass
class ArchiveCsvSummary:
    input_root: str
    dry_run: bool
    prune_csv: bool
    overwrite_existing: bool
    run_id: int | None = None
    archive_path: str | None = None
    manifest_path: str | None = None
    csv_files_seen: int = 0
    csv_files_archived: int = 0
    csv_files_pruned: int = 0
    bytes_seen: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_root": self.input_root,
            "dry_run": self.dry_run,
            "prune_csv": self.prune_csv,
            "overwrite_existing": self.overwrite_existing,
            "run_id": self.run_id,
            "archive_path": self.archive_path,
            "manifest_path": self.manifest_path,
            "csv_files_seen": self.csv_files_seen,
            "csv_files_archived": self.csv_files_archived,
            "csv_files_pruned": self.csv_files_pruned,
            "bytes_seen": self.bytes_seen,
            "warnings": self.warnings,
        }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_csv_files(input_root: Path) -> list[Path]:
    return sorted(path for path in input_root.rglob("*.csv") if path.is_file())


def _dataset_key(input_root: Path, csv_path: Path) -> str:
    parent = csv_path.parent.relative_to(input_root)
    if parent == Path("."):
        return "csv_root"
    return f"csv_archive/{parent.as_posix()}"


def _season_from_path(csv_path: Path) -> int | None:
    try:
        return int(csv_path.stem)
    except ValueError:
        return None


def _remove_empty_directories(input_root: Path) -> None:
    for directory in sorted((path for path in input_root.rglob("*") if path.is_dir()), reverse=True):
        try:
            next(directory.iterdir())
        except StopIteration:
            directory.rmdir()


def run_archive_mfl_csv_exports(
    *,
    input_root: str,
    dry_run: bool = True,
    prune_csv: bool = False,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    root = Path(input_root)
    exports_root = root.parent
    archive_root = exports_root / "archive"
    manifest_root = exports_root / "manifests"
    archive_path = archive_root / f"{root.name}_csv.zip"
    manifest_path = manifest_root / f"{root.name}_csv_archive.json"

    summary = ArchiveCsvSummary(
        input_root=str(root),
        dry_run=dry_run,
        prune_csv=prune_csv,
        overwrite_existing=overwrite_existing,
        archive_path=str(archive_path),
        manifest_path=str(manifest_path),
    )

    metadata_db = SessionLocal()
    run = models.MflIngestionRun(
        pipeline_stage="archive_csv_exports",
        source_system="mfl",
        status="running",
        dry_run=dry_run,
        truncate_before_load=False,
        input_roots=[summary.input_root],
        command="archive-mfl-csv-exports",
        notes="Archive and optionally prune MFL CSV exports",
    )
    metadata_db.add(run)
    metadata_db.commit()
    metadata_db.refresh(run)
    summary.run_id = run.id

    try:
        if not root.exists():
            summary.warnings.append(f"input root does not exist: {root}")
        csv_files = _iter_csv_files(root) if root.exists() else []
        summary.csv_files_seen = len(csv_files)

        archive_spec = str(archive_path.relative_to(exports_root))
        manifest_entries: list[dict[str, Any]] = []

        if archive_path.exists() and not overwrite_existing:
            summary.warnings.append(f"archive path already exists: {archive_path}")
            if not dry_run:
                raise FileExistsError(f"archive path already exists: {archive_path}")

        if not csv_files:
            summary.warnings.append(f"no CSV files found under: {root}")

        for csv_path in csv_files:
            relative_path = csv_path.relative_to(root)
            file_size = csv_path.stat().st_size
            file_hash = _file_sha256(csv_path)
            summary.bytes_seen += file_size

            archived_spec = f"{archive_spec}::{relative_path.as_posix()}"
            manifest_entries.append(
                {
                    "relative_path": relative_path.as_posix(),
                    "dataset_key": _dataset_key(root, csv_path),
                    "season": _season_from_path(csv_path),
                    "size_bytes": file_size,
                    "sha256": file_hash,
                    "archived_path": archived_spec,
                }
            )
            metadata_db.add(
                models.MflIngestionFile(
                    run_id=run.id,
                    dataset_key=_dataset_key(root, csv_path),
                    season=_season_from_path(csv_path),
                    source_league_id=None,
                    relative_path=str(relative_path),
                    content_type="text/csv",
                    row_count=None,
                    size_bytes=file_size,
                    sha256=file_hash,
                    retention_class="pending_archive_csv" if dry_run else "archived_raw_csv",
                    archived_path=archived_spec,
                )
            )

        if not dry_run and csv_files:
            archive_root.mkdir(parents=True, exist_ok=True)
            manifest_root.mkdir(parents=True, exist_ok=True)

            if archive_path.exists() and overwrite_existing:
                archive_path.unlink()
            if manifest_path.exists() and overwrite_existing:
                manifest_path.unlink()

            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
                for csv_path in csv_files:
                    relative_path = csv_path.relative_to(root)
                    archive_file.write(csv_path, arcname=relative_path.as_posix())
                    summary.csv_files_archived += 1

            if prune_csv:
                for csv_path in csv_files:
                    csv_path.unlink()
                    summary.csv_files_pruned += 1
                _remove_empty_directories(root)

            manifest_payload = summary.to_dict() | {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "files": manifest_entries,
            }
            manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.summary_json = summary.to_dict()
        metadata_db.add(run)
        metadata_db.commit()
        return summary.to_dict()
    except Exception as exc:
        metadata_db.rollback()
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.notes = str(exc)
        run.summary_json = summary.to_dict()
        metadata_db.add(run)
        metadata_db.commit()
        raise
    finally:
        metadata_db.close()