import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.validation_service import (
    serialize_ledger_entries,
    validate_draft_pick_boundary,
    validate_draft_pick_dynamic_rules,
    validate_league_settings_boundary,
    validate_league_settings_dynamic_rules,
    validate_keeper_settings_boundary,
    validate_keeper_settings_dynamic_rules,
    validate_playoff_settings_boundary,
    validate_playoff_settings_dynamic_rules,
    validate_trade_proposal_boundary,
    validate_trade_proposal_dynamic_rules,
    validate_waiver_claim_boundary,
    validate_waiver_claim_dynamic_rules,
)


def test_waiver_claim_boundary_valid_payload():
    report = validate_waiver_claim_boundary(
        {
            "player_id": 10,
            "bid_amount": 5,
            "drop_player_id": 11,
            "team_id": 1,
        }
    )
    assert report.valid is True
    assert report.engine == "pydantic"
    assert report.normalized["player_id"] == 10


def test_waiver_claim_boundary_invalid_payload():
    report = validate_waiver_claim_boundary(
        {
            "player_id": 0,
            "bid_amount": -1,
            "drop_player_id": None,
            "team_id": None,
        }
    )
    assert report.valid is False
    assert report.engine == "pydantic"


def test_waiver_claim_dynamic_rules_detect_conflicts():
    report = validate_waiver_claim_dynamic_rules(
        {
            "player_id": 44,
            "bid_amount": 1501,
            "drop_player_id": 44,
            "team_id": 1,
        }
    )
    assert report.valid is False
    assert "drop_player_id" in report.errors
    assert "bid_amount" in report.errors


def test_serialize_ledger_entries_shape():
    rows = [
        {
            "id": 1,
            "currency_type": "FAAB",
            "amount": 15,
            "transaction_type": "WAIVER_CLAIM_BID",
        }
    ]
    serialized = serialize_ledger_entries(rows)
    assert isinstance(serialized, list)
    assert serialized[0]["id"] == 1
    assert serialized[0]["currency_type"] == "FAAB"


def test_draft_pick_boundary_invalid_payload():
    report = validate_draft_pick_boundary(
        {
            "owner_id": 0,
            "player_id": -1,
            "amount": 0,
            "session_id": "",
            "year": 1990,
        }
    )
    assert report.valid is False


def test_draft_pick_dynamic_rules_invalid_session():
    report = validate_draft_pick_dynamic_rules(
        {
            "owner_id": 1,
            "player_id": 1,
            "amount": 5,
            "session_id": "LEAGUE 1 YEAR 2026",
            "year": 2026,
        }
    )
    assert report.valid is False
    assert "session_id" in report.errors


def test_trade_proposal_boundary_invalid_payload():
    report = validate_trade_proposal_boundary(
        {
            "to_user_id": 0,
            "offered_player_id": 0,
            "requested_player_id": 0,
            "offered_dollars": -1,
            "requested_dollars": -2,
            "note": "x" * 1001,
        }
    )
    assert report.valid is False


def test_trade_proposal_dynamic_rules_conflict():
    report = validate_trade_proposal_dynamic_rules(
        {
            "current_user_id": 2,
            "to_user_id": 2,
            "offered_player_id": 10,
            "requested_player_id": 10,
            "offered_dollars": 1.0,
            "requested_dollars": 0.0,
        }
    )
    assert report.valid is False
    assert "to_user_id" in report.errors
    assert "requested_player_id" in report.errors


def test_league_settings_boundary_invalid_payload():
    report = validate_league_settings_boundary(
        {
            "roster_size": 0,
            "salary_cap": -10,
            "starting_slots": {},
            "waiver_deadline": None,
            "starting_waiver_budget": -1,
            "waiver_system": "FAAB",
            "waiver_tiebreaker": "standings",
            "trade_deadline": None,
            "draft_year": 1900,
            "scoring_rules": [],
        }
    )
    assert report.valid is False
    assert report.engine == "pydantic"


def test_league_settings_dynamic_rules_detect_invalid_combinations():
    report = validate_league_settings_dynamic_rules(
        {
            "roster_size": 8,
            "salary_cap": 200,
            "starting_slots": {"QB": 1, "RB": 4, "WR": 4},
            "waiver_deadline": "Wed 11PM",
            "starting_waiver_budget": 100,
            "waiver_system": "UNKNOWN",
            "waiver_tiebreaker": "coinflip",
            "trade_deadline": None,
            "draft_year": 2026,
            "scoring_rules": [{"category": "passing", "event_name": "TD", "point_value": 4}],
        }
    )
    assert report.valid is False
    assert "starting_slots" in report.errors
    assert "waiver_system" in report.errors
    assert "waiver_tiebreaker" in report.errors


def test_playoff_settings_boundary_invalid_payload():
    report = validate_playoff_settings_boundary(
        {
            "playoff_qualifiers": 1,
            "playoff_reseed": True,
            "playoff_consolation": True,
            "playoff_tiebreakers": ["wins"],
        }
    )
    assert report.valid is False
    assert report.engine == "pydantic"


def test_playoff_settings_dynamic_rules_invalid_values():
    report = validate_playoff_settings_dynamic_rules(
        {
            "playoff_qualifiers": 7,
            "playoff_tiebreakers": ["wins", "wins", "coin_flip"],
        }
    )
    assert report.valid is False
    assert "playoff_qualifiers" in report.errors
    assert "playoff_tiebreakers" in report.errors


def test_keeper_settings_boundary_invalid_payload():
    report = validate_keeper_settings_boundary(
        {
            "max_keepers": 25,
            "max_years_per_player": 0,
            "cost_inflation": -1,
        }
    )
    assert report.valid is False
    assert report.engine == "pydantic"


def test_keeper_settings_dynamic_rules_invalid_values():
    report = validate_keeper_settings_dynamic_rules(
        {
            "cost_type": "not_supported",
            "deadline_date": datetime(2026, 9, 10),
            "trade_deadline": datetime(2026, 9, 1),
        }
    )
    assert report.valid is False
    assert "cost_type" in report.errors
    assert "deadline_date" in report.errors
