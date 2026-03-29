# backend/services/waiver_service.py
from .. import models
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import UTC, datetime
from .ledger_service import owner_balance, record_ledger_entry
from .validation_service import (
    validate_waiver_claim_boundary,
    validate_waiver_claim_dynamic_rules,
)


def _validate_commissioner_waiver_rules(db: Session, user: models.User) -> int:
    settings = (
        db.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == user.league_id)
        .first()
    )

    roster_limit = settings.roster_size if settings and settings.roster_size else 14

    if settings and settings.waiver_deadline:
        raw_deadline = settings.waiver_deadline.strip()
        try:
            parsed_deadline = datetime.fromisoformat(raw_deadline.replace("Z", "+00:00"))
            now = datetime.now(parsed_deadline.tzinfo) if parsed_deadline.tzinfo else datetime.now()
            if now > parsed_deadline:
                raise HTTPException(
                    status_code=400,
                    detail=f"Waiver claims are closed by commissioner rule (deadline: {settings.waiver_deadline}).",
                )
        except ValueError:
            pass

    return roster_limit


def process_claim(db: Session, user: models.User, player_id: int, bid: int, drop_id: int = None, team_id: int | None = None):
    boundary_report = validate_waiver_claim_boundary(
        {
            "player_id": player_id,
            "bid_amount": bid,
            "drop_player_id": drop_id,
            "team_id": team_id,
        }
    )
    if not boundary_report.valid:
        raise HTTPException(status_code=400, detail=boundary_report.errors)

    dynamic_report = validate_waiver_claim_dynamic_rules(
        {
            "player_id": player_id,
            "bid_amount": bid,
            "drop_player_id": drop_id,
            "team_id": team_id,
        }
    )
    if not dynamic_report.valid:
        raise HTTPException(status_code=400, detail=dynamic_report.errors)

    # 1.1 VALIDATION: Check for League ID
    if not user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league.")
    # optional team_id is for debugging/diagnostics
    if team_id and team_id != user.id:
        # log mismatch, but don't fail the claim
        print(f"WARNING: waiver claim team_id {team_id} does not match user.id {user.id}")

    league = db.query(models.League).filter(models.League.id == user.league_id).first()
    if league and (league.draft_status or "PRE_DRAFT") == "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="Waiver wire is locked while the draft is active.",
        )

    roster_limit = _validate_commissioner_waiver_rules(db, user)

    if bid < 0:
        raise HTTPException(status_code=400, detail="Bid must be non-negative.")

    owner_total_incoming = (
        db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0))
        .filter(
            models.EconomicLedger.league_id == user.league_id,
            models.EconomicLedger.currency_type == "FAAB",
            models.EconomicLedger.to_owner_id == user.id,
        )
        .scalar()
    )

    if int(owner_total_incoming or 0) > 0:
        remaining_faab = owner_balance(
            db,
            league_id=user.league_id,
            owner_id=user.id,
            currency_type="FAAB",
        )
        if bid > remaining_faab:
            raise HTTPException(status_code=400, detail="Insufficient FAAB balance.")
    else:
        waiver_budget = (
            db.query(models.WaiverBudget)
            .filter(
                models.WaiverBudget.league_id == user.league_id,
                models.WaiverBudget.owner_id == user.id,
            )
            .first()
        )
        if waiver_budget and bid > int(waiver_budget.remaining_budget or 0):
            raise HTTPException(status_code=400, detail="Insufficient FAAB balance.")

    # 1.2 VALIDATION: Is target player already taken?
    existing = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.league_id == user.league_id 
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player already owned!")

    # 2.1 CONDITIONAL DROP: If drop_id is provided, remove them first
    if drop_id:
        pick_to_drop = db.query(models.DraftPick).filter(
            models.DraftPick.player_id == drop_id,
            models.DraftPick.owner_id == user.id,
            models.DraftPick.league_id == user.league_id
        ).first()
        
        if not pick_to_drop:
            raise HTTPException(status_code=404, detail="Player to drop not found on your roster.")
        
        db.delete(pick_to_drop)
        # We don't commit yet; keep it in the same transaction
    
    # 2.2 ROSTER LIMIT CHECK: Only check if NOT dropping someone
    else:
        roster_count = db.query(models.DraftPick).filter(
            models.DraftPick.owner_id == user.id,
            models.DraftPick.league_id == user.league_id
        ).count()
        if roster_count >= roster_limit:
            raise HTTPException(status_code=400, detail="Roster full! Select a player to drop.")

    # 3.1 EXECUTION: Create pick record
    new_pick = models.DraftPick(
        owner_id=user.id,
        player_id=player_id,
        amount=bid,
        session_id="WAIVER_WIRE",
        year=2026,
        league_id=user.league_id
    )
    
    db.add(new_pick)
    db.flush()

    # record transaction history for the acquisition
    from .transaction_service import log_transaction

    log_transaction(
        db,
        league_id=user.league_id,
        player_id=player_id,
        old_owner_id=None,
        new_owner_id=user.id,
        transaction_type="waiver_add",
        notes=f"waiver claim bid={bid}",
    )
    if drop_id:
        log_transaction(
            db,
            league_id=user.league_id,
            player_id=drop_id,
            old_owner_id=user.id,
            new_owner_id=None,
            transaction_type="waiver_drop",
            notes="auto-drop from waiver claim",
        )

    if bid > 0:
        now_year = datetime.now(UTC).year
        season_year = now_year
        settings = (
            db.query(models.LeagueSettings)
            .filter(models.LeagueSettings.league_id == user.league_id)
            .first()
        )
        if settings and settings.draft_year:
            season_year = int(settings.draft_year)

        record_ledger_entry(
            db,
            league_id=user.league_id,
            season_year=season_year,
            currency_type="FAAB",
            amount=int(bid),
            from_owner_id=user.id,
            to_owner_id=None,
            transaction_type="WAIVER_CLAIM_BID",
            reference_type="DRAFT_PICK",
            reference_id=str(new_pick.id),
            notes=f"waiver claim bid for player_id={player_id}",
            created_by_user_id=user.id,
        )

    db.commit()
    db.refresh(new_pick)

    return new_pick

def process_drop(db: Session, user: models.User, player_id: int):
    league = db.query(models.League).filter(models.League.id == user.league_id).first()
    if league and (league.draft_status or "PRE_DRAFT") == "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="Waiver wire is locked while the draft is active.",
        )

    # (Keep your existing process_drop logic here)
    pick = db.query(models.DraftPick).filter(
        models.DraftPick.player_id == player_id,
        models.DraftPick.owner_id == user.id,
        models.DraftPick.league_id == user.league_id
    ).first()

    if not pick:
        raise HTTPException(status_code=404, detail="Player not on roster.")

    db.delete(pick)
    db.commit()

    # record history of manual drop
    from .transaction_service import log_transaction
    log_transaction(
        db,
        league_id=user.league_id,
        player_id=player_id,
        old_owner_id=user.id,
        new_owner_id=None,
        transaction_type="drop",
        notes="manual roster drop",
    )

    return True