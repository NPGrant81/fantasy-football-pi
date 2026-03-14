from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..core.security import get_current_user
from ..database import get_db

router = APIRouter(prefix="/leagues", tags=["Ledger"])


class LedgerEntryOut(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    transaction_type: str
    direction: str
    amount: int
    currency_type: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None


class LedgerStatementOut(BaseModel):
    owner_id: int
    balance: int
    entries: List[LedgerEntryOut]


@router.get("/{league_id}/ledger/statement", response_model=LedgerStatementOut)
def get_ledger_statement(
    league_id: int,
    owner_id: Optional[int] = Query(None),
    currency_type: Optional[str] = Query(None),
    season_year: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if int(current_user.league_id or 0) != int(league_id):
        raise HTTPException(status_code=403, detail="Not authorised for this league")

    effective_owner_id = int(owner_id or current_user.id)
    if effective_owner_id != int(current_user.id) and not current_user.is_commissioner:
        raise HTTPException(status_code=403, detail="Commissioner access required")

    target_owner = (
        db.query(models.User)
        .filter(
            models.User.id == effective_owner_id,
            models.User.league_id == league_id,
        )
        .first()
    )
    if not target_owner:
        raise HTTPException(status_code=404, detail="Owner not found in league")

    query = db.query(models.EconomicLedger).filter(
        models.EconomicLedger.league_id == league_id,
        or_(
            models.EconomicLedger.from_owner_id == effective_owner_id,
            models.EconomicLedger.to_owner_id == effective_owner_id,
        ),
    )

    if currency_type:
        query = query.filter(models.EconomicLedger.currency_type == currency_type)
    if season_year is not None:
        query = query.filter(models.EconomicLedger.season_year == season_year)

    rows = (
        query.order_by(
            models.EconomicLedger.created_at.desc(),
            models.EconomicLedger.id.desc(),
        )
        .limit(limit)
        .all()
    )

    balance = 0
    entries: List[LedgerEntryOut] = []
    for row in rows:
        is_credit = int(row.to_owner_id or 0) == effective_owner_id
        if is_credit:
            balance += int(row.amount or 0)
        else:
            balance -= int(row.amount or 0)
        entries.append(
            LedgerEntryOut(
                id=row.id,
                created_at=row.created_at,
                transaction_type=row.transaction_type,
                direction="credit" if is_credit else "debit",
                amount=int(row.amount or 0),
                currency_type=row.currency_type,
                reference_type=row.reference_type,
                reference_id=row.reference_id,
                notes=row.notes,
            )
        )

    return LedgerStatementOut(
        owner_id=effective_owner_id,
        balance=balance,
        entries=entries,
    )