from backend.services.live_scoring_sources import (
    PRIMARY_PLAY_BY_PLAY_SOURCE,
    PRIMARY_SCOREBOARD_SOURCE,
    PRIMARY_SUMMARY_SOURCE,
    build_play_by_play_url,
    build_failover_scoreboard_urls,
    build_primary_scoreboard_url,
    build_summary_url,
    scoreboard_candidate_urls,
)


def test_primary_scoreboard_source_constant_is_explicit():
    assert PRIMARY_SCOREBOARD_SOURCE == "espn_scoreboard_primary"


def test_primary_summary_and_play_by_play_source_constants_are_explicit():
    assert PRIMARY_SUMMARY_SOURCE == "espn_summary_primary"
    assert PRIMARY_PLAY_BY_PLAY_SOURCE == "espn_play_by_play_primary"


def test_build_primary_scoreboard_url_without_week_uses_site_api():
    url = build_primary_scoreboard_url(2026)
    assert url.startswith("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard")
    assert "dates=2026" in url
    assert "limit=1000" in url


def test_build_primary_scoreboard_url_with_week_uses_site_api_week_query():
    url = build_primary_scoreboard_url(2026, week=1)
    assert "dates=2026" in url
    assert "seasontype=2" in url
    assert "week=1" in url


def test_build_failover_urls_with_week_prioritizes_schedule_then_scoreboard():
    urls = build_failover_scoreboard_urls(2026, week=1)
    assert urls[0].startswith("https://cdn.espn.com/core/nfl/schedule")
    assert urls[1].startswith("https://cdn.espn.com/core/nfl/scoreboard")


def test_scoreboard_candidate_urls_primary_first_and_override_prepended():
    urls = scoreboard_candidate_urls(2026, week=1, override_url="https://example.local/mock", enable_failover=True)
    assert urls[0] == "https://example.local/mock"
    assert urls[1].startswith("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard")
    assert any(url.startswith("https://cdn.espn.com/core/nfl/schedule") for url in urls)


def test_build_summary_url_uses_event_query_param():
    url = build_summary_url("401772001")
    assert url.startswith("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary")
    assert "event=401772001" in url


def test_build_play_by_play_url_uses_game_id_query_param():
    url = build_play_by_play_url("401772001")
    assert url.startswith("https://cdn.espn.com/core/nfl/playbyplay")
    assert "xhr=1" in url
    assert "gameId=401772001" in url
