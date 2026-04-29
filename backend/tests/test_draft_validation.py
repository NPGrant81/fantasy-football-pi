import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.draft import (
    DraftPickCreate,
    _can_access_draft_session,
    draft_player,
    manager,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_draft_player_rejects_invalid_session_id(db_session):
    league = models.League(name="L-DRAFT-VALIDATION")
    owner = models.User(username="owner", hashed_password="pw")
    player = models.Player(name="Test Player", position="RB", nfl_team="ABC")
    db_session.add_all([league, owner, player])
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(player)

    pick = DraftPickCreate(
        owner_id=owner.id,
        player_id=player.id,
        amount=5,
        session_id="BAD SESSION",
        year=2026,
    )

    with pytest.raises(HTTPException) as exc:
        await draft_player(pick, db=db_session)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_draft_player_rejects_suppressed_position(db_session):
    league = models.League(name="L-DRAFT-SUPPRESSION", draft_status="PRE_DRAFT")
    owner = models.User(username="owner-suppressed", hashed_password="pw", league_id=1)
    player = models.Player(name="Suppressed Kicker", position="K", nfl_team="ABC")
    db_session.add_all([league, owner, player])
    db_session.commit()
    db_session.refresh(league)
    owner.league_id = league.id
    db_session.add(
        models.LeagueSettings(
            league_id=league.id,
            draft_year=2026,
            roster_size=14,
            starting_slots={
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "K": 0,
                "DEF": 1,
                "FLEX": 1,
                "MAX_QB": 1,
                "MAX_RB": 3,
                "MAX_WR": 3,
                "MAX_TE": 2,
                "MAX_K": 0,
                "MAX_DEF": 1,
                "MAX_FLEX": 1,
            },
        )
    )
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(player)

    pick = DraftPickCreate(
        owner_id=owner.id,
        player_id=player.id,
        amount=5,
        session_id=f"LEAGUE_{league.id}_YEAR_2026",
        year=2026,
    )

    with pytest.raises(HTTPException) as exc:
        await draft_player(pick, db=db_session)

    assert exc.value.status_code == 400
    assert "disabled for this league" in exc.value.detail


@pytest.mark.asyncio
async def test_draft_player_broadcasts_pick_payload(db_session, monkeypatch):
    league = models.League(name="L-DRAFT-WS", draft_status="PRE_DRAFT")
    owner = models.User(username="owner-ws", hashed_password="pw")
    player = models.Player(name="Realtime Runner", position="RB", nfl_team="ABC")
    db_session.add_all([league, owner, player])
    db_session.commit()
    db_session.refresh(league)
    db_session.refresh(owner)
    db_session.refresh(player)

    owner.league_id = league.id
    db_session.add(owner)
    db_session.add(
        models.LeagueSettings(
            league_id=league.id,
            draft_year=2026,
            roster_size=14,
            starting_slots={
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "K": 1,
                "DEF": 1,
                "FLEX": 1,
                "MAX_QB": 2,
                "MAX_RB": 6,
                "MAX_WR": 6,
                "MAX_TE": 3,
                "MAX_K": 2,
                "MAX_DEF": 2,
                "MAX_FLEX": 2,
            },
        )
    )
    db_session.commit()

    broadcast_mock = AsyncMock()
    monkeypatch.setattr(manager, "broadcast", broadcast_mock)

    session_id = f"LEAGUE_{league.id}_YEAR_2026"
    pick = DraftPickCreate(
        owner_id=owner.id,
        player_id=player.id,
        amount=5,
        session_id=session_id,
        year=2026,
    )

    result = await draft_player(pick, db=db_session)

    assert result.player_id == player.id
    broadcast_mock.assert_awaited_once()

    broadcast_session_id, broadcast_message = broadcast_mock.await_args.args
    assert broadcast_session_id == session_id
    assert broadcast_message["type"] == "pick"
    assert broadcast_message["payload"]["id"] == result.id
    assert broadcast_message["payload"]["session_id"] == session_id
    assert broadcast_message["payload"]["player_id"] == player.id
    assert broadcast_message["payload"]["owner_id"] == owner.id


def test_can_access_draft_session_restricts_cross_league_user():
    user = models.User(username="owner-authz", hashed_password="pw", league_id=60)
    assert _can_access_draft_session(user, "LEAGUE_60_YEAR_2026") is True
    assert _can_access_draft_session(user, "LEAGUE_61_YEAR_2026") is False


def test_can_access_draft_session_allows_commissioner_and_superuser():
    commissioner = models.User(
        username="commish-authz",
        hashed_password="pw",
        league_id=60,
        is_commissioner=True,
    )
    superuser = models.User(
        username="admin-authz",
        hashed_password="pw",
        league_id=60,
        is_superuser=True,
    )

    assert _can_access_draft_session(commissioner, "LEAGUE_999_YEAR_2026") is True
    assert _can_access_draft_session(superuser, "LEAGUE_999_YEAR_2026") is True
