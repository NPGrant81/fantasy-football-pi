import types
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import trade_scheduler, league_calendar, email_sender, waiver_logic


def test_is_player_locked_future_and_past():
    future = datetime.now() + timedelta(hours=2)
    past = datetime.now() - timedelta(hours=2)
    assert trade_scheduler.is_player_locked(1, future) is False
    assert trade_scheduler.is_player_locked(1, past) is True


def test_is_transaction_window_open_monkeypatch(monkeypatch):
    from utils import league_calendar as lc

    class FakeDT:
        @classmethod
        def now(cls):
            import datetime as _dt
            # Wednesday, hour 4 -> open
            return _dt.datetime(2025, 9, 17, 4)

    monkeypatch.setattr(lc, "datetime", FakeDT)
    assert lc.is_transaction_window_open() is True

    class FakeDT2:
        @classmethod
        def now(cls):
            import datetime as _dt
            # Sunday -> closed
            return _dt.datetime(2025, 9, 21, 12)

    monkeypatch.setattr(lc, "datetime", FakeDT2)
    assert lc.is_transaction_window_open() is False


def test_send_invite_email_simulation(monkeypatch, capsys):
    # Ensure MAIL_USERNAME/PASSWORD are not set so function takes dev path
    monkeypatch.delenv("MAIL_USERNAME", raising=False)
    monkeypatch.delenv("MAIL_PASSWORD", raising=False)
    result = email_sender.send_invite_email("x@y.com", "tester", "temppw")
    captured = capsys.readouterr()
    assert result is True
    assert "SIMULATION" in captured.out


def test_calculate_waiver_priority_simple():
    # Create fake owners with wins attribute
    Owner = lambda w: types.SimpleNamespace(wins=w)
    owners = [Owner(2), Owner(5), Owner(1)]

    class FakeQuery:
        def __init__(self, owners):
            self._owners = owners

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._owners

    class FakeDB:
        def __init__(self, owners):
            self._owners = owners

        def query(self, model):
            return FakeQuery(self._owners)

    sorted_owners = waiver_logic.calculate_waiver_priority(1, FakeDB(owners))
    assert [o.wins for o in sorted_owners] == [1, 2, 5]
