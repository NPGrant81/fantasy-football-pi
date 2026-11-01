from unittest.mock import Mock

import pandas as pd

from backend.scripts import daily_sync


def test_sync_nfl_reality_reports_empty_feed_as_not_completed(monkeypatch):
    db = Mock()
    monkeypatch.setattr(daily_sync, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        daily_sync, "fetch_current_players", lambda: pd.DataFrame()
    )

    assert daily_sync.sync_nfl_reality() is False
    db.close.assert_called_once()


def test_sync_nfl_reality_reports_completed_sync(monkeypatch):
    db = Mock()
    players = pd.DataFrame([{"status": "Active"}])
    monkeypatch.setattr(daily_sync, "SessionLocal", lambda: db)
    monkeypatch.setattr(daily_sync, "fetch_current_players", lambda: players)
    monkeypatch.setattr(daily_sync, "current_season", lambda: 2026)
    monkeypatch.setattr(
        daily_sync.player_service, "is_valid_fantasy_player", lambda **kwargs: False
    )
    monkeypatch.setattr(
        daily_sync, "deactivate_stale_player_seasons", lambda *args, **kwargs: 0
    )

    assert daily_sync.sync_nfl_reality() is True
    db.commit.assert_called_once()
    db.close.assert_called_once()
