from fastapi.testclient import TestClient
from uuid import uuid4

from ..main import app
from backend.database import SessionLocal
import backend.models as models


client = TestClient(app)


def test_players_endpoint_dedupes_name_position_team_aliases():
    suffix = uuid4().hex[:8]
    brandin_name = f"Brandin Cooks Dedup {suffix}"
    brian_name = f"Brian Thomas Jr Dedup {suffix}"

    session = SessionLocal()
    try:
        session.add_all(
            [
                models.Player(
                    name=brandin_name,
                    position="WR",
                    nfl_team="NO",
                    gsis_id=None,
                ),
                models.Player(
                    name=brandin_name,
                    position="WR",
                    nfl_team="NO",
                    gsis_id=None,
                ),
                models.Player(
                    name=brian_name,
                    position="WR",
                    nfl_team="JAX",
                    gsis_id=None,
                ),
                models.Player(
                    name=brian_name,
                    position="WR",
                    nfl_team="JAC",
                    gsis_id=None,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/players/")
    assert response.status_code == 200
    data = response.json()

    brandin = [
        row
        for row in data
        if row.get("name") == brandin_name and row.get("position") == "WR"
    ]
    brian = [
        row
        for row in data
        if row.get("name") == brian_name and row.get("position") == "WR"
    ]

    assert len(brandin) == 1
    assert len(brian) == 1
