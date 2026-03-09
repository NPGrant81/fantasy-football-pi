from uuid import uuid4

from backend.database import SessionLocal
import backend.models as models
from backend.core import security


def test_top_free_agents_excludes_owned_and_sorts_by_projection(client):
    suffix = uuid4().hex[:8]
    created_ids: list[int] = []
    league_id = None
    owner_username = None

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
        owner_username = owner_user.username

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
        token = security.create_access_token({"sub": owner_username})
        client.cookies.set("ffpi_access_token", token)
        response = client.get(f"/players/top-free-agents?league_id={league_id}&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        names = [row.get("name") for row in data]
        assert names[0] == f"Top Player {suffix}"
        assert names[1] == f"Second Player {suffix}"
        assert f"Owned Player {suffix}" not in names
        assert data[0].get("pickup_rank") == 1
        assert data[0].get("pickup_tier") in {"S", "A", "B", "C"}
        assert isinstance(data[0].get("pickup_score"), float)
        assert isinstance(data[0].get("pickup_trend_score"), float)
        assert data[0].get("pickup_trend_label") in {"Rising", "Steady", "Cooling"}
        assert isinstance(data[0].get("recent_claim_count"), int)
        assert data[0].get("pickup_rationale") == "projection_plus_adp_plus_waiver_momentum"
    finally:
        client.cookies.clear()
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


def test_top_free_agents_momentum_promotes_recent_waiver_target(client):
    suffix = uuid4().hex[:8]
    created_player_ids: list[int] = []
    created_txn_ids: list[int] = []
    league_id = None
    owner_username = None

    session = SessionLocal()
    try:
        league = models.League(name=f"Momentum League {suffix}")
        session.add(league)
        session.commit()
        session.refresh(league)
        league_id = league.id

        baseline = models.Player(
            name=f"Baseline Player {suffix}",
            position="WR",
            nfl_team="AAA",
            projected_points=9100000.0,
            adp=60.0,
        )
        momentum = models.Player(
            name=f"Momentum Player {suffix}",
            position="WR",
            nfl_team="BBB",
            projected_points=9099999.8,
            adp=60.0,
        )
        session.add_all([baseline, momentum])
        session.commit()
        created_player_ids = [row.id for row in (baseline, momentum) if row.id is not None]

        owner_user = models.User(
            username=f"momentum-owner-{suffix}",
            email=None,
            hashed_password="h",
            league_id=league_id,
        )
        session.add(owner_user)
        session.commit()
        session.refresh(owner_user)
        owner_username = owner_user.username

        txns = [
            models.TransactionHistory(
                league_id=league_id,
                player_id=momentum.id,
                old_owner_id=None,
                new_owner_id=owner_user.id,
                transaction_type="waiver_add",
            ),
            models.TransactionHistory(
                league_id=league_id,
                player_id=momentum.id,
                old_owner_id=None,
                new_owner_id=owner_user.id,
                transaction_type="waiver_add",
            ),
            models.TransactionHistory(
                league_id=league_id,
                player_id=baseline.id,
                old_owner_id=owner_user.id,
                new_owner_id=None,
                transaction_type="waiver_drop",
            ),
        ]
        session.add_all(txns)
        session.commit()
        created_txn_ids = [row.id for row in txns if row.id is not None]
    finally:
        session.close()

    try:
        token = security.create_access_token({"sub": owner_username})
        client.cookies.set("ffpi_access_token", token)
        response = client.get(f"/players/top-free-agents?league_id={league_id}&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        assert data[0].get("name") == f"Momentum Player {suffix}"
        assert data[0].get("pickup_trend_label") == "Rising"
        assert float(data[0].get("pickup_trend_score") or 0.0) > 0.0
    finally:
        client.cookies.clear()
        cleanup = SessionLocal()
        try:
            if created_txn_ids:
                cleanup.query(models.TransactionHistory).filter(
                    models.TransactionHistory.id.in_(created_txn_ids)
                ).delete(synchronize_session=False)
            if league_id is not None:
                cleanup.query(models.User).filter(
                    models.User.league_id == league_id
                ).delete(synchronize_session=False)
                cleanup.query(models.League).filter(
                    models.League.id == league_id
                ).delete(synchronize_session=False)
            if created_player_ids:
                cleanup.query(models.Player).filter(
                    models.Player.id.in_(created_player_ids)
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


def test_top_free_agents_returns_ranked_players_with_reasons(client):
    suffix = uuid4().hex[:8]
    session = SessionLocal()
    created_ids: list[int] = []
    league_id = None
    owner_username = None

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
        owner_username = owner.username

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
        token = security.create_access_token({"sub": owner_username})
        client.cookies.set("ffpi_access_token", token)
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
        assert buzz["pickup_rationale"] == "projection_plus_adp_plus_waiver_momentum"
        assert buzz["pickup_trend_label"] in {"Rising", "Steady", "Cooling"}
        assert "pickup_score" in buzz
    finally:
        client.cookies.clear()
        cleanup = SessionLocal()
        try:
            cleanup.query(models.WaiverClaim).filter(models.WaiverClaim.player_id.in_(created_ids)).delete(synchronize_session=False)
            cleanup.query(models.Player).filter(models.Player.id.in_(created_ids)).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
