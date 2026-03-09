from uuid import uuid4

from backend.database import SessionLocal
import backend.models as models


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


def test_top_free_agents_returns_ranked_players_with_reasons(client):
    suffix = uuid4().hex[:8]
    session = SessionLocal()
    created_ids: list[int] = []
    league_id = None

    try:
        league = models.League(name=f"Rank League {suffix}")
        session.add(league)
        session.commit()
        session.refresh(league)
        league_id = league.id

        owner = models.User(
            username=f"owner-{suffix}",
            email=None,
            hashed_password="h",
            league_id=league.id,
        )
        session.add(owner)
        session.commit()
        session.refresh(owner)

        p1 = models.Player(
            name=f"High Projection {suffix}",
            position="WR",
            nfl_team="BUF",
            projected_points=170.0,
            adp=40.0,
        )
        p2 = models.Player(
            name=f"Waiver Buzz {suffix}",
            position="RB",
            nfl_team="DAL",
            projected_points=150.0,
            adp=55.0,
        )
        p3 = models.Player(
            name=f"Depth Option {suffix}",
            position="TE",
            nfl_team="KC",
            projected_points=90.0,
            adp=120.0,
        )
        session.add_all([p1, p2, p3])
        session.commit()
        session.refresh(p1)
        session.refresh(p2)
        session.refresh(p3)

        created_ids.extend([p1.id, p2.id, p3.id])

        # Add two claims for p2 to ensure waiver momentum metadata is populated.
        c1 = models.WaiverClaim(league_id=league.id, user_id=owner.id, player_id=p2.id, bid_amount=5)
        c2 = models.WaiverClaim(league_id=league.id, user_id=owner.id, player_id=p2.id, bid_amount=7)
        session.add_all([c1, c2])
        session.commit()
    finally:
        session.close()

    try:
        response = client.get(f"/players/top-free-agents?league_id={league_id}&limit=25")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        high_name = f"High Projection {suffix}"
        buzz_name = f"Waiver Buzz {suffix}"
        depth_name = f"Depth Option {suffix}"

        names = [row.get("name") for row in data]
        assert high_name in names
        assert buzz_name in names
        assert depth_name in names

        # Deterministic ranking should keep stronger profile above lower profiles.
        assert names.index(high_name) < names.index(depth_name)

        buzz = next(row for row in data if row["name"] == buzz_name)
        assert buzz["recent_claim_count"] == 2
        assert isinstance(buzz["pickup_reasons"], list)
        assert len(buzz["pickup_reasons"]) >= 1
        assert "pickup_score" in buzz
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(models.WaiverClaim).filter(models.WaiverClaim.player_id.in_(created_ids)).delete(synchronize_session=False)
            cleanup.query(models.Player).filter(models.Player.id.in_(created_ids)).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
