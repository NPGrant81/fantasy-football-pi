from types import SimpleNamespace

from etl.services.consensus_service import build_and_store_consensus_draft_values
from backend.models_draft_value import DraftValue, PlatformProjection
from backend.models import Player


class _QueryStub:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def yield_per(self, size):
        return self

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, projection_rows, player_rows, existing_rows):
        self._projection_rows = projection_rows
        self._player_rows = player_rows
        self._existing_rows = existing_rows
        self.added = []
        self.committed = False

    def query(self, *entities):
        if len(entities) == 4 and getattr(entities[0], "class_", None) is PlatformProjection:
            return _QueryStub(self._projection_rows)
        if len(entities) == 2 and getattr(entities[0], "class_", None) is Player:
            return _QueryStub(self._player_rows)
        if len(entities) == 1 and entities[0] is DraftValue:
            return _QueryStub(self._existing_rows)
        raise AssertionError(f"Unexpected query entities: {entities}")

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True


def test_consensus_handles_adp_only_auction_only_and_skips_signalless_player():
    projection_rows = [
        SimpleNamespace(player_id=1, source="espn", auction_value=40.0, adp=None),
        SimpleNamespace(player_id=2, source="yahoo", auction_value=None, adp=28.0),
        SimpleNamespace(player_id=3, source="draftsharks", auction_value=None, adp=None),
    ]
    player_rows = [
        SimpleNamespace(id=1, position="QB"),
        SimpleNamespace(id=2, position="RB"),
        SimpleNamespace(id=3, position="WR"),
    ]

    session = _FakeSession(projection_rows, player_rows, existing_rows=[])

    summary = build_and_store_consensus_draft_values(session, season=2026)

    assert summary["updated"] == 2
    assert summary["skipped"] == 0
    assert session.committed is True
    assert len(session.added) == 2

    added_by_player = {int(row.player_id): row for row in session.added}
    assert added_by_player[1].avg_auction_value == 40.0
    assert added_by_player[1].median_adp is None
    assert added_by_player[2].avg_auction_value == 0.0
    assert added_by_player[2].median_adp == 28.0


def test_consensus_upserts_existing_without_duplicates_and_computes_vor_threshold():
    projection_rows = [
        SimpleNamespace(player_id=10, source="espn", auction_value=50.0, adp=3.0),
        SimpleNamespace(player_id=11, source="espn", auction_value=30.0, adp=12.0),
    ]
    player_rows = [
        SimpleNamespace(id=10, position="QB"),
        SimpleNamespace(id=11, position="QB"),
    ]

    existing = DraftValue(player_id=10, season=2026)
    existing.avg_auction_value = 10.0
    existing.median_adp = 99.0

    session = _FakeSession(projection_rows, player_rows, existing_rows=[existing])

    summary = build_and_store_consensus_draft_values(session, season=2026)

    assert summary["updated"] == 2
    assert summary["skipped"] == 0
    assert session.committed is True

    # Only player_id=11 should be inserted; player_id=10 should be updated in place.
    assert len(session.added) == 1
    assert int(session.added[0].player_id) == 11

    assert existing.avg_auction_value == 50.0
    assert existing.median_adp == 3.0
    # With QB values [50, 30], replacement is 30 (60th percentile index logic), so VOR is 20.
    assert existing.value_over_replacement == 20.0
