from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend.scripts import audit_player_duplicates


def test_run_audit_apply_moves_player_season_and_alias_refs_without_fk_failure(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        keep = models.Player(
            name="Duplicate Target",
            position="WR",
            nfl_team="ATL",
            adp=1.0,
            projected_points=10.0,
        )
        duplicate = models.Player(
            name="Duplicate Target",
            position="WR",
            nfl_team="FA",
            adp=0.0,
            projected_points=0.0,
        )
        session.add_all([keep, duplicate])
        session.flush()

        # Same season on both rows creates a potential uq_player_season conflict
        # when duplicate references are moved to the keep player.
        session.add_all(
            [
                models.PlayerSeason(player_id=keep.id, season=2025, nfl_team="ATL", position="WR", source="sync"),
                models.PlayerSeason(player_id=duplicate.id, season=2025, nfl_team="FA", position="WR", source="sync"),
            ]
        )

        # Same alias/source on both rows creates a potential uq_player_alias_source conflict.
        session.add_all(
            [
                models.PlayerAlias(player_id=keep.id, alias_name="D. Target", source="canonical", is_primary=True),
                models.PlayerAlias(player_id=duplicate.id, alias_name="D. Target", source="canonical", is_primary=False),
            ]
        )

        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(audit_player_duplicates, "SessionLocal", TestingSessionLocal)

    summary = audit_player_duplicates.run_audit(apply_changes=True)

    assert summary["duplicate_groups"] == 1
    assert summary["duplicate_rows"] == 1
    assert summary["rows_merged"] == 1

    verify = TestingSessionLocal()
    try:
        players = verify.query(models.Player).filter(models.Player.name == "Duplicate Target").all()
        assert len(players) == 1

        aliases = verify.query(models.PlayerAlias).all()
        seasons = verify.query(models.PlayerSeason).all()
        assert len(aliases) == 1
        assert len(seasons) == 1

        surviving_player_id = players[0].id
        assert aliases[0].player_id == surviving_player_id
        assert seasons[0].player_id == surviving_player_id
    finally:
        verify.close()
