from sqlalchemy import func, case
from sqlalchemy.orm import Session

from .. import models


def record_ledger_entry(
    db: Session,
    *,
    league_id: int,
    currency_type: str,
    amount: int,
    transaction_type: str,
    season_year: int | None = None,
    from_owner_id: int | None = None,
    to_owner_id: int | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    notes: str | None = None,
    metadata_json: dict | None = None,
    created_by_user_id: int | None = None,
) -> models.EconomicLedger:
    if amount <= 0:
        raise ValueError("amount must be a positive integer")

    entry = models.EconomicLedger(
        league_id=league_id,
        season_year=season_year,
        currency_type=currency_type,
        amount=int(amount),
        from_owner_id=from_owner_id,
        to_owner_id=to_owner_id,
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        metadata_json=metadata_json,
        created_by_user_id=created_by_user_id,
    )
    db.add(entry)
    db.flush()
    return entry


def owner_balance(
    db: Session,
    *,
    league_id: int,
    owner_id: int,
    currency_type: str,
    season_year: int | None = None,
) -> int:
    query = db.query(
        func.coalesce(
            func.sum(
                case(
                    (models.EconomicLedger.to_owner_id == owner_id, models.EconomicLedger.amount),
                    else_=0,
                )
                - case(
                    (models.EconomicLedger.from_owner_id == owner_id, models.EconomicLedger.amount),
                    else_=0,
                )
            ),
            0,
        )
    ).filter(
        models.EconomicLedger.league_id == league_id,
        models.EconomicLedger.currency_type == currency_type,
    )

    if season_year is not None:
        query = query.filter(models.EconomicLedger.season_year == season_year)

    return int(query.scalar() or 0)


def has_owner_ledger_entries(
    db: Session,
    *,
    league_id: int,
    owner_id: int,
    currency_type: str,
    season_year: int | None = None,
) -> bool:
    query = db.query(models.EconomicLedger.id).filter(
        models.EconomicLedger.league_id == league_id,
        models.EconomicLedger.currency_type == currency_type,
        (models.EconomicLedger.to_owner_id == owner_id) | (models.EconomicLedger.from_owner_id == owner_id),
    )

    if season_year is not None:
        query = query.filter(models.EconomicLedger.season_year == season_year)

    return query.first() is not None


def owner_incoming_total(
    db: Session,
    *,
    league_id: int,
    owner_id: int,
    currency_type: str,
    season_year: int | None = None,
) -> int:
    query = db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0)).filter(
        models.EconomicLedger.league_id == league_id,
        models.EconomicLedger.currency_type == currency_type,
        models.EconomicLedger.to_owner_id == owner_id,
    )

    if season_year is not None:
        query = query.filter(models.EconomicLedger.season_year == season_year)

    return int(query.scalar() or 0)


def owner_has_incoming_credits(
    db: Session,
    *,
    league_id: int,
    owner_id: int,
    currency_type: str,
    season_year: int | None = None,
) -> bool:
    return owner_incoming_total(
        db,
        league_id=league_id,
        owner_id=owner_id,
        currency_type=currency_type,
        season_year=season_year,
    ) > 0


def owner_draft_budget_total(
    db: Session,
    *,
    league_id: int,
    owner_id: int,
    season_year: int,
    include_keeper_locks: bool = False,
) -> int:
    incoming = owner_incoming_total(
        db,
        league_id=league_id,
        owner_id=owner_id,
        currency_type="DRAFT_DOLLARS",
        season_year=season_year,
    )

    outgoing_query = db.query(func.coalesce(func.sum(models.EconomicLedger.amount), 0)).filter(
        models.EconomicLedger.league_id == league_id,
        models.EconomicLedger.currency_type == "DRAFT_DOLLARS",
        models.EconomicLedger.from_owner_id == owner_id,
        models.EconomicLedger.season_year == season_year,
    )
    if not include_keeper_locks:
        outgoing_query = outgoing_query.filter(models.EconomicLedger.transaction_type != "KEEPER_LOCK")

    outgoing = int(outgoing_query.scalar() or 0)
    return int(incoming - outgoing)
