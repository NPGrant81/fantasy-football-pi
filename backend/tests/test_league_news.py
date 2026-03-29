import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.routers.league import get_league_news
from fastapi import HTTPException
import models


class FakeQuery:
    def __init__(self, data, is_single=False):
        self._data = data
        self._is_single = is_single

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        if self._is_single:
            return [self._data] if self._data else []
        return self._data

    def first(self):
        if self._is_single:
            return self._data
        if not self._data:
            return None
        return self._data[0]


class FakeDB:
    def __init__(self, league, picks):
        self._league = league
        self._picks = picks

    def query(self, model):
        if model is models.League:
            return FakeQuery(self._league, is_single=True)
        if model is models.DraftPick:
            return FakeQuery(self._picks, is_single=False)
        raise AssertionError(f"Unexpected model: {model}")


def test_get_league_news_returns_draft_pick_items():
    league = SimpleNamespace(id=1)
    owner = SimpleNamespace(username="alice")
    player = SimpleNamespace(name="Patrick Mahomes")
    pick = SimpleNamespace(
        owner=owner,
        owner_id=1,
        player=player,
        player_id=101,
        amount=22,
        timestamp="2026-02-18T12:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )

    db = FakeDB(league=league, picks=[pick])
    items = get_league_news(1, db=db)

    assert len(items) == 1
    assert items[0].type == "info"
    assert "alice drafted Patrick Mahomes" in items[0].title
    assert items[0].timestamp == "2026-02-18T12:00:00Z"
    assert items[0].sentiment_label in {"neutral", "positive", "negative"}


def test_get_league_news_falls_back_to_just_now():
    league = SimpleNamespace(id=1)
    owner = SimpleNamespace(username="alice")
    player = SimpleNamespace(name="Travis Kelce")
    pick = SimpleNamespace(
        owner=owner,
        owner_id=1,
        player=player,
        player_id=102,
        amount=15,
        timestamp=None,
        league_id=1,
        session_id="LEAGUE_1",
    )

    db = FakeDB(league=league, picks=[pick])
    items = get_league_news(1, db=db)

    assert items[0].timestamp == "Just now"


def test_get_league_news_raises_for_missing_league():
    db = FakeDB(league=None, picks=[])

    with pytest.raises(HTTPException) as exc:
        get_league_news(1, db=db)

    assert exc.value.status_code == 404


def test_get_league_news_excludes_hist_users():
    """Historical MFL-import users (hist_YYYY_XXXX) must never bleed into League News."""
    league = SimpleNamespace(id=1)
    real_owner = SimpleNamespace(username="alice")
    hist_owner = SimpleNamespace(username="hist_2003_0006")
    player = SimpleNamespace(name="Patrick Mahomes")

    real_pick = SimpleNamespace(
        owner=real_owner,
        owner_id=1,
        player=player,
        player_id=101,
        amount=22,
        timestamp="2026-02-18T12:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )
    hist_pick = SimpleNamespace(
        owner=hist_owner,
        owner_id=2,
        player=player,
        player_id=101,
        amount=1,
        timestamp="2003-08-01T00:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )

    # FakeDB returns both picks; real filtering is done at the ORM level.
    # Here we verify the function-level logic does not surface hist_ entries
    # when the FakeQuery would pass them through (documents the contract).
    db = FakeDB(league=league, picks=[real_pick, hist_pick])
    items = get_league_news(1, db=db)

    hist_titles = [i.title for i in items if "hist_" in i.title]
    assert hist_titles == [], f"Historical users leaked into news: {hist_titles}"


def test_get_league_news_owner_filter_returns_players_on_owner_roster():
    league = SimpleNamespace(id=1)
    owner_a = SimpleNamespace(username="alice")
    owner_b = SimpleNamespace(username="bob")

    pick_a = SimpleNamespace(
        owner=owner_a,
        owner_id=10,
        player=SimpleNamespace(name="Ja'Marr Chase"),
        player_id=501,
        amount=22,
        timestamp="2026-02-18T12:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )
    # News item from another owner about same player should remain when filtering for owner_a.
    pick_b_same_player = SimpleNamespace(
        owner=owner_b,
        owner_id=11,
        player=SimpleNamespace(name="Ja'Marr Chase"),
        player_id=501,
        amount=18,
        timestamp="2026-02-19T12:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )
    pick_b_other_player = SimpleNamespace(
        owner=owner_b,
        owner_id=11,
        player=SimpleNamespace(name="Josh Allen"),
        player_id=777,
        amount=30,
        timestamp="2026-02-20T12:00:00Z",
        league_id=1,
        session_id="LEAGUE_1",
    )

    db = FakeDB(league=league, picks=[pick_b_other_player, pick_b_same_player, pick_a])
    items = get_league_news(1, owner_id=10, db=db)

    titles = [item.title for item in items]
    assert any("Ja'Marr Chase" in title for title in titles)
    assert not any("Josh Allen" in title for title in titles)


def test_get_league_news_rejects_invalid_since_timestamp():
    league = SimpleNamespace(id=1)
    db = FakeDB(league=league, picks=[])

    with pytest.raises(HTTPException) as exc:
        get_league_news(1, since="not-a-timestamp", db=db)

    assert exc.value.status_code == 400
