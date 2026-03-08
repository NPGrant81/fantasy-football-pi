from backend.services.scoring_import_service import (
    parse_csv_rows_to_rules,
    parse_point_value,
    parse_range,
    parse_positions,
)


def test_parse_point_value_every_25_maps_to_per_unit():
    points, calc_type = parse_point_value("1 point for every 25")
    assert calc_type == "per_unit"
    assert points == 0.04


def test_parse_range_handles_excel_month_tokens():
    lo, hi = parse_range("7-Feb")
    assert lo == 2.0
    assert hi == 7.0


def test_parse_positions_maps_provider_ids():
    positions, position_ids = parse_positions("8002,8004")
    assert positions == ["QB", "WR"]
    assert position_ids == [8002, 8004]


def test_parse_csv_rows_to_rules_supports_legacy_headers():
    csv_content = """Event,Range_Yds,Point_Value,PostionID
Passing Yards,1-999,.10 points each,8002
"""
    rows = parse_csv_rows_to_rules(csv_content, source_platform="espn_csv", season_year=2026)

    assert len(rows) == 1
    item = rows[0]
    assert item.event_name == "Passing Yards"
    assert item.category == "passing"
    assert item.range_min == 1.0
    assert item.range_max == 999.0
    assert item.point_value == 0.1
    assert item.calculation_type == "per_unit"
    assert item.applicable_positions == ["QB"]
    assert item.position_ids == [8002]
    assert item.season_year == 2026
    assert item.source == "espn_csv"
