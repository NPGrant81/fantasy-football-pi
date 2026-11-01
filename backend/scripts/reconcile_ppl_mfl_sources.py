"""Build an unapproved, offline PPL repair worksheet from selected MFL exports."""

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
from backend.scripts.reconcile_ppl_history import (
    _amount,
    _index,
    _integer,
    _label,
    _position,
    _position_id,
    _read_sources,
)
from backend.services.player_service import normalize_display_name

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
) -> dict[str, Any]:
    if not season_exports or set(draft_exports) - set(season_exports):
        raise ValueError("Select season exports before any draft override.")
    sources, hashes = _read_sources(source_root)
    reports = []
    selected = []
    for season, root in sorted(season_exports.items()):
        if season not in KNOWN_LEAGUE_BY_SEASON:
            raise ValueError("Season has no verified MFL league mapping.")
        rows = {}
        draft_hash = ""
        for report in HEADERS:
            path = (
                draft_exports[season]
                if report == "draftResults" and season in draft_exports
                else root / report / f"{season}.csv"
            )
            rows[report], digest = _read_export(path, report, season)
            selected.append({"season": season, "report": report, "sha256": digest})
            if report == "draftResults":
                draft_hash = digest
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
    return {
        "writes_performed_to_databases": False,
        "api_requests_sent": 0,
        "ready_to_import": False,
        "legacy_source_files_sha256": hashes,
        "legacy_conflict_register": _legacy_conflict_register(sources, hashes),
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
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("--output already exists; choose a new evidence file.")
    try:
        report = run_source_reconciliation(
            source_root=args.source_root,
            season_exports=_selections(args.season_export),
            draft_exports=_selections(args.draft_export),
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
    print(f"Unapproved source repair worksheet saved: {args.output}")
    print("BLOCKED: source candidates require identity and event-grain review.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
