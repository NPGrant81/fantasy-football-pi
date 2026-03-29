import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
import models_draft_value as draft_value_models
from backend.main import app
from backend.database import get_db
from backend.core.security import get_current_user

# ---------------------------------------------------------------------------
# Module-scoped SQLite engine using StaticPool so all connections share the
# same in-memory database (required for TestClient + seed data to coexist).
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
models.Base.metadata.create_all(bind=_engine)
draft_value_models.Base.metadata.create_all(bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app, raise_server_exceptions=True)


def _new_session():
    return _TestingSessionLocal()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_history_returns_player_name_and_position():
    suffix = uuid4().hex[:8]
    session_id = f"s1-{suffix}"
    username = f"testuser-{suffix}"
    player_name = f"Test Player {suffix}"

    session = _new_session()
    try:
        user = models.User(username=username, league_id=None)
        session.add(user)
        session.flush()
        user_id = user.id

        player = models.Player(name=player_name, position='RB')
        session.add(player)
        session.flush()

        pick = models.DraftPick(
            owner_id=user_id,
            player_id=player.id,
            amount=10,
            session_id=session_id,
            year=2025,
        )
        session.add(pick)
        session.commit()
    finally:
        session.close()

    r = client.get('/draft/history', params={'session_id': session_id})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    assert entry.get('player_name') == player_name
    assert entry.get('position') == 'RB'
    assert entry.get('amount') == 10
    assert entry.get('owner_id') == user_id


def test_rankings_returns_ordered_players_for_season():
    suffix = uuid4().hex[:8]
    rank_one_name = f"Rank One {suffix}"
    rank_two_name = f"Rank Two {suffix}"

    session = _new_session()
    try:
        p1 = models.Player(name=rank_one_name, position='WR', nfl_team='AAA')
        p2 = models.Player(name=rank_two_name, position='RB', nfl_team='BBB')
        session.add_all([p1, p2])
        session.flush()

        session.add_all([
            draft_value_models.DraftValue(
                player_id=p1.id,
                season=2026,
                avg_auction_value=52.0,
                value_over_replacement=21.5,
                consensus_tier='S',
            ),
            draft_value_models.DraftValue(
                player_id=p2.id,
                season=2026,
                avg_auction_value=39.0,
                value_over_replacement=12.0,
                consensus_tier='A',
            ),
        ])
        # PlayerSeason records required by the rankings service's has_active_season filter
        session.add_all([
            models.PlayerSeason(player_id=p1.id, season=2026, is_active=True),
            models.PlayerSeason(player_id=p2.id, season=2026, is_active=True),
        ])
        session.commit()
    finally:
        session.close()

    mock_user = models.User(id=9999, username='ranktest', league_id=1, is_commissioner=False)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    response = client.get('/draft/rankings', params={'season': 2026, 'limit': 200})

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    names = [row.get('player_name') for row in data]
    assert rank_one_name in names
    assert rank_two_name in names
    assert names.index(rank_one_name) < names.index(rank_two_name)

    rank_one_row = next(row for row in data if row.get('player_name') == rank_one_name)
    assert rank_one_row['consensus_tier'] == 'S'


def test_history_by_year_isolated_from_new_season_writes():
    suffix = uuid4().hex[:8]
    season_2025_name = f"Archive 2025 Player {suffix}"
    season_2026_name = f"Archive 2026 Player {suffix}"

    session = _new_session()
    try:
        league = models.League(name=f"Archive League {suffix}")
        session.add(league)
        session.flush()

        owner = models.User(username=f"archive-owner-{suffix}", league_id=league.id)
        session.add(owner)
        session.flush()

        player_2025 = models.Player(name=season_2025_name, position='WR')
        player_2026 = models.Player(name=season_2026_name, position='RB')
        session.add_all([player_2025, player_2026])
        session.flush()

        session.add(models.DraftPick(
            owner_id=owner.id,
            player_id=player_2025.id,
            amount=12,
            year=2025,
            session_id=f"LEAGUE_{league.id}_YEAR_2025",
            league_id=league.id,
        ))
        session.commit()

        owner_id = owner.id
        league_id = league.id
        player_2026_id = player_2026.id
    finally:
        session.close()

    mock_user = models.User(
        id=owner_id,
        username=f"archive-owner-{suffix}",
        league_id=league_id,
        is_commissioner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    write_response = client.post(
        '/draft/pick',
        json={
            'owner_id': owner_id,
            'player_id': player_2026_id,
            'amount': 15,
            'session_id': f'LEAGUE_{league_id}_YEAR_2026',
            'year': 2026,
        },
    )
    assert write_response.status_code == 200

    season_2025_history = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2025},
    )
    season_2026_history = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2026},
    )

    assert season_2025_history.status_code == 200
    assert season_2026_history.status_code == 200

    data_2025 = season_2025_history.json()
    data_2026 = season_2026_history.json()

    assert len(data_2025) == 1
    assert data_2025[0]['player_name'] == season_2025_name
    assert data_2025[0]['amount'] == 12

    assert len(data_2026) == 1
    assert data_2026[0]['player_name'] == season_2026_name
    assert data_2026[0]['amount'] == 15


def test_history_by_year_excludes_keeper_carryover_by_default():
    suffix = uuid4().hex[:8]

    session = _new_session()
    try:
        league = models.League(name=f"Archive Keeper League {suffix}")
        session.add(league)
        session.flush()

        owner = models.User(username=f"keeper-owner-{suffix}", league_id=league.id)
        session.add(owner)
        session.flush()

        keeper_player = models.Player(name=f"Keeper Player {suffix}", position='WR')
        draft_player = models.Player(name=f"Draft Player {suffix}", position='RB')
        session.add_all([keeper_player, draft_player])
        session.flush()

        # Prior-year locked keeper should only appear when include_keepers=true
        session.add(
            models.Keeper(
                league_id=league.id,
                owner_id=owner.id,
                player_id=keeper_player.id,
                season=2025,
                keep_cost=55,
                status='locked',
                approved_by_commish=True,
            )
        )
        session.add(
            models.DraftPick(
                owner_id=owner.id,
                player_id=draft_player.id,
                amount=12,
                year=2026,
                session_id=f"LEAGUE_{league.id}_YEAR_2026",
                league_id=league.id,
            )
        )
        session.commit()

        owner_id = owner.id
        league_id = league.id
    finally:
        session.close()

    mock_user = models.User(
        id=owner_id,
        username=f"keeper-owner-{suffix}",
        league_id=league_id,
        is_commissioner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    default_response = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2026},
    )
    include_response = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2026, 'include_keepers': True},
    )

    assert default_response.status_code == 200
    assert include_response.status_code == 200

    default_rows = default_response.json()
    include_rows = include_response.json()

    assert len(default_rows) == 1
    assert default_rows[0]['player_name'] == f"Draft Player {suffix}"
    assert default_rows[0]['is_keeper'] is False

    assert len(include_rows) == 2
    assert any(row.get('is_keeper') is True for row in include_rows)


def test_history_by_year_respects_round_pick_ordering():
    suffix = uuid4().hex[:8]

    session = _new_session()
    try:
        league = models.League(name=f"Archive Order League {suffix}")
        session.add(league)
        session.flush()

        owner = models.User(username=f"order-owner-{suffix}", league_id=league.id)
        session.add(owner)
        session.flush()

        player_a = models.Player(name=f"Order A {suffix}", position='WR')
        player_b = models.Player(name=f"Order B {suffix}", position='RB')
        session.add_all([player_a, player_b])
        session.flush()

        # Intentionally insert out of order by id so ordering must come from round/pick.
        session.add(
            models.DraftPick(
                owner_id=owner.id,
                player_id=player_b.id,
                amount=20,
                year=2026,
                round_num=2,
                pick_num=5,
                session_id=f"LEAGUE_{league.id}_YEAR_2026",
                league_id=league.id,
            )
        )
        session.add(
            models.DraftPick(
                owner_id=owner.id,
                player_id=player_a.id,
                amount=30,
                year=2026,
                round_num=1,
                pick_num=1,
                session_id=f"LEAGUE_{league.id}_YEAR_2026",
                league_id=league.id,
            )
        )
        session.commit()

        owner_id = owner.id
        league_id = league.id
    finally:
        session.close()

    mock_user = models.User(
        id=owner_id,
        username=f"order-owner-{suffix}",
        league_id=league_id,
        is_commissioner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2026},
    )
    assert response.status_code == 200

    rows = response.json()
    assert len(rows) == 2
    assert rows[0]['player_name'] == f"Order A {suffix}"
    assert rows[1]['player_name'] == f"Order B {suffix}"


def test_history_by_year_excludes_rows_without_round_and_pick():
    suffix = uuid4().hex[:8]

    session = _new_session()
    try:
        league = models.League(name=f"Archive Draft Filter League {suffix}")
        session.add(league)
        session.flush()

        owner = models.User(username=f"draft-filter-owner-{suffix}", league_id=league.id)
        session.add(owner)
        session.flush()

        draft_player = models.Player(name=f"Drafted Properly {suffix}", position='QB')
        waiver_like_player = models.Player(name=f"Waiver Like {suffix}", position='RB')
        session.add_all([draft_player, waiver_like_player])
        session.flush()

        session.add(
            models.DraftPick(
                owner_id=owner.id,
                player_id=draft_player.id,
                amount=22,
                year=2026,
                round_num=1,
                pick_num=3,
                session_id=f"LEAGUE_{league.id}_YEAR_2026",
                league_id=league.id,
            )
        )
        session.add(
            models.DraftPick(
                owner_id=owner.id,
                player_id=waiver_like_player.id,
                amount=1,
                year=2026,
                round_num=None,
                pick_num=None,
                session_id="default",
                league_id=league.id,
            )
        )
        session.commit()

        owner_id = owner.id
        league_id = league.id
    finally:
        session.close()

    mock_user = models.User(
        id=owner_id,
        username=f"draft-filter-owner-{suffix}",
        league_id=league_id,
        is_commissioner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.get(
        '/draft/history/by-year',
        params={'league_id': league_id, 'year': 2026},
    )
    assert response.status_code == 200

    rows = response.json()
    assert len(rows) == 1
    assert rows[0]['player_name'] == f"Drafted Properly {suffix}"

