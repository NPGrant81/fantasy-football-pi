# backend/services/waiver_service.py
from .. import models
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
import models


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


def process_claim(db: Session, user: models.User, player_id: int, bid: int, drop_id: int = None):
    # 1.1 VALIDATION: Check for League ID
    if not user.league_id:
        raise HTTPException(status_code=400, detail="User not in a league.")

    league = db.query(models.League).filter(models.League.id == user.league_id).first()
    if league and (league.draft_status or "PRE_DRAFT") == "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="Waiver wire is locked while the draft is active.",
        )

    roster_limit = _validate_commissioner_waiver_rules(db, user)

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
    db.commit()
    db.refresh(new_pick)

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