import io
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile

import models
from backend.routers.scoring import upload_points_override


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


def make_league_and_commissioner(db):
    league = models.League(name="UploadLeague")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="commissioner",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db.add(commissioner)
    db.commit()
    db.refresh(commissioner)
    return league, commissioner


def make_player(db, name):
    player = models.Player(name=name, position="WR")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def test_upload_points_override_csv_applies_rows_and_logs_audit(db_session):
    league, commissioner = make_league_and_commissioner(db_session)
    p1 = make_player(db_session, "Player One")
    p2 = make_player(db_session, "Player Two")

    # existing row should be replaced when replace_existing_for_source=True
    db_session.add(
        models.PlayerWeeklyStat(
            player_id=p1.id,
            season=2026,
            week=2,
            fantasy_points=3.0,
            source="manual_override",
            stats={"seed": True},
        )
    )
    db_session.commit()

    payload = f"player_id,points\n{p1.id},17.5\n{p2.id},10\n".encode("utf-8")
    upload = UploadFile(file=io.BytesIO(payload), filename="override.csv")

    summary = asyncio.run(
        upload_points_override(
            file=upload,
            season=2026,
            week=2,
            source="manual_override",
            replace_existing_for_source=True,
            player_id_column=None,
            points_column=None,
            db=db_session,
            current_user=commissioner,
        )
    )

    assert summary.rows_received == 2
    assert summary.rows_applied == 2
    assert summary.rows_deleted == 1
    assert summary.inserted == 2
    assert summary.updated == 0

    stats = (
        db_session.query(models.PlayerWeeklyStat)
        .filter(
            models.PlayerWeeklyStat.season == 2026,
            models.PlayerWeeklyStat.week == 2,
            models.PlayerWeeklyStat.source == "manual_override",
        )
        .all()
    )
    by_player = {row.player_id: row.fantasy_points for row in stats}
    assert by_player[p1.id] == 17.5
    assert by_player[p2.id] == 10.0

    log = (
        db_session.query(models.ScoringRuleChangeLog)
        .filter(models.ScoringRuleChangeLog.change_type == "stats_override_imported")
        .one()
    )
    assert log.league_id == league.id
    assert (log.new_value or {}).get("filename") == "override.csv"
    assert (log.new_value or {}).get("rows_applied") == 2


def test_upload_points_override_xlsx_supports_custom_column_mapping(db_session):
    _, commissioner = make_league_and_commissioner(db_session)
    p1 = make_player(db_session, "Spreadsheet Player")

    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Player ID", "Override Pts"])
    sheet.append([p1.id, 21.25])

    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)

    upload = UploadFile(file=stream, filename="override.xlsx")
    summary = asyncio.run(
        upload_points_override(
            file=upload,
            season=2026,
            week=3,
            source="manual_override",
            replace_existing_for_source=True,
            player_id_column="Player ID",
            points_column="Override Pts",
            db=db_session,
            current_user=commissioner,
        )
    )

    assert summary.rows_applied == 1
    row = (
        db_session.query(models.PlayerWeeklyStat)
        .filter(
            models.PlayerWeeklyStat.player_id == p1.id,
            models.PlayerWeeklyStat.season == 2026,
            models.PlayerWeeklyStat.week == 3,
            models.PlayerWeeklyStat.source == "manual_override",
        )
        .one()
    )
    assert row.fantasy_points == 21.25


def test_upload_points_override_rejects_unknown_player_id(db_session):
    _, commissioner = make_league_and_commissioner(db_session)
    payload = b"player_id,points\n999999,12\n"
    upload = UploadFile(file=io.BytesIO(payload), filename="override.csv")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_points_override(
                file=upload,
                season=2026,
                week=4,
                source="manual_override",
                replace_existing_for_source=True,
                player_id_column=None,
                points_column=None,
                db=db_session,
                current_user=commissioner,
            )
        )

    assert exc.value.status_code == 400
    assert "Unknown player_id" in str(exc.value.detail)
