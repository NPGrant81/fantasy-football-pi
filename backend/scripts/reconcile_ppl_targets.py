"""Read-only, hash-bound target identity proposals for reviewed PPL history."""

from collections import Counter, defaultdict
from typing import Any

import sqlalchemy as sa

from backend.historical_schema_adoption import (
    TARGET_REVISION,
    _data_digest,
    _digest,
)
from backend.legacy_schema_bridge import _schema_snapshot
from backend.scripts.reconcile_ppl_events import auction_observation_key, _total_bid
from backend.scripts.reconcile_ppl_history import _position
from backend.services.player_service import _dedupe_normalized_name

REVIEWED_SCHEMA_DIGEST = (
    "4f67593995de3c848922cacebf89325255b338bf2d690a465d0e90652d78dce9"
)
COPY_PREFIXES = ("ffpi_528_slice6_", "ffpi_528_slice7_")
PROVIDERS = ("mfl_id", "sleeper_id", "gsis_id", "espn_id")


def capture_target_snapshot(
    engine: sa.Engine, expected_database: str, league_id: int
) -> dict[str, Any]:
    url = engine.url
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"localhost", "127.0.0.1"}
        or not expected_database.startswith(COPY_PREFIXES)
        or url.database != expected_database
        or bool(url.query)
    ):
        raise ValueError("Target review requires an explicit loopback slice-6/7 copy.")
    with engine.connect().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    ) as connection:
        if (
            connection.scalar(sa.select(sa.func.current_database()))
            != expected_database
        ):
            raise ValueError(
                "Connected target database differs from the selected copy."
            )
        if str(connection.scalar(sa.select(sa.func.inet_server_addr()))) not in {
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Target server address is not loopback.")
        if connection.scalar(sa.select(sa.func.current_schema())) != "public":
            raise ValueError("Target review requires the public schema.")
        schemas = set(sa.inspect(connection).get_schema_names()) - {
            "information_schema",
            "public",
        }
        if schemas:
            raise ValueError("Unexpected target schemas; refusing target review.")
        metadata = sa.MetaData()
        metadata.reflect(connection, schema="public")
        if "public.alembic_version" not in metadata.tables:
            raise ValueError("Target copy has no Alembic revision table.")
        version = metadata.tables["public.alembic_version"]
        if list(connection.scalars(sa.select(version.c.version_num))) != [
            TARGET_REVISION
        ]:
            raise ValueError("Target copy must already have the reviewed adoption.")
        schema = _schema_snapshot(connection, "public")
        schema.pop("alembic_version", None)
        if _digest(schema) != REVIEWED_SCHEMA_DIGEST:
            raise ValueError(
                "Target schema differs from the complete reviewed contract."
            )
        tables = {
            table.name: _data_digest(connection, table)
            for table in sorted(metadata.tables.values(), key=lambda item: item.name)
        }

        def rows(name: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
            table = metadata.tables[f"public.{name}"]
            return [
                dict(row)
                for row in connection.execute(
                    sa.select(*(table.c[column] for column in columns))
                ).mappings()
            ]

        leagues = rows("leagues", ("id", "current_season", "draft_status"))
        selected_leagues = [row for row in leagues if row["id"] == league_id]
        if len(selected_leagues) != 1:
            raise ValueError("Target league does not exist exactly once.")
        return {
            "database": expected_database,
            "league": selected_leagues[0],
            "revision": TARGET_REVISION,
            "schema_sha256": REVIEWED_SCHEMA_DIGEST,
            "table_digests": tables,
            "players": rows(
                "players", ("id", "name", "position", "nfl_team", *PROVIDERS)
            ),
            "player_seasons": rows(
                "player_seasons",
                ("id", "player_id", "season", "mfl_id", "position", "source"),
            ),
            "users": rows(
                "users",
                (
                    "id",
                    "username",
                    "league_id",
                    "is_historical_stub",
                    "is_superuser",
                    "is_commissioner",
                ),
            ),
            "league_mfl_seasons": rows(
                "league_mfl_seasons", ("league_id", "season", "mfl_league_id")
            ),
        }


def build_target_review(
    report: dict[str, Any],
    native_seasons: dict[int, dict[str, list[dict[str, str]]]],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Propose representatives, never authorize writes or merge existing rows."""
    approval = report.get("approved_event_resolutions", {})
    if approval.get("ready_for_slice_6") is not True:
        raise ValueError("Target review requires replayed source-event approvals.")
    events = approval["resolution"]["events"]
    keys = set()
    for event in events:
        key = auction_observation_key(
            league_mfl_id=event["league_mfl_id"],
            season=event["season"],
            player_mfl_id=event["player_mfl_id"],
            franchise_id=event["franchise_id"],
            winning_bid=event["winning_bid"],
        )
        if key != event["source_event_key"] or key in keys:
            raise ValueError(
                "Target review encountered a changed/duplicate source event."
            )
        keys.add(key)
    if not events:
        raise ValueError("Target review requires nonempty approved observations.")
    players = {row["id"]: row for row in snapshot["players"]}
    if len(players) != len(snapshot["players"]):
        raise ValueError("Target player IDs must be unique.")
    league_id = snapshot["league"]["id"]
    native = defaultdict(list)
    hashes = {
        (row["season"], row["report"]): row["sha256"]
        for row in report["selected_mfl_exports"]
    }
    for season, exports in native_seasons.items():
        for number, row in enumerate(exports["players"], start=2):
            native[(season, row["player_mfl_id"])].append(
                {
                    "name_key": _dedupe_normalized_name(row["player_name"]),
                    "position": _position(row["position"]),
                    "evidence_ref": f"{hashes[(season, 'players')]}:{number}",
                }
            )
    links = defaultdict(list)
    target_native_ids = defaultdict(set)
    for row in snapshot["player_seasons"]:
        if row["mfl_id"]:
            target_native_ids[row["player_id"]].add(row["mfl_id"])
            links[row["mfl_id"]].append(row)
    by_name = defaultdict(set)
    bound = defaultdict(set)
    for row in players.values():
        by_name[(_dedupe_normalized_name(row["name"]), _position(row["position"]))].add(
            row["id"]
        )
        if row["mfl_id"]:
            bound[row["mfl_id"]].add(row["id"])
    player_review = []
    blockers = []
    for identifier in sorted({event["player_mfl_id"] for event in events}):
        required_seasons = sorted(
            {
                event["season"]
                for event in events
                if event["player_mfl_id"] == identifier
            }
        )
        eligible = defaultdict(list)
        rejected = []
        catalog = [
            row
            for (season, native_id), rows in native.items()
            if native_id == identifier
            for row in rows
        ]
        if any(not native[(year, identifier)] for year in required_seasons):
            raise ValueError(
                "Approved event lacks same-season native catalog evidence."
            )
        name_candidates = set().union(
            *(by_name[(row["name_key"], row["position"])] for row in catalog)
        )
        for link in sorted(links[identifier], key=lambda row: row["id"]):
            evidence = native[(link["season"], identifier)]
            if not evidence:
                continue
            target = players.get(link["player_id"])
            reason = None
            if not target:
                reason = "dangling_target_player"
            elif target_native_ids[target["id"]] != {identifier}:
                reason = "target_linked_to_multiple_native_ids"
            elif target["mfl_id"] not in (None, "", identifier):
                reason = "conflicting_canonical_native_id"
            elif str(link["source"] or "").lower() != "mfl":
                reason = "unverified_season_provider"
            else:
                identity = (
                    _dedupe_normalized_name(target["name"]),
                    _position(target["position"]),
                )
                if not any(
                    identity == (row["name_key"], row["position"])
                    and _position(link["position"]) == row["position"]
                    for row in evidence
                ):
                    reason = "same_season_identity_disagreement"
            if reason:
                rejected.append(
                    {
                        "player_season_id": link["id"],
                        "target_player_id": link["player_id"],
                        "linked_native_ids": sorted(
                            target_native_ids[link["player_id"]]
                        ),
                        "season_link_sha256": _digest(link),
                        "reason": reason,
                    }
                )
            else:
                eligible[target["id"]].append(
                    {
                        "player_season_id": link["id"],
                        "season": link["season"],
                        "native_catalog_refs": [
                            row["evidence_ref"] for row in evidence
                        ],
                    }
                )
        reasons = []
        if rejected:
            reasons.append("conflicting_retained_season_evidence")
        if bound[identifier] - eligible.keys():
            reasons.append("uncorroborated_canonical_binding")
        if len(bound[identifier]) > 1:
            reasons.append("multiple_canonical_native_bindings")
        if any(
            len(
                {
                    players[target_id][provider]
                    for target_id in eligible
                    if players[target_id][provider]
                }
            )
            > 1
            for provider in PROVIDERS
        ):
            reasons.append("conflicting_provider_ids_across_candidates")
        if not eligible:
            reasons.append("no_native_corroborated_target")
        candidates = sorted(bound[identifier] or eligible.keys())
        fatal = set(reasons) - {"conflicting_retained_season_evidence"}
        proposed = min(candidates) if candidates and not fatal else None
        if reasons:
            blockers.append(
                {
                    "kind": "target_player_review_blocked",
                    "player_mfl_id": identifier,
                    "reasons": reasons,
                }
            )
        player_review.append(
            {
                "player_mfl_id": identifier,
                "required_seasons": required_seasons,
                "name_only_candidate_ids": sorted(name_candidates - eligible.keys()),
                "native_corroborated_candidates": [
                    {
                        "target_player_id": target_id,
                        "target_row_sha256": _digest(players[target_id]),
                        "provider_ids": {
                            provider: players[target_id][provider]
                            for provider in PROVIDERS
                        },
                        "same_season_evidence": evidence,
                    }
                    for target_id, evidence in sorted(eligible.items())
                ],
                "rejected_season_links": rejected,
                "proposed_target_player_id": proposed,
                "approved": False,
            }
        )
    representatives = [
        row["proposed_target_player_id"]
        for row in player_review
        if row["proposed_target_player_id"] is not None
    ]
    if len(representatives) != len(set(representatives)):
        blockers.append({"kind": "distinct_native_players_share_target_representative"})
    owner_review = []
    for season, franchise in sorted(
        {(event["season"], event["franchise_id"]) for event in events}
    ):
        league_mfl_ids = {
            event["league_mfl_id"] for event in events if event["season"] == season
        }
        target_leagues = [
            row["mfl_league_id"]
            for row in snapshot["league_mfl_seasons"]
            if row["league_id"] == league_id and row["season"] == season
        ]
        if len(target_leagues) != 1 or set(target_leagues) != league_mfl_ids:
            blockers.append({"kind": "target_season_league_mismatch", "season": season})
        username = f"hist_{season}_{franchise}"
        collisions = [
            row
            for row in snapshot["users"]
            if str(row["username"] or "").casefold() == username.casefold()
        ]
        reusable = (
            len(collisions) == 1
            and collisions[0]["username"] == username
            and collisions[0]["league_id"] == league_id
            and collisions[0]["is_historical_stub"] is True
            and not collisions[0]["is_superuser"]
            and not collisions[0]["is_commissioner"]
        )
        if collisions and not reusable:
            blockers.append(
                {
                    "kind": "unsafe_archival_account_collision",
                    "season": season,
                    "franchise_id": franchise,
                }
            )
        owner_review.append(
            {
                "season": season,
                "franchise_id": franchise,
                "proposed_username": username,
                "target_owner_id": collisions[0]["id"] if reusable else None,
                "disposition": (
                    "reuse_archival" if reusable else "create_nonlogin_archival"
                ),
                "approved": False,
            }
        )
    return {
        "target_database": snapshot["database"],
        "target_league_id": league_id,
        "target_revision": snapshot["revision"],
        "target_schema_sha256": snapshot["schema_sha256"],
        "target_table_digests": snapshot["table_digests"],
        "target_snapshot_sha256": _digest(snapshot),
        "source_event_approval_sha256": _digest(approval),
        "representative_policy": (
            "Existing native binding first; otherwise propose the lowest target ID "
            "among same-season native-corroborated rows. Requires explicit approval; "
            "not a name-based identity inference or permission to merge/redirect rows."
        ),
        "players": player_review,
        "season_franchises": owner_review,
        "summary": {
            "events": len(events),
            "exact_bid_total": _total_bid([event["winning_bid"] for event in events]),
            "players": len(player_review),
            "native_candidate_counts": dict(
                sorted(
                    Counter(
                        len(row["native_corroborated_candidates"])
                        for row in player_review
                    ).items()
                )
            ),
            "archival_account_dispositions": dict(
                Counter(row["disposition"] for row in owner_review)
            ),
        },
        "blockers": blockers,
        "ready_for_mapping_review": not blockers,
        "approved": False,
        "ready_to_import": False,
        "writes_performed_to_databases": False,
        "remaining_gates": [
            "Explicit hash-bound target mapping and archival-account approval",
            "Approved-plan importer with durable full observation provenance",
            "Live roster/ownership/financial consumer isolation",
            "New backed-up working clone; exact totals, preservation and idempotent rerun",
            "Production promotion requires separate approval",
        ],
    }


def target_resolution_proposal(review: dict[str, Any]) -> dict[str, Any]:
    fatal = [
        row
        for row in review["blockers"]
        if row.get("reasons") != ["conflicting_retained_season_evidence"]
    ]
    if fatal or any(
        row["proposed_target_player_id"] is None for row in review["players"]
    ):
        raise ValueError("Unresolved target identity/account evidence blocks approval.")
    return {
        "players": [
            {
                "player_mfl_id": row["player_mfl_id"],
                "target_player_id": row["proposed_target_player_id"],
            }
            for row in review["players"]
        ],
        "season_franchises": [
            {key: value for key, value in row.items() if key != "approved"}
            for row in review["season_franchises"]
        ],
        "excluded_season_links": [
            {"player_mfl_id": row["player_mfl_id"], **link}
            for row in review["players"]
            for link in row["rejected_season_links"]
        ],
        "duplicate_policy": "preserve_all_original_rows_no_merges_or_relationship_redirects",
        "excluded_link_policy": "preserve_unchanged_never_use_for_canonical_selection",
        "account_policy": "nonlogin_archival_only_no_privileges_or_live_membership",
        "storage": "separate_historical_auction_observations_v1",
    }


def approve_target_resolutions(
    report: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    review = report["target_mapping_review"]
    if (
        decisions.get("approved") is not True
        or not isinstance(decisions.get("review_basis"), str)
        or not decisions["review_basis"].strip()
        or decisions.get("review_sha256") != _digest(report)
        or review["source_event_approval_sha256"]
        != _digest(report["approved_event_resolutions"])
        or decisions.get("resolution") != target_resolution_proposal(review)
    ):
        raise ValueError(
            "Target approval must cover the exact reviewed plan and exclusions."
        )
    return {
        "review_sha256": _digest(report),
        "target_snapshot_sha256": review["target_snapshot_sha256"],
        "source_event_approval_sha256": review["source_event_approval_sha256"],
        "resolution": decisions["resolution"],
        "review_basis": decisions["review_basis"],
        "approved": True,
        "scope": "new_local_working_clone_only_not_production",
    }
