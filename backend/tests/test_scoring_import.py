import os
import tempfile
from backend.scripts import import_scoring_rules


def test_sanitize_simple_range_and_points():
    row = {'Event': 'Test Event', 'Range_Yds': '10-20', 'Point_Value': '5', 'PostionID': '8002'}
    clean = import_scoring_rules.sanitize_row(row)
    assert clean['event_name'] == 'Test Event'
    assert clean['range_min'] == 10
    assert clean['range_max'] == 20
    assert clean['point_value'] == 5.0
    assert clean['calculation_type'] == 'flat_bonus'
    assert clean['applicable_positions'] == ['QB']


def test_sanitize_excel_date_and_per_unit():
    row = {'Event': 'Yds', 'Range_Yds': 'Jan-99', 'Point_Value': '.5 points each', 'PostionID': '8003'}
    clean = import_scoring_rules.sanitize_row(row)
    # date parsing should use jan -> 1 for min and 99 for max
    assert clean['range_min'] == 1
    assert clean['range_max'] == 99
    assert clean['calculation_type'] == 'per_unit'
    assert clean['point_value'] == 0.5
    assert clean['applicable_positions'] == ['RB']


def test_insert_rules_creates_records(tmp_path, monkeypatch):
    # create a temporary sqlite file and engine/session for the importer
    db_file = tmp_path / "db.sqlite"
    db_url = f"sqlite:///{db_file}".replace('\\', '/')

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import backend.scripts.import_scoring_rules as importer

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # patch the importer module to use our test database
    importer.engine = engine
    importer.SessionLocal = SessionLocal
    # ensure tables exist on the new engine
    importer.Base.metadata.create_all(bind=engine)
    # debug: show what tables metadata thinks it has
    print('metadata tables:', importer.Base.metadata.tables.keys())
    # verify table actually exists on disk
    from sqlalchemy import text
    with engine.connect() as conn:
        names = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
    print('sqlite tables on disk:', names)
    assert 'scoring_rules' in names, f"tables={names}"

    # sanitize and insert a single record
    records = [
        importer.sanitize_row({'Event': 'Foo', 'Range_Yds': '1-2', 'Point_Value': '1', 'PostionID': '8002'})
    ]
    importer.insert_rules(123, records)

    # verify data inserted directly using the same engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("SELECT count(*) FROM scoring_rules WHERE league_id = :lid"), {'lid': 123})
        assert res.scalar() == 1
