"""Load normalized MFL HTML record datasets into Postgres.

The loader ingests CSVs produced by `normalize-mfl-html-records` into a
single fact table for downstream querying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from backend import models
from backend.database import SessionLocal


@dataclass
class LoadSummary:
    input_roots: list[str]
    dry_run: bool
    truncate_before_load: bool
    target_league_id: int | None
    run_id: int | None = None
    files_seen: int = 0
    files_loaded: int = 0
    rows_seen: int = 0
    rows_inserted: int = 0
    rows_skipped_existing: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_roots": self.input_roots,
            "dry_run": self.dry_run,
            "truncate_before_load": self.truncate_before_load,
            "target_league_id": self.target_league_id,
            "run_id": self.run_id,
            "files_seen": self.files_seen,
            "files_loaded": self.files_loaded,
            "rows_seen": self.rows_seen,
            "rows_inserted": self.rows_inserted,
            "rows_skipped_existing": self.rows_skipped_existing,
            "warnings": self.warnings,
        }


def _row_fingerprint(dataset_key: str, row: dict[str, Any]) -> str:
    payload = json.dumps({"dataset_key": dataset_key, "row": row}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(inner) for inner in value]
    return value


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:  # noqa: BLE001
        return None


def _iter_dataset_csvs(input_root: Path) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    for dataset_dir in sorted(input_root.glob("html_*_normalized")):
        if not dataset_dir.is_dir():
            continue
        dataset_key = dataset_dir.name
        for csv_path in sorted(dataset_dir.glob("*.csv")):
            pairs.append((dataset_key, csv_path))
    return pairs


def _single_int_from_rows(rows: list[dict[str, Any]], key: str) -> int | None:
    values = {
        value
        for row in rows
        if (value := _safe_int(row.get(key))) is not None
    }
    if len(values) == 1:
        return values.pop()
    return None


def _single_str_from_rows(rows: list[dict[str, Any]], key: str) -> str | None:
    values = {
        text
        for row in rows
        if (text := str(row.get(key) or "").strip())
    }
    if len(values) == 1:
        return values.pop()
    return None


def run_load_mfl_html_normalized(
    *,
    input_roots: list[str],
    dry_run: bool = True,
    truncate_before_load: bool = False,
    target_league_id: int | None = None,
) -> dict[str, Any]:
    roots = [Path(root) for root in input_roots]
    summary = LoadSummary(
        input_roots=[str(root) for root in roots],
        dry_run=dry_run,
        truncate_before_load=truncate_before_load,
        target_league_id=target_league_id,
    )

    metadata_db = SessionLocal()
    run = models.MflIngestionRun(
        pipeline_stage="load_html_normalized",
        source_system="mfl",
        target_league_id=target_league_id,
        status="running",
        dry_run=dry_run,
        truncate_before_load=truncate_before_load,
        input_roots=summary.input_roots,
        command="load-mfl-html-normalized",
        notes="Normalized MFL HTML records load",
    )
    metadata_db.add(run)
    metadata_db.commit()
    metadata_db.refresh(run)
    summary.run_id = run.id

    db = SessionLocal()
    try:
        if truncate_before_load and not dry_run:
            db.query(models.MflHtmlRecordFact).delete(synchronize_session=False)
            db.flush()

        seen_fingerprints: set[tuple[str, str]] = set()

        for root in roots:
            if not root.exists():
                summary.warnings.append(f"input root does not exist: {root}")
                continue

            dataset_csvs = _iter_dataset_csvs(root)
            if not dataset_csvs:
                summary.warnings.append(f"no normalized datasets found under: {root}")
                continue

            for dataset_key, csv_path in dataset_csvs:
                summary.files_seen += 1
                try:
                    frame = pd.read_csv(csv_path)
                except Exception as exc:  # noqa: BLE001
                    summary.warnings.append(f"failed reading {csv_path}: {exc}")
                    continue

                rows = frame.to_dict(orient="records")
                summary.rows_seen += len(rows)

                metadata_file = models.MflIngestionFile(
                    run_id=run.id,
                    dataset_key=dataset_key,
                    season=_single_int_from_rows(rows, "season"),
                    source_league_id=_single_str_from_rows(rows, "league_id"),
                    relative_path=str(csv_path.relative_to(root)),
                    content_type="text/csv",
                    row_count=len(rows),
                    size_bytes=csv_path.stat().st_size,
                    sha256=_file_sha256(csv_path),
                    retention_class="generated_export",
                )
                metadata_db.add(metadata_file)
                metadata_db.commit()

                for row in rows:
                    safe_row = _json_safe(row)
                    fingerprint = _row_fingerprint(dataset_key, safe_row)
                    query = db.query(models.MflHtmlRecordFact.id)
                    if hasattr(query, "filter"):
                        exists = (
                            query
                            .filter(models.MflHtmlRecordFact.dataset_key == dataset_key)
                            .filter(models.MflHtmlRecordFact.row_fingerprint == fingerprint)
                            .first()
                            is not None
                        )
                    else:
                        exists = False
                    if exists:
                        summary.rows_skipped_existing += 1
                        continue

                    fp_key = (dataset_key, fingerprint)
                    if fp_key in seen_fingerprints:
                        summary.rows_skipped_existing += 1
                        continue
                    seen_fingerprints.add(fp_key)

                    record = models.MflHtmlRecordFact(
                        dataset_key=dataset_key,
                        season=_safe_int(safe_row.get("season")),
                        target_league_id=target_league_id,
                        league_id=str(safe_row.get("league_id") or "").strip() or None,
                        source_endpoint=str(safe_row.get("source_endpoint") or "").strip() or None,
                        source_url=str(safe_row.get("source_url") or "").strip() or None,
                        extracted_at_utc=str(safe_row.get("extracted_at_utc") or "").strip() or None,
                        normalization_version=str(safe_row.get("normalization_version") or "v1").strip(),
                        row_fingerprint=fingerprint,
                        record_json=safe_row,
                    )
                    db.add(record)
                    summary.rows_inserted += 1

                summary.files_loaded += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.summary_json = summary.to_dict()
        metadata_db.add(run)
        metadata_db.commit()

        return summary.to_dict()
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.notes = str(exc)
        run.summary_json = summary.to_dict()
        metadata_db.add(run)
        metadata_db.commit()
        raise
    finally:
        db.close()
        metadata_db.close()
