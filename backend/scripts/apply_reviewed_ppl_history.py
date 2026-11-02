"""Apply a hash-bound PPL observation plan only to a new local working clone."""

import argparse
from decimal import Decimal
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from backend.historical_schema_adoption import _data_digest, _digest, _sequence_state
from backend.legacy_schema_bridge import _bootstrap_schema_contract, _schema_snapshot
from backend.scripts.reconcile_ppl_attributes import read_team_taxonomy
from backend.scripts.reconcile_ppl_events import (
    EVENT_GRAIN,
    _amount,
    _bid,
    _total_bid,
    auction_observation_key,
)
from backend.scripts.reconcile_ppl_targets import (
    REVIEWED_SCHEMA_DIGEST,
    TARGET_REVISION,
    approve_target_resolutions,
)

OBSERVATION_REVISION = "0031_historical_observations"
SOURCE = "mfl"
TABLE = "historical_auction_observations"


def exact_storage_bid(value: object) -> Decimal:
    bid = _bid(value)
    whole, _, fraction = bid.partition(".")
    if len(whole) > 12 or len(fraction) > 6:
        raise ValueError(
            "Bid exceeds the exact NUMERIC(18,6) storage contract; no rounding."
        )
    return _amount(bid)


def observation_team(
    attributes: dict[str, Any],
    teams: dict[int, set[str]],
    team_ids: dict[str, set[int]],
) -> tuple[str | None, list[str]]:
    if "source_team_id" in attributes:
        labels = sorted(teams.get(attributes["source_team_id"], set()))
    else:
        label = attributes.get("nfl_team")
        labels = [label] if label in team_ids and len(team_ids[label]) == 1 else []
    if not labels:
        raise ValueError("Reviewed observation has an unsupported/missing team.")
    return (labels[0] if len(labels) == 1 else None), labels


def _archival_values(table: sa.Table, username: str, league_id: int) -> dict[str, Any]:
    values = {column.name: None for column in table.columns if column.name != "id"}
    values.update(
        username=username,
        league_id=league_id,
        is_historical_stub=True,
        is_superuser=False,
        is_commissioner=False,
        future_draft_budget=0,
    )
    return values


def _projected_original_digest(connection, table, player_bindings, created_users):
    hashes = []
    for row in connection.execute(sa.select(table)).mappings():
        values = dict(row)
        if table.name == "users" and values["username"] in created_users:
            expected = _archival_values(table, values["username"], values["league_id"])
            if {key: value for key, value in values.items() if key != "id"} != expected:
                raise ValueError("Created archival account changed; refusing replay.")
            continue
        if table.name == "players" and values["id"] in player_bindings:
            binding = player_bindings[values["id"]]
            if values["mfl_id"] != binding["player_mfl_id"]:
                raise ValueError("Approved canonical player binding changed.")
            values["mfl_id"] = binding["original_mfl_id"]
        hashes.append(bytes.fromhex(_digest(values)))
    return len(hashes), hashlib.sha256(b"".join(sorted(hashes))).hexdigest()


def apply_reviewed_history(
    engine: sa.Engine,
    expected_database: str,
    report: dict[str, Any],
    decisions: dict[str, Any],
    teams_path: Path,
) -> dict[str, Any]:
    url = engine.url
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"localhost", "127.0.0.1"}
        or not expected_database.startswith("ffpi_528_slice7_")
        or url.database != expected_database
        or bool(url.query)
    ):
        raise ValueError(
            "Application requires an explicitly named new loopback slice-7 clone."
        )
    approved = approve_target_resolutions(report, decisions)
    teams_hash, teams, team_ids, _ = read_team_taxonomy(teams_path)
    source_approval = report["approved_event_resolutions"]
    if teams_hash != source_approval["teams_sha256"]:
        raise ValueError("Team taxonomy changed since source approval.")
    review = report["target_mapping_review"]
    league_id = review["target_league_id"]
    resolution = approved["resolution"]
    player_map = {
        row["player_mfl_id"]: row["target_player_id"] for row in resolution["players"]
    }
    events = source_approval["resolution"]["events"]
    if not events:
        raise ValueError("Refusing an empty observation application.")
    event_keys = set()
    team_attribution = {}
    for event in events:
        key = auction_observation_key(
            league_mfl_id=event["league_mfl_id"],
            season=event["season"],
            player_mfl_id=event["player_mfl_id"],
            franchise_id=event["franchise_id"],
            winning_bid=event["winning_bid"],
        )
        if key != event["source_event_key"] or key in event_keys:
            raise ValueError("Approved observation identity changed or repeats.")
        event_keys.add(key)
        exact_storage_bid(event["winning_bid"])
        team_attribution[key] = observation_team(event["attributes"], teams, team_ids)
    plan_hash = _digest(
        {"approved_targets": approved, "source_approval": source_approval}
    )
    bindings = {}
    for row in review["players"]:
        selected = next(
            c
            for c in row["native_corroborated_candidates"]
            if c["target_player_id"] == player_map[row["player_mfl_id"]]
        )
        bindings[selected["target_player_id"]] = {
            "player_mfl_id": row["player_mfl_id"],
            "original_mfl_id": selected["provider_ids"]["mfl_id"],
        }
    created_names = {
        row["proposed_username"]
        for row in resolution["season_franchises"]
        if row["disposition"] == "create_nonlogin_archival"
    }
    with engine.connect().execution_options(
        isolation_level="SERIALIZABLE"
    ) as connection:
        with connection.begin():
            connection.scalar(sa.select(sa.func.set_config("lock_timeout", "5s", True)))
            connection.execute(sa.select(sa.func.pg_advisory_xact_lock(528, 7)))
            if (
                connection.scalar(sa.select(sa.func.current_database()))
                != expected_database
            ):
                raise ValueError(
                    "Connected database does not match the approved clone."
                )
            if str(connection.scalar(sa.select(sa.func.inet_server_addr()))) not in {
                "127.0.0.1",
                "::1",
            }:
                raise ValueError("Application server address is not loopback.")
            if connection.scalar(sa.select(sa.func.current_schema())) != "public":
                raise ValueError("Application requires the public schema.")
            if set(sa.inspect(connection).get_schema_names()) - {
                "information_schema",
                "public",
            }:
                raise ValueError("Unexpected application schemas.")
            metadata = sa.MetaData()
            metadata.reflect(connection, schema="public")
            if "public.alembic_version" not in metadata.tables:
                raise ValueError("Working clone has no Alembic revision table.")
            version = metadata.tables["public.alembic_version"]
            revisions = list(connection.scalars(sa.select(version.c.version_num)))
            first = revisions == [TARGET_REVISION]
            if not first and revisions != [OBSERVATION_REVISION]:
                raise ValueError("Working clone has an unreviewed migration revision.")
            sequence_before = _sequence_state(connection)
            if first:
                schema = _schema_snapshot(connection, "public")
                schema.pop("alembic_version", None)
                if _digest(schema) != REVIEWED_SCHEMA_DIGEST:
                    raise ValueError(
                        "Working clone differs from the reviewed input schema."
                    )
                for name, digest in review["target_table_digests"].items():
                    if list(
                        _data_digest(connection, metadata.tables[f"public.{name}"])
                    ) != list(digest):
                        raise ValueError(f"Working clone baseline changed in {name}.")
                with Operations.context(MigrationContext.configure(connection)):
                    importlib.import_module(
                        "db.migrations.0031_historical_observations"
                    ).upgrade()
                connection.execute(
                    version.update().values(version_num=OBSERVATION_REVISION)
                )
                metadata = sa.MetaData()
                metadata.reflect(connection, schema="public")
            _, expected_schema = _bootstrap_schema_contract(connection)
            actual_schema = _schema_snapshot(connection, "public")
            actual_schema.pop("alembic_version", None)
            if actual_schema != expected_schema:
                raise ValueError(
                    "Working clone does not match the complete bootstrap schema."
                )
            players = metadata.tables["public.players"]
            users = metadata.tables["public.users"]
            observations = metadata.tables[f"public.{TABLE}"]
            if first:
                for target_id, binding in bindings.items():
                    result = connection.execute(
                        players.update()
                        .where(players.c.id == target_id)
                        .values(mfl_id=binding["player_mfl_id"])
                    )
                    if result.rowcount != 1:
                        raise ValueError("Approved target player disappeared.")
            owners = {}
            for entry in resolution["season_franchises"]:
                existing = list(
                    connection.execute(
                        sa.select(users).where(
                            sa.func.lower(users.c.username)
                            == entry["proposed_username"].lower()
                        )
                    ).mappings()
                )
                if first and entry["disposition"] == "create_nonlogin_archival":
                    if existing:
                        raise ValueError(
                            "Archival username collision; no users repurposed."
                        )
                    owner_id = connection.scalar(
                        users.insert()
                        .values(
                            **_archival_values(
                                users, entry["proposed_username"], league_id
                            )
                        )
                        .returning(users.c.id)
                    )
                else:
                    if (
                        len(existing) != 1
                        or existing[0]["league_id"] != league_id
                        or existing[0]["username"] != entry["proposed_username"]
                        or existing[0]["is_historical_stub"] is not True
                        or existing[0]["is_superuser"]
                        or existing[0]["is_commissioner"]
                        or (
                            entry["target_owner_id"] is not None
                            and existing[0]["id"] != entry["target_owner_id"]
                        )
                    ):
                        raise ValueError("Approved archival account identity changed.")
                    owner_id = existing[0]["id"]
                owners[(entry["season"], entry["franchise_id"])] = owner_id
            expected_rows = {}
            for event in events:
                team, labels = team_attribution[event["source_event_key"]]
                values = {
                    "league_id": league_id,
                    "season": event["season"],
                    "owner_id": owners[(event["season"], event["franchise_id"])],
                    "player_id": player_map[event["player_mfl_id"]],
                    "source": SOURCE,
                    "source_event_id": event["source_event_key"],
                    "league_mfl_id": event["league_mfl_id"],
                    "player_mfl_id": event["player_mfl_id"],
                    "franchise_id": event["franchise_id"],
                    "winning_bid": exact_storage_bid(event["winning_bid"]),
                    "position": event["attributes"]["position"],
                    "nfl_team": team,
                    "team_labels": labels,
                    "plan_sha256": plan_hash,
                    "provenance": {
                        "event": event,
                        "event_grain": EVENT_GRAIN,
                        "review_sha256": approved["review_sha256"],
                        "source_event_approval_sha256": approved[
                            "source_event_approval_sha256"
                        ],
                        "target_approval_sha256": _digest(approved),
                        "legacy_source_files_sha256": report[
                            "legacy_source_files_sha256"
                        ],
                        "selected_mfl_exports": report["selected_mfl_exports"],
                        "teams_sha256": teams_hash,
                    },
                }
                expected_rows[event["source_event_key"]] = values
            if first:
                connection.execute(observations.insert(), list(expected_rows.values()))
            actual_rows = list(connection.execute(sa.select(observations)).mappings())
            actual_by_key = {
                row["source_event_id"]: {
                    key: value for key, value in row.items() if key != "id"
                }
                for row in actual_rows
            }
            if len(actual_rows) != len(expected_rows) or actual_by_key != expected_rows:
                raise ValueError(
                    "Persisted observations/provenance differ from the approved plan."
                )
            for name, digest in review["target_table_digests"].items():
                if name == "alembic_version":
                    continue
                preserved = _projected_original_digest(
                    connection,
                    metadata.tables[f"public.{name}"],
                    bindings,
                    created_names,
                )
                if list(preserved) != list(digest):
                    raise ValueError(
                        f"Unapproved original-row mutation in {name}; rolling back."
                    )
            sequence_after = _sequence_state(connection)
            if first:
                if any(
                    sequence_after[name] != state
                    for name, state in sequence_before.items()
                    if name != "users_id_seq"
                ):
                    raise ValueError("An unrelated original sequence changed.")
            elif sequence_after != sequence_before:
                raise ValueError("Idempotent replay changed sequence state.")
            return {
                "database": expected_database,
                "revision": OBSERVATION_REVISION,
                "plan_sha256": plan_hash,
                "observations": len(actual_rows),
                "exact_bid_total": _total_bid(
                    [event["winning_bid"] for event in events]
                ),
                "inserted_observations": len(actual_rows) if first else 0,
                "created_archival_accounts": len(created_names) if first else 0,
                "bound_players": len(bindings) if first else 0,
                "original_tables_verified": len(review["target_table_digests"]) - 1,
                "original_rows_preserved_except_approved_mfl_bindings": True,
                "schema_sha256": _digest(actual_schema),
                "live_roster_transaction_financial_tables_unchanged": True,
                "production_modified": False,
            }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--teams", type=Path, required=True)
    parser.add_argument("--working-copy", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("Verification output already exists; choose a new path.")
        report = json.loads(args.review.read_text(encoding="utf-8"))
        decisions = json.loads(args.approvals.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or not isinstance(decisions, dict):
            raise ValueError("Review and approval manifests must be JSON objects.")
        url = os.environ.get("PPL_TARGET_DATABASE_URL")
        if not url:
            raise ValueError("PPL_TARGET_DATABASE_URL is required.")
        with args.output.open("x", encoding="utf-8") as handle:
            engine = sa.create_engine(url)
            try:
                result = apply_reviewed_history(
                    engine, args.working_copy, report, decisions, args.teams
                )
            finally:
                engine.dispose()
            json.dump(result, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError, RuntimeError, sa.exc.SQLAlchemyError) as error:
        print(
            f"ERROR: reviewed copy application failed ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1
    print(f"Verified copy-only observation application: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
