from fastapi.testclient import TestClient
from ..main import app
from backend.database import SessionLocal
import backend.models as models
import backend.models_draft_value as draft_value_models

client = TestClient(app)


def test_history_returns_player_name_and_position():
    # use a fresh db session to insert rows directly
    session = SessionLocal()
    try:
        # remove any previous test records to avoid unique conflicts
        session.query(models.DraftPick).filter(models.DraftPick.session_id=='s1').delete()
        session.query(models.Player).filter(models.Player.name=='Test Player').delete()
        session.query(models.User).filter(models.User.username=='testuser').delete()
        session.commit()

        # create owner and player records
        user = models.User(username='testuser', league_id=None)
        session.add(user)
        session.flush()
        user_id = user.id

        player = models.Player(name='Test Player', position='RB')
        session.add(player)
        session.flush()

        pick = models.DraftPick(
            owner_id=user_id,
            player_id=player.id,
            amount=10,
            session_id='s1',
            year=2025,
        )
        session.add(pick)
        session.commit()
    finally:
        session.close()

    # call the endpoint
    r = client.get('/draft/history', params={'session_id': 's1'})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    # enriched fields should be present
    assert entry.get('player_name') == 'Test Player'
    assert entry.get('position') == 'RB'
    assert entry.get('amount') == 10
    assert entry.get('owner_id') == user_id


def test_rankings_returns_ordered_players_for_season():
    session = SessionLocal()
    try:
        session.query(draft_value_models.DraftValue).filter(
            draft_value_models.DraftValue.season == 2026
        ).delete()
        session.query(models.Player).filter(
            models.Player.name.in_(['Rank One', 'Rank Two'])
        ).delete(synchronize_session=False)
        session.commit()

        p1 = models.Player(name='Rank One', position='WR', nfl_team='AAA')
        p2 = models.Player(name='Rank Two', position='RB', nfl_team='BBB')
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

    response = client.get('/draft/rankings', params={'season': 2026, 'limit': 10})
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 2
    assert data[0]['player_name'] == 'Rank One'
    assert data[0]['rank'] == 1
    assert data[0]['consensus_tier'] == 'S'
    assert data[1]['player_name'] == 'Rank Two'
