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


def test_validate_multi_asset_trade_rejects_fractional_draft_dollars():
    report = validate_multi_asset_trade(
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=1.5)],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=9)],
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert any("whole number" in message for message in report.errors["assets_from_a[0]"])


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


# ==== HAPPY PATH TESTS ====


def test_validate_multi_asset_trade_accepts_valid_players_and_picks():
    report = validate_multi_asset_trade(
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1),
            TradeAssetInput(asset_type="PLAYER", player_id=2),
        ],
        assets_from_b=[
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=100),
        ],
    )

    assert report.valid
    assert not report.errors


def test_validate_multi_asset_trade_accepts_mixed_asset_types():
    report = validate_multi_asset_trade(
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=25),
        ],
        assets_from_b=[
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=50),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=50),
        ],
    )

    assert report.valid
    assert not report.errors


def test_validate_trade_window_accepts_open_window():
    now = datetime.now(UTC)
    report = validate_trade_window(
        trade_start_at=now - timedelta(days=1),
        trade_end_at=now + timedelta(days=10),
        allow_playoff_trades=True,
        is_playoff=False,
        now=now,
    )

    assert report.valid
    assert not report.errors


def test_validate_trade_window_accepts_playoff_trades_when_enabled():
    now = datetime.now(UTC)
    report = validate_trade_window(
        trade_start_at=now - timedelta(days=1),
        trade_end_at=now + timedelta(days=10),
        allow_playoff_trades=True,
        is_playoff=True,
        now=now,
    )

    assert report.valid
    assert not report.errors


def test_validate_trade_window_accepts_no_window_restrictions():
    report = validate_trade_window(
        trade_start_at=None,
        trade_end_at=None,
        allow_playoff_trades=True,
        is_playoff=False,
        now=None,
    )

    assert report.valid
    assert not report.errors


def test_validate_draft_pick_ownership_accepts_owned_picks_within_limits():
    report = validate_draft_pick_ownership(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=10, season_year=2026),
        ],
        assets_from_b=[
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=50, season_year=2027),
        ],
        owned_pick_ids_by_team={1: {10, 11, 12}, 2: {50, 51}},
        max_future_year_offset=2,
        current_season=2026,
    )

    assert report.valid
    assert not report.errors


def test_validate_draft_capital_accepts_within_available_balance():
    report = validate_draft_capital(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=15)],
        assets_from_b=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=10)],
        available_draft_dollars={1: 50, 2: 40},
    )

    assert report.valid
    assert not report.errors


def test_validate_draft_capital_accepts_zero_dollars_when_other_assets_present():
    report = validate_draft_capital(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
        assets_from_b=[TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=100)],
        available_draft_dollars={1: 50, 2: 40},
    )

    assert report.valid
    assert not report.errors


def test_validate_position_suppression_accepts_non_suppressed_positions():
    report = validate_position_suppression(
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1, position="RB"),
            TradeAssetInput(asset_type="PLAYER", player_id=2, position="WR"),
        ],
        assets_from_b=[
            TradeAssetInput(asset_type="PLAYER", player_id=3, position="QB"),
        ],
        suppressed_positions={"K", "DEF"},
        player_positions_by_id={},
    )

    assert report.valid
    assert not report.errors


def test_validate_position_suppression_allows_non_player_assets():
    report = validate_position_suppression(
        assets_from_a=[
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=1),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=25),
        ],
        assets_from_b=[],
        suppressed_positions={"K", "DEF"},
        player_positions_by_id={},
    )

    assert report.valid
    assert not report.errors


def test_validate_roster_limits_accepts_valid_trade():
    report = validate_roster_limits(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=2)],
        roster_sizes={1: 12, 2: 12},
        max_roster_size=15,
        min_roster_size=8,
    )

    assert report.valid
    assert not report.errors


def test_validate_roster_limits_accepts_boundary_sizes():
    report = validate_roster_limits(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1),
            TradeAssetInput(asset_type="PLAYER", player_id=2),
            TradeAssetInput(asset_type="PLAYER", player_id=3),
        ],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=4)],
        roster_sizes={1: 15, 2: 8},
        max_roster_size=15,
        min_roster_size=8,
    )

    assert report.valid
    assert not report.errors


def test_validate_trade_request_accepts_valid_full_trade():
    now = datetime.now(UTC)
    context = TradeValidationContext(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1, position="RB"),
            TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=100, season_year=2027),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=20),
        ],
        assets_from_b=[
            TradeAssetInput(asset_type="PLAYER", player_id=2, position="WR"),
            TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=15),
        ],
        roster_sizes={1: 12, 2: 12},
        max_roster_size=15,
        min_roster_size=8,
        available_draft_dollars={1: 50, 2: 50},
        owned_pick_ids_by_team={1: {100, 101}, 2: {200}},
        suppressed_positions={"K", "DEF"},
        player_positions_by_id={},
        trade_start_at=now - timedelta(days=5),
        trade_end_at=now + timedelta(days=10),
        allow_playoff_trades=True,
        is_playoff=False,
        max_future_year_offset=2,
        current_season=2026,
        now=now,
    )

    report = validate_trade_request(context)

    assert report.valid
    assert not report.errors


# ==== ADDITIONAL EDGE CASES AND COMPREHENSIVE NEGATIVE TESTS ====


def test_validate_trade_window_blocks_not_yet_open_window():
    now = datetime.now(UTC)
    report = validate_trade_window(
        trade_start_at=now + timedelta(days=2),
        trade_end_at=now + timedelta(days=10),
        allow_playoff_trades=True,
        is_playoff=False,
        now=now,
    )

    assert not report.valid
    assert any("not open yet" in message for message in report.errors.get("trade_window", []))


def test_validate_trade_window_blocks_playoffs_when_disabled():
    now = datetime.now(UTC)
    report = validate_trade_window(
        trade_start_at=now - timedelta(days=1),
        trade_end_at=now + timedelta(days=10),
        allow_playoff_trades=False,
        is_playoff=True,
        now=now,
    )

    assert not report.valid
    assert any("disabled during playoffs" in message for message in report.errors.get("trade_window", []))


def test_validate_draft_pick_ownership_detects_unowned_pick():
    report = validate_draft_pick_ownership(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=999, season_year=2026)],
        assets_from_b=[],
        owned_pick_ids_by_team={1: {1, 2, 3}},
        max_future_year_offset=2,
        current_season=2026,
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert any("does not own" in message for message in report.errors["assets_from_a[0]"])


def test_validate_draft_pick_ownership_detects_future_year_beyond_limit():
    report = validate_draft_pick_ownership(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_PICK", draft_pick_id=10, season_year=2030)],
        assets_from_b=[],
        owned_pick_ids_by_team={1: {10}},
        max_future_year_offset=2,
        current_season=2026,
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert any("beyond allowed future year limit" in message for message in report.errors["assets_from_a[0]"])


def test_validate_draft_capital_rejects_overages_on_both_sides():
    report = validate_draft_capital(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=100)],
        assets_from_b=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=75)],
        available_draft_dollars={1: 50, 2: 60},
    )

    assert not report.valid
    assert "assets_from_a" in report.errors
    assert "assets_from_b" in report.errors


def test_validate_roster_limits_rejects_below_minimum():
    report = validate_roster_limits(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[
            TradeAssetInput(asset_type="PLAYER", player_id=1),
            TradeAssetInput(asset_type="PLAYER", player_id=2),
            TradeAssetInput(asset_type="PLAYER", player_id=3),
        ],
        assets_from_b=[],
        roster_sizes={1: 8, 2: 12},
        max_roster_size=15,
        min_roster_size=8,
    )

    assert not report.valid
    assert "assets_from_a" in report.errors


def test_validate_roster_limits_rejects_above_maximum():
    report = validate_roster_limits(
        team_a_id=1,
        team_b_id=2,
        assets_from_a=[],
        assets_from_b=[
            TradeAssetInput(asset_type="PLAYER", player_id=1),
            TradeAssetInput(asset_type="PLAYER", player_id=2),
            TradeAssetInput(asset_type="PLAYER", player_id=3),
        ],
        roster_sizes={1: 14, 2: 12},  # Team A at 14 receiving 3 would be 17 > max 15
        max_roster_size=15,
        min_roster_size=8,
    )

    assert not report.valid
    assert "assets_from_a" in report.errors  # Team A roster is what goes out of bounds


def test_validate_position_suppression_uses_provided_position_over_lookup():
    """When position is provided in asset, it takes precedence over player_positions_by_id lookup."""
    report = validate_position_suppression(
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1, position="K")],
        assets_from_b=[],
        suppressed_positions={"K"},
        player_positions_by_id={1: "RB"},  # This should be ignored in favor of provided position
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors


def test_validate_position_suppression_falls_back_to_lookup_when_not_provided():
    """When position is not provided, use player_positions_by_id."""
    report = validate_position_suppression(
        assets_from_a=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
        assets_from_b=[],
        suppressed_positions={"K"},
        player_positions_by_id={1: "K"},
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors


def test_validate_multi_asset_trade_rejects_invalid_asset_type():
    report = validate_multi_asset_trade(
        assets_from_a=[TradeAssetInput(asset_type="INVALID_TYPE", player_id=1)],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=2)],
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert any("must be one of" in message for message in report.errors["assets_from_a[0]"])


def test_validate_multi_asset_trade_rejects_player_without_id():
    report = validate_multi_asset_trade(
        assets_from_a=[TradeAssetInput(asset_type="PLAYER")],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors


def test_validate_multi_asset_trade_rejects_zero_or_negative_draft_dollars():
    report = validate_multi_asset_trade(
        assets_from_a=[TradeAssetInput(asset_type="DRAFT_DOLLARS", amount=0)],
        assets_from_b=[TradeAssetInput(asset_type="PLAYER", player_id=1)],
    )

    assert not report.valid
    assert "assets_from_a[0]" in report.errors
    assert any("greater than zero" in message for message in report.errors["assets_from_a[0]"])
