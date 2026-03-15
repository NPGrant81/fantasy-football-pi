import pandas as pd

from backend.scripts.normalize_mfl_html_records import run_normalize_mfl_html_records


def test_normalize_league_champions_unpivots_year_columns(tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    source_dir = input_root / "league_champions"
    source_dir.mkdir(parents=True, exist_ok=True)

    source = pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_system": "mfl_html",
                "source_endpoint": "league_champions",
                "source_url": "https://example.test/o194",
                "extracted_at_utc": "2026-03-14T00:00:00+00:00",
                "2025_place": "1.",
                "2025_franchise": "Team Alpha",
                "2024_place": "2.",
                "2024_franchise": "Team Beta",
            }
        ]
    )
    source.to_csv(source_dir / "2026.csv", index=False)

    summary = run_normalize_mfl_html_records(
        input_root=str(input_root),
        output_root=str(output_root),
        report_keys=["league_champions"],
    )

    assert summary["files_processed"] == 1
    out_path = output_root / "html_league_champions_normalized" / "2026.csv"
    out_df = pd.read_csv(out_path)

    assert len(out_df) == 2
    assert set(out_df["champion_season"]) == {2024, 2025}
    assert set(out_df["place_rank"]) == {1, 2}
    assert set(out_df["franchise_name_clean"]) == {"Team Alpha", "Team Beta"}


def test_normalize_all_time_series_unpivots_wlt(tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    source_dir = input_root / "all_time_series_records"
    source_dir.mkdir(parents=True, exist_ok=True)

    source = pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_system": "mfl_html",
                "source_endpoint": "all_time_series_records",
                "source_url": "https://example.test/o171",
                "extracted_at_utc": "2026-03-14T00:00:00+00:00",
                "opponent": "Team Gamma",
                "2024_w_l_t": "2-1-0",
                "2025_w_l_t": "1-2-0",
                "total_w_l_t": "3-3-0",
                "pct": "0.500",
            }
        ]
    )
    source.to_csv(source_dir / "2026.csv", index=False)

    summary = run_normalize_mfl_html_records(
        input_root=str(input_root),
        output_root=str(output_root),
        report_keys=["all_time_series_records"],
    )

    assert summary["files_processed"] == 1
    out_path = output_root / "html_all_time_series_normalized" / "2026.csv"
    out_df = pd.read_csv(out_path)

    assert len(out_df) == 2
    assert set(out_df["series_season"]) == {2024, 2025}
    assert set(out_df["season_wins"]) == {1, 2}
    assert set(out_df["season_losses"]) == {1, 2}
    assert set(out_df["season_ties"]) == {0}
    assert set(out_df["opponent_franchise_raw"]) == {"Team Gamma"}
