from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
import zipfile

from backend import models
from backend.database import SessionLocal


@dataclass
class RestoreSummary:
    archive_path: str
    destination_root: str
    manifest_path: str | None
    dry_run: bool
    overwrite_existing: bool
    verify_manifest: bool
    run_id: int | None = None
    files_listed: int = 0
    files_restored: int = 0
    bytes_restored: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive_path": self.archive_path,
            "destination_root": self.destination_root,
            "manifest_path": self.manifest_path,
            "dry_run": self.dry_run,
            "overwrite_existing": self.overwrite_existing,
            "verify_manifest": self.verify_manifest,
            "run_id": self.run_id,
            "files_listed": self.files_listed,
            "files_restored": self.files_restored,
            "bytes_restored": self.bytes_restored,
            "warnings": self.warnings,
        }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(manifest_path: Path | None) -> dict[str, Any] | None:
    if manifest_path is None:
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _relative_entries(archive_file: zipfile.ZipFile) -> list[str]:
    return sorted(info.filename for info in archive_file.infolist() if not info.is_dir())


def _remove_destination(destination_root: Path) -> None:
    if destination_root.exists():
        shutil.rmtree(destination_root)


def _is_within_directory(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _safe_extract_archive(archive_file: zipfile.ZipFile, destination: Path) -> None:
    for member in archive_file.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"unsafe archive entry path: {member.filename}")

        target_path = destination / member_path
        if not _is_within_directory(destination, target_path):
            raise ValueError(f"archive entry escapes destination: {member.filename}")

        if member.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with archive_file.open(member, "r") as source, target_path.open("wb") as dest:
            shutil.copyfileobj(source, dest)


def run_restore_mfl_archive(
    *,
    archive_path: str,
    destination_root: str,
    manifest_path: str | None = None,
    dry_run: bool = True,
    overwrite_existing: bool = False,
    verify_manifest: bool = True,
) -> dict[str, Any]:
    archive = Path(archive_path)
    destination = Path(destination_root)
    manifest = Path(manifest_path) if manifest_path else None

    summary = RestoreSummary(
        archive_path=str(archive),
        destination_root=str(destination),
        manifest_path=str(manifest) if manifest else None,
        dry_run=dry_run,
        overwrite_existing=overwrite_existing,
        verify_manifest=verify_manifest,
    )

    metadata_db = SessionLocal()
    run = models.MflIngestionRun(
        pipeline_stage="restore_archived_exports",
        source_system="mfl",
        status="running",
        dry_run=dry_run,
        truncate_before_load=False,
        input_roots=[summary.archive_path],
        command="restore-mfl-archive",
        notes="Restore archived MFL export files from zip",
    )
    metadata_db.add(run)
    metadata_db.commit()
    metadata_db.refresh(run)
    summary.run_id = run.id

    try:
        if not archive.exists():
            raise FileNotFoundError(f"archive path does not exist: {archive}")
        if manifest is not None and not manifest.exists():
            raise FileNotFoundError(f"manifest path does not exist: {manifest}")

        manifest_payload = _load_manifest(manifest)
        manifest_files = manifest_payload.get("files", []) if manifest_payload else []
        manifest_map = {
            entry["relative_path"]: entry
            for entry in manifest_files
            if entry.get("relative_path")
        }

        with zipfile.ZipFile(archive) as archive_file:
            archive_entries = _relative_entries(archive_file)
            summary.files_listed = len(archive_entries)

            if verify_manifest and manifest_payload is not None:
                manifest_paths = sorted(manifest_map.keys())
                if manifest_paths != archive_entries:
                    raise ValueError("manifest file list does not match archive contents")

            if destination.exists() and any(destination.iterdir()):
                if not overwrite_existing:
                    raise FileExistsError(f"destination root already exists and is not empty: {destination}")
                if not dry_run:
                    _remove_destination(destination)

            if dry_run:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.summary_json = summary.to_dict()
                metadata_db.add(run)
                metadata_db.commit()
                return summary.to_dict()

            destination.mkdir(parents=True, exist_ok=True)
            _safe_extract_archive(archive_file, destination)

        restored_files = sorted(path for path in destination.rglob("*") if path.is_file())
        summary.files_restored = len(restored_files)

        for restored_file in restored_files:
            relative_path = restored_file.relative_to(destination).as_posix()
            size_bytes = restored_file.stat().st_size
            sha256 = _file_sha256(restored_file)
            summary.bytes_restored += size_bytes

            if verify_manifest and manifest_payload is not None:
                manifest_entry = manifest_map.get(relative_path)
                if manifest_entry is None:
                    raise ValueError(f"restored file missing from manifest: {relative_path}")
                if manifest_entry.get("sha256") and manifest_entry["sha256"] != sha256:
                    raise ValueError(f"checksum mismatch for restored file: {relative_path}")

            suffix = restored_file.suffix.lower()
            content_type = {
                ".html": "text/html",
                ".json": "application/json",
                ".csv": "text/csv",
            }.get(suffix, "application/octet-stream")

            manifest_entry = manifest_map.get(relative_path, {}) if manifest_payload else {}
            metadata_db.add(
                models.MflIngestionFile(
                    run_id=run.id,
                    dataset_key=str(manifest_entry.get("dataset_key") or f"restored/{restored_file.parent.relative_to(destination).as_posix() if restored_file.parent != destination else 'root'}"),
                    season=manifest_entry.get("season"),
                    source_league_id=None,
                    relative_path=relative_path,
                    content_type=content_type,
                    row_count=None,
                    size_bytes=size_bytes,
                    sha256=sha256,
                    retention_class="restored_archive_file",
                    archived_path=str(manifest_entry.get("archived_path") or ""),
                )
            )

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