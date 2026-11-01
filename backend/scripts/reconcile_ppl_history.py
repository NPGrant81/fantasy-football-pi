"""Read-only reconciliation of retained PPL CSVs and restored database copies."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from typing import Any
import csv

import sqlalchemy as sa
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.dialects import postgresql

from backend.services.player_service import normalize_display_name

REQUIRED_HEADERS = {
    "users.csv": {"OwnerID", "OwnerName"},
    "players.csv": {"Player_ID", "PlayerName", "PositionID"},
    "positions.csv": {"PositionID", "Position"},
    "draft_results.csv": {
        "PlayerID",
        "OwnerID",
        "Year",
        "WinningBid",
        "PositionID",
        "TeamID",
    },
}


def _integer(value: object) -> int:
    try:
        number = Decimal(str(value).strip())
        if (
            not number.is_finite()
            or number != number.to_integral_value()
            or number <= 0
        ):
            raise ValueError("Expected a positive integral identifier or season.")
        return int(number)
    except InvalidOperation as error:
        raise ValueError(
            "Expected a positive integral identifier or season."
        ) from error


def _amount(value: object) -> Decimal:
    try:
        amount = Decimal(str(value).replace("$", "").replace(",", "").strip())
        if not amount.is_finite() or amount < 0:
            raise ValueError("Expected a finite nonnegative bid.")
        return amount
    except InvalidOperation as error:
        raise ValueError("Expected a finite nonnegative bid.") from error


def _label(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _position(value: object) -> str:
    position = str(value or "").strip().upper()
    return {"DEF": "DST", "D/ST": "DST", "PK": "K"}.get(position, position)


def _position_id(value: object) -> int | None:
    try:
        return _integer(value)
    except ValueError:
        # Missing/invalid positions produce provenance blockers, never a guessed position.
        return None


def _draft_attribute(value: object) -> str:
    if value is None or not str(value).strip():
        return ""
    identifier = _position_id(value)
    return str(identifier) if identifier is not None else str(value).strip()


def _read_sources(root: Path) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    sources = {}
    digests = {}
    for name, required in REQUIRED_HEADERS.items():
        path = root / name
        raw = path.read_bytes()
        digests[name] = hashlib.sha256(raw).hexdigest()
        # These retained bootstrap CSVs were exported with ISO-8859-1.
        with io.StringIO(raw.decode("ISO-8859-1"), newline="") as handle:
            reader = csv.DictReader(handle)
            if not required <= set(reader.fieldnames or ()):
                raise ValueError(f"{name} is missing required columns.")
            rows = []
            for line, row in enumerate(reader, start=2):
                if None in row or any(row.get(column) is None for column in required):
                    raise ValueError(f"{name}:{line} has a malformed CSV row.")
                rows.append(dict(row))
            sources[name] = rows
    return sources, digests


def _index(
    rows: list[dict[str, Any]], identifier: str
) -> dict[int, dict[str, Any] | None]:
    result: dict[int, dict[str, Any] | None] = {}
    for row in rows:
        key = _integer(row[identifier])
        if key in result and result[key] != row:
            result[key] = None
        else:
            result[key] = row
    return result


def reconcile_rows(
    *,
    sources: dict[str, list[dict[str, Any]]],
    staging_picks: list[dict[str, Any]],
    staging_players: list[dict[str, Any]],
    staging_users: list[dict[str, Any]],
    target_players: list[dict[str, Any]],
    target_users: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return candidate identities, never infer approval from names or IDs."""
    source_players = _index(sources["players.csv"], "Player_ID")
    source_users = _index(sources["users.csv"], "OwnerID")
    positions = _index(sources["positions.csv"], "PositionID")
    players = _index(staging_players, "Player_ID")
    users = _index(staging_users, "id")

    csv_picks = Counter(
        (
            _integer(row["Year"]),
            _integer(row["OwnerID"]),
            _integer(row["PlayerID"]),
            _amount(row["WinningBid"]),
            _draft_attribute(row["PositionID"]),
            _draft_attribute(row["TeamID"]),
        )
        for row in sources["draft_results.csv"]
    )
    staged = Counter(
        (
            _integer(row["year"]),
            _integer(row["owner_id"]),
            _integer(row["player_id"]),
            _amount(row["amount"]),
            _draft_attribute(row["position_id"]),
            _draft_attribute(row["team_id"]),
        )
        for row in staging_picks
    )
    missing = csv_picks - staged
    unexpected = staged - csv_picks
    all_keys = set(csv_picks) | set(staged)
    owner_seasons = sorted({(key[0], key[1]) for key in all_keys})
    player_ids = sorted({key[2] for key in all_keys})
    blockers = []
    for source, picks in (("csv", csv_picks), ("staging", staged)):
        for key, count in sorted(picks.items()):
            invalid = [
                column
                for column, value in zip(("position_id", "team_id"), key[4:])
                if _position_id(value) is None
            ]
            if invalid:
                blockers.append(
                    {
                        "kind": "incomplete_draft_attributes",
                        "source": source,
                        "season": key[0],
                        "source_owner_id": key[1],
                        "source_player_id": key[2],
                        "attributes": invalid,
                        "rows": count,
                    }
                )

    target_by_name: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in target_players:
        key = (_label(normalize_display_name(row["name"])), _position(row["position"]))
        if all(key):
            target_by_name[key].add(_integer(row["id"]))
    target_owner_labels: dict[str, set[int]] = defaultdict(set)
    for row in target_users:
        for column in ("username", "team_name"):
            label = _label(row.get(column))
            if label:
                target_owner_labels[label].add(_integer(row["id"]))

    player_report = []
    for identifier in player_ids:
        archived = source_players.get(identifier)
        staged_player = players.get(identifier)
        verified = bool(
            archived
            and staged_player
            and _label(archived["PlayerName"])
            and _label(archived["PlayerName"]) == _label(staged_player["PlayerName"])
            and _position_id(archived["PositionID"]) is not None
            and _position_id(archived["PositionID"])
            == _position_id(staged_player["PositionID"])
        )
        position_id = _position_id(archived["PositionID"]) if archived else None
        position_row = positions.get(position_id) if position_id is not None else None
        candidates = []
        if verified and position_row:
            key = (
                _label(normalize_display_name(archived["PlayerName"])),
                _position(position_row["Position"]),
            )
            candidates = sorted(target_by_name.get(key, set()))
        if not verified or not position_row:
            blockers.append(
                {"kind": "unverified_player_provenance", "source_player_id": identifier}
            )
        player_report.append(
            {
                "source_player_id": identifier,
                "csv_staging_identity_verified": verified,
                "candidate_target_ids": candidates,
                "status": (
                    "review_required"
                    if len(candidates) == 1
                    else ("ambiguous" if candidates else "unmapped")
                ),
            }
        )

    owner_report = []
    for season, identifier in owner_seasons:
        archived = source_users.get(identifier)
        staged_user = users.get(identifier)
        verified = bool(
            archived
            and staged_user
            and _label(archived["OwnerName"])
            and _label(archived["OwnerName"]) == _label(staged_user["username"])
        )
        candidates = (
            sorted(target_owner_labels.get(_label(archived["OwnerName"]), set()))
            if verified
            else []
        )
        if not verified:
            blockers.append(
                {
                    "kind": "unverified_owner_provenance",
                    "season": season,
                    "source_owner_id": identifier,
                }
            )
        owner_report.append(
            {
                "season": season,
                "source_owner_id": identifier,
                "csv_staging_identity_verified": verified,
                "candidate_target_ids": candidates,
                "status": (
                    "review_required"
                    if len(candidates) == 1
                    else ("ambiguous" if candidates else "unmapped")
                ),
            }
        )

    def differences(counter: Counter) -> list[dict[str, Any]]:
        return [
            {
                "season": key[0],
                "source_owner_id": key[1],
                "source_player_id": key[2],
                "amount": str(key[3]),
                "source_position_id": key[4] or None,
                "source_team_id": key[5] or None,
                "rows": count,
            }
            for key, count in sorted(counter.items())
        ]

    years = sorted({key[0] for key in all_keys})
    return {
        "writes_performed": False,
        "ready_to_import": False,
        "approval_required": [
            "observed target schema adoption",
            "explicit season-owner and canonical-player mappings",
            "CSV/staging differences and source event identity",
        ],
        "mapping_review_template": {
            "approved": False,
            "players": [
                {
                    "source_player_id": row["source_player_id"],
                    "target_player_id": None,
                    "evidence": [],
                }
                for row in player_report
            ],
            "season_owners": [
                {
                    "season": row["season"],
                    "source_owner_id": row["source_owner_id"],
                    "target_owner_id": None,
                    "evidence": [],
                }
                for row in owner_report
            ],
        },
        "season_totals": [
            {
                "season": year,
                "csv_rows": sum(
                    count for key, count in csv_picks.items() if key[0] == year
                ),
                "staging_rows": sum(
                    count for key, count in staged.items() if key[0] == year
                ),
            }
            for year in years
        ],
        "csv_rows_missing_from_staging": differences(missing),
        "staging_rows_not_in_csv": differences(unexpected),
        "duplicate_csv_rows": sum(count - 1 for count in csv_picks.values()),
        "duplicate_staging_rows": sum(count - 1 for count in staged.values()),
        "player_candidates": player_report,
        "season_owner_candidates": owner_report,
        "provenance_blockers": blockers,
        "conflicting_source_ids": {
            name: sorted(key for key, row in index.items() if row is None)
            for name, index in (
                ("csv_players", source_players),
                ("csv_owners", source_users),
                ("csv_positions", positions),
                ("staging_players", players),
                ("staging_owners", users),
            )
        },
    }


def _rows(
    connection: Connection, name: str, columns: list[str]
) -> list[dict[str, Any]]:
    table = sa.Table(name, sa.MetaData(), schema="public", autoload_with=connection)
    return [
        dict(row)
        for row in connection.execute(
            sa.select(*(table.c[column] for column in columns))
        ).mappings()
    ]


def _unique_drift(
    expected: sa.Table,
    constraints: list[dict[str, Any]],
    indexes: list[dict[str, Any]],
) -> dict[str, Any]:
    def sql(expression: Any) -> str | None:
        if expression is None:
            return None
        if isinstance(expression, str):
            return expression.strip()
        return str(
            expression.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True, "include_table": False},
            )
        ).strip()

    def contract(
        terms: list[dict[str, str]], predicate: str | None, nulls: bool
    ) -> str:
        return json.dumps(
            {
                "terms": terms,
                "predicate": predicate,
                "nulls_not_distinct": nulls,
            },
            sort_keys=True,
        )

    expected_contracts = set()
    for item in (
        *[c for c in expected.constraints if isinstance(c, sa.UniqueConstraint)],
        *[i for i in expected.indexes if i.unique],
    ):
        expressions = item.expressions if isinstance(item, sa.Index) else item.columns
        terms = [
            (
                {"column": expression.name}
                if isinstance(expression, sa.Column)
                else {"expression": sql(expression)}
            )
            for expression in expressions
        ]
        options = item.dialect_options["postgresql"]
        expected_contracts.add(
            contract(
                terms,
                sql(options.get("where")),
                bool(options.get("nulls_not_distinct")),
            )
        )
    actual_contracts = set()
    for item in (*constraints, *[i for i in indexes if i["unique"]]):
        expressions = item.get("expressions", [])
        terms = [
            (
                {"column": column}
                if column is not None
                else {"expression": expressions[index]}
            )
            for index, column in enumerate(item["column_names"])
        ]
        options = item.get("dialect_options", {})
        actual_contracts.add(
            contract(
                terms,
                sql(options.get("postgresql_where")),
                bool(options.get("postgresql_nulls_not_distinct")),
            )
        )
    missing = [
        json.loads(value) for value in sorted(expected_contracts - actual_contracts)
    ]
    extra = [
        json.loads(value) for value in sorted(actual_contracts - expected_contracts)
    ]
    return {
        "missing_orm_unique_contracts": missing,
        "extra_observed_unique_contracts": extra,
        "missing_orm_unique_keys": [
            [term.get("column") for term in value["terms"]] for value in missing
        ],
        "extra_observed_unique_keys": [
            [term.get("column") for term in value["terms"]] for value in extra
        ],
    }


def _affected_unique_drift(
    observed: sa.Inspector, metadata: sa.MetaData, table_names: set[str]
) -> dict[str, Any]:
    result = {}
    for table_name in (
        "draft_picks",
        "waiver_budgets",
        "players",
        "transaction_history",
        "users",
    ):
        if table_name not in table_names:
            result[table_name] = {"missing_table": True}
            continue
        expected = metadata.tables[table_name]
        result[table_name] = {
            **_unique_drift(
                expected,
                observed.get_unique_constraints(table_name, schema="public"),
                observed.get_indexes(table_name, schema="public"),
            ),
            "observed_only_columns": sorted(
                {
                    column["name"]
                    for column in observed.get_columns(table_name, schema="public")
                }
                - set(expected.columns.keys())
            ),
        }
    return result


def run_reconciliation(
    *, source_root: Path, target_url: str, staging_url: str, league_id: int
) -> dict[str, Any]:
    from backend.legacy_schema_bridge import _schema_snapshot
    from backend import models
    from backend.apply_migrations import ALEMBIC_CONFIG_PATH, _known_revisions
    from alembic.config import Config

    sources, digests = _read_sources(source_root)
    target = make_url(target_url)
    staging = make_url(staging_url)
    for url in (target, staging):
        if {"dbname", "database", "service", "servicefile"} & {
            key.casefold() for key in url.query
        }:
            raise ValueError("Database-name and service overrides are not permitted.")
        if url.get_backend_name() != "postgresql" or not (
            url.database or ""
        ).startswith("ffpi_528_"):
            raise ValueError(
                "Reconciliation requires explicitly named ffpi_528_ working copies."
            )
    if target.database == staging.database:
        raise ValueError("Target and staging must be distinct working copies.")
    target_engine = sa.create_engine(target)
    staging_engine = sa.create_engine(staging)
    try:
        with target_engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as app:
            with staging_engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as etl:
                with app.begin(), etl.begin():
                    app.exec_driver_sql("SET TRANSACTION READ ONLY")
                    etl.exec_driver_sql("SET TRANSACTION READ ONLY")
                    leagues = sa.Table(
                        "leagues", sa.MetaData(), schema="public", autoload_with=app
                    )
                    if (
                        app.scalar(
                            sa.select(leagues.c.id).where(leagues.c.id == league_id)
                        )
                        is None
                    ):
                        raise ValueError("Target league does not exist.")
                    users = sa.Table(
                        "users", sa.MetaData(), schema="public", autoload_with=app
                    )
                    target_users = [
                        dict(row)
                        for row in app.execute(
                            sa.select(
                                users.c.id, users.c.username, users.c.team_name
                            ).where(users.c.league_id == league_id)
                        ).mappings()
                    ]
                    report = reconcile_rows(
                        sources=sources,
                        staging_picks=_rows(
                            etl,
                            "draft_picks",
                            [
                                "player_id",
                                "owner_id",
                                "year",
                                "amount",
                                "position_id",
                                "team_id",
                            ],
                        ),
                        staging_players=_rows(
                            etl, "players", ["Player_ID", "PlayerName", "PositionID"]
                        ),
                        staging_users=_rows(etl, "users", ["id", "username"]),
                        target_players=_rows(
                            app, "players", ["id", "name", "position"]
                        ),
                        target_users=target_users,
                    )
                    snapshot = _schema_snapshot(app, "public")
                    revisions = _rows(app, "alembic_version", ["version_num"])
                    known_revisions = _known_revisions(Config(str(ALEMBIC_CONFIG_PATH)))
                    observed = sa.inspect(app)
                    table_names = set(observed.get_table_names(schema="public"))
                    missing_tables = sorted(
                        set(models.Base.metadata.tables) - table_names
                    )
                    missing_columns = sorted(
                        f"{table_name}.{column}"
                        for table_name in set(models.Base.metadata.tables) & table_names
                        for column in (
                            set(models.Base.metadata.tables[table_name].columns.keys())
                            - {
                                item["name"]
                                for item in observed.get_columns(
                                    table_name, schema="public"
                                )
                            }
                        )
                    )
                    constraint_drift = _affected_unique_drift(
                        observed, models.Base.metadata, table_names
                    )
                    report.update(
                        {
                            "source_files_sha256": digests,
                            "target_database": target.database,
                            "staging_database": staging.database,
                            "target_league_id": league_id,
                            "target_schema_sha256": hashlib.sha256(
                                json.dumps(
                                    snapshot, sort_keys=True, default=str
                                ).encode()
                            ).hexdigest(),
                            "target_revisions": revisions,
                            "unknown_revisions": sorted(
                                row["version_num"]
                                for row in revisions
                                if row["version_num"] not in known_revisions
                            ),
                            "observed_schema_contract": snapshot,
                            "missing_orm_tables": missing_tables,
                            "missing_orm_columns": missing_columns,
                            "affected_unique_key_drift": constraint_drift,
                            "schema_status": "review_required_not_automatically_stamped",
                        }
                    )
        return report
    finally:
        target_engine.dispose()
        staging_engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--target-league-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.target_league_id <= 0:
        parser.error("--target-league-id must be positive.")
    target_url = os.environ.get("PPL_TARGET_DATABASE_URL")
    staging_url = os.environ.get("PPL_STAGING_DATABASE_URL")
    if not target_url or not staging_url:
        parser.error(
            "PPL_TARGET_DATABASE_URL and PPL_STAGING_DATABASE_URL are required."
        )
    if args.output.exists():
        parser.error("--output already exists; choose a new evidence file.")
    try:
        report = run_reconciliation(
            source_root=args.source_root,
            target_url=target_url,
            staging_url=staging_url,
            league_id=args.target_league_id,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Reports contain IDs, not names/passwords. Do not overwrite a reviewed report.
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    except sa.exc.SQLAlchemyError:
        # Driver exceptions may contain credentials, SQL parameters or account details.
        print(
            "ERROR: database connection or schema inspection failed.", file=sys.stderr
        )
        return 1
    except (OSError, ValueError, csv.Error) as error:
        print(
            f"ERROR: reconciliation input or report failed ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1
    print(f"Reconciliation saved: {args.output}")
    print(
        "BLOCKED: review schema adoption, identity mappings and source differences before import."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
