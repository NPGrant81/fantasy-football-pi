import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from routers.league import (
    AddMemberRequest,
    add_league_member,
    create_owner,
    remove_league_member,
    update_owner,
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


def test_update_owner_updates_username_and_email(db_session):
    league = models.League(name="Test League")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    commissioner = models.User(
        username="commish",
        email="commish@test.com",
        hashed_password="hashed",
        is_commissioner=True,
        league_id=league.id,
    )
    owner = models.User(
        username="owner-old",
        email="owner-old@test.com",
        hashed_password="hashed",
        league_id=league.id,
    )
    db_session.add_all([commissioner, owner])
    db_session.commit()
    db_session.refresh(owner)

    response = update_owner(
        owner_id=owner.id,
        request=AddMemberRequest(username="owner-new", email="owner-new@test.com"),
        current_user=commissioner,
        db=db_session,
    )

    db_session.refresh(owner)
    assert response["message"] == "Owner updated."
    assert owner.username == "owner-new"
    assert owner.email == "owner-new@test.com"


def test_add_and_remove_member_blocked_for_other_league_commissioner(db_session):
    league_one = models.League(name="League One")
    league_two = models.League(name="League Two")
    db_session.add_all([league_one, league_two])
    db_session.commit()
    db_session.refresh(league_one)
    db_session.refresh(league_two)

    other_league_commissioner = models.User(
        username="other-commish",
        email="other-commish@test.com",
        hashed_password="hashed",
        is_commissioner=True,
        league_id=league_two.id,
    )
    owner = models.User(
        username="owner-a",
        email="owner-a@test.com",
        hashed_password="hashed",
        league_id=league_one.id,
    )
    db_session.add_all([other_league_commissioner, owner])
    db_session.commit()

    with pytest.raises(HTTPException) as add_exc:
        add_league_member(
            league_id=league_one.id,
            request=AddMemberRequest(username="owner-a"),
            current_user=other_league_commissioner,
            db=db_session,
        )
    assert add_exc.value.status_code == 403

    with pytest.raises(HTTPException) as remove_exc:
        remove_league_member(
            league_id=league_one.id,
            user_id=owner.id,
            current_user=other_league_commissioner,
            db=db_session,
        )
    assert remove_exc.value.status_code == 403


def test_create_owner_rejects_cross_league_assignment(db_session):
    league_one = models.League(name="League A")
    league_two = models.League(name="League B")
    db_session.add_all([league_one, league_two])
    db_session.commit()
    db_session.refresh(league_one)
    db_session.refresh(league_two)

    commissioner = models.User(
        username="commish-a",
        email="commish-a@test.com",
        hashed_password="hashed",
        is_commissioner=True,
        league_id=league_one.id,
    )
    db_session.add(commissioner)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        create_owner(
            request=AddMemberRequest(
                username="owner-cross",
                email="owner-cross@test.com",
                league_id=league_two.id,
            ),
            current_user=commissioner,
            db=db_session,
        )

    assert exc.value.status_code == 403
    assert "their league" in exc.value.detail
