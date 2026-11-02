import os
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from backend import apply_migrations
from backend.historical_schema_adoption import _data_digest, _digest, _sequence_state
from backend.scripts import apply_reviewed_ppl_history as script
from backend.scripts.reconcile_ppl_attributes import read_team_taxonomy
from backend.scripts.reconcile_ppl_events import auction_observation_key
from backend.scripts.reconcile_ppl_targets import (
    build_target_review,
    capture_target_snapshot,
    target_resolution_proposal,
)


@pytest.mark.parametrize("value", ["0", "1.230000", "999999999999.999999", "0.000001"])
def test_storage_bid_is_exact(value):
    assert script.exact_storage_bid(value) == Decimal(value)


@pytest.mark.parametrize(
    "value", ["-1", "NaN", "Infinity", "0.0000001", "1000000000000"]
)
def test_storage_bid_refuses_rounding_and_overflow(value):
    with pytest.raises(ValueError):
        script.exact_storage_bid(value)


@pytest.mark.parametrize(
    "attributes,expected",
    [
        ({"source_team_id": 1}, ("PHI", ["PHI"])),
        ({"source_team_id": 2}, (None, ["LVR", "OAK"])),
        ({"source_team_id": 3}, (None, ["FA", "FA*"])),
        ({"nfl_team": "FA"}, ("FA", ["FA"])),
    ],
)
def test_observation_team_preserves_approved_alias_sets_and_native_supplements(
    attributes, expected
):
    teams = {1: {"PHI"}, 2: {"LVR", "OAK"}, 3: {"FA", "FA*"}}
    ids = {
        label: {identifier} for identifier, labels in teams.items() for label in labels
    }
    assert script.observation_team(attributes, teams, ids) == expected


@pytest.mark.parametrize(
    "attributes", [{}, {"source_team_id": 999}, {"nfl_team": "UNKNOWN"}]
)
def test_observation_team_rejects_missing_or_unsupported_evidence(attributes):
    with pytest.raises(ValueError):
        script.observation_team(attributes, {}, {})


@pytest.fixture
def observation_copy(monkeypatch, tmp_path):
    url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")
    name = f"ffpi_528_slice7_test_{uuid4().hex}"
    admin = sa.create_engine(url)
    engine = None
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE template0')
        target_url = admin.url.set(database=name)
        monkeypatch.setenv(
            "DATABASE_URL", target_url.render_as_string(hide_password=False)
        )
        command.upgrade(
            apply_migrations._bootstrap_config(apply_migrations.ALEMBIC_CONFIG_PATH),
            "bootstrap_0030",
        )
        command.stamp(
            Config(str(apply_migrations.ALEMBIC_CONFIG_PATH)),
            script.TARGET_REVISION,
            purge=True,
        )
        engine = sa.create_engine(target_url)
        with engine.begin() as c:
            metadata = sa.MetaData()
            metadata.reflect(c, schema="public")
            c.execute(
                metadata.tables["public.leagues"].insert(),
                {"id": 60, "name": name, "current_season": 2026},
            )
            c.execute(
                metadata.tables["public.players"].insert(),
                [
                    {"id": 10, "name": "Brown, AJ", "position": "WR"},
                    {"id": 20, "name": "AJ Brown Jr.", "position": "WR"},
                ],
            )
            c.execute(
                metadata.tables["public.users"].insert(),
                {
                    "username": "unchanged",
                    "league_id": 60,
                    "is_historical_stub": False,
                },
            )
            c.execute(
                metadata.tables["public.player_seasons"].insert(),
                [
                    {
                        "player_id": 10,
                        "season": 2024,
                        "mfl_id": "00123",
                        "position": "WR",
                        "source": "mfl",
                        "is_active": True,
                    },
                    {
                        "player_id": 20,
                        "season": 2025,
                        "mfl_id": "00123",
                        "position": "WR",
                        "source": "mfl",
                        "is_active": True,
                    },
                ],
            )
            c.execute(
                metadata.tables["public.league_mfl_seasons"].insert(),
                [
                    {"league_id": 60, "season": year, "mfl_league_id": "11422"}
                    for year in (2024, 2025)
                ],
            )
        teams_path = tmp_path / "teams.csv"
        teams_path.write_text("Team,TeamID\nPHI,3\n", encoding="ISO-8859-1")
        team_hash, _, _, _ = read_team_taxonomy(teams_path)
        events = []
        for season, bid in [(2024, "5.01"), (2025, "1")]:
            event = {
                "season": season,
                "league_mfl_id": "11422",
                "player_mfl_id": "00123",
                "franchise_id": "0001",
                "winning_bid": bid,
            }
            event["source_event_key"] = auction_observation_key(**event)
            event["attributes"] = {
                "source_team_id": 3,
                "position": "WR",
                "team_basis": "season_catalog_snapshot_not_auction_time",
            }
            event["native_evidence_ref"] = f"native-{season}:2"
            events.append(event)
        report = {
            "approved_event_resolutions": {
                "ready_for_slice_6": True,
                "resolution": {"events": events},
                "teams_sha256": team_hash,
            },
            "legacy_source_files_sha256": {"draft_results.csv": "legacy-hash"},
            "selected_mfl_exports": [
                {"season": year, "report": "players", "sha256": f"catalog-{year}"}
                for year in (2024, 2025)
            ],
        }
        native = {
            year: {
                "players": [
                    {
                        "player_mfl_id": "00123",
                        "player_name": "AJ Brown",
                        "position": "WR",
                    }
                ]
            }
            for year in (2024, 2025)
        }
        report["target_mapping_review"] = build_target_review(
            report, native, capture_target_snapshot(engine, name, 60)
        )
        decisions = {
            "approved": True,
            "review_basis": "Explicit synthetic test-plan approval",
            "review_sha256": _digest(report),
            "resolution": target_resolution_proposal(report["target_mapping_review"]),
        }
        yield engine, name, report, decisions, teams_path
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}"')
        admin.dispose()


def _contents(engine):
    with engine.connect() as c:
        metadata = sa.MetaData()
        metadata.reflect(c, schema="public")
        return (
            {t.name: _data_digest(c, t) for t in metadata.tables.values()},
            _sequence_state(c),
        )


def test_application_preserves_originals_and_reruns_without_sequence_changes(
    observation_copy,
):
    engine, name, report, decisions, teams = observation_copy
    result = script.apply_reviewed_history(engine, name, report, decisions, teams)
    assert result["observations"] == 2
    assert result["exact_bid_total"] == "6.01"
    assert result["created_archival_accounts"] == 2
    assert result["bound_players"] == 1
    before = _contents(engine)
    replay = script.apply_reviewed_history(engine, name, report, decisions, teams)
    assert replay["inserted_observations"] == replay["created_archival_accounts"] == 0
    assert replay["bound_players"] == 0
    assert _contents(engine) == before
    with engine.connect() as c:
        t = sa.Table(script.TABLE, sa.MetaData(), schema="public", autoload_with=c)
        rows = list(c.execute(sa.select(t)).mappings())
        assert {row["player_id"] for row in rows} == {10}
        assert rows[0]["provenance"]["event"]["native_evidence_ref"] == "native-2024:2"
        assert {row["nfl_team"] for row in rows} == {"PHI"}
        for name in (
            "draft_picks",
            "transaction_history",
            "waiver_budgets",
            "draft_budgets",
        ):
            table = sa.Table(name, sa.MetaData(), schema="public", autoload_with=c)
            assert c.scalar(sa.select(sa.func.count()).select_from(table)) == 0


def test_changed_baseline_blocks_before_schema_or_data_changes(observation_copy):
    engine, name, report, decisions, teams = observation_copy
    with engine.begin() as c:
        players = sa.Table("players", sa.MetaData(), schema="public", autoload_with=c)
        c.execute(players.update().where(players.c.id == 20).values(name="Changed"))
    before = _contents(engine)
    with pytest.raises(ValueError, match="baseline changed"):
        script.apply_reviewed_history(engine, name, report, decisions, teams)
    assert _contents(engine) == before


@pytest.mark.parametrize(
    "mutation", ["provenance", "player_binding", "archival_privilege", "extra_event"]
)
def test_conflicting_replay_refuses_without_further_mutation(
    observation_copy, mutation
):
    engine, name, report, decisions, teams = observation_copy
    script.apply_reviewed_history(engine, name, report, decisions, teams)
    with engine.begin() as c:
        metadata = sa.MetaData()
        metadata.reflect(c, schema="public")
        if mutation == "provenance":
            t = metadata.tables["public." + script.TABLE]
            c.execute(t.update().values(provenance={"changed": True}))
        elif mutation == "player_binding":
            t = metadata.tables["public.players"]
            c.execute(t.update().where(t.c.id == 10).values(mfl_id="00456"))
        elif mutation == "archival_privilege":
            t = metadata.tables["public.users"]
            c.execute(
                t.update()
                .where(t.c.is_historical_stub.is_(True))
                .values(is_commissioner=True)
            )
        else:
            t = metadata.tables["public." + script.TABLE]
            row = dict(c.execute(sa.select(t)).mappings().first())
            row.pop("id")
            row["source_event_id"] = "unapproved"
            c.execute(t.insert().values(**row))
    before = _contents(engine)
    with pytest.raises(ValueError):
        script.apply_reviewed_history(engine, name, report, decisions, teams)
    assert _contents(engine) == before


def test_late_verification_failure_rolls_back_observations_accounts_bindings_and_schema(
    observation_copy, monkeypatch
):
    engine, name, report, decisions, teams = observation_copy
    before = _contents(engine)
    original = script._projected_original_digest

    def fail_users(connection, table, bindings, created):
        if table.name == "users":
            return (0, "deliberately-invalid")
        return original(connection, table, bindings, created)

    monkeypatch.setattr(script, "_projected_original_digest", fail_users)
    with pytest.raises(ValueError, match="Unapproved original-row mutation"):
        script.apply_reviewed_history(engine, name, report, decisions, teams)
    # PostgreSQL sequences are not transactional, but original rows/schema are.
    assert _contents(engine)[0] == before[0]
    with engine.connect() as c:
        assert script.TABLE not in sa.inspect(c).get_table_names(schema="public")


def test_changed_target_approval_is_rejected_before_connection(observation_copy):
    engine, name, report, decisions, teams = observation_copy
    decisions = deepcopy(decisions)
    decisions["resolution"]["players"][0]["target_player_id"] = 20
    before = _contents(engine)
    with pytest.raises(ValueError, match="exact reviewed plan"):
        script.apply_reviewed_history(engine, name, report, decisions, teams)
    assert _contents(engine) == before


@pytest.mark.parametrize(
    "url,name",
    [
        ("sqlite://", "ffpi_528_slice7_test"),
        ("postgresql://localhost/fantasy_football", "fantasy_football"),
        ("postgresql://remote/ffpi_528_slice7_test", "ffpi_528_slice7_test"),
        ("postgresql://localhost/ffpi_528_slice6_test", "ffpi_528_slice6_test"),
        (
            "postgresql://localhost/ffpi_528_slice7_test?host=remote",
            "ffpi_528_slice7_test",
        ),
        (
            "postgresql://localhost/ffpi_528_slice7_test?hostaddr=192.0.2.1",
            "ffpi_528_slice7_test",
        ),
    ],
)
def test_application_guards_originals_remote_and_prior_copies_before_connecting(
    url, name, tmp_path
):
    engine = sa.create_engine(url)
    try:
        with pytest.raises(ValueError, match="new loopback slice-7"):
            script.apply_reviewed_history(engine, name, {}, {}, tmp_path / "teams.csv")
    finally:
        engine.dispose()


@pytest.mark.parametrize("output_state", ["existing", "missing_parent"])
def test_cli_reserves_writable_exclusive_report_before_database_work(
    tmp_path, monkeypatch, output_state
):
    review = tmp_path / "review.json"
    approvals = tmp_path / "approvals.json"
    review.write_text("{}", encoding="utf-8")
    approvals.write_text("{}", encoding="utf-8")
    output = tmp_path / "report.json"
    if output_state == "existing":
        output.write_text("preserve", encoding="utf-8")
    else:
        output = tmp_path / "absent" / "report.json"
    monkeypatch.setenv("PPL_TARGET_DATABASE_URL", "sqlite://")

    def unexpected_connection(*args, **kwargs):
        pytest.fail(
            "Database work must not start without exclusive writable evidence output."
        )

    monkeypatch.setattr(script.sa, "create_engine", unexpected_connection)
    assert (
        script.main(
            [
                "--review",
                str(review),
                "--approvals",
                str(approvals),
                "--teams",
                str(tmp_path / "teams.csv"),
                "--working-copy",
                "ffpi_528_slice7_test",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    if output_state == "existing":
        assert output.read_text(encoding="utf-8") == "preserve"
