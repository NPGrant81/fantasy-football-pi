"""Offline, row-specific attribute proposals; never rewrite retained history."""

from collections import Counter, defaultdict
import csv
import hashlib
import io
from pathlib import Path
from typing import Any

from backend.scripts.reconcile_ppl_history import _integer, _position, _position_id


def _taxonomy_position(value: str) -> str:
    return {"TD": "DST", "KICKER": "K"}.get(_position(value), _position(value))


def build_attribute_audit(
    *,
    sources: dict[str, list[dict[str, Any]]],
    report: dict[str, Any],
    native_seasons: dict[int, dict[str, list[dict[str, str]]]],
    teams_path: Path,
) -> dict[str, Any]:
    raw = teams_path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("ISO-8859-1"), newline=""))
    if not {"Team", "TeamID"} <= set(reader.fieldnames or ()):
        raise ValueError("Team taxonomy is missing required columns.")
    teams: dict[int, set[str]] = defaultdict(set)
    team_ids: dict[str, set[int]] = defaultdict(set)
    team_refs: dict[int, list[str]] = defaultdict(list)
    team_hash = hashlib.sha256(raw).hexdigest()
    for number, row in enumerate(reader, start=2):
        if None in row or not row.get("Team") or row.get("TeamID") is None:
            raise ValueError("Team taxonomy has a malformed row.")
        identifier, label = _integer(row["TeamID"]), row["Team"].strip().upper()
        if not label:
            raise ValueError("Team taxonomy has an empty label.")
        teams[identifier].add(label)
        team_ids[label].add(identifier)
        team_refs[identifier].append(f"{team_hash}:{number}")
    if any(len(ids) != 1 for ids in team_ids.values()):
        raise ValueError("Team taxonomy has ambiguous label identifiers.")

    hashes = report["legacy_source_files_sha256"]
    taxonomy = []
    positions: dict[int, set[str]] = defaultdict(set)
    for number, row in enumerate(sources["positions.csv"], start=2):
        canonical = _taxonomy_position(row["Position"])
        positions[_integer(row["PositionID"])].add(canonical)
        taxonomy.append(
            {
                "legacy_evidence_ref": f"{hashes['positions.csv']}:{number}",
                "original_label": row["Position"],
                "position": canonical,
            }
        )
    supported_positions = {"QB", "RB", "WR", "TE", "DST", "K", "FB"}
    taxonomy_blockers = [
        row for row in taxonomy if row["position"] not in supported_positions
    ]
    taxonomy_blockers.extend(
        {"source_position_id": key}
        for key, values in positions.items()
        if len(values) != 1
    )
    native_events = {
        (season["season"], event["evidence_ref"]): event
        for season in report["seasons"]
        for event in season["native_events"]
    }
    catalog: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    export_hashes = {
        (entry["season"], entry["report"]): entry["sha256"]
        for entry in report["selected_mfl_exports"]
    }
    for year, exports in native_seasons.items():
        for number, row in enumerate(exports["players"], start=2):
            catalog[(year, row["player_mfl_id"])].append(
                {
                    "position": _position(row["position"]),
                    "nfl_team": (row.get("nfl_team") or "").strip().upper(),
                    "evidence_ref": f"{export_hashes[(year, 'players')]}:{number}",
                    "extracted_at_utc": row["extracted_at_utc"],
                }
            )
    owners = {
        row["legacy_evidence_ref"]: row
        for row in report["approved_owner_resolutions"]["resolved_event_owners"]
    }
    identity_positions: dict[int, dict[int, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    identity_refs: dict[int, set[str]] = defaultdict(set)
    drafts = []
    for number, row in enumerate(sources["draft_results.csv"], start=2):
        ref = f"{hashes['draft_results.csv']}:{number}"
        owner = owners[ref]
        year = _integer(row["Year"])
        event = native_events[(year, owner["native_evidence_ref"])]
        observations = catalog[(year, event["player_mfl_id"])]
        attributes = {(r["position"], r["nfl_team"]) for r in observations}
        unique = len(attributes) == 1
        position, team = next(iter(attributes)) if unique else ("", "")
        source_position = _position_id(row["PositionID"])
        source_team = _position_id(row["TeamID"])
        valid_team = source_team in teams
        candidate_teams = team_ids.get(team, set())
        team_differs = valid_team and team not in teams[source_team]
        retain_team = valid_team and not team_differs
        resolved_team = (
            source_team
            if retain_team
            else (next(iter(candidate_teams)) if len(candidate_teams) == 1 else None)
        )
        position_basis = (
            "retain"
            if positions.get(source_position) == {position}
            else ("repair_missing" if source_position is None else "repair_mismatch")
        )
        team_basis = (
            "retain_legacy"
            if retain_team
            else "season_catalog_snapshot_not_auction_time"
        )
        blocked = (
            not unique or position not in supported_positions or resolved_team is None
        )
        identifier = _integer(row["PlayerID"])
        if not blocked:
            identity_positions[identifier][year].add(position)
            identity_refs[identifier].update(r["evidence_ref"] for r in observations)
        drafts.append(
            {
                "legacy_evidence_ref": ref,
                "season": year,
                "source_player_id": identifier,
                "native_evidence_ref": owner["native_evidence_ref"],
                "player_mfl_id": event["player_mfl_id"],
                "original_position_id": row["PositionID"],
                "original_team_id": row["TeamID"],
                "position_basis": position_basis,
                "team_basis": team_basis,
                "legacy_team_labels": sorted(teams.get(source_team, set())),
                "team_catalog_differs": team_differs,
                "native_catalog_observations": observations,
                "team_taxonomy_refs": team_refs.get(resolved_team, []),
                "proposal": {
                    "legacy_evidence_ref": ref,
                    "native_evidence_ref": owner["native_evidence_ref"],
                    "player_mfl_id": event["player_mfl_id"],
                    "native_catalog_refs": [r["evidence_ref"] for r in observations],
                    "position": position,
                    "source_team_id": resolved_team,
                    "team_basis": team_basis,
                },
                "status": "blocked" if blocked else "review_required",
                "approved": False,
            }
        )
    for player in report["approved_player_resolutions"]["resolved_players"]:
        identifier = player["source_player_id"]
        for (year, native_id), observations in catalog.items():
            if native_id == player["player_mfl_id"]:
                identity_positions[identifier][year].update(
                    r["position"] for r in observations
                )
                identity_refs[identifier].update(
                    r["evidence_ref"] for r in observations
                )
    catalog_rows = []
    for number, row in enumerate(sources["players.csv"], start=2):
        identifier = _integer(row["Player_ID"])
        native_positions = identity_positions.get(identifier, {})
        seasonal = [
            {"season": year, "position": next(iter(values))}
            for year, values in sorted(native_positions.items())
            if len(values) == 1 and values <= supported_positions
        ]
        blocked = len(seasonal) != len(native_positions)
        canonical = {entry["position"] for entry in seasonal}
        original = positions.get(_position_id(row["PositionID"]))
        catalog_rows.append(
            {
                "legacy_evidence_ref": f"{hashes['players.csv']}:{number}",
                "source_player_id": identifier,
                "original_position_id": row["PositionID"],
                "native_catalog_refs": sorted(identity_refs.get(identifier, set())),
                "proposal": (
                    {
                        "legacy_evidence_ref": f"{hashes['players.csv']}:{number}",
                        "season_positions": seasonal,
                        "native_catalog_refs": sorted(
                            identity_refs.get(identifier, set())
                        ),
                    }
                    if native_positions and not blocked
                    else None
                ),
                "status": (
                    "outside_reviewed_identity_scope"
                    if not native_positions
                    else (
                        "blocked"
                        if blocked
                        else (
                            "season_specific_positions"
                            if len(canonical) > 1
                            else (
                                "retain" if original == canonical else "repair_mismatch"
                            )
                        )
                    )
                ),
                "approved": False,
            }
        )
    return {
        "teams_sha256": team_hash,
        "taxonomy_proposals": taxonomy,
        "taxonomy_blockers": taxonomy_blockers,
        "draft_rows": drafts,
        "catalog_rows": catalog_rows,
        "draft_status_counts": dict(Counter(r["status"] for r in drafts)),
        "position_basis_counts": dict(Counter(r["position_basis"] for r in drafts)),
        "team_basis_counts": dict(Counter(r["team_basis"] for r in drafts)),
        "catalog_status_counts": dict(Counter(r["status"] for r in catalog_rows)),
        "ready_for_approval": (
            not taxonomy_blockers
            and all(r["status"] != "blocked" for r in drafts + catalog_rows)
        ),
        "approved": False,
        "ready_for_slice_5": False,
        "ready_to_import": False,
        "limitations": [
            "Season catalogs are snapshots, not proof of NFL team at auction time.",
            "Team repairs require explicit snapshot attribution review, not an auction-time claim.",
            "Original team IDs and labels survive all repair proposals.",
            "Catalog position resolutions are season-specific, never a global current-position rewrite.",
            "Unlinked catalog rows are preserved outside the reviewed identity scope.",
            "Taxonomy aliases do not authorize a global draft position-ID rewrite.",
        ],
    }


def approve_attribute_resolutions(
    report: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    audit = report["attribute_repair_audit"]
    if (
        decisions.get("approved") is not True
        or not isinstance(decisions.get("review_basis"), str)
        or not decisions["review_basis"].strip()
        or decisions.get("legacy_source_files_sha256")
        != report["legacy_source_files_sha256"]
        or decisions.get("selected_mfl_exports") != report["selected_mfl_exports"]
        or decisions.get("teams_sha256") != audit["teams_sha256"]
    ):
        raise ValueError("Attribute approvals must match reviewed source hashes.")
    if not audit["ready_for_approval"]:
        raise ValueError("Unresolved attribute evidence blocks approval.")
    expected = {
        "taxonomy": audit["taxonomy_proposals"],
        "draft_rows": [row["proposal"] for row in audit["draft_rows"]],
        "catalog_positions": [
            row["proposal"] for row in audit["catalog_rows"] if row["proposal"]
        ],
    }
    if any(decisions.get(key) != rows for key, rows in expected.items()):
        raise ValueError("Every attribute proposal requires exact row-specific review.")
    return {
        **expected,
        "review_basis": decisions["review_basis"],
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "teams_sha256": audit["teams_sha256"],
        "ready_for_slice_5": True,
        "ready_to_import": False,
        "scope": "reviewed_draft_attributes_and_linked_catalog_positions_only",
        "writes_performed_to_databases": False,
    }
