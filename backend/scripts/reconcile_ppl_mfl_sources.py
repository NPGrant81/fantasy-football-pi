"""Build offline PPL repair evidence and replay reviewed source resolutions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from typing import Any

from backend.scripts.extract_mfl_history import KNOWN_LEAGUE_BY_SEASON
from backend.scripts.reconcile_ppl_attributes import (
    approve_attribute_resolutions,
    build_attribute_audit,
)
from backend.scripts.reconcile_ppl_history import (
    _amount,
    _index,
    _integer,
    _label,
    _position,
    _position_id,
    _read_sources,
)
from backend.services.player_service import (
    _dedupe_normalized_name,
    normalize_display_name,
)

HEADERS = {
    "players": {"player_mfl_id", "player_name", "position"},
    "franchises": {"franchise_id"},
    "draftResults": {
        "player_mfl_id",
        "franchise_id",
        "winning_bid",
        "draft_source",
        "draft_style",
    },
}
METADATA = {
    "season",
    "league_id",
    "source_system",
    "source_endpoint",
    "extracted_at_utc",
}


def _source_id(value: object) -> str:
    """Validate a numeric native ID without stripping significant leading zeros."""
    identifier = str(value).strip()
    if not identifier.isascii() or not identifier.isdigit() or int(identifier) <= 0:
        raise ValueError("Expected a positive native MFL identifier.")
    return identifier


def _legacy_conflict_register(
    sources: dict[str, list[dict[str, Any]]], hashes: dict[str, str]
) -> list[dict[str, Any]]:
    register = []
    for name, identifier in (
        ("players.csv", "Player_ID"),
        ("users.csv", "OwnerID"),
        ("positions.csv", "PositionID"),
    ):
        conflicts = {
            key for key, row in _index(sources[name], identifier).items() if row is None
        }
        for key in sorted(conflicts):
            variants: dict[str, dict[str, Any]] = {}
            originals = []
            for number, row in enumerate(sources[name], start=2):
                if _integer(row[identifier]) != key:
                    continue
                originals.append(row)
                digest = hashlib.sha256(
                    json.dumps(row, sort_keys=True).encode("utf-8")
                ).hexdigest()
                variant = variants.setdefault(
                    digest, {"variant_sha256": digest, "source_row_refs": []}
                )
                variant["source_row_refs"].append(f"{hashes[name]}:{number}")
            columns = set().union(*(row.keys() for row in originals))
            register.append(
                {
                    "source_file": name,
                    "source_id": key,
                    "differing_columns": sorted(
                        column
                        for column in columns
                        if len({row.get(column) for row in originals}) > 1
                    ),
                    "variants": list(variants.values()),
                    "approved": False,
                    "resolution": None,
                    "evidence": [],
                }
            )
    return register


def _read_export(
    path: Path, report_type: str, season: int
) -> tuple[list[dict[str, str]], str]:
    raw = path.read_bytes()
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle)
        required = HEADERS[report_type] | METADATA
        if not required <= set(reader.fieldnames or ()):
            raise ValueError(f"{report_type} export is missing required columns.")
        rows = []
        for row in reader:
            if None in row or any(row.get(column) is None for column in required):
                raise ValueError(f"{report_type} export has a malformed row.")
            if (
                _integer(row["season"]) != season
                or row["league_id"] != KNOWN_LEAGUE_BY_SEASON[season]
                or row["source_system"] != "mfl"
                or row["source_endpoint"] != report_type
                or not row["extracted_at_utc"].strip()
            ):
                raise ValueError(f"{report_type} export has conflicting provenance.")
            rows.append(dict(row))
    return rows, hashlib.sha256(raw).hexdigest()


def _native_event_candidates(
    *,
    players: list[dict[str, str]],
    franchises: list[dict[str, str]],
    drafts: list[dict[str, str]],
    draft_sha256: str,
) -> dict[tuple[str, object], list[dict[str, Any]]]:
    native_catalog: dict[str, set[tuple[str, str]]] = defaultdict(set)
    native_franchises = {_source_id(row["franchise_id"]) for row in franchises}
    for row in players:
        native_catalog[_source_id(row["player_mfl_id"])].add(
            (
                _label(normalize_display_name(row["player_name"])),
                _position(row["position"]),
            )
        )
    events: dict[tuple[str, object], list[dict[str, Any]]] = defaultdict(list)
    for number, row in enumerate(drafts, start=2):
        if _source_id(row["franchise_id"]) not in native_franchises:
            continue
        identities = native_catalog.get(_source_id(row["player_mfl_id"]), set())
        if len(identities) != 1:
            continue
        name, position = next(iter(identities))
        if not name or not position:
            continue
        try:
            bid = _amount(row["winning_bid"])
        except ValueError:
            continue
        if row["draft_source"] != "auctionResults" or row["draft_style"] != "auction":
            continue
        events[(name, bid)].append(
            {
                "evidence_ref": f"{draft_sha256}:{number}",
                "player_mfl_id": row["player_mfl_id"],
                "franchise_id": row["franchise_id"],
                "native_position": position,
            }
        )
    return events


def _position_conflict_audit(
    *,
    season: int,
    sources: dict[str, list[dict[str, Any]]],
    players: list[dict[str, str]],
    franchises: list[dict[str, str]],
    drafts: list[dict[str, str]],
    draft_sha256: str,
) -> dict[str, Any]:
    conflicting_ids = {
        identifier
        for identifier, row in _index(sources["positions.csv"], "PositionID").items()
        if row is None
    }
    legacy_names: dict[int, set[str]] = defaultdict(set)
    for row in sources["players.csv"]:
        name = _label(normalize_display_name(row["PlayerName"]))
        if name:
            legacy_names[_integer(row["Player_ID"])].add(name)
    events = _native_event_candidates(
        players=players,
        franchises=franchises,
        drafts=drafts,
        draft_sha256=draft_sha256,
    )
    rows = []
    for number, row in enumerate(sources["draft_results.csv"], start=2):
        identifier = _position_id(row["PositionID"])
        if _integer(row["Year"]) != season or identifier not in conflicting_ids:
            continue
        candidates = [
            event
            for name in sorted(legacy_names[_integer(row["PlayerID"])])
            for event in events.get((name, _amount(row["WinningBid"])), [])
        ]
        rows.append(
            {
                "legacy_csv_row": number,
                "source_position_id": identifier,
                "source_player_id": _integer(row["PlayerID"]),
                "source_owner_id": _integer(row["OwnerID"]),
                "winning_bid": str(_amount(row["WinningBid"])),
                "candidate_native_positions": sorted(
                    {event["native_position"] for event in candidates}
                ),
                "candidate_native_events": candidates,
                "status": (
                    "no_candidate"
                    if not candidates
                    else (
                        "single_event_review" if len(candidates) == 1 else "ambiguous"
                    )
                ),
                "approved": False,
            }
        )
    return {
        "method": "all_legacy_name_variants_and_exact_bid_without_position_assumption",
        "rows": rows,
        "position_ids": [
            {
                "source_position_id": identifier,
                "affected_draft_rows": sum(
                    row["source_position_id"] == identifier for row in rows
                ),
                "candidate_position_sets": [
                    {"native_positions": list(positions), "rows": count}
                    for positions, count in sorted(
                        Counter(
                            tuple(row["candidate_native_positions"])
                            for row in rows
                            if row["source_position_id"] == identifier
                        ).items()
                    )
                ],
                "global_replacement_approved": False,
            }
            for identifier in sorted(conflicting_ids)
        ],
        "limitations": [
            "All legacy player variants participate; a candidate is not an approved identity.",
            "Matching names and bids cannot authorize a global position-ID replacement.",
            "No native event candidate does not prove missing history.",
        ],
    }


def _player_conflict_audit(
    *,
    season: int,
    sources: dict[str, list[dict[str, Any]]],
    players: list[dict[str, str]],
    franchises: list[dict[str, str]],
    drafts: list[dict[str, str]],
    draft_sha256: str,
) -> list[dict[str, Any]]:
    conflicts = {
        identifier
        for identifier, row in _index(sources["players.csv"], "Player_ID").items()
        if row is None
    }
    variants: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for number, row in enumerate(sources["players.csv"], start=2):
        identifier = _integer(row["Player_ID"])
        if identifier not in conflicts:
            continue
        digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        variant = variants[identifier].setdefault(
            digest,
            {
                "name": _label(normalize_display_name(row["PlayerName"])),
                "alias_key": _dedupe_normalized_name(row["PlayerName"]),
                "defense_label": "D/ST" in str(row["PlayerName"]).upper(),
                "legacy_catalog_rows": [],
            },
        )
        variant["legacy_catalog_rows"].append(number)
    native_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    native_names_by_alias: dict[str, set[str]] = defaultdict(set)
    for number, row in enumerate(players, start=2):
        name = _label(normalize_display_name(row["player_name"]))
        if name:
            native_names_by_alias[_dedupe_normalized_name(row["player_name"])].add(name)
            native_by_name[name].append(
                {
                    "player_mfl_id": _source_id(row["player_mfl_id"]),
                    "native_position": _position(row["position"]),
                    "native_catalog_row": number,
                }
            )

    def candidate_names(variant: dict[str, Any]) -> set[str]:
        return (
            {variant["name"]} | native_names_by_alias[variant["alias_key"]]
            if variant["name"]
            else set()
        )

    def variant_report(digest: str, variant: dict[str, Any]) -> dict[str, Any]:
        catalog = [
            {
                **row,
                "match_method": (
                    "exact_display_name"
                    if name == variant["name"]
                    else "existing_suffix_punctuation_normalizer"
                ),
            }
            for name in sorted(candidate_names(variant))
            for row in native_by_name.get(name, [])
        ]
        identities = {row["player_mfl_id"] for row in catalog}
        return {
            "variant_sha256": digest,
            "legacy_catalog_rows": variant["legacy_catalog_rows"],
            "candidate_native_catalog": catalog,
            "status": (
                "missing_name"
                if not variant["name"]
                else (
                    "single_native_id_review"
                    if len(identities) == 1
                    else ("ambiguous" if identities else "no_candidate")
                )
            ),
            "approved": False,
        }

    events = _native_event_candidates(
        players=players,
        franchises=franchises,
        drafts=drafts,
        draft_sha256=draft_sha256,
    )
    affected: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for number, row in enumerate(sources["draft_results.csv"], start=2):
        identifier = _integer(row["PlayerID"])
        if _integer(row["Year"]) != season or identifier not in conflicts:
            continue
        bid = _amount(row["WinningBid"])
        candidates: dict[str, dict[str, Any]] = {}
        for digest, variant in variants[identifier].items():
            if not variant["name"]:
                continue
            for name in sorted(candidate_names(variant)):
                for event in events.get((name, bid), []):
                    candidate = candidates.setdefault(
                        event["evidence_ref"],
                        {**event, "supporting_variant_sha256": []},
                    )
                    candidate["supporting_variant_sha256"].append(digest)
        event_candidates = list(candidates.values())
        affected[identifier].append(
            {
                "legacy_csv_row": number,
                "source_owner_id": _integer(row["OwnerID"]),
                "winning_bid": str(bid),
                "candidate_native_events": event_candidates,
                "status": (
                    "single_event_review"
                    if len(event_candidates) == 1
                    else ("ambiguous" if event_candidates else "no_candidate")
                ),
                "approved": False,
                "resolution": None,
            }
        )
    return [
        {
            "source_player_id": identifier,
            "variant_relationship": (
                "suffix_or_punctuation_alias_review"
                if len({v["alias_key"] for v in variants[identifier].values()}) == 1
                else (
                    "defense_label_alias_review"
                    if any(v["defense_label"] for v in variants[identifier].values())
                    else "nontrivial_alias_or_identity_review"
                )
            ),
            "variants": [
                variant_report(digest, variant)
                for digest, variant in sorted(variants[identifier].items())
            ],
            "affected_draft_rows": affected[identifier],
            "status": (
                "review_required" if affected[identifier] else "catalog_only_review"
            ),
            "approved": False,
        }
        for identifier in sorted(conflicts)
    ]


def _player_conflict_dispositions(
    sources: dict[str, list[dict[str, Any]]], reports: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        for profile in report["player_conflict_audit"]:
            by_player[profile["source_player_id"]].append(
                {"season": report["season"], **profile}
            )
    result = []
    for identifier, profiles in sorted(by_player.items()):
        all_rows = [
            number
            for number, row in enumerate(sources["draft_results.csv"], start=2)
            if _integer(row["PlayerID"]) == identifier
        ]
        covered = {
            row["legacy_csv_row"]
            for profile in profiles
            for row in profile["affected_draft_rows"]
        }
        event_rows = [
            row for profile in profiles for row in profile["affected_draft_rows"]
        ]
        missing = sorted(set(all_rows) - covered)
        if missing:
            disposition = "blocked_missing_season_evidence"
        elif any(row["status"] != "single_event_review" for row in event_rows):
            disposition = "blocked_ambiguous_or_missing_event"
        elif not event_rows:
            disposition = "blocked_catalog_only_identity_review"
        else:
            disposition = "event_resolutions_ready_for_review"
        selected = {
            row["candidate_native_events"][0]["player_mfl_id"]
            for row in event_rows
            if row["status"] == "single_event_review"
        }
        result.append(
            {
                "source_player_id": identifier,
                "variant_relationship": profiles[0]["variant_relationship"],
                "affected_draft_rows": len(all_rows),
                "uncovered_legacy_rows": missing,
                "event_status_counts": dict(
                    Counter(row["status"] for row in event_rows)
                ),
                "single_event_candidate_native_ids": sorted(selected),
                "row_specific_identity_required": len(selected) > 1,
                "disposition": disposition,
                "approved": False,
                "resolution": None,
                "evidence": [],
                "reconstruction_blocked": True,
            }
        )
    return result


def reconcile_season(
    *,
    season: int,
    sources: dict[str, list[dict[str, Any]]],
    players: list[dict[str, str]],
    franchises: list[dict[str, str]],
    drafts: list[dict[str, str]],
    draft_sha256: str,
) -> dict[str, Any]:
    """Name/position/bid comparisons nominate source events, never approve identities."""
    legacy_players = _index(sources["players.csv"], "Player_ID")
    positions = _index(sources["positions.csv"], "PositionID")
    native_players: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in players:
        native_players[_source_id(row["player_mfl_id"])].add(
            (
                _label(normalize_display_name(row["player_name"])),
                _position(row["position"]),
            )
        )
    native_franchises = {_source_id(row["franchise_id"]) for row in franchises}
    if len(native_franchises) != len(franchises):
        raise ValueError("Repeated franchise IDs require source review.")

    blockers = []
    if not drafts or not players or not franchises:
        blockers.append({"kind": "empty_source_export_requires_review"})
    events = []
    by_signature: dict[tuple[str, str, object], list[int]] = defaultdict(list)
    duplicate_keys: Counter = Counter()
    for index, row in enumerate(drafts):
        player_id = _source_id(row["player_mfl_id"])
        franchise_id = _source_id(row["franchise_id"])
        signatures = native_players.get(player_id, set())
        reasons = []
        if len(signatures) != 1 or not all(next(iter(signatures), ("", ""))):
            reasons.append("missing_or_conflicting_native_player")
        if franchise_id not in native_franchises:
            reasons.append("missing_native_franchise")
        try:
            bid = _amount(row["winning_bid"])
        except ValueError:
            bid = None
            reasons.append("missing_or_invalid_bid")
        if row["draft_source"] != "auctionResults" or row["draft_style"] != "auction":
            reasons.append("unsupported_draft_grain")
        reference = f"{draft_sha256}:{index + 2}"
        event = {
            "evidence_ref": reference,
            "player_mfl_id": player_id,
            "franchise_id": franchise_id,
            "winning_bid": str(bid) if bid is not None else None,
            "legacy_candidate_rows": [],
            "status": "blocked" if reasons else "review_required",
        }
        events.append(event)
        if reasons:
            blockers.append(
                {
                    "kind": "invalid_native_draft",
                    "evidence_ref": reference,
                    "reasons": reasons,
                }
            )
        else:
            name, position = next(iter(signatures))
            by_signature[(name, position, bid)].append(index)
        duplicate_keys[(player_id, franchise_id, bid)] += 1

    legacy_report = []
    owner_support: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row_number, row in enumerate(sources["draft_results.csv"], start=2):
        if _integer(row["Year"]) != season:
            continue
        identifier = _integer(row["PlayerID"])
        owner_id = _integer(row["OwnerID"])
        legacy_bid = _amount(row["WinningBid"])
        archived = legacy_players.get(identifier)
        position_id = _position_id(row["PositionID"])
        position_row = positions.get(position_id) if position_id else None
        # A draft's declared position cannot override a contradictory player identity.
        verified = bool(
            archived
            and position_row
            and _label(archived["PlayerName"])
            and _position(position_row["Position"])
            and _position_id(archived["PositionID"]) == position_id
        )
        candidates = []
        if verified:
            signature = (
                _label(normalize_display_name(archived["PlayerName"])),
                _position(position_row["Position"]),
                legacy_bid,
            )
            candidates = by_signature.get(signature, [])
        for index in candidates:
            events[index]["legacy_candidate_rows"].append(row_number)
        legacy_report.append(
            {
                "legacy_csv_row": row_number,
                "source_player_id": identifier,
                "source_owner_id": owner_id,
                "candidate_evidence_refs": [
                    events[index]["evidence_ref"] for index in candidates
                ],
                "status": (
                    "unverified_legacy_identity"
                    if not verified
                    else (
                        "single_candidate_review"
                        if len(candidates) == 1
                        else ("ambiguous" if candidates else "no_candidate")
                    )
                ),
            }
        )
        if len(candidates) == 1:
            owner_support[(owner_id, events[candidates[0]]["franchise_id"])].append(
                row_number
            )

    for event in events:
        if event["status"] == "blocked":
            continue
        event["status"] = (
            "no_legacy_candidate"
            if not event["legacy_candidate_rows"]
            else (
                "single_candidate_review"
                if len(event["legacy_candidate_rows"]) == 1
                else "ambiguous"
            )
        )
    repeated = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    if repeated:
        blockers.append(
            {
                "kind": "repeated_native_event_tuple_requires_grain_review",
                "additional_rows": repeated,
            }
        )
    owner_franchises: dict[int, set[str]] = defaultdict(set)
    franchise_owners: dict[str, set[int]] = defaultdict(set)
    for owner_id, franchise_id in owner_support:
        owner_franchises[owner_id].add(franchise_id)
        franchise_owners[franchise_id].add(owner_id)
    owner_conflicts = {
        "split_legacy_owners": [
            {"source_owner_id": owner, "candidate_franchise_ids": sorted(ids)}
            for owner, ids in sorted(owner_franchises.items())
            if len(ids) > 1
        ],
        "shared_native_franchises": [
            {"franchise_id": franchise, "candidate_source_owner_ids": sorted(ids)}
            for franchise, ids in sorted(franchise_owners.items())
            if len(ids) > 1
        ],
    }
    if any(owner_conflicts.values()):
        blockers.append({"kind": "conflicting_season_owner_evidence"})
    return {
        "season": season,
        "native_catalog_conflicts": [
            {
                "player_mfl_id": identifier,
                "rows": [
                    {
                        "native_catalog_row": number,
                        "player_name": row["player_name"],
                        "native_position": _position(row["position"]),
                    }
                    for number, row in enumerate(players, start=2)
                    if _source_id(row["player_mfl_id"]) == identifier
                ],
            }
            for identifier, identities in sorted(native_players.items())
            if len(identities) > 1
        ],
        "player_conflict_audit": _player_conflict_audit(
            season=season,
            sources=sources,
            players=players,
            franchises=franchises,
            drafts=drafts,
            draft_sha256=draft_sha256,
        ),
        "position_conflict_audit": _position_conflict_audit(
            season=season,
            sources=sources,
            players=players,
            drafts=drafts,
            franchises=franchises,
            draft_sha256=draft_sha256,
        ),
        "league_mfl_id": KNOWN_LEAGUE_BY_SEASON[season],
        "native_draft_rows": len(events),
        "legacy_draft_rows": len(legacy_report),
        "legacy_status_counts": dict(Counter(row["status"] for row in legacy_report)),
        "native_status_counts": dict(Counter(row["status"] for row in events)),
        "native_events": events,
        "legacy_candidates": legacy_report,
        "source_owner_franchise_candidates": [
            {
                "source_owner_id": owner,
                "franchise_id": franchise,
                "supporting_legacy_rows": rows,
                "approved": False,
            }
            for (owner, franchise), rows in sorted(owner_support.items())
        ],
        "source_owner_conflicts": owner_conflicts,
        "native_mapping_review_template": {
            "approved": False,
            "franchises": [
                {"franchise_id": identifier, "target_owner_id": None, "evidence": []}
                for identifier in sorted(native_franchises)
            ],
            "drafted_players": [
                {"player_mfl_id": identifier, "target_player_id": None, "evidence": []}
                for identifier in sorted({event["player_mfl_id"] for event in events})
            ],
        },
        "blockers": blockers,
        "approved": False,
    }


def run_source_reconciliation(
    *,
    source_root: Path,
    season_exports: dict[int, Path],
    draft_exports: dict[int, Path],
    player_resolutions: dict[str, Any] | None = None,
    owner_resolutions: dict[str, Any] | None = None,
    audit_attributes: bool = False,
    attribute_resolutions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not season_exports or set(draft_exports) - set(season_exports):
        raise ValueError("Select season exports before any draft override.")
    sources, hashes = _read_sources(source_root)
    reports = []
    selected = []
    native_seasons = {}
    for season, root in sorted(season_exports.items()):
        if season not in KNOWN_LEAGUE_BY_SEASON:
            raise ValueError("Season has no verified MFL league mapping.")
        rows = {}
        export_hashes = {}
        draft_hash = ""
        for report in HEADERS:
            path = (
                draft_exports[season]
                if report == "draftResults" and season in draft_exports
                else root / report / f"{season}.csv"
            )
            rows[report], digest = _read_export(path, report, season)
            export_hashes[report] = digest
            selected.append({"season": season, "report": report, "sha256": digest})
            if report == "draftResults":
                draft_hash = digest
        native_seasons[season] = rows
        reports.append(
            reconcile_season(
                season=season,
                sources=sources,
                players=rows["players"],
                franchises=rows["franchises"],
                drafts=rows["draftResults"],
                draft_sha256=draft_hash,
            )
        )
        for profile in reports[-1]["player_conflict_audit"]:
            for variant in profile["variants"]:
                variant["legacy_catalog_row_refs"] = [
                    f"{hashes['players.csv']}:{number}"
                    for number in variant["legacy_catalog_rows"]
                ]
                for candidate in variant["candidate_native_catalog"]:
                    candidate["evidence_ref"] = (
                        f"{export_hashes['players']}:{candidate['native_catalog_row']}"
                    )
            for event in profile["affected_draft_rows"]:
                event["legacy_evidence_ref"] = (
                    f"{hashes['draft_results.csv']}:{event['legacy_csv_row']}"
                )
        for conflict in reports[-1]["native_catalog_conflicts"]:
            for row in conflict["rows"]:
                row["evidence_ref"] = (
                    f"{export_hashes['players']}:{row['native_catalog_row']}"
                )
    result = {
        "writes_performed_to_databases": False,
        "api_requests_sent": 0,
        "ready_to_import": False,
        "legacy_source_files_sha256": hashes,
        "legacy_conflict_register": _legacy_conflict_register(sources, hashes),
        "player_conflict_dispositions": _player_conflict_dispositions(sources, reports),
        "selected_mfl_exports": selected,
        "seasons": reports,
        "limitations": [
            "Native export row references are evidence locators, not source-event IDs.",
            "Name/position/bid and owner overlap are candidates, never approved mappings.",
            "No legacy candidate does not prove a missing event when identities are unresolved.",
            "Resolve schema adoption and native event grain before any database import.",
            "Resolve every legacy ID conflict before reconstruction; do not substitute native history.",
        ],
    }
    if player_resolutions is not None:
        approval = approve_player_resolutions(result, player_resolutions)
        result["approved_player_resolutions"] = approval
        result["owner_conflict_audit"] = _owner_conflict_audit(
            sources=sources,
            report=result,
            native_seasons=native_seasons,
            approved_players=approval,
            reviewed_event_identities=(
                owner_resolutions.get("event_identities", [])
                if owner_resolutions
                else []
            ),
        )
        if owner_resolutions is not None:
            result["approved_owner_resolutions"] = approve_owner_resolutions(
                result, owner_resolutions
            )
    elif owner_resolutions is not None:
        raise ValueError("Owner resolutions require validated player approvals.")
    if audit_attributes or attribute_resolutions is not None:
        if "approved_owner_resolutions" not in result:
            raise ValueError("Attribute review requires validated owner approvals.")
        result["attribute_repair_audit"] = build_attribute_audit(
            sources=sources,
            report=result,
            native_seasons=native_seasons,
            teams_path=source_root / "teams.csv",
        )
        if attribute_resolutions is not None:
            result["approved_attribute_resolutions"] = approve_attribute_resolutions(
                result, attribute_resolutions
            )
    return result


def _owner_conflict_audit(
    *,
    sources: dict[str, list[dict[str, Any]]],
    report: dict[str, Any],
    native_seasons: dict[int, dict[str, list[dict[str, str]]]],
    approved_players: dict[str, Any],
    reviewed_event_identities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Trace source owners per season without name-based or majority approval."""
    approved = {
        row["source_player_id"]: row["player_mfl_id"]
        for row in approved_players["resolved_players"]
    }
    legacy_names: dict[int, set[str]] = defaultdict(set)
    for row in sources["players.csv"]:
        name = _dedupe_normalized_name(row["PlayerName"])
        if name:
            legacy_names[_integer(row["Player_ID"])].add(name)
    owner_variants: dict[int, list[str]] = defaultdict(list)
    for number, row in enumerate(sources["users.csv"], start=2):
        owner_variants[_integer(row["OwnerID"])].append(
            f"{report['legacy_source_files_sha256']['users.csv']}:{number}"
        )
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    identity_overrides = {}
    for entry in reviewed_event_identities or []:
        number = _integer(entry["legacy_csv_row"])
        if (
            number in identity_overrides
            or number < 2
            or number > len(sources["draft_results.csv"]) + 1
            or entry.get("approved") is not True
            or entry.get("legacy_evidence_ref")
            != (f"{report['legacy_source_files_sha256']['draft_results.csv']}:{number}")
        ):
            raise ValueError(
                "Supplemental identity requires exact reviewed source evidence."
            )
        identity_overrides[number] = _source_id(entry["player_mfl_id"])
    native_by_year = {}
    for season in report["seasons"]:
        year = season["season"]
        by_name: dict[str, set[str]] = defaultdict(set)
        for row in native_seasons[year]["players"]:
            by_name[_dedupe_normalized_name(row["player_name"])].add(
                _source_id(row["player_mfl_id"])
            )
        native_by_year[year] = by_name
    for number, row in enumerate(sources["draft_results.csv"], start=2):
        year, owner = _integer(row["Year"]), _integer(row["OwnerID"])
        identifier = _integer(row["PlayerID"])
        candidates = []
        if year in native_seasons:
            native_ids = (
                {approved[identifier]}
                if identifier in approved
                else set().union(
                    *(
                        native_by_year[year].get(name, set())
                        for name in legacy_names[identifier]
                    )
                )
            )
            if number in identity_overrides:
                if (
                    identifier in approved
                    and identity_overrides[number] != approved[identifier]
                ):
                    raise ValueError(
                        "Supplemental identity conflicts with approved player resolution."
                    )
                native_ids = {identity_overrides[number]}
            season_report = next(s for s in report["seasons"] if s["season"] == year)
            candidates = [
                event
                for event in season_report["native_events"]
                if event["status"] != "blocked"
                and event["player_mfl_id"] in native_ids
                and _amount(event["winning_bid"]) == _amount(row["WinningBid"])
            ]
            if number in identity_overrides:
                catalog_ids = {
                    _source_id(player["player_mfl_id"])
                    for player in native_seasons[year]["players"]
                }
                if (
                    identity_overrides[number] not in catalog_ids
                    or len(candidates) != 1
                ):
                    raise ValueError(
                        "Supplemental identity lacks unique catalog/auction support."
                    )
        groups[(year, owner)].append(
            {
                "legacy_evidence_ref": (
                    f"{report['legacy_source_files_sha256']['draft_results.csv']}:{number}"
                ),
                "legacy_csv_row": number,
                "source_player_id": identifier,
                "candidate_native_events": [
                    {
                        key: event[key]
                        for key in (
                            "evidence_ref",
                            "player_mfl_id",
                            "franchise_id",
                            "winning_bid",
                        )
                    }
                    for event in candidates
                ],
                "status": (
                    "missing_season_evidence"
                    if year not in native_seasons
                    else (
                        "single_event_review"
                        if len(candidates) == 1
                        else ("ambiguous" if candidates else "no_candidate")
                    )
                ),
                "approved": False,
            }
        )
    seasons = []
    for (year, owner), rows in sorted(groups.items()):
        support: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            if row["status"] == "single_event_review":
                support[row["candidate_native_events"][0]["franchise_id"]].append(
                    row["legacy_evidence_ref"]
                )
        seasons.append(
            {
                "season": year,
                "source_owner_id": owner,
                "source_owner_variant_refs": owner_variants.get(owner, []),
                "draft_rows": rows,
                "status_counts": dict(Counter(row["status"] for row in rows)),
                "candidate_franchises": [
                    {"franchise_id": franchise, "supporting_legacy_refs": refs}
                    for franchise, refs in sorted(support.items())
                ],
                "status": (
                    "missing_owner_provenance"
                    if owner not in owner_variants
                    else (
                        "split_owner_evidence"
                        if len(support) > 1
                        else (
                            "season_mapping_review"
                            if len(support) == 1
                            else "no_supported_mapping"
                        )
                    )
                ),
                "approved": False,
                "resolution": None,
            }
        )
    shared = []
    for year in sorted({row["season"] for row in seasons}):
        franchise_owners: dict[str, set[int]] = defaultdict(set)
        for row in seasons:
            if row["season"] == year:
                for candidate in row["candidate_franchises"]:
                    franchise_owners[candidate["franchise_id"]].add(
                        row["source_owner_id"]
                    )
        shared.extend(
            {
                "season": year,
                "franchise_id": franchise,
                "source_owner_ids": sorted(owners),
            }
            for franchise, owners in sorted(franchise_owners.items())
            if len(owners) > 1
        )
    return {
        "season_owner_entries": seasons,
        "shared_franchise_evidence": shared,
        "legacy_owner_conflicts": [
            entry
            for entry in report["legacy_conflict_register"]
            if entry["source_file"] == "users.csv"
        ],
        "ready_for_slice_4": False,
        "ready_to_import": False,
        "method": "approved_conflicting_player_ids_or_name_candidates_and_exact_bid",
        "limitations": [
            "Names of owners are not used to approve identity or target-account mappings.",
            "A split requires explicit event-specific review, not majority replacement.",
            "Single-event/name evidence is a candidate; unresolved rows remain blockers.",
            "No cross-season owner fallback or database changes are performed.",
        ],
    }


def approve_owner_resolutions(
    report: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    audit = report["owner_conflict_audit"]
    if (
        decisions.get("approved") is not True
        or not isinstance(decisions.get("review_basis"), str)
        or not decisions["review_basis"].strip()
        or decisions.get("legacy_source_files_sha256")
        != report["legacy_source_files_sha256"]
        or decisions.get("selected_mfl_exports") != report["selected_mfl_exports"]
    ):
        raise ValueError("Owner approvals must match reviewed source hashes.")
    expected_variants = {
        variant["variant_sha256"]
        for conflict in audit["legacy_owner_conflicts"]
        for variant in conflict["variants"]
    }
    variants = decisions.get("reviewed_owner_variant_sha256", [])
    if len(variants) != len(expected_variants) or set(variants) != expected_variants:
        raise ValueError("Every conflicting owner variant requires explicit review.")
    expected = {
        (entry["season"], entry["source_owner_id"]): entry
        for entry in audit["season_owner_entries"]
    }
    mappings = {}
    for entry in decisions.get("season_owners", []):
        key = (_integer(entry["season"]), _integer(entry["source_owner_id"]))
        if key in mappings or key not in expected or entry.get("approved") is not True:
            raise ValueError(
                "Owner mappings contain unapproved, duplicate or unknown entries."
            )
        franchise = _source_id(entry["franchise_id"])
        if franchise not in {
            c["franchise_id"] for c in expected[key]["candidate_franchises"]
        }:
            raise ValueError("Owner mapping lacks same-season event evidence.")
        mappings[key] = franchise
    if set(mappings) != set(expected):
        raise ValueError("Every season-owner entry requires a reviewed mapping.")
    if len({(year, franchise) for (year, owner), franchise in mappings.items()}) != len(
        mappings
    ):
        raise ValueError(
            "Season owner mappings must not collapse distinct source owners."
        )
    exceptions = {}
    for entry in decisions.get("event_owner_exceptions", []):
        ref = entry["legacy_evidence_ref"]
        if ref in exceptions or entry.get("approved") is not True:
            raise ValueError("Event owner exceptions must be unique and approved.")
        exceptions[ref] = entry
    resolved_rows = []
    used = set()
    native_refs = set()
    for key, profile in sorted(expected.items()):
        if not profile["source_owner_variant_refs"]:
            raise ValueError("Owner provenance is missing.")
        for row in profile["draft_rows"]:
            if row["status"] != "single_event_review":
                raise ValueError("Every owner event must have unique native evidence.")
            candidate = row["candidate_native_events"][0]
            native_key = (key[0], candidate["evidence_ref"])
            if native_key in native_refs:
                raise ValueError("Multiple legacy rows claim the same native event.")
            native_refs.add(native_key)
            ref = row["legacy_evidence_ref"]
            corrected_owner = key[1]
            franchise = mappings[key]
            if ref in exceptions:
                entry = exceptions[ref]
                corrected_owner = _integer(entry["resolved_source_owner_id"])
                corrected_key = (key[0], corrected_owner)
                if corrected_key not in mappings or corrected_owner == key[1]:
                    raise ValueError(
                        "Owner exception must use a distinct reviewed same-season owner."
                    )
                franchise = mappings[corrected_key]
                if entry.get("native_evidence_ref") != candidate["evidence_ref"]:
                    raise ValueError("Owner exception native evidence is stale.")
                used.add(ref)
            if franchise != candidate["franchise_id"]:
                raise ValueError(
                    "Owner mapping conflicts with event; explicit exception required."
                )
            resolved_rows.append(
                {
                    "season": key[0],
                    "original_source_owner_id": key[1],
                    "resolved_source_owner_id": corrected_owner,
                    "franchise_id": franchise,
                    "legacy_evidence_ref": ref,
                    "native_evidence_ref": candidate["evidence_ref"],
                    "approved": True,
                }
            )
    if set(exceptions) != used:
        raise ValueError("Owner exceptions contain unknown legacy rows.")
    return {
        "owner_identity_gate": "resolved_source_season_franchises",
        "season_owners": decisions["season_owners"],
        "resolved_event_owners": resolved_rows,
        "reviewed_owner_variant_sha256": sorted(expected_variants),
        "event_identities": decisions.get("event_identities", []),
        "review_basis": decisions["review_basis"],
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "ready_for_slice_4": True,
        "ready_to_import": False,
        "scope": "legacy_source_ownership_only_not_target_accounts",
        "writes_performed_to_databases": False,
    }


def _selections(values: list[str]) -> dict[int, Path]:
    result = {}
    for value in values:
        year, separator, path = value.partition("=")
        if not separator or not path.strip():
            raise ValueError("Export selections must be YEAR=PATH.")
        season = _integer(year)
        if season in result:
            raise ValueError("Select exactly one export per season.")
        result[season] = Path(path)
    return result


def approve_player_resolutions(
    report: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    """Validate explicit human-reviewed identities against immutable source evidence."""
    if (
        decisions.get("approved") is not True
        or not isinstance(decisions.get("review_basis"), str)
        or not decisions["review_basis"].strip()
        or decisions.get("legacy_source_files_sha256")
        != report["legacy_source_files_sha256"]
        or decisions.get("selected_mfl_exports") != report["selected_mfl_exports"]
    ):
        raise ValueError(
            "Player approval must match reviewed source hashes and evidence."
        )
    entries = decisions.get("players")
    if not isinstance(entries, list):
        raise ValueError("Player approval requires a complete identity list.")
    profiles = {
        row["source_player_id"]: row for row in report["player_conflict_dispositions"]
    }
    indexed = {}
    for entry in entries:
        identifier = _integer(entry["source_player_id"])
        if identifier in indexed or identifier not in profiles:
            raise ValueError(
                "Player approval contains duplicate or unknown identities."
            )
        indexed[identifier] = entry
    if set(indexed) != set(profiles):
        raise ValueError("Every player conflict must have an explicit resolution.")
    resolved = []
    for identifier, profile in sorted(profiles.items()):
        entry = indexed[identifier]
        native_id = _source_id(entry["player_mfl_id"])
        if any(
            conflict["player_mfl_id"] == native_id
            for season in report["seasons"]
            for conflict in season["native_catalog_conflicts"]
        ):
            raise ValueError("Approved native ID has conflicting catalog identities.")
        seasonal = [
            player
            for season in report["seasons"]
            for player in season["player_conflict_audit"]
            if player["source_player_id"] == identifier
        ]
        variants = {
            variant["variant_sha256"]
            for player in seasonal
            for variant in player["variants"]
        }
        reviewed_variants = entry.get("reviewed_variant_sha256")
        if (
            not isinstance(reviewed_variants, list)
            or len(reviewed_variants) != len(variants)
            or set(reviewed_variants) != variants
            or entry.get("aliases_reviewed") is not True
            or profile["uncovered_legacy_rows"]
        ):
            raise ValueError("All player variants and affected seasons require review.")
        catalog = [
            candidate
            for player in seasonal
            for variant in player["variants"]
            for candidate in variant["candidate_native_catalog"]
            if candidate["player_mfl_id"] == native_id
        ]
        # Explicit native position distinguishes defense from similarly named team aggregates.
        position = entry.get("native_position")
        catalog = [
            candidate
            for candidate in catalog
            if candidate["native_position"] == position
        ]
        if not catalog or not position:
            raise ValueError(
                "Approved native identity/position lacks catalog evidence."
            )
        events = [
            event for player in seasonal for event in player["affected_draft_rows"]
        ]
        for event in events:
            candidates = event["candidate_native_events"]
            if (
                event["status"] != "single_event_review"
                or len(candidates) != 1
                or candidates[0]["player_mfl_id"] != native_id
                or candidates[0]["native_position"] != position
            ):
                raise ValueError(
                    "Approved identity conflicts with affected event evidence."
                )
        resolved.append(
            {
                "source_player_id": identifier,
                "player_mfl_id": native_id,
                "native_position": position,
                "reviewed_variant_sha256": sorted(variants),
                "catalog_evidence_refs": sorted(
                    {candidate["evidence_ref"] for candidate in catalog}
                ),
                "legacy_event_refs": sorted(
                    {event["legacy_evidence_ref"] for event in events}
                ),
                "native_event_refs": sorted(
                    {
                        event["candidate_native_events"][0]["evidence_ref"]
                        for event in events
                    }
                ),
                "approved": True,
                "scope": "legacy_player_identity_only",
            }
        )
    return {
        "player_identity_gate": "resolved",
        "resolved_players": resolved,
        "review_basis": decisions["review_basis"],
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "ready_for_slice_3": True,
        "ready_to_import": False,
        "writes_performed_to_databases": False,
        "remaining_gates": [
            "season-owner identity approval",
            "position/team attribute repair",
            "event reconciliation",
            "schema/runtime adoption",
            "target player mapping",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument(
        "--season-export", action="append", required=True, metavar="YEAR=ROOT"
    )
    parser.add_argument(
        "--draft-export", action="append", default=[], metavar="YEAR=CSV"
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--player-resolutions", type=Path)
    parser.add_argument("--owner-resolutions", type=Path)
    parser.add_argument("--audit-attributes", action="store_true")
    parser.add_argument("--attribute-resolutions", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("--output already exists; choose a new evidence file.")
    try:
        decisions = (
            json.loads(args.player_resolutions.read_text(encoding="utf-8"))
            if args.player_resolutions
            else None
        )
        report = run_source_reconciliation(
            source_root=args.source_root,
            season_exports=_selections(args.season_export),
            draft_exports=_selections(args.draft_export),
            player_resolutions=decisions,
            owner_resolutions=(
                json.loads(args.owner_resolutions.read_text(encoding="utf-8"))
                if args.owner_resolutions
                else None
            ),
            audit_attributes=args.audit_attributes,
            attribute_resolutions=(
                json.loads(args.attribute_resolutions.read_text(encoding="utf-8"))
                if args.attribute_resolutions
                else None
            ),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError, csv.Error) as error:
        print(
            f"ERROR: source reconciliation failed ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1
    if args.attribute_resolutions:
        print(f"Reviewed attribute resolutions saved: {args.output}")
        print("Slice 5 ready; target mappings, schema and imports remain BLOCKED.")
    elif args.audit_attributes:
        print(f"Unapproved attribute repair worksheet saved: {args.output}")
        print("BLOCKED: row-specific attribute repairs require explicit approval.")
    elif args.owner_resolutions:
        print(f"Reviewed source-owner resolutions saved: {args.output}")
        print("Slice 4 ready; target-account mappings and imports remain BLOCKED.")
    elif args.player_resolutions:
        print(f"Reviewed player identity resolutions saved: {args.output}")
        print(
            "Slice 3 ready; imports remain BLOCKED by the remaining remediation gates."
        )
    else:
        print(f"Unapproved source repair worksheet saved: {args.output}")
        print("BLOCKED: source candidates require identity and event-grain review.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
