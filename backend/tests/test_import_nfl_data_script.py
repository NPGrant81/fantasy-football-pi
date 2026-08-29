from backend.scripts import import_nfl_data


def test_import_fresh_data_closes_session_after_cleanup_error(monkeypatch):
    events = []

    class FakeQuery:
        def delete(self):
            raise RuntimeError("cleanup failed")

    class FakeSession:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, *_args):
            events.append("exit")

        def query(self, _model):
            return FakeQuery()

        def rollback(self):
            events.append("rollback")

    roster = import_nfl_data.pd.DataFrame(
        [
            {
                "player_id": "player-1",
                "player_name": "Test Player",
                "position": "QB",
                "team": "TST",
            }
        ]
    )
    monkeypatch.setattr(import_nfl_data, "SessionLocal", FakeSession)
    monkeypatch.setattr(import_nfl_data, "assert_schema_ready", lambda *_args: None)
    monkeypatch.setattr(
        import_nfl_data,
        "fetch_rosters_for_seasons",
        lambda _seasons: roster,
    )
    monkeypatch.setattr(
        import_nfl_data.player_service,
        "is_valid_fantasy_player",
        lambda **_kwargs: True,
    )

    import_nfl_data.import_fresh_data()

    assert events == ["enter", "rollback", "exit"]