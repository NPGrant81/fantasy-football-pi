import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from routers.league import get_league_news
from fastapi import HTTPException
import models


class FakeQuery:
    def __init__(self, data, is_single=False):
        self._data = data
        self._is_single = is_single

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
        player=player,
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


def test_get_league_news_falls_back_to_just_now():
    league = SimpleNamespace(id=1)
    owner = SimpleNamespace(username="alice")
    player = SimpleNamespace(name="Travis Kelce")
    pick = SimpleNamespace(
        owner=owner,
        player=player,
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
