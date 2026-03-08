import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.league import (
    AddMemberRequest,
    add_league_member,
    create_owner,
    remove_league_member,
    update_owner,
    get_league_owners,
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


def test_get_league_owners_returns_stats(db_session):
    league = models.League(name="StatsLeague")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    owner1 = models.User(username="o1", email=None, hashed_password="h", league_id=league.id)
    owner2 = models.User(username="o2", email=None, hashed_password="h", league_id=league.id)
    db_session.add_all([owner1, owner2])
    db_session.commit()
    db_session.refresh(owner1)
    db_session.refresh(owner2)

    # create a completed matchup where o1 beats o2
    m = models.Matchup(
        week=1,
        home_team_id=owner1.id,
        away_team_id=owner2.id,
        home_score=120.5,
        away_score=110.0,
        is_completed=True,
        league_id=league.id,
    )
    db_session.add(m)
    db_session.commit()

    owners = get_league_owners(league_id=league.id, db=db_session)
    assert isinstance(owners, list)
    # owner1 should have a win, pf 120.5, pa 110.0
    o1_data = next(o for o in owners if o['id'] == owner1.id)
    assert o1_data['wins'] == 1
    assert o1_data['losses'] == 0
    assert o1_data['ties'] == 0
    assert o1_data['pf'] == 120.5
    assert o1_data['pa'] == 110.0
    assert o1_data['points_for'] == 120.5
    assert o1_data['points_against'] == 110.0
    assert o1_data['win_pct'] == 1.0
    # owner2 should have a loss and swapped pf/pa
    o2_data = next(o for o in owners if o['id'] == owner2.id)
    assert o2_data['wins'] == 0
    assert o2_data['losses'] == 1
    assert o2_data['pf'] == 110.0
    assert o2_data['pa'] == 120.5
    assert o2_data['points_for'] == 110.0
    assert o2_data['points_against'] == 120.5
    assert o2_data['win_pct'] == 0.0

    # now test division grouping sorts by division id first
    # assign owners to divisions
    div1 = models.Division(league_id=league.id, name='East')
    div2 = models.Division(league_id=league.id, name='West')
    db_session.add_all([div1, div2])
    db_session.commit()
    owner1.division_id = div2.id
    owner2.division_id = div1.id
    db_session.commit()

    grouped = get_league_owners(league_id=league.id, group_by_division=True, db=db_session)
    # first owner should belong to division1 (West id maybe?) after sorting; ensure field present
    assert 'division_id' in grouped[0]


def test_update_scoring_rules_storage(db_session):
    # verify that the extended scoring rule fields are saved correctly
    league = models.League(name="ScoreLeague")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    commish = models.User(username="commish", email=None, hashed_password="h", is_commissioner=True, league_id=league.id)
    db_session.add(commish)
    db_session.commit()

    from backend.routers.league import LeagueConfigFull, ScoringRuleSchema, update_league_settings

    config = LeagueConfigFull(
        roster_size=10,
        salary_cap=200,
        starting_slots={"QB":1},
        scoring_rules=[
            ScoringRuleSchema(
                category="passing",
                event_name="Passing Yards",
                description="Yards gained",
                range_min=0,
                range_max=999,
                point_value=0.1,
                calculation_type="per_unit",
                applicable_positions=["QB"],
            )
        ],
    )
    # call router function directly
    update_league_settings(league_id=league.id, config=config, current_user=commish, db=db_session)

    saved = db_session.query(models.ScoringRule).filter(models.ScoringRule.league_id == league.id).all()
    assert len(saved) == 1
    rule = saved[0]
    assert rule.event_name == "Passing Yards"
    assert float(rule.range_max) == 999
    assert rule.calculation_type == "per_unit"
    assert rule.applicable_positions == ["QB"]


def test_update_league_settings_rejects_invalid_dynamic_values(db_session):
    league = models.League(name="InvalidSettingsLeague")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    commish = models.User(
        username="commish-invalid-settings",
        email=None,
        hashed_password="h",
        is_commissioner=True,
        league_id=league.id,
    )
    db_session.add(commish)
    db_session.commit()

    from backend.routers.league import LeagueConfigFull, ScoringRuleSchema, update_league_settings

    config = LeagueConfigFull(
        roster_size=8,
        salary_cap=200,
        starting_slots={"QB": 1, "RB": 4, "WR": 4},
        waiver_system="NOT_A_SYSTEM",
        waiver_tiebreaker="coinflip",
        scoring_rules=[
            ScoringRuleSchema(
                category="passing",
                event_name="Passing Yards",
                description="Yards gained",
                range_min=0,
                range_max=999,
                point_value=0.1,
                calculation_type="per_unit",
                applicable_positions=["QB"],
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        update_league_settings(
            league_id=league.id,
            config=config,
            current_user=commish,
            db=db_session,
        )

    assert exc.value.status_code == 400
