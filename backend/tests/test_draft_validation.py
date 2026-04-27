import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.draft import DraftPickCreate, draft_player


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
