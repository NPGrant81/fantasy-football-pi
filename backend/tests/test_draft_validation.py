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
