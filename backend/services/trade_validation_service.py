from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable


_ALLOWED_ASSET_TYPES = {"PLAYER", "DRAFT_PICK", "DRAFT_DOLLARS"}


@dataclass
class TradeAssetInput:
    asset_type: str
    player_id: int | None = None
    draft_pick_id: int | None = None
    amount: float | int | None = None
    season_year: int | None = None
    position: str | None = None


@dataclass
class TradeValidationReport:
    valid: bool
    errors: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class TradeValidationContext:
    team_a_id: int
    team_b_id: int
    assets_from_a: list[TradeAssetInput]
    assets_from_b: list[TradeAssetInput]
    roster_sizes: dict[int, int]
    max_roster_size: int
    min_roster_size: int = 1
    available_draft_dollars: dict[int, float] = field(default_factory=dict)
    owned_pick_ids_by_team: dict[int, set[int]] = field(default_factory=dict)
    suppressed_positions: set[str] = field(default_factory=set)
    player_positions_by_id: dict[int, str] = field(default_factory=dict)
    trade_start_at: datetime | None = None
    trade_end_at: datetime | None = None
    allow_playoff_trades: bool = True
    is_playoff: bool = False
    max_future_year_offset: int | None = None
    current_season: int | None = None
    now: datetime | None = None


def _new_report() -> TradeValidationReport:
    return TradeValidationReport(valid=True, errors={})


def _add_error(report: TradeValidationReport, key: str, message: str) -> None:
    report.valid = False
    report.errors.setdefault(key, []).append(message)


def validate_multi_asset_trade(
    assets_from_a: Iterable[TradeAssetInput],
    assets_from_b: Iterable[TradeAssetInput],
) -> TradeValidationReport:
    report = _new_report()
    a_assets = list(assets_from_a)
    b_assets = list(assets_from_b)

    if not a_assets:
        _add_error(report, "assets_from_a", "must include at least one asset")
    if not b_assets:
        _add_error(report, "assets_from_b", "must include at least one asset")

    for side, asset_list in (("assets_from_a", a_assets), ("assets_from_b", b_assets)):
        for idx, asset in enumerate(asset_list):
            path = f"{side}[{idx}]"
            asset_type = (asset.asset_type or "").strip().upper()
            if asset_type not in _ALLOWED_ASSET_TYPES:
                _add_error(report, path, "asset_type must be one of PLAYER, DRAFT_PICK, DRAFT_DOLLARS")
                continue

            if asset_type == "PLAYER" and asset.player_id is None:
                _add_error(report, path, "player asset must include player_id")
            if asset_type == "DRAFT_PICK" and asset.draft_pick_id is None:
                _add_error(report, path, "draft pick asset must include draft_pick_id")
            if asset_type == "DRAFT_DOLLARS":
                amount = float(asset.amount or 0)
                if amount <= 0:
                    _add_error(report, path, "draft dollar asset amount must be greater than zero")
                elif not amount.is_integer():
                    _add_error(report, path, "draft dollar asset amount must be a whole number")

    return report


def validate_trade_window(
    *,
    trade_start_at: datetime | None,
    trade_end_at: datetime | None,
    allow_playoff_trades: bool,
    is_playoff: bool,
    now: datetime | None = None,
) -> TradeValidationReport:
    report = _new_report()
    check_now = now or datetime.now(UTC)

    if trade_start_at and trade_end_at and trade_end_at < trade_start_at:
        _add_error(report, "trade_window", "trade_end_at must be greater than or equal to trade_start_at")
        return report

    if trade_start_at and check_now < trade_start_at:
        _add_error(report, "trade_window", "trade window is not open yet")

    if trade_end_at and check_now > trade_end_at:
        _add_error(report, "trade_window", "trade window is closed")

    if is_playoff and not allow_playoff_trades:
        _add_error(report, "trade_window", "trades are disabled during playoffs")

    return report


def validate_draft_pick_ownership(
    *,
    team_a_id: int,
    team_b_id: int,
    assets_from_a: Iterable[TradeAssetInput],
    assets_from_b: Iterable[TradeAssetInput],
    owned_pick_ids_by_team: dict[int, set[int]],
    max_future_year_offset: int | None = None,
    current_season: int | None = None,
) -> TradeValidationReport:
    report = _new_report()

    def _check_side(side_key: str, team_id: int, assets: list[TradeAssetInput]) -> None:
        owned = owned_pick_ids_by_team.get(team_id, set())
        for idx, asset in enumerate(assets):
            if (asset.asset_type or "").upper() != "DRAFT_PICK":
                continue
            path = f"{side_key}[{idx}]"
            if asset.draft_pick_id is None:
                _add_error(report, path, "draft pick asset missing draft_pick_id")
                continue
            if asset.draft_pick_id not in owned:
                _add_error(report, path, "team does not own this draft pick")
            if (
                max_future_year_offset is not None
                and current_season is not None
                and asset.season_year is not None
                and asset.season_year > (current_season + max_future_year_offset)
            ):
                _add_error(report, path, "draft pick season is beyond allowed future year limit")

    _check_side("assets_from_a", team_a_id, list(assets_from_a))
    _check_side("assets_from_b", team_b_id, list(assets_from_b))
    return report


def validate_draft_capital(
    *,
    team_a_id: int,
    team_b_id: int,
    assets_from_a: Iterable[TradeAssetInput],
    assets_from_b: Iterable[TradeAssetInput],
    available_draft_dollars: dict[int, float],
) -> TradeValidationReport:
    report = _new_report()

    def _total_offered(assets: Iterable[TradeAssetInput]) -> float:
        total = 0.0
        for asset in assets:
            if (asset.asset_type or "").upper() == "DRAFT_DOLLARS":
                total += float(asset.amount or 0)
        return total

    offered_by_a = _total_offered(assets_from_a)
    offered_by_b = _total_offered(assets_from_b)

    if offered_by_a > float(available_draft_dollars.get(team_a_id, 0)):
        _add_error(report, "assets_from_a", "team A cannot trade more draft dollars than available")
    if offered_by_b > float(available_draft_dollars.get(team_b_id, 0)):
        _add_error(report, "assets_from_b", "team B cannot trade more draft dollars than available")

    return report


def validate_position_suppression(
    *,
    assets_from_a: Iterable[TradeAssetInput],
    assets_from_b: Iterable[TradeAssetInput],
    suppressed_positions: set[str],
    player_positions_by_id: dict[int, str],
) -> TradeValidationReport:
    report = _new_report()
    normalized_suppressed = {position.strip().upper() for position in suppressed_positions}

    def _check_side(side_key: str, assets: list[TradeAssetInput]) -> None:
        for idx, asset in enumerate(assets):
            if (asset.asset_type or "").upper() != "PLAYER":
                continue
            player_position = (asset.position or player_positions_by_id.get(int(asset.player_id or 0)) or "").strip().upper()
            if player_position and player_position in normalized_suppressed:
                _add_error(report, f"{side_key}[{idx}]", f"position {player_position} is suppressed for trading")

    _check_side("assets_from_a", list(assets_from_a))
    _check_side("assets_from_b", list(assets_from_b))
    return report


def validate_roster_limits(
    *,
    team_a_id: int,
    team_b_id: int,
    assets_from_a: Iterable[TradeAssetInput],
    assets_from_b: Iterable[TradeAssetInput],
    roster_sizes: dict[int, int],
    max_roster_size: int,
    min_roster_size: int = 1,
) -> TradeValidationReport:
    report = _new_report()

    players_out_a = sum(1 for asset in assets_from_a if (asset.asset_type or "").upper() == "PLAYER")
    players_in_a = sum(1 for asset in assets_from_b if (asset.asset_type or "").upper() == "PLAYER")
    players_out_b = sum(1 for asset in assets_from_b if (asset.asset_type or "").upper() == "PLAYER")
    players_in_b = sum(1 for asset in assets_from_a if (asset.asset_type or "").upper() == "PLAYER")

    size_a = int(roster_sizes.get(team_a_id, 0)) - players_out_a + players_in_a
    size_b = int(roster_sizes.get(team_b_id, 0)) - players_out_b + players_in_b

    if size_a > max_roster_size or size_a < min_roster_size:
        _add_error(report, "assets_from_a", f"team A roster would be out of bounds after trade (size={size_a})")
    if size_b > max_roster_size or size_b < min_roster_size:
        _add_error(report, "assets_from_b", f"team B roster would be out of bounds after trade (size={size_b})")

    return report


def validate_trade_request(context: TradeValidationContext) -> TradeValidationReport:
    report = _new_report()

    checks = [
        validate_multi_asset_trade(context.assets_from_a, context.assets_from_b),
        validate_trade_window(
            trade_start_at=context.trade_start_at,
            trade_end_at=context.trade_end_at,
            allow_playoff_trades=context.allow_playoff_trades,
            is_playoff=context.is_playoff,
            now=context.now,
        ),
        validate_draft_pick_ownership(
            team_a_id=context.team_a_id,
            team_b_id=context.team_b_id,
            assets_from_a=context.assets_from_a,
            assets_from_b=context.assets_from_b,
            owned_pick_ids_by_team=context.owned_pick_ids_by_team,
            max_future_year_offset=context.max_future_year_offset,
            current_season=context.current_season,
        ),
        validate_draft_capital(
            team_a_id=context.team_a_id,
            team_b_id=context.team_b_id,
            assets_from_a=context.assets_from_a,
            assets_from_b=context.assets_from_b,
            available_draft_dollars=context.available_draft_dollars,
        ),
        validate_position_suppression(
            assets_from_a=context.assets_from_a,
            assets_from_b=context.assets_from_b,
            suppressed_positions=context.suppressed_positions,
            player_positions_by_id=context.player_positions_by_id,
        ),
        validate_roster_limits(
            team_a_id=context.team_a_id,
            team_b_id=context.team_b_id,
            assets_from_a=context.assets_from_a,
            assets_from_b=context.assets_from_b,
            roster_sizes=context.roster_sizes,
            max_roster_size=context.max_roster_size,
            min_roster_size=context.min_roster_size,
        ),
    ]

    for check in checks:
        if not check.valid:
            report.valid = False
            for key, messages in check.errors.items():
                report.errors.setdefault(key, []).extend(messages)

    return report
