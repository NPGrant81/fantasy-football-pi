"""Audit and optionally clean duplicate players from the database.

Usage examples (from repo root):
  python -m backend.manage audit-player-duplicates
  python -m backend.manage audit-player-duplicates --fail-on-duplicates
  python -m backend.manage audit-player-duplicates --apply
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend import models
from backend import models_draft_value as dv_models
from backend.database import SessionLocal
from backend.services import player_service

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


@dataclass
class DuplicateGroup:
    key: tuple[Any, ...]
    keep_id: int
    duplicate_ids: list[int]


def _query_players(db: Session) -> list[models.Player]:
    return (
        db.query(models.Player)
        .filter(models.Player.position.in_(ALLOWED_POSITIONS))
        .order_by(models.Player.id.asc())
        .all()
    )


def _find_duplicate_groups(players: list[models.Player]) -> list[DuplicateGroup]:
    grouped: dict[tuple[Any, ...], list[models.Player]] = {}
    for player in players:
        key = player_service.canonical_player_key(player)
        grouped.setdefault(key, []).append(player)

    duplicates: list[DuplicateGroup] = []
    for key, group in grouped.items():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=player_service.canonical_player_rank, reverse=True)
        keep = ranked[0]
        drop = [row.id for row in ranked[1:] if row.id is not None]
        if keep.id is None or not drop:
            continue
        duplicates.append(DuplicateGroup(key=key, keep_id=keep.id, duplicate_ids=drop))

    return sorted(duplicates, key=lambda row: len(row.duplicate_ids), reverse=True)


def _reference_counts(db: Session, player_id: int) -> dict[str, int]:
    checks = {
        "draft_picks.player_id": lambda: db.query(func.count(models.DraftPick.id))
        .filter(models.DraftPick.player_id == player_id)
        .scalar(),
        "keepers.player_id": lambda: db.query(func.count(models.Keeper.id))
        .filter(models.Keeper.player_id == player_id)
        .scalar(),
        "waiver_claims.player_id": lambda: db.query(func.count(models.WaiverClaim.id))
        .filter(models.WaiverClaim.player_id == player_id)
        .scalar(),
        "waiver_claims.drop_player_id": lambda: db.query(func.count(models.WaiverClaim.id))
        .filter(models.WaiverClaim.drop_player_id == player_id)
        .scalar(),
        "transaction_history.player_id": lambda: db.query(func.count(models.TransactionHistory.id))
        .filter(models.TransactionHistory.player_id == player_id)
        .scalar(),
        "player_weekly_stats.player_id": lambda: db.query(func.count(models.PlayerWeeklyStat.id))
        .filter(models.PlayerWeeklyStat.player_id == player_id)
        .scalar(),
        "trade_proposals.offered_player_id": lambda: db.query(func.count(models.TradeProposal.id))
        .filter(models.TradeProposal.offered_player_id == player_id)
        .scalar(),
        "trade_proposals.requested_player_id": lambda: db.query(func.count(models.TradeProposal.id))
        .filter(models.TradeProposal.requested_player_id == player_id)
        .scalar(),
        "manual_player_mappings.player_id": lambda: db.query(func.count(models.ManualPlayerMapping.id))
        .filter(models.ManualPlayerMapping.player_id == player_id)
        .scalar(),
        "player_id_mappings.player_id": lambda: db.query(func.count(dv_models.PlayerIDMapping.id))
        .filter(dv_models.PlayerIDMapping.player_id == player_id)
        .scalar(),
        "platform_projections.player_id": lambda: db.query(func.count(dv_models.PlatformProjection.id))
        .filter(dv_models.PlatformProjection.player_id == player_id)
        .scalar(),
        "draft_values.player_id": lambda: db.query(func.count(dv_models.DraftValue.id))
        .filter(dv_models.DraftValue.player_id == player_id)
        .scalar(),
    }

    counts: dict[str, int] = {}
    for label, operation in checks.items():
        try:
            with db.begin_nested():
                counts[label] = int(operation() or 0)
        except SQLAlchemyError:
            # Schema drift: keep report running and mark the reference as unavailable.
            counts[label] = -1

    return counts


def _delete_conflicting_unique_rows(db: Session, keep_id: int, duplicate_id: int) -> dict[str, int]:
    keep_weekly = aliased(models.PlayerWeeklyStat)
    dup_weekly = aliased(models.PlayerWeeklyStat)

    deleted_weekly = (
        db.query(dup_weekly)
        .filter(dup_weekly.player_id == duplicate_id)
        .filter(
            exists()
            .where(keep_weekly.player_id == keep_id)
            .where(keep_weekly.season == dup_weekly.season)
            .where(keep_weekly.week == dup_weekly.week)
            .where(keep_weekly.source == dup_weekly.source)
        )
        .delete(synchronize_session=False)
    )

    keep_dv = aliased(dv_models.DraftValue)
    dup_dv = aliased(dv_models.DraftValue)

    deleted_draft_values = (
        db.query(dup_dv)
        .filter(dup_dv.player_id == duplicate_id)
        .filter(
            exists()
            .where(keep_dv.player_id == keep_id)
            .where(keep_dv.season == dup_dv.season)
        )
        .delete(synchronize_session=False)
    )

    return {
        "player_weekly_stats": int(deleted_weekly or 0),
        "draft_values": int(deleted_draft_values or 0),
    }


def _merge_duplicate_player(db: Session, keep_id: int, duplicate_id: int) -> dict[str, int]:
    conflicts = _delete_conflicting_unique_rows(db, keep_id, duplicate_id)

    updates = {
        "draft_picks.player_id": lambda: db.query(models.DraftPick)
        .filter(models.DraftPick.player_id == duplicate_id)
        .update({models.DraftPick.player_id: keep_id}, synchronize_session=False),
        "keepers.player_id": lambda: db.query(models.Keeper)
        .filter(models.Keeper.player_id == duplicate_id)
        .update({models.Keeper.player_id: keep_id}, synchronize_session=False),
        "waiver_claims.player_id": lambda: db.query(models.WaiverClaim)
        .filter(models.WaiverClaim.player_id == duplicate_id)
        .update({models.WaiverClaim.player_id: keep_id}, synchronize_session=False),
        "waiver_claims.drop_player_id": lambda: db.query(models.WaiverClaim)
        .filter(models.WaiverClaim.drop_player_id == duplicate_id)
        .update({models.WaiverClaim.drop_player_id: keep_id}, synchronize_session=False),
        "transaction_history.player_id": lambda: db.query(models.TransactionHistory)
        .filter(models.TransactionHistory.player_id == duplicate_id)
        .update({models.TransactionHistory.player_id: keep_id}, synchronize_session=False),
        "player_weekly_stats.player_id": lambda: db.query(models.PlayerWeeklyStat)
        .filter(models.PlayerWeeklyStat.player_id == duplicate_id)
        .update({models.PlayerWeeklyStat.player_id: keep_id}, synchronize_session=False),
        "trade_proposals.offered_player_id": lambda: db.query(models.TradeProposal)
        .filter(models.TradeProposal.offered_player_id == duplicate_id)
        .update({models.TradeProposal.offered_player_id: keep_id}, synchronize_session=False),
        "trade_proposals.requested_player_id": lambda: db.query(models.TradeProposal)
        .filter(models.TradeProposal.requested_player_id == duplicate_id)
        .update({models.TradeProposal.requested_player_id: keep_id}, synchronize_session=False),
        "manual_player_mappings.player_id": lambda: db.query(models.ManualPlayerMapping)
        .filter(models.ManualPlayerMapping.player_id == duplicate_id)
        .update({models.ManualPlayerMapping.player_id: keep_id}, synchronize_session=False),
        "player_id_mappings.player_id": lambda: db.query(dv_models.PlayerIDMapping)
        .filter(dv_models.PlayerIDMapping.player_id == duplicate_id)
        .update({dv_models.PlayerIDMapping.player_id: keep_id}, synchronize_session=False),
        "platform_projections.player_id": lambda: db.query(dv_models.PlatformProjection)
        .filter(dv_models.PlatformProjection.player_id == duplicate_id)
        .update({dv_models.PlatformProjection.player_id: keep_id}, synchronize_session=False),
        "draft_values.player_id": lambda: db.query(dv_models.DraftValue)
        .filter(dv_models.DraftValue.player_id == duplicate_id)
        .update({dv_models.DraftValue.player_id: keep_id}, synchronize_session=False),
    }

    updated: dict[str, int] = {}
    for label, operation in updates.items():
        try:
            with db.begin_nested():
                updated[label] = int(operation() or 0)
        except SQLAlchemyError:
            updated[label] = -1

    deleted_players = (
        db.query(models.Player)
        .filter(models.Player.id == duplicate_id)
        .delete(synchronize_session=False)
    )

    updated = {key: int(value or 0) for key, value in updated.items()}
    updated["players.deleted"] = int(deleted_players or 0)
    updated["player_weekly_stats.conflicts_deleted"] = conflicts["player_weekly_stats"]
    updated["draft_values.conflicts_deleted"] = conflicts["draft_values"]
    return updated


def run_audit(*, apply_changes: bool = False, fail_on_duplicates: bool = False, json_output: str | None = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        players = _query_players(db)
        duplicate_groups = _find_duplicate_groups(players)

        report_groups: list[dict[str, Any]] = []
        merged = 0
        moved = 0

        for group in duplicate_groups:
            duplicate_details = []
            for dup_id in group.duplicate_ids:
                duplicate_details.append(
                    {
                        "player_id": dup_id,
                        "references": _reference_counts(db, dup_id),
                    }
                )

            group_report: dict[str, Any] = {
                "key": [str(part) for part in group.key],
                "keep_id": group.keep_id,
                "duplicates": duplicate_details,
            }

            if apply_changes:
                group_report["actions"] = []
                for dup_id in group.duplicate_ids:
                    actions = _merge_duplicate_player(db, group.keep_id, dup_id)
                    group_report["actions"].append({"duplicate_id": dup_id, "changes": actions})
                    merged += 1
                    moved += sum(actions.values())

            report_groups.append(group_report)

        if apply_changes:
            db.commit()

        summary = {
            "total_players_checked": len(players),
            "duplicate_groups": len(duplicate_groups),
            "duplicate_rows": sum(len(group.duplicate_ids) for group in duplicate_groups),
            "apply_changes": apply_changes,
            "rows_merged": merged,
            "rows_touched": moved,
            "groups": report_groups,
        }

        if json_output:
            output_path = Path(json_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
