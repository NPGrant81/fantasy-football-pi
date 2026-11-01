from copy import deepcopy

import pytest

from backend.scripts.reconcile_ppl_history import (
    _amount,
    _integer,
    _read_sources,
    reconcile_rows,
    run_reconciliation,
)


@pytest.fixture
def reconciliation_data():
    return {
        "sources": {
            "users.csv": [{"OwnerID": "1", "OwnerName": "Archive Owner"}],
            "players.csv": [
                {"Player_ID": "10", "PlayerName": "Brown, AJ", "PositionID": "2"}
            ],
            "positions.csv": [{"PositionID": "2", "Position": "WR"}],
            "draft_results.csv": [
                {
                    "Year": "2020",
                    "OwnerID": "1",
                    "PlayerID": "10",
                    "WinningBid": "$5.00",
                    "PositionID": "2",
                    "TeamID": "3",
                }
            ],
        },
        "staging_picks": [
            {
                "year": 2020,
                "owner_id": 1,
                "player_id": 10,
                "amount": 5,
                "position_id": 2,
                "team_id": 3,
            }
        ],
        "staging_players": [
            {"Player_ID": 10, "PlayerName": "Brown, AJ", "PositionID": 2}
        ],
        "staging_users": [{"id": 1, "username": "Archive Owner"}],
        "target_players": [{"id": 99, "name": "AJ Brown", "position": "WR"}],
        "target_users": [{"id": 7, "username": "Archive Owner", "team_name": None}],
    }


def test_reconciliation_names_are_only_candidates_and_inputs_unchanged(
    reconciliation_data,
):
    before = deepcopy(reconciliation_data)
    report = reconcile_rows(**reconciliation_data)
    assert report["ready_to_import"] is False
    assert report["writes_performed"] is False
    assert report["player_candidates"][0]["candidate_target_ids"] == [99]
    assert report["season_owner_candidates"][0]["candidate_target_ids"] == [7]
    assert report["season_owner_candidates"][0]["status"] == "review_required"
    assert not report["provenance_blockers"]
    assert reconciliation_data == before
    assert "Archive Owner" not in str(report)


def test_reconciliation_does_not_copy_overlapping_ids(reconciliation_data):
    reconciliation_data["target_players"] = [
        {"id": 10, "name": "Different", "position": "WR"}
    ]
    reconciliation_data["target_users"] = [
        {"id": 1, "username": "Different", "team_name": None}
    ]
    report = reconcile_rows(**reconciliation_data)
    assert report["player_candidates"][0]["status"] == "unmapped"
    assert report["season_owner_candidates"][0]["status"] == "unmapped"


def test_reconciliation_preserves_ambiguity_and_per_season_owners(reconciliation_data):
    reconciliation_data["target_users"].append(
        {"id": 8, "username": "other", "team_name": "Archive Owner"}
    )
    reconciliation_data["sources"]["draft_results.csv"].append(
        {
            "Year": "2021",
            "OwnerID": "1",
            "PlayerID": "10",
            "WinningBid": "6",
            "PositionID": "2",
            "TeamID": "3",
        }
    )
    report = reconcile_rows(**reconciliation_data)
    assert len(report["season_owner_candidates"]) == 2
    assert all(
        row["status"] == "ambiguous" for row in report["season_owner_candidates"]
    )
    assert report["csv_rows_missing_from_staging"] == [
        {
            "season": 2021,
            "source_owner_id": 1,
            "source_player_id": 10,
            "amount": "6",
            "source_position_id": "2",
            "source_team_id": "3",
            "rows": 1,
        }
    ]


def test_reconciliation_detects_provenance_conflicts(reconciliation_data):
    reconciliation_data["staging_players"][0]["PlayerName"] = "Other Player"
    reconciliation_data["staging_users"][0]["username"] = "Other Owner"
    report = reconcile_rows(**reconciliation_data)
    assert len(report["provenance_blockers"]) == 2
    assert report["player_candidates"][0]["candidate_target_ids"] == []
    assert report["season_owner_candidates"][0]["candidate_target_ids"] == []


def test_reconciliation_uses_multiset_and_exact_amounts(reconciliation_data):
    reconciliation_data["sources"]["draft_results.csv"] *= 2
    reconciliation_data["staging_picks"][0]["amount"] = "5.01"
    report = reconcile_rows(**reconciliation_data)
    assert report["duplicate_csv_rows"] == 1
    assert report["csv_rows_missing_from_staging"][0]["rows"] == 2
    assert report["staging_rows_not_in_csv"][0]["amount"] == "5.01"


@pytest.mark.parametrize("column", ["position_id", "team_id"])
def test_reconciliation_compares_draft_attributes(reconciliation_data, column):
    reconciliation_data["staging_picks"][0][column] = 9
    report = reconcile_rows(**reconciliation_data)
    assert report["csv_rows_missing_from_staging"][0]["rows"] == 1
    assert report["staging_rows_not_in_csv"][0][f"source_{column}"] == "9"


def test_missing_draft_attributes_are_not_guessed(reconciliation_data):
    reconciliation_data["sources"]["draft_results.csv"][0]["TeamID"] = "#N/A"
    reconciliation_data["staging_picks"][0]["team_id"] = None
    report = reconcile_rows(**reconciliation_data)
    assert report["csv_rows_missing_from_staging"][0]["source_team_id"] == "#N/A"
    assert report["staging_rows_not_in_csv"][0]["source_team_id"] is None
    assert len(report["provenance_blockers"]) == 2
    assert all(
        row["attributes"] == ["team_id"] for row in report["provenance_blockers"]
    )


def test_mapping_template_does_not_approve_candidate_identities(reconciliation_data):
    report = reconcile_rows(**reconciliation_data)
    template = report["mapping_review_template"]
    assert template["approved"] is False
    assert template["players"] == [
        {"source_player_id": 10, "target_player_id": None, "evidence": []}
    ]
    assert template["season_owners"] == [
        {"season": 2020, "source_owner_id": 1, "target_owner_id": None, "evidence": []}
    ]


def test_cli_preserves_existing_report(tmp_path, monkeypatch):
    from backend.scripts import reconcile_ppl_history as script

    output = tmp_path / "reviewed.json"
    output.write_text("reviewed", encoding="utf-8")
    monkeypatch.setenv("PPL_TARGET_DATABASE_URL", "postgresql://localhost/ffpi_528_app")
    monkeypatch.setenv(
        "PPL_STAGING_DATABASE_URL", "postgresql://localhost/ffpi_528_etl"
    )

    def unexpected_call(**kwargs):
        pytest.fail("An existing report must be rejected before reading databases.")

    monkeypatch.setattr(script, "run_reconciliation", unexpected_call)
    with pytest.raises(SystemExit):
        script.main(
            [
                "--source-root",
                str(tmp_path),
                "--target-league-id",
                "60",
                "--output",
                str(output),
            ]
        )
    assert output.read_text(encoding="utf-8") == "reviewed"


def test_cli_redacts_database_errors(tmp_path, monkeypatch, capsys):
    import sqlalchemy as sa
    from backend.scripts import reconcile_ppl_history as script

    monkeypatch.setenv("PPL_TARGET_DATABASE_URL", "postgresql://localhost/ffpi_528_app")
    monkeypatch.setenv(
        "PPL_STAGING_DATABASE_URL", "postgresql://localhost/ffpi_528_etl"
    )

    def fail(**kwargs):
        raise sa.exc.OperationalError(
            "SELECT private_value", {}, Exception("password=private-secret")
        )

    monkeypatch.setattr(script, "run_reconciliation", fail)
    output = tmp_path / "report.json"
    assert (
        script.main(
            [
                "--source-root",
                str(tmp_path),
                "--target-league-id",
                "60",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "database connection or schema inspection failed" in captured.err
    assert "private" not in captured.err
    assert not output.exists()


def test_cli_persists_blocked_report(tmp_path, monkeypatch, reconciliation_data):
    import json
    from backend.scripts import reconcile_ppl_history as script

    monkeypatch.setenv("PPL_TARGET_DATABASE_URL", "postgresql://localhost/ffpi_528_app")
    monkeypatch.setenv(
        "PPL_STAGING_DATABASE_URL", "postgresql://localhost/ffpi_528_etl"
    )
    report = reconcile_rows(**reconciliation_data)
    monkeypatch.setattr(script, "run_reconciliation", lambda **kwargs: report)
    output = tmp_path / "report.json"
    assert (
        script.main(
            [
                "--source-root",
                str(tmp_path),
                "--target-league-id",
                "60",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_conflicting_source_ids_cannot_be_restored_by_later_duplicate(
    reconciliation_data,
):
    original = reconciliation_data["sources"]["players.csv"][0]
    conflicting = {**original, "PlayerName": "Different Player"}
    reconciliation_data["sources"]["players.csv"].extend([conflicting, original])
    report = reconcile_rows(**reconciliation_data)
    assert report["conflicting_source_ids"]["csv_players"] == [10]
    assert report["player_candidates"][0]["status"] == "unmapped"
    assert report["player_candidates"][0]["candidate_target_ids"] == []


def test_missing_position_is_an_explicit_provenance_blocker(reconciliation_data):
    reconciliation_data["sources"]["players.csv"][0]["PositionID"] = ""
    report = reconcile_rows(**reconciliation_data)
    assert report["player_candidates"][0]["csv_staging_identity_verified"] is False
    assert report["provenance_blockers"] == [
        {"kind": "unverified_player_provenance", "source_player_id": 10}
    ]


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_names_never_verify_identity(reconciliation_data, name):
    reconciliation_data["sources"]["players.csv"][0]["PlayerName"] = name
    reconciliation_data["staging_players"][0]["PlayerName"] = None
    reconciliation_data["sources"]["users.csv"][0]["OwnerName"] = name
    reconciliation_data["staging_users"][0]["username"] = ""
    report = reconcile_rows(**reconciliation_data)
    assert len(report["provenance_blockers"]) == 2
    assert report["player_candidates"][0]["csv_staging_identity_verified"] is False
    assert (
        report["season_owner_candidates"][0]["csv_staging_identity_verified"] is False
    )


@pytest.mark.parametrize("parameter", ["dbname", "database", "service", "servicefile"])
@pytest.mark.parametrize("side", ["target_url", "staging_url"])
def test_database_overrides_are_rejected_before_engine_creation(
    reconciliation_data, tmp_path, monkeypatch, parameter, side
):
    import sqlalchemy as sa
    from backend.scripts import reconcile_ppl_history as script

    monkeypatch.setattr(
        script, "_read_sources", lambda root: (reconciliation_data["sources"], {})
    )

    def unexpected_engine(*args, **kwargs):
        pytest.fail("Connection overrides must be rejected before engine creation.")

    monkeypatch.setattr(sa, "create_engine", unexpected_engine)
    urls = {
        "target_url": "postgresql://localhost/ffpi_528_app",
        "staging_url": "postgresql://localhost/ffpi_528_etl",
    }
    urls[side] += f"?{parameter}=fantasy_football"
    with pytest.raises(ValueError, match="overrides"):
        script.run_reconciliation(source_root=tmp_path, league_id=60, **urls)


def test_missing_affected_tables_are_not_inspected():
    from unittest.mock import Mock
    import sqlalchemy as sa
    from backend.scripts.reconcile_ppl_history import _affected_unique_drift

    inspector = Mock(spec=sa.Inspector)
    drift = _affected_unique_drift(inspector, sa.MetaData(), set())
    assert drift["waiver_budgets"] == {"missing_table": True}
    assert drift["transaction_history"] == {"missing_table": True}
    inspector.get_unique_constraints.assert_not_called()
    inspector.get_indexes.assert_not_called()
    inspector.get_columns.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"postgresql_where": "is_historical_stub = false"},
        {"postgresql_nulls_not_distinct": True},
    ],
)
def test_unique_contract_detects_partial_and_null_semantics(options):
    import sqlalchemy as sa
    from backend.scripts.reconcile_ppl_history import _unique_drift

    table = sa.Table(
        "users", sa.MetaData(), sa.Column("username", sa.String, unique=True)
    )
    observed = [
        {"unique": True, "column_names": ["username"], "dialect_options": options}
    ]
    drift = _unique_drift(table, [], observed)
    assert drift["missing_orm_unique_keys"] == [["username"]]
    assert drift["extra_observed_unique_keys"] == [["username"]]
    assert len(drift["extra_observed_unique_contracts"]) == 1


def test_unique_contract_detects_expression_changes_and_deduplicates_backing_index():
    import sqlalchemy as sa
    from backend.scripts.reconcile_ppl_history import _unique_drift

    table = sa.Table("users", sa.MetaData(), sa.Column("username", sa.String))
    sa.Index("uq_lower_username", sa.func.lower(table.c.username), unique=True)
    observed = [
        {
            "unique": True,
            "column_names": [None],
            "expressions": ["upper(username)"],
            "dialect_options": {},
        }
    ]
    drift = _unique_drift(table, [], observed)
    assert drift["missing_orm_unique_contracts"][0]["terms"] == [
        {"expression": "lower(username)"}
    ]
    assert drift["extra_observed_unique_contracts"][0]["terms"] == [
        {"expression": "upper(username)"}
    ]
    plain = sa.Table("plain", sa.MetaData(), sa.Column("id", sa.Integer, unique=True))
    assert _unique_drift(
        plain,
        [{"column_names": ["id"]}],
        [{"unique": True, "column_names": ["id"]}],
    ) == {
        "missing_orm_unique_contracts": [],
        "extra_observed_unique_contracts": [],
        "missing_orm_unique_keys": [],
        "extra_observed_unique_keys": [],
    }


def test_retained_csv_sources_have_hashes_and_strict_headers(tmp_path):
    (tmp_path / "users.csv").write_text(
        "OwnerID,WrongHeader\n1,owner\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="missing required columns"):
        _read_sources(tmp_path)


def test_source_hashes_cover_exact_parsed_bytes(tmp_path, reconciliation_data):
    import csv
    import hashlib
    import io

    for name, rows in reconciliation_data["sources"].items():
        handle = io.StringIO(newline="")
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        (tmp_path / name).write_bytes(handle.getvalue().encode("ISO-8859-1"))
    sources, hashes = _read_sources(tmp_path)
    assert sources == reconciliation_data["sources"]
    assert hashes == {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in sources
    }
    with pytest.raises(ValueError, match="distinct working copies"):
        run_reconciliation(
            source_root=tmp_path,
            target_url="postgresql://localhost/ffpi_528_same",
            staging_url="postgresql+psycopg2://other@localhost/ffpi_528_same",
            league_id=60,
        )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/fantasy_football",
        "sqlite:///test.db",
    ],
)
def test_reconciliation_refuses_original_database_before_connecting(
    tmp_path, reconciliation_data, url
):
    import csv

    for name, rows in reconciliation_data["sources"].items():
        with (tmp_path / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    with pytest.raises(ValueError, match="working copies"):
        run_reconciliation(
            source_root=tmp_path,
            target_url=url,
            staging_url="postgresql://localhost/ffpi_528_etl",
            league_id=60,
        )


@pytest.mark.parametrize("value", ["1.5", "NaN", "Infinity", "0", "-1", ""])
def test_reconciliation_rejects_invalid_identifiers(value):
    with pytest.raises(ValueError):
        _integer(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", ""])
def test_reconciliation_rejects_invalid_amounts(value):
    with pytest.raises(ValueError):
        _amount(value)
