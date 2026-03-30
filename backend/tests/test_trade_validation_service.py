from datetime import UTC, datetime, timedelta

from backend.services.trade_validation_service import (
    TradeAssetInput,
    TradeValidationContext,
    validate_draft_capital,
    validate_draft_pick_ownership,
    validate_multi_asset_trade,
    validate_position_suppression,
    validate_roster_limits,
    validate_trade_request,
    validate_trade_window,
)


def test_validate_multi_asset_trade_requires_assets_on_both_sides():
    report = validate_multi_asset_trade(
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
        assets_from_b=[],
    )

    assert not report.valid
    assert "assets_from_b" in report.errors


def test_validate_trade_window_blocks_closed_window():
    now = datetime.now(UTC)
    report = validate_trade_window(
        trade_start_at=now - timedelta(days=2),
        trade_end_at=now - timedelta(minutes=1),
        allow_playoff_trades=True,
        is_playoff=False,
        now=now,
    )

    assert not report.valid
    assert any("closed" in message for message in report.errors.get("trade_window", []))


def test_validate_draft_pick_ownership_detects_missing_pick_and_future_year():
    report = validate_draft_pick_ownership(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=99, season_year=2032)],
        assets_from_b=[],
        owned_pick_ids_by_team={1: {10, 11}},
        max_future_year_offset=2,
        current_season=2026,
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert len(report.errors["assets_from_a[0]"]) >= 1


def test_validate_draft_capital_enforces_available_balances():
    report = validate_draft_capital(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=40)],
        assets_from_b=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=5)],
        available_draft_dollars={1: 25, 2: 20},
    )

    assert not report.valid
    assert "assets_from_a" in report.errors
    assert "assets_from_b" not in report.errors


def test_validate_position_suppression_rejects_blocked_position():
    report = validate_position_suppression(
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1, position="K")],
        assets_from_b=[],
        suppressed_positions={"K", "DEF"},
        player_positions_by_id={},
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors


def test_validate_roster_limits_flags_out_of_bounds_sizes():
    report = validate_roster_limits(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=11),
            TradeAssetInput(asset_type="PLAYER", player_id=12),
            TradeAssetInput(asset_type="PLAYER", player_id=13),
        ],
        assets_from_b=[],
        roster_sizes={1: 2, 2: 14},
        max_roster_size=15,
        min_roster_size=1,
    )

    assert not report.valid
    assert "assets_from_a" in report.errors


def test_validate_trade_request_aggregates_errors_from_multiple_checks():
    now = datetime.now(UTC)
    context = TradeValidationContext(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=100, position="K"),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=50),
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=77, season_year=2035),
        ],
        assets_from_b=[],
        roster_sizes={1: 2, 2: 12},
        max_roster_size=15,
        available_draft_dollars={1: 10, 2: 10},
        owned_pick_ids_by_team={1: {1, 2}},
        suppressed_positions={"K"},
        player_positions_by_id={},
        trade_start_at=now - timedelta(days=5),
        trade_end_at=now - timedelta(days=1),
        allow_playoff_trades=False,
        is_playoff=True,
        max_future_year_offset=2,
        current_season=2026,
        now=now,
    )

    report = validate_trade_request(context)

    assert not report.valid
    assert "assets_from_b" in report.errors
    assert "trade_window" in report.errors
    assert "assets_from_a" in report.errors or "assets_from_a[2]" in report.errors
