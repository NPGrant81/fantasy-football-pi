"""Reconcile preserved event observations offline without changing history."""

from collections import Counter, defaultdict, deque
from datetime import datetime
from decimal import localcontext
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.scripts.reconcile_ppl_history import (
    _amount,
    _draft_attribute,
    _integer,
    _position,
)
from backend.services.player_service import _dedupe_normalized_name

EVENT_GRAIN = {
    "version": "mfl-auction-observation-v1",
    "source_system": "mfl",
    "source_endpoint": "auctionResults",
    "key_fields": [
        "league_mfl_id",
        "season",
        "player_mfl_id",
        "franchise_id",
        "winning_bid",
    ],
    "identical_key_policy": "block_preserve_every_occurrence_never_deduplicate",
    "changed_observation_policy": "new_review_required_not_automatic_correction_or_append",
    "chronology": "not_established_by_snapshot_timestamps_or_export_order",
}


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, default=str, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bid(value: object) -> str:
    amount = _amount(value)
    if amount == 0:
        return "0"
    text = format(amount, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _total_bid(bids: list[str]) -> str:
    if not bids:
        return "0"
    precision = (
        max(len(bid.partition(".")[0]) for bid in bids)
        + max(len(bid.partition(".")[2]) for bid in bids)
        + len(str(len(bids)))
        + 1
    )
    with localcontext() as context:
        context.prec = precision
        return _bid(sum((_amount(bid) for bid in bids), _amount(0)))


def auction_observation_key(
    *,
    league_mfl_id: str,
    season: int,
    player_mfl_id: str,
    franchise_id: str,
    winning_bid: object,
) -> str:
    ids = (league_mfl_id, player_mfl_id, franchise_id)
    if not all(
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and int(value) > 0
        for value in ids
    ):
        raise ValueError("Auction observation requires positive native string IDs.")
    return "mfl-auction-v1:" + _digest(
        {
            "version": EVENT_GRAIN["version"],
            "source_system": "mfl",
            "source_endpoint": "auctionResults",
            "league_mfl_id": league_mfl_id,
            "season": _integer(season),
            "player_mfl_id": player_mfl_id,
            "franchise_id": franchise_id,
            "winning_bid": _bid(winning_bid),
        }
    )


def read_staging_snapshot(path: Path, verification_path: Path) -> dict[str, Any]:
    raw, baseline_raw = path.read_bytes(), verification_path.read_bytes()
    snapshot, baseline = json.loads(raw), json.loads(baseline_raw)
    if not isinstance(snapshot, dict) or not isinstance(baseline, dict):
        raise ValueError("Staging evidence must contain JSON objects.")
    database = snapshot.get("database")
    tables = baseline.get("tables")
    if (
        snapshot.get("format") != "ppl-staging-events-v1"
        or not isinstance(database, str)
        or not database.startswith("ffpi_528_")
        or database != baseline.get("working_database")
        or snapshot.get("table") != "public.draft_picks"
        or snapshot.get("verification_sha256")
        != hashlib.sha256(baseline_raw).hexdigest()
        or not isinstance(tables, dict)
        or snapshot.get("table_manifest") != tables.get("public.draft_picks")
    ):
        raise ValueError("Staging snapshot must match the preserved copy verification.")
    captured = snapshot.get("captured_at_utc")
    if not isinstance(captured, str) or datetime.fromisoformat(captured).tzinfo is None:
        raise ValueError("Staging snapshot requires a timezone-aware capture time.")
    manifest = snapshot["table_manifest"]
    expected_columns = [
        "player_id",
        "owner_id",
        "year",
        "position_id",
        "team_id",
        "amount",
    ]
    if (
        not isinstance(manifest, dict)
        or not isinstance(manifest.get("columns"), list)
        or any(
            not isinstance(col, list) or len(col) != 3 for col in manifest["columns"]
        )
        or [col[0] for col in manifest["columns"]] != expected_columns
    ):
        raise ValueError(
            "Staging snapshot column contract differs from reviewed grain."
        )
    rows = snapshot.get("rows")
    if (
        not isinstance(rows, list)
        or not rows
        or any(not isinstance(row, list) or len(row) != 6 for row in rows)
        or len(rows) != manifest.get("row_count")
    ):
        raise ValueError("Staging snapshot requires every original draft row.")
    row_hashes = sorted(bytes.fromhex(_digest(row)) for row in rows)
    if hashlib.sha256(b"".join(row_hashes)).hexdigest() != manifest.get(
        "all_rows_sha256"
    ):
        raise ValueError(
            "Staging snapshot rows do not match the preserved full-row hash."
        )
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "verification_sha256": hashlib.sha256(baseline_raw).hexdigest(),
        "database": database,
        "rows": [dict(zip(expected_columns, row)) for row in rows],
    }


def _legacy_key(row: dict[str, Any]) -> tuple:
    return (
        _integer(row["Year"]),
        _integer(row["OwnerID"]),
        _integer(row["PlayerID"]),
        _amount(row["WinningBid"]),
        _draft_attribute(row["PositionID"]),
        _draft_attribute(row["TeamID"]),
    )


def build_event_audit(
    *,
    sources: dict[str, list[dict[str, Any]]],
    report: dict[str, Any],
    native_seasons: dict[int, dict[str, list[dict[str, str]]]],
    staging: dict[str, Any],
) -> dict[str, Any]:
    hashes = report["legacy_source_files_sha256"]
    owner_rows = report["approved_owner_resolutions"]["resolved_event_owners"]
    owner_by_ref = {row["legacy_evidence_ref"]: row for row in owner_rows}
    attributes = {
        row["legacy_evidence_ref"]: row
        for row in report["approved_attribute_resolutions"]["draft_rows"]
    }
    staged_by_key: dict[tuple, deque[str]] = defaultdict(deque)
    staged_totals: dict[int, list[str]] = defaultdict(list)
    for number, row in enumerate(staging["rows"], start=1):
        key = _legacy_key(
            {
                "Year": row["year"],
                "OwnerID": row["owner_id"],
                "PlayerID": row["player_id"],
                "WinningBid": row["amount"],
                "PositionID": row["position_id"],
                "TeamID": row["team_id"],
            }
        )
        staged_by_key[key].append(f"{staging['sha256']}:{number}")
        staged_totals[key[0]].append(_bid(row["amount"]))
    legacy = []
    legacy_totals: dict[int, list[str]] = defaultdict(list)
    claims = {}
    for number, row in enumerate(sources["draft_results.csv"], start=2):
        ref = f"{hashes['draft_results.csv']}:{number}"
        key = _legacy_key(row)
        owner = owner_by_ref[ref]
        native_ref = owner["native_evidence_ref"]
        if native_ref in claims:
            raise ValueError(
                "Legacy events must not collapse onto one native observation."
            )
        claims[native_ref] = ref
        staged_ref = staged_by_key[key].popleft() if staged_by_key[key] else None
        legacy_totals[key[0]].append(_bid(row["WinningBid"]))
        legacy.append(
            {
                "legacy_evidence_ref": ref,
                "native_evidence_ref": native_ref,
                "staging_evidence_ref": staged_ref,
                "season": key[0],
                "source_owner_id": key[1],
                "source_player_id": key[2],
                "winning_bid": _bid(row["WinningBid"]),
                "disposition": (
                    "retain_matched_observation"
                    if staged_ref
                    else "restore_staging_gap"
                ),
            }
        )
    if len(claims) != len(owner_rows) or set(owner_by_ref) != set(attributes):
        raise ValueError("Event review requires complete distinct prerequisite rows.")
    blockers = []
    unexpected = [ref for refs in staged_by_key.values() for ref in refs]
    if unexpected:
        blockers.append({"kind": "unexpected_staging_observations", "refs": unexpected})
    seasons = {s["season"]: s for s in report["seasons"]}
    selected = {
        (row["season"], row["report"]): row["sha256"]
        for row in report["selected_mfl_exports"]
    }
    owner_mappings = defaultdict(list)
    for row in report["approved_owner_resolutions"]["season_owners"]:
        owner_mappings[(row["season"], row["franchise_id"])].append(
            row["source_owner_id"]
        )
    player_approvals = {
        row["source_player_id"]: row["player_mfl_id"]
        for row in report["approved_player_resolutions"]["resolved_players"]
    }
    legacy_players = defaultdict(list)
    for number, row in enumerate(sources["players.csv"], start=2):
        legacy_players[_integer(row["Player_ID"])].append((number, row))
    proposals = []
    key_refs = defaultdict(list)
    player_groups = defaultdict(list)
    across_seasons = defaultdict(list)
    native_totals: dict[int, list[str]] = defaultdict(list)
    timestamp_counts = {}
    native_refs = set()
    for year, exports in sorted(native_seasons.items()):
        if not exports["players"] or not exports["draftResults"]:
            blockers.append(
                {"kind": "empty_native_season_requires_review", "season": year}
            )
        by_ref = {row["evidence_ref"]: row for row in seasons[year]["native_events"]}
        catalog = defaultdict(list)
        for number, row in enumerate(exports["players"], start=2):
            catalog[row["player_mfl_id"]].append((number, row))
        stamps = Counter()
        for number, row in enumerate(exports["draftResults"], start=2):
            ref = f"{selected[(year, 'draftResults')]}:{number}"
            native_refs.add(ref)
            event = by_ref[ref]
            reasons = []
            raw = json.loads(row.get("raw_pick", "null"))
            if (
                not isinstance(raw, dict)
                or raw.get("player") != row["player_mfl_id"]
                or raw.get("franchise") != row["franchise_id"]
                or raw.get("source") != "auctionResults"
                or _amount(raw.get("cost")) != _amount(row["winning_bid"])
            ):
                reasons.append("raw_normalized_event_disagreement")
            if event["status"] == "blocked":
                reasons.append("invalid_native_observation")
            stamp = raw.get("timestamp") if isinstance(raw, dict) else None
            stamps[str(stamp)] += 1
            key = auction_observation_key(
                league_mfl_id=seasons[year]["league_mfl_id"],
                season=year,
                player_mfl_id=row["player_mfl_id"],
                franchise_id=row["franchise_id"],
                winning_bid=row["winning_bid"],
            )
            key_refs[key].append(ref)
            player_groups[(year, row["player_mfl_id"])].append(ref)
            across_seasons[row["player_mfl_id"]].append(
                {
                    "season": year,
                    "source_event_key": key,
                    "native_evidence_ref": ref,
                }
            )
            native_totals[year].append(_bid(row["winning_bid"]))
            legacy_ref = claims.get(ref)
            proposal = {
                "source_event_key": key,
                "season": year,
                "league_mfl_id": seasons[year]["league_mfl_id"],
                "player_mfl_id": row["player_mfl_id"],
                "franchise_id": row["franchise_id"],
                "winning_bid": _bid(row["winning_bid"]),
                "native_evidence_ref": ref,
                "raw_timestamp": stamp,
                "legacy_evidence_ref": legacy_ref,
                "disposition": (
                    "preserve_linked_legacy" if legacy_ref else "supplement_native_only"
                ),
            }
            if legacy_ref:
                proposal["source_owner_id"] = owner_by_ref[legacy_ref][
                    "resolved_source_owner_id"
                ]
                proposal["source_player_id"] = next(
                    r["source_player_id"]
                    for r in legacy
                    if r["legacy_evidence_ref"] == legacy_ref
                )
                proposal["attributes"] = attributes[legacy_ref]
            else:
                observations = catalog[row["player_mfl_id"]]
                identities = {
                    (
                        _dedupe_normalized_name(r["player_name"]),
                        _position(r["position"]),
                        (r.get("nfl_team") or "").strip(),
                    )
                    for _, r in observations
                }
                if len(identities) != 1:
                    reasons.append("supplement_conflicting_catalog")
                name, position, team = (
                    next(iter(identities)) if len(identities) == 1 else ("", "", "")
                )
                candidates = []
                for identifier, variants in sorted(legacy_players.items()):
                    native_id = player_approvals.get(identifier)
                    if native_id == row["player_mfl_id"] or (
                        native_id is None
                        and name
                        and all(
                            _dedupe_normalized_name(r["PlayerName"]) == name
                            for _, r in variants
                        )
                    ):
                        candidates.append(
                            {
                                "source_player_id": identifier,
                                "legacy_catalog_refs": [
                                    f"{hashes['players.csv']}:{n}" for n, _ in variants
                                ],
                            }
                        )
                owners = owner_mappings[(year, row["franchise_id"])]
                if len(candidates) != 1 or len(owners) != 1:
                    reasons.append(
                        "supplement_requires_unique_source_player_and_season_owner"
                    )
                if (
                    position not in {"QB", "RB", "WR", "TE", "DST", "K", "FB"}
                    or not team
                ):
                    reasons.append("supplement_missing_attributes")
                proposal["source_owner_id"] = owners[0] if len(owners) == 1 else None
                proposal["source_player_candidates"] = candidates
                proposal["source_player_id"] = (
                    candidates[0]["source_player_id"] if len(candidates) == 1 else None
                )
                proposal["attributes"] = {
                    "position": position,
                    "nfl_team": team,
                    "team_basis": "season_catalog_snapshot_not_auction_time",
                    "native_catalog_refs": [
                        f"{selected[(year, 'players')]}:{n}" for n, _ in observations
                    ],
                    "catalog_extracted_at_utc": sorted(
                        {r["extracted_at_utc"] for _, r in observations}
                    ),
                }
            if reasons:
                blockers.append(
                    {
                        "kind": "invalid_event_proposal",
                        "native_evidence_ref": ref,
                        "reasons": reasons,
                    }
                )
            proposals.append(proposal)
        timestamp_counts[year] = {
            "distinct_values": len(stamps),
            "shared_timestamp_additional_rows": sum(n - 1 for n in stamps.values()),
            "establishes_chronology": False,
        }
    if set(claims) - native_refs:
        blockers.append({"kind": "legacy_claims_missing_native_evidence"})
    collisions = [
        {"source_event_key": key, "native_evidence_refs": refs}
        for key, refs in sorted(key_refs.items())
        if len(refs) > 1
    ]
    if collisions:
        blockers.append(
            {"kind": "identical_observation_collisions", "groups": collisions}
        )
    repeats = [
        {"season": year, "player_mfl_id": player, "native_evidence_refs": refs}
        for (year, player), refs in sorted(player_groups.items())
        if len(refs) > 1
    ]
    seasonal_repeats = [
        {"player_mfl_id": player, "observations": observations}
        for player, observations in sorted(across_seasons.items())
        if len({row["season"] for row in observations}) > 1
    ]
    totals = []
    for year in sorted(set(native_totals) | set(legacy_totals) | set(staged_totals)):
        total = {"season": year}
        for label, grouped in (
            ("native", native_totals),
            ("legacy", legacy_totals),
            ("staging", staged_totals),
        ):
            bids = grouped.get(year, [])
            total[f"{label}_rows"] = len(bids)
            total[f"{label}_amount"] = _total_bid(bids)
        totals.append(total)
    return {
        "staging_snapshot_sha256": staging["sha256"],
        "staging_verification_sha256": staging["verification_sha256"],
        "staging_database": staging["database"],
        "proposal": {
            "event_grain": EVENT_GRAIN,
            "events": proposals,
            "legacy_coverage": legacy,
            "repeated_player_observations": repeats,
            "players_in_multiple_seasons": seasonal_repeats,
            "season_totals": totals,
        },
        "legacy_disposition_counts": dict(Counter(r["disposition"] for r in legacy)),
        "native_disposition_counts": dict(Counter(r["disposition"] for r in proposals)),
        "timestamp_observations": timestamp_counts,
        "unexpected_staging_refs": unexpected,
        "blockers": blockers,
        "ready_for_approval": not blockers,
        "ready_for_slice_6": False,
        "ready_to_import": False,
        "limitations": [
            "Keys identify reviewed auction observations, not an ordered transaction ledger.",
            "Shared season timestamps and export ordering never distinguish repeated acquisitions.",
            "Identical tuples remain separate evidence and block approval; no occurrence-index keys.",
            "A changed amount/owner is a changed observation requiring fresh review, not automatic append.",
            "Staging occurrence references are snapshot locators, not source event identities.",
        ],
    }


def approve_event_resolutions(
    report: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    audit = report["event_reconciliation_audit"]
    bindings = {
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "teams_sha256": report["approved_attribute_resolutions"]["teams_sha256"],
        "staging_snapshot_sha256": audit["staging_snapshot_sha256"],
        "staging_verification_sha256": audit["staging_verification_sha256"],
    }
    if (
        decisions.get("approved") is not True
        or not isinstance(decisions.get("review_basis"), str)
        or not decisions["review_basis"].strip()
        or any(decisions.get(key) != value for key, value in bindings.items())
    ):
        raise ValueError(
            "Event approval must match all reviewed source and staging hashes."
        )
    if not audit["ready_for_approval"]:
        raise ValueError("Unresolved event evidence blocks approval.")
    if decisions.get("resolution") != audit["proposal"]:
        raise ValueError(
            "Every event, gap, repetition and exact total requires explicit review."
        )
    return {
        **bindings,
        "resolution": audit["proposal"],
        "review_basis": decisions["review_basis"],
        "ready_for_slice_6": True,
        "ready_to_import": False,
        "writes_performed_to_databases": False,
        "scope": "reviewed_historical_auction_observations_not_import_permission",
    }
