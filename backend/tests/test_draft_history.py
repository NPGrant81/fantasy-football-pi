from fastapi.testclient import TestClient
from uuid import uuid4
from ..main import app
from backend.database import SessionLocal
from backend.core.security import get_current_user
import backend.models as models
import backend.models_draft_value as draft_value_models

client = TestClient(app)


def test_history_returns_player_name_and_position():
    suffix = uuid4().hex[:8]
    session_id = f"s1-{suffix}"
    username = f"testuser-{suffix}"
    player_name = f"Test Player {suffix}"

    # use a fresh db session to insert rows directly
    session = SessionLocal()
    try:
        # create owner and player records
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

    # call the endpoint
    r = client.get('/draft/history', params={'session_id': session_id})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    # enriched fields should be present
    assert entry.get('player_name') == player_name
    assert entry.get('position') == 'RB'
    assert entry.get('amount') == 10
    assert entry.get('owner_id') == user_id


def test_rankings_returns_ordered_players_for_season():
    suffix = uuid4().hex[:8]
    rank_one_name = f"Rank One {suffix}"
    rank_two_name = f"Rank Two {suffix}"

    session = SessionLocal()
    try:
        p1 = models.Player(name=rank_one_name, position='WR', nfl_team='AAA')
        p2 = models.Player(name=rank_two_name, position='RB', nfl_team='BBB')
        session.add_all([p1, p2])
        session.flush()

        session.add_all(
            [
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
            ]
        )
        session.commit()
    finally:
        session.close()

    mock_user = models.User(id=9999, username='ranktest', league_id=1, is_commissioner=False)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.get('/draft/rankings', params={'season': 2026, 'limit': 200})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    names = [row.get('player_name') for row in data]
    assert rank_one_name in names
    assert rank_two_name in names
    assert names.index(rank_one_name) < names.index(rank_two_name)

    rank_one_row = next(row for row in data if row.get('player_name') == rank_one_name)
    assert rank_one_row['consensus_tier'] == 'S'
