from pathlib import Path

import pandas as pd

from backend.scripts import load_mfl_html_normalized
from backend.scripts.load_mfl_html_normalized import _row_fingerprint


def test_row_fingerprint_is_stable_for_key_order():
    row_a = {"season": 2026, "league_id": "11422", "value": 1}
    row_b = {"value": 1, "league_id": "11422", "season": 2026}

    fp_a = _row_fingerprint("html_league_champions_normalized", row_a)
    fp_b = _row_fingerprint("html_league_champions_normalized", row_b)

    assert fp_a == fp_b


def test_row_fingerprint_changes_when_dataset_changes():
    row = {"season": 2026, "league_id": "11422", "value": 1}

    fp_a = _row_fingerprint("html_league_champions_normalized", row)
    fp_b = _row_fingerprint("html_league_awards_normalized", row)

    assert fp_a != fp_b


class _FakeQuery:
    def delete(self, synchronize_session=False):
        return 0

    def all(self):
        return []


class _FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.commit_count = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.committed = True
        self.commit_count += 1

    def rollback(self):
        self.rolled_back = True

    def refresh(self, record):
        if getattr(record, "id", None) is None:
            record.id = 1

    def flush(self):
        return None

    def close(self):
        self.closed = True


def test_run_load_sets_target_league_id(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "html_league_awards_normalized"
    dataset_dir.mkdir(parents=True)
    csv_path = dataset_dir / "2026.csv"
    pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_endpoint": "league_awards",
                "source_url": "https://example.test",
                "extracted_at_utc": "2026-03-14T00:00:00Z",
                "normalization_version": "v1",
                "award_season": 2026,
            }
        ]
    ).to_csv(csv_path, index=False)

    fake_db = _FakeDb()
    monkeypatch.setattr(load_mfl_html_normalized, "SessionLocal", lambda: fake_db)

    summary = load_mfl_html_normalized.run_load_mfl_html_normalized(
        input_roots=[str(tmp_path)],
        dry_run=False,
        target_league_id=60,
    )

    assert summary["target_league_id"] == 60
    assert summary["run_id"] == 1
    assert summary["rows_inserted"] == 1
    assert fake_db.committed is True
    assert fake_db.closed is True

    fact_rows = [record for record in fake_db.added if hasattr(record, "row_fingerprint")]
    run_rows = [record for record in fake_db.added if hasattr(record, "pipeline_stage")]
    file_rows = [record for record in fake_db.added if hasattr(record, "relative_path")]

    assert run_rows[0].target_league_id == 60
    assert file_rows[0].source_league_id == "11422"
    assert fact_rows[0].target_league_id == 60
    assert fact_rows[0].league_id == "11422"
