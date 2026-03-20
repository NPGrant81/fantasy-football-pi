import pandas as pd

from backend.scripts import extract_mfl_html_reports


def test_known_report_pages_include_requested_record_reports():
    expected = {
        "league_champions": "194",
        "league_awards": "202",
        "franchise_records": "156",
        "player_records": "157",
        "matchup_records": "158",
        "all_time_series_records": "171",
        "season_records": "204",
        "career_records": "208",
        "record_streaks": "232",
    }
    for report_key, option_code in expected.items():
        assert report_key in extract_mfl_html_reports.KNOWN_REPORT_PAGES
        report_meta = extract_mfl_html_reports.KNOWN_REPORT_PAGES[report_key]
        assert report_meta["option_code"] == option_code
        assert report_meta["table_index"] == 1


def test_extract_html_reports_writes_csv_and_raw_html(tmp_path, monkeypatch):
    def fake_fetch_report_html(*, url, timeout_seconds, session_cookie):
        assert "O=194" in url
        assert timeout_seconds == 11
        assert session_cookie == "MFL_AUTH=1"
        return "<html><body>fake</body></html>"

    def fake_read_html(_html_buffer):
        header = pd.DataFrame([["Guest (Login)", "League Champions"]])
        data = pd.DataFrame(
            {
                "Place": [1, 2],
                "Franchise": ["Moneybags Moore", "The PUcocks"],
            }
        )
        footer = pd.DataFrame([["footer"]])
        return [header, data, footer]

    def fake_resolve_html_host(*, season, league_id, timeout_seconds, session_cookie):
        assert season == 2002
        assert league_id == "29721"
        assert timeout_seconds == 11
        assert session_cookie == "MFL_AUTH=1"
        return "https://www47.myfantasyleague.com"

    monkeypatch.setattr(extract_mfl_html_reports, "_fetch_report_html", fake_fetch_report_html)
    monkeypatch.setattr(extract_mfl_html_reports.pd, "read_html", fake_read_html)
    monkeypatch.setattr(extract_mfl_html_reports, "_resolve_html_host", fake_resolve_html_host)

    summary = extract_mfl_html_reports.run_extract_mfl_html_reports(
        start_year=2002,
        end_year=2002,
        report_keys=["league_champions"],
        output_root=str(tmp_path),
        timeout_seconds=11,
        session_cookie="MFL_AUTH=1",
    )

    assert summary["extracted_reports"] == 1
    assert summary["failed_reports"] == 0

    csv_path = tmp_path / "league_champions" / "2002.csv"
    html_path = tmp_path / "raw" / "league_champions" / "2002.html"
    assert csv_path.exists()
    assert html_path.exists()

    frame = pd.read_csv(csv_path)
    assert list(frame["franchise"]) == ["Moneybags Moore", "The PUcocks"]
    assert list(frame["place"]) == [1, 2]
    assert set(["season", "league_id", "source_system", "source_endpoint", "source_url"]).issubset(frame.columns)


def test_flatten_columns_handles_multiindex_table():
    frame = pd.DataFrame(
        [[470.0, "15.6%", 3011.0, "100.0%"]],
        columns=pd.MultiIndex.from_tuples(
            [
                ("QB", "Pts"),
                ("QB", "Pct"),
                ("Total", "Pts"),
                ("Total", "Pct"),
            ]
        ),
    )

    flattened = extract_mfl_html_reports._flatten_columns(frame)
    assert list(flattened.columns) == ["qb_pts", "qb_pct", "total_pts", "total_pct"]


def test_extract_draft_results_detailed_enriches_player_ids(monkeypatch):
    def fake_read_html(_html_buffer):
        header = pd.DataFrame([["Auction Results", "Details"]])
        data = pd.DataFrame(
            {
                "Player": ["Achane, De'Von MIA RB", "Addison, Jordan MIN WR", "Unknown Player FA WR"],
                "Winning Bid": ["$57.00", "$3.00", "$1.00"],
                "Winning Bidder": ["Franchise A", "Franchise B", "Franchise C"],
            }
        )
        footer = pd.DataFrame([["footer"]])
        return [header, data, footer]

    def fake_player_lookup(*, season, league_id, timeout_seconds):
        assert season == 2025
        assert league_id == "11422"
        assert timeout_seconds == 20
        return {
            ("achanedevon", "MIA", "RB"): "16177",
            ("addisonjordan", "MIN", "WR"): "15997",
        }

    monkeypatch.setattr(extract_mfl_html_reports.pd, "read_html", fake_read_html)
    monkeypatch.setattr(extract_mfl_html_reports, "_fetch_player_lookup", fake_player_lookup)

    frame = extract_mfl_html_reports._extract_report_table(
        "<html><body>fake</body></html>",
        report_key="draft_results_detailed",
        season=2025,
        league_id="11422",
        timeout_seconds=20,
    )

    assert list(frame["player_name"]) == ["Achane, De'Von", "Addison, Jordan", "Unknown Player"]
    assert list(frame["nfl_team"]) == ["MIA", "MIN", "FA"]
    assert list(frame["position"]) == ["RB", "WR", "WR"]
    assert list(frame["player_mfl_id"][:2]) == ["16177", "15997"]
    assert pd.isna(frame.loc[2, "player_mfl_id"])


def test_annotate_frame_renames_conflicting_report_columns():
    frame = pd.DataFrame(
        [
            {
                "season": 2002,
                "league_id": "29721",
                "source_url": "https://example.test/report",
                "award_title": "Champion",
            }
        ]
    )

    annotated = extract_mfl_html_reports._annotate_frame(
        frame,
        season=2002,
        league_id="29721",
        report_key="league_awards",
        url="https://example.test/report",
        extracted_at_utc="2026-03-14T00:00:00+00:00",
    )

    assert "report_season" in annotated.columns
    assert "report_league_id" in annotated.columns
    assert "report_source_url" in annotated.columns
    assert annotated.loc[0, "season"] == 2002
    assert annotated.loc[0, "report_season"] == 2002