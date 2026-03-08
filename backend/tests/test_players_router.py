from uuid import uuid4

from backend.database import SessionLocal
import backend.models as models


def test_top_free_agents_excludes_owned_and_sorts_by_projection(client):
    suffix = uuid4().hex[:8]
    created_ids: list[int] = []
    league_id = None

    session = SessionLocal()
    try:
        league = models.League(name=f"Top Free Agent League {suffix}")
        session.add(league)
        session.commit()
        session.refresh(league)
        league_id = league.id

        owned = models.Player(
            name=f"Owned Player {suffix}",
            position="WR",
            nfl_team="AAA",
            projected_points=999999.0,
            adp=1.0,
        )
        top = models.Player(
            name=f"Top Player {suffix}",
            position="RB",
            nfl_team="BBB",
            projected_points=999998.0,
            adp=12.0,
        )
        second = models.Player(
            name=f"Second Player {suffix}",
            position="WR",
            nfl_team="CCC",
            projected_points=999997.0,
            adp=20.0,
        )
        third = models.Player(
            name=f"Third Player {suffix}",
            position="QB",
            nfl_team="DDD",
            projected_points=999996.0,
            adp=30.0,
        )
        session.add_all([owned, top, second, third])
        session.commit()

        created_ids = [row.id for row in (owned, top, second, third) if row.id is not None]

        owner_user = models.User(
            username=f"owner-{suffix}",
            email=None,
            hashed_password="h",
            league_id=league_id,
        )
        session.add(owner_user)
        session.commit()
        session.refresh(owner_user)

        session.add(
            models.DraftPick(
                owner_id=owner_user.id,
                player_id=owned.id,
                league_id=league_id,
                current_status="STARTER",
            )
        )
        session.commit()
    finally:
        session.close()

    try:
        response = client.get(f"/players/top-free-agents?league_id={league_id}&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        names = [row.get("name") for row in data]
        assert names[0] == f"Top Player {suffix}"
        assert names[1] == f"Second Player {suffix}"
        assert f"Owned Player {suffix}" not in names
    finally:
        cleanup = SessionLocal()
        try:
            if league_id is not None:
                cleanup.query(models.DraftPick).filter(
                    models.DraftPick.league_id == league_id
                ).delete(synchronize_session=False)
                cleanup.query(models.User).filter(
                    models.User.league_id == league_id
                ).delete(synchronize_session=False)
                cleanup.query(models.League).filter(
                    models.League.id == league_id
                ).delete(synchronize_session=False)
            if created_ids:
                cleanup.query(models.Player).filter(
                    models.Player.id.in_(created_ids)
                ).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()


def test_players_endpoint_dedupes_name_position_team_aliases(client):
    suffix = uuid4().hex[:8]
    brandin_name = f"Brandin Cooks Dedup {suffix}"
    brian_name = f"Brian Thomas Jr Dedup {suffix}"
    created_ids: list[int] = []

    session = SessionLocal()
    try:
        players = [
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

        session.add_all(players)
        session.commit()
        created_ids = [row.id for row in players if row.id is not None]
    finally:
        session.close()

    try:
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
    finally:
        cleanup = SessionLocal()
        try:
            if created_ids:
                cleanup.query(models.Player).filter(
                    models.Player.id.in_(created_ids)
                ).delete(synchronize_session=False)
                cleanup.commit()
        finally:
            cleanup.close()
