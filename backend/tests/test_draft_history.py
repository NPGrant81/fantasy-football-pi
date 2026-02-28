from fastapi.testclient import TestClient
from ..main import app
from backend.database import SessionLocal
import backend.models as models

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
